"""Simple Kivy overview for the spoiler-free NSMBDS client status."""

from __future__ import annotations

import logging

# kvui must be imported before Kivy in frozen Archipelago builds.
from kvui import GameManager

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.button import Button
from kivy.uix.checkbox import CheckBox
from kivy.utils import escape_markup
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.gridlayout import MDGridLayout
from kivymd.uix.label import MDLabel
from kivymd.uix.progressindicator import MDLinearProgressIndicator
from kivymd.uix.scrollview import MDScrollView

from .state import InventoryEntry, ProgressCount, TrackerSnapshot, build_tracker_snapshot
from ....version import DISPLAY_VERSION
from ...launcher import (
    auto_launch_enabled,
    browse_for_emuhawk,
    browse_for_rom,
    configured_rom_path,
    find_emuhawk,
    launch_game,
    launch_state,
    materialize_lua_runtime,
    set_auto_launch,
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


class ProgressRow(MDBoxLayout):
    """One compact progress label and bar."""

    def __init__(self, title: str, progress: ProgressCount, **kwargs):
        super().__init__(
            orientation="vertical",
            adaptive_height=True,
            spacing=dp(3),
            **kwargs,
        )
        heading = MDBoxLayout(
            orientation="horizontal",
            adaptive_height=True,
            spacing=dp(8),
        )
        heading.add_widget(_label(title))
        count = _label(
            f"[color={CYAN}]{progress.checked} / {progress.total}[/color]",
            halign="right",
        )
        count.size_hint_x = None
        count.width = dp(90)
        heading.add_widget(count)
        self.add_widget(heading)
        self.add_widget(MDLinearProgressIndicator(
            max=max(1, progress.total),
            value=min(progress.checked, max(1, progress.total)),
            size_hint_y=None,
            height=dp(5),
        ))


def _inventory_text(entry: InventoryEntry) -> str:
    if entry.required > 1:
        value = f"{min(entry.received, entry.required)} / {entry.required}"
        color = GREEN if entry.received >= entry.required else GREY
    elif entry.received:
        value = "Received"
        color = GREEN
    else:
        value = "Missing"
        color = GREY
    return f"[color={color}]{entry.name}: {value}[/color]"


class NSMBDSTrackerPanel(MDScrollView):
    """Compact client overview without map-tracker or location-list overload."""

    def __init__(self, ctx, **kwargs):
        super().__init__(**kwargs)
        self.ctx = ctx
        self._snapshot: TrackerSnapshot | None = None
        self.content = MDBoxLayout(
            orientation="vertical",
            adaptive_height=True,
            padding=dp(18),
            spacing=dp(3),
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
        self.content.add_widget(_label("[size=26sp][b]NSMBDS Overview[/b][/size]"))
        self.content.add_widget(_label(
            "[b]Server:[/b] "
            f"{snapshot.server_status}    |    "
            "[b]BizHawk:[/b] "
            f"{snapshot.bizhawk_status}    |    "
            "[b]ROM:[/b] "
            f"{snapshot.rom_status}"
        ))

        if not snapshot.seed_loaded:
            self.content.add_widget(_label(
                f"[size=19sp][color={GREY}]Connect to a seed to load locations.[/color][/size]",
                halign="center",
            ))
            return

        death_link_warning = (
            "    [color=FF5252][b]DEATHLINK ACTIVE[/b][/color]"
            if snapshot.death_link_enabled
            else ""
        )
        self.content.add_widget(_label(
            f"[size=20sp][b]Goal[/b]{death_link_warning}[/size]"
        ))
        self.content.add_widget(_label(
            f"[color={ORANGE}][b]{snapshot.goal_name}[/b][/color]: {snapshot.goal_progress}"
        ))
        if snapshot.star_coin_lifetime or (getattr(self.ctx, "slot_data", None) or {}).get("star_coin_items", False):
            self.content.add_widget(_label(
                f"[size=18sp][color={CYAN}][b]Star Coins:[/b] "
                f"{snapshot.star_coin_available} available | "
                f"{snapshot.star_coin_lifetime} received total | "
                f"{snapshot.star_coin_spent} spent[/color][/size]"
            ))
        if snapshot.trap_shields or snapshot.life_insurance:
            protections = []
            if snapshot.trap_shields:
                protections.append(
                    f"[color={CYAN}][b]SHIELD x{snapshot.trap_shields}[/b][/color]"
                )
            if snapshot.life_insurance:
                protections.append(
                    f"[color={GREEN}][b]LIFE INSURANCE x{snapshot.life_insurance}[/b][/color]"
                )
            self.content.add_widget(_label(
                "[size=18sp]Active Protection: " + "    ".join(protections) + "[/size]"
            ))
        self.content.add_widget(ProgressRow("Goal Progress", snapshot.goal_count))
        self.content.add_widget(ProgressRow("All Checks", snapshot.total_progress))

        progress_columns = MDBoxLayout(
            orientation="horizontal",
            adaptive_height=True,
            spacing=dp(18),
        )
        world_column = MDBoxLayout(
            orientation="vertical",
            adaptive_height=True,
            spacing=dp(3),
            pos_hint={"top": 1},
        )
        category_column = MDBoxLayout(
            orientation="vertical",
            adaptive_height=True,
            spacing=dp(3),
            pos_hint={"top": 1},
        )

        world_column.add_widget(_label("[size=20sp][b]World Progress[/b][/size]"))
        if snapshot.world_progress:
            for world, progress in snapshot.world_progress:
                world_column.add_widget(ProgressRow(world, progress))
        else:
            world_column.add_widget(_label(
                f"[color={GREY}]Connect to a seed to load active locations.[/color]"
            ))

        category_column.add_widget(_label("[size=20sp][b]Check Categories[/b][/size]"))
        if snapshot.category_progress:
            for category, progress in snapshot.category_progress:
                category_column.add_widget(ProgressRow(category, progress))
        else:
            category_column.add_widget(_label(
                f"[color={GREY}]No active check categories loaded yet.[/color]"
            ))
        progress_columns.add_widget(world_column)
        progress_columns.add_widget(category_column)
        self.content.add_widget(progress_columns)

        self.content.add_widget(_label("[size=20sp][b]Received Progression[/b][/size]"))
        for group, entries in snapshot.inventory:
            self.content.add_widget(_label(f"[size=17sp][b]{group}[/b][/size]"))
            inventory_grid = MDGridLayout(
                cols=3,
                adaptive_height=True,
                spacing=(dp(12), dp(3)),
            )
            for entry in entries:
                inventory_label = _label(_inventory_text(entry), halign="left")
                inventory_label.pos_hint = {"top": 1, "x": 0}
                inventory_grid.add_widget(inventory_label)
            self.content.add_widget(inventory_grid)

        pending_total = sum(entry.received for entry in snapshot.pending_powerups)
        self.content.add_widget(_label(
            f"[size=20sp][b]Waiting Power-Ups ({pending_total})[/b][/size]"
        ))
        if snapshot.pending_powerups:
            waiting_text = "    ".join(
                f"[color={ORANGE}]{entry.name} x{entry.received}[/color]"
                for entry in snapshot.pending_powerups
            )
        else:
            waiting_text = f"[color={GREY}]None[/color]"
        self.content.add_widget(_label(waiting_text))


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

        emuhawk_ready = bool(
            emuhawk
            and emuhawk.is_file()
            and emuhawk.name.lower() == "emuhawk.exe"
        )

        rom_ready = bool(
            rom
            and rom.is_file()
            and rom.suffix.lower() == ".nds"
        )

        if emuhawk_ready and rom_ready:
            self._launch()

        elif not emuhawk_ready:
            self._set_message(
                "Automatic launch is waiting for a valid EmuHawk.exe.",
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

        emuhawk_ready = bool(
            emuhawk
            and emuhawk.is_file()
            and emuhawk.name.lower() == "emuhawk.exe"
        )

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
                f"Invalid path: {emuhawk}",
                error=True,
            )

        else:
            self.bizhawk_status.text = self._status_label(
                "BizHawk",
                False,
                "Select EmuHawk.exe",
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


class NSMBDSTrackerManager(GameManager):
    """Standard Archipelago client UI with NSMBDS overview and launch tabs."""

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
        Clock.schedule_interval(self.tracker_panel.refresh, 0.5)
        if isinstance(self.launch_panel, NSMBDSLaunchPanel):
            Clock.schedule_interval(self.launch_panel.refresh, 1.0)
            Clock.schedule_once(self.launch_panel.maybe_auto_launch, 0.25)
        return root


def make_tracker_gui(_ctx) -> type[NSMBDSTrackerManager]:
    """Return the GUI class expected by ``CommonContext.run_gui``."""
    return NSMBDSTrackerManager
