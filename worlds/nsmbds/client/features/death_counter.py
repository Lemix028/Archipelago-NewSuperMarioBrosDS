"""Seed/slot death totals, with server sharing and a local restart fallback."""

from __future__ import annotations

import hashlib
import logging
import math

logger = logging.getLogger("NSMBDS.DeathCounter")
GAME = "New Super Mario Bros. DS"


class DeathCounterMixin:
    def _initialize_death_counter(self) -> None:
        self._death_count = 0
        self._death_link_death_count = 0
        self._other_death_counts = {}
        self._observed_death_links = {}
        self._seen_death_links = []
        self._death_counter_keys = {}
        self._death_counter_sync_pending = False
        self._death_counter_write_pending = False
        self._death_counter_save_pending = False
        self._last_sent_death_link_time = None

    def _death_counter_key(self, slot=None) -> str | None:
        identity = self._session_identity
        if not identity or identity[0] is None or identity[2] is None:
            return None
        identity = (identity[0], identity[1], identity[2] if slot is None else slot)
        digest = hashlib.sha256(repr(identity).encode("utf-8")).hexdigest()[:24]
        return f"nsmbds_deaths_v1_{digest}"

    @staticmethod
    def _valid_death_count(value) -> bool:
        return type(value) is int and value >= 0

    def _configure_death_counter(self, ctx) -> None:
        key = self._death_counter_key()
        if key is None:
            return
        try:
            import Utils
            record = Utils.persistent_load().get("nsmbds", {}).get(key, {})
            if isinstance(record, dict):
                self._merge_own_death_counts(record)
                observed = record.get("observed", {})
                if isinstance(observed, dict):
                    for name, count in observed.items():
                        if isinstance(name, str) and self._valid_death_count(count):
                            self._observed_death_links[name] = max(count, self._observed_death_links.get(name, 0))
                for event in record.get("seen", []) if isinstance(record.get("seen"), list) else []:
                    if (isinstance(event, (list, tuple)) and len(event) == 2
                            and isinstance(event[0], str) and type(event[1]) in (float, int)
                            and math.isfinite(event[1]) and tuple(event) not in self._seen_death_links):
                        self._seen_death_links.append(tuple(event))
                self._seen_death_links = self._seen_death_links[-256:]
        except (ImportError, OSError, TypeError, ValueError):
            logger.warning("Could not restore the seed death counter.", exc_info=True)
        slots = getattr(ctx, "slot_info", {})
        self._death_counter_keys = {key: (ctx.slot, "total"), key + "_deathlink": (ctx.slot, "deathlink")}
        for slot, info in slots.items():
            if slot == ctx.slot or getattr(info, "game", None) != GAME:
                continue
            other_key = self._death_counter_key(slot)
            self._death_counter_keys[other_key] = (slot, "total")
            self._death_counter_keys[other_key + "_deathlink"] = (slot, "deathlink")
        self._death_counter_sync_pending = True
        self._death_counter_write_pending = True

    def _merge_own_death_counts(self, record) -> None:
        for field, attribute in (("total", "_death_count"), ("deathlink", "_death_link_death_count")):
            value = record.get(field)
            if self._valid_death_count(value):
                setattr(self, attribute, max(value, getattr(self, attribute)))
        self._death_count = max(self._death_count, self._death_link_death_count)

    def _save_death_counter(self) -> None:
        key = self._death_counter_key()
        if key is None:
            return
        try:
            import Utils
            Utils.persistent_store("nsmbds", key, {
                "total": self._death_count,
                "deathlink": self._death_link_death_count,
                "observed": dict(self._observed_death_links),
                "seen": list(self._seen_death_links),
            }, force_store=True)
            self._death_counter_save_pending = False
        except (ImportError, OSError, TypeError, ValueError):
            self._death_counter_save_pending = True
            logger.warning("Could not save the seed death counter; will retry.", exc_info=True)

    def _record_death(self, *, death_link: bool) -> None:
        self._death_count += 1
        if death_link:
            self._death_link_death_count += 1
        self._death_counter_write_pending = True
        self._save_death_counter()

    def _accept_death_link_packet(self, ctx, data) -> bool:
        """Reject invalid/own/repeated Bounces before rolling grace or queuing."""
        if not isinstance(data, dict) or not (ctx.slot_data or {}).get("death_link", False):
            return False
        source, timestamp = data.get("source"), data.get("time")
        if (not isinstance(source, str) or not source or type(timestamp) not in (int, float)
                or not math.isfinite(timestamp)):
            return False
        names = getattr(ctx, "player_names", {})
        info = getattr(ctx, "slot_info", {}).get(ctx.slot)
        own_names = {names.get(ctx.slot), getattr(ctx, "auth", None), getattr(info, "name", None)}
        if source in own_names or timestamp == self._last_sent_death_link_time:
            return False
        event = (source, timestamp)
        if event in self._seen_death_links:
            return False
        self._seen_death_links.append(event)
        self._seen_death_links = self._seen_death_links[-256:]
        self._observed_death_links[source] = self._observed_death_links.get(source, 0) + 1
        self._save_death_counter()
        return True

    def _handle_death_counter_packet(self, ctx, cmd, args) -> None:
        values = args.get("keys", {}) if cmd == "Retrieved" else {args.get("key"): args.get("value")}
        for key, value in values.items():
            target = self._death_counter_keys.get(key)
            if target is None or value is None or not self._valid_death_count(value):
                continue
            slot, field = target
            if slot == ctx.slot:
                before = (self._death_count, self._death_link_death_count)
                self._merge_own_death_counts({field: value})
                if before != (self._death_count, self._death_link_death_count):
                    self._save_death_counter()
                    self._death_counter_write_pending = True
            else:
                record = self._other_death_counts.setdefault(slot, {})
                record[field] = max(value, record.get(field, 0))

    async def _sync_death_counter(self, ctx) -> None:
        if self._death_counter_save_pending:
            self._save_death_counter()
        key = self._death_counter_key()
        if key is None:
            return
        if self._death_counter_sync_pending:
            keys = list(self._death_counter_keys)
            await ctx.send_msgs([{"cmd": "SetNotify", "keys": keys}, {"cmd": "Get", "keys": keys}])
            self._death_counter_sync_pending = False
        if self._death_counter_write_pending:
            counts = (self._death_count, self._death_link_death_count)
            await ctx.send_msgs([
                {"cmd": "Set", "key": target, "default": 0, "want_reply": True,
                 "operations": [{"operation": "max", "value": count}]}
                for target, count in ((key, counts[0]), (key + "_deathlink", counts[1]))
            ])
            self._death_counter_write_pending = counts != (self._death_count, self._death_link_death_count)

    def _other_death_counter_rows(self, ctx) -> tuple:
        names = getattr(ctx, "player_names", {})
        rows = []
        for slot, record in sorted(self._other_death_counts.items()):
            if "total" in record:
                rows.append((str(names.get(slot, f"Player {slot}")), record["total"], record.get("deathlink"), True))
        exact_names = {row[0] for row in rows}
        for name, count in sorted(self._observed_death_links.items()):
            if name not in exact_names:
                rows.append((name, count, None, False))
        return tuple(rows)
