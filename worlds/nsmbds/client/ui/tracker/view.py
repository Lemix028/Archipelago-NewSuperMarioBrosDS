"""Compact two-column overview for the spoiler-free NSMBDS client status."""

from __future__ import annotations

import logging

# kvui must be imported before Kivy in frozen Archipelago builds.
from kvui import GameManager

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.button import Button
from kivy.uix.checkbox import CheckBox
from kivy.uix.progressbar import ProgressBar
from kivy.uix.slider import Slider
from kivy.uix.spinner import Spinner
from kivy.utils import escape_markup
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.gridlayout import MDGridLayout
from kivymd.uix.label import MDLabel
from kivymd.uix.scrollview import MDScrollView

from .state import InventoryEntry, ProgressCount, TrackerSnapshot, build_tracker_snapshot
from ....version import DISPLAY_VERSION
from ....items import ITEM_TABLE
from ...launcher import (
    EMULATOR_FEED_FADE_CHOICES,
    EMULATOR_FEED_POSITIONS,
    auto_launch_enabled,
    browse_for_emuhawk,
    browse_for_rom,
    configured_rom_path,
    emuhawk_launcher_error,
    emulator_feed_config,
    find_emuhawk,
    is_valid_emuhawk_launcher,
    launch_game,
    launch_state,
    materialize_lua_runtime,
    set_auto_launch,
    set_emulator_feed_enabled,
    set_emulator_feed_fade_seconds,
    set_emulator_feed_position,
    set_emulator_feed_width,
)


GREEN = "72D572"
GREY = "9E9E9E"
CYAN = "62C6E8"
ORANGE = "FFB74D"
RED = "FF5252"
logger = logging.getLogger("NSMBDS")


def request_client_shutdown(ctx) -> None:
    """Wake and disconnect client tasks so closing the Kivy window cannot hang."""
    ctx.exit_event.set()
    ctx.watcher_event.set()

    handler = getattr(ctx, "client_handler", None)
    feed_task = getattr(handler, "_emulator_feed_flush_task", None)
    if feed_task is not None and not feed_task.done():
        feed_task.cancel()

    try:
        from worlds._bizhawk import disconnect

        disconnect(ctx.bizhawk_ctx)
    except Exception:
        logger.debug("BizHawk was already disconnected during client shutdown.", exc_info=True)


def _label(text: str, *, halign: str = "left") -> MDLabel:
    label = MDLabel(
        text=text,
        markup=True,
        adaptive_height=True,
        size_hint_y=None,
        halign=halign,
        valign="top",
    )
    label.bind(
        width=lambda instance, width: setattr(
            instance,
            "text_size",
            (max(0, width), None),
        )
    )
    return label


class NSMBDSTrackerPanel(MDScrollView):
    """Compact client overview without map-tracker or location-list overload."""

    def __init__(self, ctx, **kwargs):
        super().__init__(**kwargs)
        self.ctx = ctx
        self._snapshot: TrackerSnapshot | None = None
        self.content = MDBoxLayout(
            orientation="vertical",
            adaptive_height=True,
            padding=dp(10),
            spacing=dp(5),
        )
        self.add_widget(self.content)
        self.refresh(force=True)

    def refresh(self, *_args, force: bool = False) -> None:
        snapshot = build_tracker_snapshot(self.ctx)
        if force or snapshot != self._snapshot:
            self._snapshot = snapshot
            self._render(snapshot)

    def _render(self, snapshot: TrackerSnapshot) -> None:
        self.content.clear_widgets()
        self.content.padding = dp(10)
        self.content.spacing = dp(5)
        connections = MDGridLayout(cols=2, adaptive_height=True, spacing=dp(12))
        for title, status in (
            ("Server", snapshot.server_status),
            ("BizHawk", snapshot.bizhawk_status),
        ):
            connections.add_widget(_compact_label(
                f"[color={GREY}]{title}[/color]  {escape_markup(status)}"
            ))
        self.content.add_widget(connections)
        if not snapshot.seed_loaded:
            self.content.add_widget(_compact_label("Connect to a seed to load progress."))
            return

        death_link = (
            f"    [color={ORANGE}][b]DeathLink ON[/b][/color]"
            if snapshot.death_link_enabled else ""
        )
        self.content.add_widget(_compact_label(
            f"[b]{escape_markup(snapshot.goal_name)}[/b]  "
            f"{escape_markup(snapshot.goal_progress)}{death_link}"
        ))
        summary = MDGridLayout(cols=2, adaptive_height=True, spacing=dp(16))
        summary.add_widget(_compact_progress("Goal", snapshot.goal_count))
        summary.add_widget(_compact_progress("All checks", snapshot.total_progress))
        self.content.add_widget(summary)
        if snapshot.star_coin_lifetime or (getattr(self.ctx, "slot_data", None) or {}).get("star_coin_items", False):
            self.content.add_widget(_compact_label(
                f"[b]Star Coins[/b]  [color={ORANGE}]{snapshot.star_coin_available} available[/color]"
                f"    {snapshot.star_coin_spent} spent    "
                f"[color={GREY}]{snapshot.star_coin_lifetime} received total[/color]"
            ))

        # Keep the long inventory alongside progress instead of below it.
        body = MDBoxLayout(orientation="horizontal", adaptive_height=True, spacing=dp(18))
        progress_column = MDBoxLayout(
            orientation="vertical", adaptive_height=True, spacing=dp(3),
            size_hint_x=0.38, pos_hint={"top": 1},
        )
        inventory_column = MDBoxLayout(
            orientation="vertical", adaptive_height=True, spacing=dp(3),
            size_hint_x=0.62, pos_hint={"top": 1},
        )
        def update_columns(_instance, width):
            narrow = width < dp(620)
            body.orientation = "vertical" if narrow else "horizontal"
            progress_column.size_hint_x = 1 if narrow else 0.38
            inventory_column.size_hint_x = 1 if narrow else 0.62
        body.bind(width=update_columns)

        progress_column.add_widget(_compact_heading("Worlds"))
        for index, (world, progress) in enumerate(snapshot.world_progress):
            progress_column.add_widget(_compact_progress(escape_markup(world), progress, shaded=index % 2 == 0))
        progress_column.add_widget(_compact_heading("Check categories"))
        for index, (category, progress) in enumerate(snapshot.category_progress):
            progress_column.add_widget(_compact_progress(escape_markup(category), progress, shaded=index % 2 == 0))
        if not snapshot.category_progress:
            progress_column.add_widget(_compact_label(f"[color={GREY}]No active categories[/color]"))

        for group, entries in snapshot.inventory:
            received = sum(min(entry.received, entry.required) for entry in entries)
            required = sum(entry.required for entry in entries)
            inventory_column.add_widget(_compact_heading(escape_markup(group), f"{received}/{required}"))
            grid = MDGridLayout(cols=2, adaptive_height=True, spacing=(dp(10), dp(1)))
            def resize_inventory(instance, width):
                instance.cols = max(1, min(3, int((width + dp(10)) / dp(175))))
            grid.bind(width=resize_inventory)
            for entry in entries:
                grid.add_widget(_compact_inventory(entry))
            inventory_column.add_widget(grid)
        body.add_widget(progress_column)
        body.add_widget(inventory_column)
        self.content.add_widget(body)

        self.content.add_widget(_compact_heading("Power-ups"))
        locks = dict(snapshot.powerup_locks)
        powerup_grid = MDGridLayout(cols=5, adaptive_height=True, spacing=dp(8))
        def resize_powerup_grid(instance, width):
            instance.cols = max(2, min(5, int((width + dp(8)) / dp(130))))
        powerup_grid.bind(width=resize_powerup_grid)
        for entry in snapshot.pending_powerups:
            is_next = entry.name == snapshot.next_powerup
            selected = entry.name == snapshot.selected_powerup
            reason = locks.get(entry.name)
            row = MDBoxLayout(
                orientation="vertical", size_hint_y=None, height=dp(65), spacing=dp(4),
            )
            name = escape_markup(entry.name)
            row.add_widget(_compact_label(f"[b]{name}[/b]  ×{entry.received}", halign="center"))
            selectable = entry.received > 0 and not reason
            if selected:
                button_text = "SELECTED"
                button_color = (0.10, 0.55, 0.72, 1)
            elif is_next:
                button_text = "NEXT"
                button_color = (0.18, 0.42, 0.50, 1)
            elif selectable:
                button_text = "SET NEXT"
                button_color = (0.25, 0.28, 0.31, 1)
            elif reason:
                button_text = "LOCKED"
                button_color = (0.16, 0.17, 0.18, 1)
            else:
                button_text = "—"
                button_color = (0.16, 0.17, 0.18, 1)
            button = Button(
                text=button_text,
                size_hint_y=None, height=dp(28), font_size="12sp",
                background_normal="", background_down="",
                background_color=button_color,
                color=(1, 1, 1, 1),
            )
            if selected or selectable:
                button.bind(on_release=lambda _button, name=entry.name, cancel=selected:
                            self._select_next_powerup(None if cancel else ITEM_TABLE[name][0]))
            row.add_widget(button)
            powerup_grid.add_widget(row)
        self.content.add_widget(powerup_grid)
        progress_column.add_widget(_compact_label(
            f"Shields: {snapshot.trap_shields}    "
            f"Life Insurance: {snapshot.life_insurance}"
        ))

    def _select_next_powerup(self, item_id: int | None) -> None:
        handler = getattr(self.ctx, "client_handler", None)
        if handler is not None and handler.select_next_powerup(self.ctx, item_id):
            self.refresh(force=True)


def _compact_label(text: str, *, halign: str = "left") -> MDLabel:
    label = _label(text, halign=halign)
    label.font_size = "13sp"
    return label


def _compact_heading(text: str, detail: str = "") -> MDBoxLayout:
    heading = MDBoxLayout(
        orientation="vertical", adaptive_height=True,
        padding=(0, dp(4), 0, dp(2)), spacing=dp(3),
    )
    line = MDBoxLayout(orientation="horizontal", adaptive_height=True, spacing=dp(6))
    line.add_widget(_compact_label(f"[b]{text}[/b]"))
    if detail:
        count = _compact_label(f"[color={GREY}]{detail}[/color]", halign="right")
        count.size_hint_x = None
        count.width = dp(60)
        line.add_widget(count)
    heading.add_widget(line)
    heading.add_widget(MDBoxLayout(
        size_hint_y=None, height=dp(1), md_bg_color=(0.5, 0.5, 0.5, 0.25),
    ))
    return heading


def _compact_inventory(entry: InventoryEntry) -> MDBoxLayout:
    row = MDBoxLayout(orientation="horizontal", adaptive_height=True, spacing=dp(3))
    complete = entry.received >= entry.required
    color = GREEN if complete else (ORANGE if entry.received else GREY)
    # A fixed status column keeps item names aligned; color is not the only cue.
    marker = _compact_label(f"[color={color}][b]{'+' if complete else ('~' if entry.received else '-')}[/b][/color]")
    marker.size_hint_x = None
    marker.width = dp(14)
    marker.pos_hint = {"top": 1}
    row.add_widget(marker)
    name = escape_markup(entry.name)
    name_label = _compact_label(name if entry.received else f"[color={GREY}]{name}[/color]")
    name_label.pos_hint = {"top": 1}
    row.add_widget(name_label)
    if entry.required > 1:
        count = _compact_label(
            f"[color={color}]{min(entry.received, entry.required)}/{entry.required}[/color]",
            halign="right",
        )
        count.size_hint_x = None
        count.pos_hint = {"top": 1}
        count.width = dp(44)
        row.add_widget(count)
    return row

def _compact_progress(title: str, progress: ProgressCount, *, shaded: bool = False) -> MDBoxLayout:
    """Name, slim bar and right-aligned count on one line."""
    row = MDBoxLayout(
        orientation="horizontal", adaptive_height=True, spacing=dp(6),
        padding=(dp(3), dp(1)), md_bg_color=(0.5, 0.5, 0.5, 0.07 if shaded else 0),
    )
    name = _compact_label(title)
    name.size_hint_x = 0.55
    row.add_widget(name)
    row.add_widget(ProgressBar(
        max=max(1, progress.total), value=min(progress.checked, max(1, progress.total)),
        size_hint_x=0.45, size_hint_y=None, height=dp(4), pos_hint={"center_y": 0.5},
    ))
    complete = progress.total > 0 and progress.checked >= progress.total
    count = _compact_label(
        f"[color={GREEN if complete else GREY}]{progress.checked}/{progress.total}[/color]",
        halign="right",
    )
    count.size_hint_x = None
    count.pos_hint = {"center_y": 0.5}
    count.width = dp(max(66, len(f"{progress.checked}/{progress.total}") * 8))
    row.add_widget(count)
    return row

def _button(text: str, callback) -> Button:
    button = Button(
        text=text,
        size_hint_y=None,
        height=dp(44),
        background_normal="",
        background_color=(0.16, 0.48, 0.72, 1),
    )
    button.bind(on_release=callback)
    return button


class NSMBDSLaunchPanel(MDScrollView):
    """One-click setup and launch controls for BizHawk."""

    STATUS_MESSAGE_SECONDS = 4.0

    def __init__(self, ctx, **kwargs):
        super().__init__(**kwargs)
        self.ctx = ctx
        self._auto_launch_attempted = False
        self._message_clear_event = None

        self.content = MDBoxLayout(
            orientation="vertical",
            adaptive_height=True,
            padding=dp(20),
            spacing=dp(12),
        )
        self.add_widget(self.content)

        # ------------------------------------------------------------------
        # Header
        # ------------------------------------------------------------------

        self.content.add_widget(
            _label("[size=26sp][b]Launch Game[/b][/size]")
        )

        self.content.add_widget(
            _label(
                "[color=#B8B8B8]"
                "Start your generated NSMBDS Archipelago seed with BizHawk."
                "[/color]"
            )
        )

        # ------------------------------------------------------------------
        # Setup status
        # ------------------------------------------------------------------

        self.content.add_widget(
            _label("[size=19sp][b]Setup[/b][/size]")
        )

        self.bizhawk_status = _label("")
        self.rom_status = _label("")
        self.lua_status = _label("")

        self.content.add_widget(self.bizhawk_status)
        self.content.add_widget(self.rom_status)
        self.content.add_widget(self.lua_status)

        # ------------------------------------------------------------------
        # Configuration buttons
        # ------------------------------------------------------------------

        buttons = MDGridLayout(
            cols=2,
            adaptive_height=True,
            spacing=dp(10),
        )

        buttons.add_widget(
            _button("Change BizHawk", self._select_emuhawk)
        )

        buttons.add_widget(
            _button("Change Seed ROM", self._select_rom)
        )

        self.content.add_widget(buttons)

        # ------------------------------------------------------------------
        # Launch
        # ------------------------------------------------------------------

        self.launch_button = _button(
            "Launch NSMBDS",
            self._launch,
        )
        self.launch_button.height = dp(54)
        self.launch_button.background_color = (0.17, 0.62, 0.31, 1)

        self.content.add_widget(self.launch_button)

        # ------------------------------------------------------------------
        # Automatic launch
        # ------------------------------------------------------------------

        auto_row = MDBoxLayout(
            orientation="horizontal",
            adaptive_height=True,
            spacing=dp(8),
        )

        self.auto_checkbox = CheckBox(
            active=auto_launch_enabled(),
            size_hint=(None, None),
            size=(dp(36), dp(36)),
        )
        self.auto_checkbox.bind(active=self._set_auto_launch)

        auto_row.add_widget(self.auto_checkbox)
        auto_row.add_widget(
            _label("Automatically launch when the NSMBDS Client starts")
        )

        self.content.add_widget(auto_row)

        # ------------------------------------------------------------------
        # Temporary status / notification
        # ------------------------------------------------------------------

        self.message = _label("")
        self.content.add_widget(self.message)

        self.refresh(force=True)

    # ----------------------------------------------------------------------
    # Status helpers
    # ----------------------------------------------------------------------

    def _set_message(
        self,
        text: str,
        *,
        error: bool = False,
        duration: float | None = None,
    ) -> None:
        """Show a temporary status message below the launcher."""

        if self._message_clear_event is not None:
            self._message_clear_event.cancel()
            self._message_clear_event = None

        color = RED if error else CYAN

        self.message.text = (
            f"[color={color}]"
            f"{escape_markup(text)}"
            f"[/color]"
        )

        if duration is None:
            duration = self.STATUS_MESSAGE_SECONDS

        if duration > 0:
            self._message_clear_event = Clock.schedule_once(
                self._clear_message,
                duration,
            )

    def _clear_message(self, *_args) -> None:
        self.message.text = ""
        self._message_clear_event = None

    @staticmethod
    def _status_label(
        title: str,
        ready: bool,
        detail: str,
        *,
        error: bool = False,
    ) -> str:
        """Create a compact setup status entry."""

        if ready:
            state_color = GREEN
            state_text = "Ready"
        elif error:
            state_color = RED
            state_text = "Error"
        else:
            state_color = RED
            state_text = "Missing"

        detail_text = escape_markup(detail)

        return (
            f"[b]{title}[/b]   "
            f"[color={state_color}][b]{state_text}[/b][/color]\n"
            f"[size=12sp][color=#A8A8A8]{detail_text}[/color][/size]"
        )

    # ----------------------------------------------------------------------
    # File selection
    # ----------------------------------------------------------------------

    def _select_emuhawk(self, *_args) -> None:
        try:
            selected = browse_for_emuhawk()

            if selected:
                self._set_message("BizHawk path saved.")

        except Exception as exc:
            self._set_message(str(exc), error=True)

        self.refresh(force=True)

    def _select_rom(self, *_args) -> None:
        try:
            selected = browse_for_rom()

            if selected:
                self._set_message("Patched seed ROM saved.")

        except Exception as exc:
            self._set_message(str(exc), error=True)

        self.refresh(force=True)

    # ----------------------------------------------------------------------
    # Launch
    # ----------------------------------------------------------------------

    def _launch(self, *_args) -> None:
        try:
            launch_game()
            self._set_message(launch_state.last_message)

        except Exception as exc:
            self._set_message(str(exc), error=True)

        self.refresh(force=True)

    # ----------------------------------------------------------------------
    # Automatic launch
    # ----------------------------------------------------------------------

    def _set_auto_launch(self, _checkbox, active: bool) -> None:
        try:
            set_auto_launch(active)

            self._set_message(
                "Automatic launch enabled."
                if active
                else "Automatic launch disabled."
            )

        except Exception as exc:
            self._set_message(str(exc), error=True)

    def maybe_auto_launch(self, *_args) -> None:
        if self._auto_launch_attempted:
            return

        self._auto_launch_attempted = True

        if not auto_launch_enabled():
            return

        emuhawk = find_emuhawk()
        rom = configured_rom_path()

        emuhawk_ready = is_valid_emuhawk_launcher(emuhawk)

        rom_ready = bool(
            rom
            and rom.is_file()
            and rom.suffix.lower() == ".nds"
        )

        if emuhawk_ready and rom_ready:
            self._launch()

        elif not emuhawk_ready:
            self._set_message(
                "Automatic launch is waiting for a valid BizHawk launcher. "
                f"{emuhawk_launcher_error(emuhawk)}",
                error=True,
            )

        else:
            self._set_message(
                "Automatic launch is waiting for a valid patched seed ROM.",
                error=True,
            )

    # ----------------------------------------------------------------------
    # Refresh
    # ----------------------------------------------------------------------

    def refresh(self, *_args, force: bool = False) -> None:
        # ------------------------------------------------------------------
        # BizHawk
        # ------------------------------------------------------------------

        emuhawk = find_emuhawk()

        emuhawk_ready = is_valid_emuhawk_launcher(emuhawk)

        if emuhawk_ready:
            self.bizhawk_status.text = self._status_label(
                "BizHawk",
                True,
                str(emuhawk),
            )

        elif emuhawk:
            self.bizhawk_status.text = self._status_label(
                "BizHawk",
                False,
                emuhawk_launcher_error(emuhawk) or f"Invalid path: {emuhawk}",
                error=True,
            )

        else:
            self.bizhawk_status.text = self._status_label(
                "BizHawk",
                False,
                "Select BizHawk Launcher",
            )

        # ------------------------------------------------------------------
        # Patched ROM
        # ------------------------------------------------------------------

        rom = configured_rom_path()

        rom_ready = bool(
            rom
            and rom.is_file()
            and rom.suffix.lower() == ".nds"
        )

        if rom_ready:
            self.rom_status.text = self._status_label(
                "Seed ROM",
                True,
                str(rom),
            )

        elif rom:
            self.rom_status.text = self._status_label(
                "Seed ROM",
                False,
                f"Invalid or missing ROM: {rom}",
                error=True,
            )

        else:
            self.rom_status.text = self._status_label(
                "Seed ROM",
                False,
                "Open a .apnsmbds file or select its generated .nds file",
            )

        # ------------------------------------------------------------------
        # Lua runtime
        # ------------------------------------------------------------------

        lua_ready = False

        try:
            bootstrap = materialize_lua_runtime()

            lua_ready = bool(
                bootstrap
                and bootstrap.is_file()
                and bootstrap.suffix.lower() == ".lua"
            )

            if lua_ready:
                self.lua_status.text = self._status_label(
                    "Lua Runtime",
                    True,
                    str(bootstrap),
                )

            else:
                self.lua_status.text = self._status_label(
                    "Lua Runtime",
                    False,
                    "Bundled Lua bootstrap could not be found.",
                    error=True,
                )

        except Exception as exc:
            self.lua_status.text = self._status_label(
                "Lua Runtime",
                False,
                str(exc),
                error=True,
            )

        # ------------------------------------------------------------------
        # Running process
        # ------------------------------------------------------------------

        process_running = bool(
            launch_state.process is not None
            and launch_state.process.poll() is None
        )

        # ------------------------------------------------------------------
        # Launch button state
        # ------------------------------------------------------------------

        if process_running:
            self.launch_button.text = "BizHawk Running"
            self.launch_button.disabled = True

        elif not emuhawk_ready:
            self.launch_button.text = "Configure BizHawk"
            self.launch_button.disabled = True

        elif not rom_ready:
            self.launch_button.text = "Select Seed ROM"
            self.launch_button.disabled = True

        elif not lua_ready:
            self.launch_button.text = "Lua Runtime Error"
            self.launch_button.disabled = True

        else:
            self.launch_button.text = "Launch NSMBDS"
            self.launch_button.disabled = False


class NSMBDSSettingsPanel(MDScrollView):
    """Persistent client-side presentation settings for the Lua runtime."""

    POSITION_LABELS = {
        "bottom_left": "Bottom Left",
        "bottom_right": "Bottom Right",
        "top_left": "Top Left",
        "top_right": "Top Right",
    }
    FADE_LABELS = {
        0: "Never",
        5: "5 seconds",
        10: "10 seconds",
        20: "20 seconds",
        30: "30 seconds",
        60: "60 seconds",
    }

    POSITION_VALUES = {label: value for value, label in POSITION_LABELS.items()}
    FADE_VALUES = {label: value for value, label in FADE_LABELS.items()}

    def __init__(self, _ctx, **kwargs):
        super().__init__(**kwargs)
        self._updating_controls = False
        self._width_save_event = None
        self.content = MDBoxLayout(
            orientation="vertical",
            adaptive_height=True,
            padding=(dp(24), dp(20), dp(24), dp(24)),
            spacing=dp(14),
        )
        self.add_widget(self.content)
        self.content.add_widget(_label("[size=26sp][b]Settings[/b][/size]"))
        self.content.add_widget(_label(
            "[size=19sp][b]Emulator Feed[/b][/size]\n"
            "[color=#B8B8B8]Configure the message overlay shown inside BizHawk. "
            "Changes are saved and applied automatically.[/color]"
        ))

        config = emulator_feed_config()
        status_control = MDBoxLayout(
            orientation="horizontal",
            spacing=dp(8),
        )
        self.feed_checkbox = CheckBox(
            active=config.enabled,
            size_hint=(None, None),
            size=(dp(40), dp(40)),
        )
        self.feed_checkbox.bind(active=self._set_enabled)
        status_control.add_widget(self.feed_checkbox)
        status_control.add_widget(_label("Enabled"))
        self.content.add_widget(self._setting_row(
            "Status",
            "Show item, check, and client messages.",
            status_control,
        ))

        width_control = MDBoxLayout(
            orientation="horizontal",
            spacing=dp(12),
        )
        self.width_slider = Slider(
            min=200,
            max=1200,
            step=50,
            value=config.width,
            value_track=True,
            value_track_color=(0.38, 0.78, 0.91, 1),
            cursor_size=(dp(20), dp(20)),
            background_width=dp(3),
        )
        self.width_slider.bind(value=self._preview_width)
        width_control.add_widget(self.width_slider)
        self.width_label = _label("", halign="right")
        self.width_label.size_hint_x = None
        self.width_label.width = dp(72)
        width_control.add_widget(self.width_label)
        self.content.add_widget(self._setting_row(
            "Width",
            "Horizontal size of the overlay.",
            width_control,
        ))

        self.position_spinner = Spinner(
            text=self.POSITION_LABELS[config.position],
            values=tuple(self.POSITION_LABELS[value] for value in EMULATOR_FEED_POSITIONS),
            background_normal="",
            background_down="",
            background_color=self._theme_color("surfaceContainerHighColor", (0.18, 0.20, 0.24, 1)),
            color=self._theme_color("onSurfaceColor", (1, 1, 1, 1)),
        )
        self.position_spinner.bind(text=self._set_position)
        self.content.add_widget(self._setting_row(
            "Position",
            "Screen corner used by the overlay.",
            self.position_spinner,
        ))

        self.fade_spinner = Spinner(
            text=self.FADE_LABELS.get(config.fade_seconds, f"{config.fade_seconds} seconds"),
            values=tuple(self.FADE_LABELS[value] for value in EMULATOR_FEED_FADE_CHOICES),
            background_normal="",
            background_down="",
            background_color=self._theme_color("surfaceContainerHighColor", (0.18, 0.20, 0.24, 1)),
            color=self._theme_color("onSurfaceColor", (1, 1, 1, 1)),
        )
        self.fade_spinner.bind(text=self._set_fade)
        self.content.add_widget(self._setting_row(
            "Fade Out",
            "Time before new messages disappear.",
            self.fade_spinner,
        ))

        controls_card = MDBoxLayout(
            orientation="vertical",
            adaptive_height=True,
            padding=(dp(16), dp(12)),
            spacing=dp(8),
            md_bg_color=self._theme_color("surfaceContainerLowColor", (0.5, 0.5, 0.5, 0.08)),
        )
        controls_card.add_widget(_label(
            "[size=16sp][b]BizHawk Controls & Shortcuts[/b][/size]\n"
            f"[color={GREY}]In-game hotkeys and actions while running:[/color]"
        ))
        controls_card.add_widget(self._shortcut_row(
            "Ctrl + Shift + H",
            "Toggle Emulator Feed",
            "Temporarily show or hide the in-game message overlay",
        ))
        controls_card.add_widget(self._shortcut_row(
            "Mouse Wheel",
            "Scroll Message History",
            "Browse older item, check, and trap messages",
        ))
        self.content.add_widget(controls_card)
        self.refresh()

    @staticmethod
    def _theme_color(name: str, fallback: tuple[float, float, float, float]):
        try:
            from kivy.app import App

            theme = getattr(App.get_running_app(), "theme_cls", None)
            return tuple(getattr(theme, name)) if theme is not None else fallback
        except (AttributeError, TypeError):
            return fallback

    @staticmethod
    def _setting_row(title: str, description: str, control) -> MDBoxLayout:
        row = MDBoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(62),
            spacing=dp(24),
        )
        text = _label(
            f"[b]{title}[/b]\n[color={GREY}]{description}[/color]"
        )
        text.size_hint_x = 0.52
        row.add_widget(text)

        control_box = MDBoxLayout(
            orientation="horizontal",
            size_hint_x=0.48,
            padding=(0, dp(10), 0, dp(10)),
        )
        control_box.add_widget(control)
        row.add_widget(control_box)
        return row

    @staticmethod
    def _shortcut_row(shortcut: str, action: str, note: str) -> MDBoxLayout:
        row = MDBoxLayout(
            orientation="horizontal",
            adaptive_height=True,
            spacing=dp(12),
            padding=(0, dp(2)),
        )
        key_box = MDBoxLayout(
            orientation="horizontal",
            adaptive_height=True,
            size_hint_x=None,
            width=dp(150),
            pos_hint={"center_y": 0.5},
        )
        key_label = _compact_label(f"[color={CYAN}][b]{shortcut}[/b][/color]")
        key_box.add_widget(key_label)
        row.add_widget(key_box)

        desc = _label(
            f"[b]{action}[/b]  —  [color={GREY}]{note}[/color]"
        )
        desc.pos_hint = {"center_y": 0.5}
        row.add_widget(desc)
        return row

    def refresh(self) -> None:
        config = emulator_feed_config()
        self._updating_controls = True
        self.width_label.text = f"[b]{config.width} px[/b]"
        self.feed_checkbox.active = config.enabled
        self.width_slider.value = config.width
        self.position_spinner.text = self.POSITION_LABELS[config.position]
        self.fade_spinner.text = self.FADE_LABELS.get(
            config.fade_seconds,
            f"{config.fade_seconds} seconds",
        )
        self._updating_controls = False

    def _set_enabled(self, _switch, active: bool) -> None:
        if not self._updating_controls:
            set_emulator_feed_enabled(active)

    def _preview_width(self, _slider, value: float) -> None:
        width = int(value)
        self.width_label.text = f"[b]{width} px[/b]"
        if self._updating_controls:
            return
        if self._width_save_event is not None:
            self._width_save_event.cancel()
        self._width_save_event = Clock.schedule_once(self._save_width, 0.25)

    def _save_width(self, *_args) -> None:
        self._width_save_event = None
        set_emulator_feed_width(int(self.width_slider.value))

    def _set_position(self, _spinner, label: str) -> None:
        if not self._updating_controls and label in self.POSITION_VALUES:
            set_emulator_feed_position(self.POSITION_VALUES[label])

    def _set_fade(self, _spinner, label: str) -> None:
        if not self._updating_controls and label in self.FADE_VALUES:
            set_emulator_feed_fade_seconds(self.FADE_VALUES[label])


class NSMBDSTrackerManager(GameManager):
    """Standard Archipelago client UI with overview, launch, and settings tabs."""

    base_title = f"NSMBDS Client | APWorld v{DISPLAY_VERSION} | Archipelago"

    def on_stop(self):
        request_client_shutdown(self.ctx)
        return super().on_stop()

    def build(self):
        root = super().build()
        self.tracker_panel = NSMBDSTrackerPanel(self.ctx)
        self.add_client_tab("Overview", self.tracker_panel)
        try:
            self.launch_panel = NSMBDSLaunchPanel(self.ctx)
        except Exception as exc:
            logger.exception("Could not initialize the NSMBDS Launch Game panel.")
            self.launch_panel = MDBoxLayout(
                orientation="vertical",
                adaptive_height=True,
                padding=dp(18),
            )
            self.launch_panel.add_widget(_label(
                f"[color={RED}][b]Launch Game could not initialize.[/b][/color]\n"
                f"{escape_markup(str(exc))}\nCheck the BizHawk Client log for details."
            ))
        self.add_client_tab("Launch Game", self.launch_panel)
        self.settings_panel = NSMBDSSettingsPanel(self.ctx)
        self.add_client_tab("Settings", self.settings_panel)
        Clock.schedule_interval(self.tracker_panel.refresh, 0.5)
        if isinstance(self.launch_panel, NSMBDSLaunchPanel):
            Clock.schedule_interval(self.launch_panel.refresh, 1.0)
            Clock.schedule_once(self.launch_panel.maybe_auto_launch, 0.25)
        return root


def make_tracker_gui(_ctx) -> type[NSMBDSTrackerManager]:
    """Return the GUI class expected by ``CommonContext.run_gui``."""
    return NSMBDSTrackerManager
