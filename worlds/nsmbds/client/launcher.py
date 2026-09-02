"""User-facing BizHawk launcher for the NSMBDS client."""

from __future__ import annotations

import importlib.resources
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from ..version import DISPLAY_VERSION


PATCH_SUFFIX = ".apnsmbds"
ROM_SUFFIX = ".nds"
BOOTSTRAP_NAME = "nsmbds_bizhawk_bootstrap.lua"
ROM_GAME_CODE = b"A2DE"
ROM_GAME_CODE_OFFSET = 0x0C
PATCH_MARKER_OFFSET = 0x013A57A8
PATCH_MARKER = bytes.fromhex("1E FF 2F E1 41 50 4E 53 01 00 00 00 00 00 00 00 00 00 00 00")
EMULATOR_FEED_POSITIONS = (
    "bottom_left",
    "bottom_right",
    "top_left",
    "top_right",
)
EMULATOR_FEED_FADE_CHOICES = (0, 5, 10, 20, 30, 60)


@dataclass(frozen=True)
class EmulatorFeedConfig:
    enabled: bool
    width: int
    position: str
    fade_seconds: int


@dataclass
class LaunchState:
    """Paths and status shared between startup argument handling and the GUI."""

    patch_file: Path | None = None
    rom_file: Path | None = None
    last_message: str = "Select or open a patched NSMBDS seed ROM."
    launched: bool = False
    process: subprocess.Popen | None = None


launch_state = LaunchState()
_materialized_bootstrap: Path | None = None


def configure_launch_from_args(args: Iterable[str]) -> LaunchState:
    """Remember the ROM produced by the normal Archipelago patch argument."""
    launch_state.patch_file = None
    launch_state.rom_file = None
    launch_state.launched = False
    launch_state.process = None
    for value in args:
        candidate = Path(value).expanduser()
        if candidate.suffix.lower() == PATCH_SUFFIX:
            patch_file = candidate.resolve()
            launch_state.patch_file = patch_file
            launch_state.rom_file = patch_file.with_suffix(ROM_SUFFIX)
            launch_state.last_message = "Patched seed ROM is ready to launch."
            break
    return launch_state


def _settings():
    from settings import get_settings

    return get_settings()


def _nsmbds_value(name: str, default=None):
    return getattr(_settings().nsmbds_options, name, default)


def _set_nsmbds_value(name: str, value) -> None:
    settings = _settings()
    options = settings.nsmbds_options
    current = getattr(options, name)
    if current is None:
        setattr(options, name, value)
        settings.save()
        return
    value_type = type(current)
    setattr(options, name, value_type(value) if value_type is not bool else bool(value))
    settings.save()


def _resolved_setting_path(value: object) -> Path | None:
    if value is None or str(value) in {"", "None"}:
        return None
    resolved = value.resolve() if hasattr(value, "resolve") else str(value)
    return Path(resolved).expanduser().resolve()


def configured_emuhawk_path() -> Path | None:
    """Return Archipelago's shared EmuHawk setting, including an invalid path."""
    value = _settings().bizhawkclient_options.emuhawk_path
    return _resolved_setting_path(value)


def emuhawk_launcher_error(path: Path | None) -> str | None:
    """Explain why a path cannot be used as the BizHawk launcher."""
    if path is None:
        return "BizHawk is not configured. Select a BizHawk launcher first."
    if not path.is_file():
        return f"BizHawk launcher was not found: {path}"
    if sys.platform == "win32":
        if path.name.lower() != "emuhawk.exe":
            return f"Selected file is not a valid BizHawk launcher: {path}"
    elif not os.access(path, os.X_OK):
        return (
            f"BizHawk launcher is not executable: {path}. "
            f'Grant execute permission with chmod +x "{path}".'
        )
    return None


def is_valid_emuhawk_launcher(path: Path | None) -> bool:
    """Return whether *path* is a launchable BizHawk entry point on this platform."""
    return emuhawk_launcher_error(path) is None


def _candidate_emuhawk_paths() -> Iterable[Path]:
    configured = configured_emuhawk_path()
    if configured:
        yield configured

    local_app_data = os.environ.get("LOCALAPPDATA")
    program_files = os.environ.get("ProgramFiles")
    user_profile = os.environ.get("USERPROFILE")
    home = Path.home()
    roots = [Path.cwd(), home, home / "Downloads", home / "Desktop"]
    if local_app_data:
        roots.append(Path(local_app_data))
    if program_files:
        roots.append(Path(program_files))
    if user_profile:
        roots.extend((Path(user_profile) / "Desktop", Path(user_profile) / "Downloads"))

    launcher_name = "EmuHawk.exe" if sys.platform == "win32" else "EmuHawkMono.sh"
    for root in roots:
        yield root / launcher_name
        yield root / "BizHawk" / launcher_name
        if sys.platform == "win32":
            yield root / "BizHawk-win-x64" / launcher_name
        if root.is_dir():
            for directory in root.glob("BizHawk*"):
                if directory.is_dir():
                    yield directory / launcher_name


def find_emuhawk() -> Path | None:
    """Find a configured or conventionally installed BizHawk executable."""
    configured = configured_emuhawk_path()
    invalid_candidate = configured
    seen: set[Path] = set()
    for candidate in _candidate_emuhawk_paths():
        candidate = candidate.expanduser().resolve()
        if candidate in seen:
            continue
        seen.add(candidate)
        if is_valid_emuhawk_launcher(candidate):
            return candidate
        if invalid_candidate is None and candidate.is_file():
            invalid_candidate = candidate
    return invalid_candidate


def browse_for_emuhawk() -> Path | None:
    """Select and persist a BizHawk launcher using a platform-neutral dialog."""
    from Utils import open_filename

    settings = _settings()
    current = settings.bizhawkclient_options.emuhawk_path
    current_path = _resolved_setting_path(current)
    patterns = ["*.exe"] if sys.platform == "win32" else ["*.sh", "*"]
    chosen = open_filename(
        "Select BizHawk Launcher",
        [("BizHawk Launcher", patterns), ("All Files", ["*.*"])],
        str(current_path or ""),
    )
    if not chosen:
        return None
    value_type = type(current) if current is not None else str
    settings.bizhawkclient_options.emuhawk_path = value_type(chosen)
    settings.save()
    return _resolved_setting_path(settings.bizhawkclient_options.emuhawk_path)


def _remember_rom(path: Path) -> None:
    _set_nsmbds_value("last_patched_rom", str(path))


def _last_patched_rom_value() -> object:
    """Read the optional ROM setting without treating an empty path as the working directory."""
    try:
        return _nsmbds_value("last_patched_rom", "")
    except OSError:
        return ""


def configured_rom_path() -> Path | None:
    """Prefer this process's patch output, then the last selected seed ROM."""
    if launch_state.rom_file:
        return launch_state.rom_file
    return _resolved_setting_path(_last_patched_rom_value())


def browse_for_rom() -> Path | None:
    """Select and remember an already-patched NSMBDS seed ROM."""
    from Utils import open_filename

    current = _last_patched_rom_value() or ""
    chosen = open_filename(
        "Select Patched NSMBDS Seed ROM",
        [("Nintendo DS ROM", ["*.nds"]), ("All Files", ["*.*"])],
        str(current),
    )
    if not chosen:
        return None
    path = _resolved_setting_path(chosen)
    if path:
        validate_seed_rom(path)
        launch_state.rom_file = path
        _remember_rom(path)
    return path


def validate_seed_rom(path: Path) -> None:
    """Reject missing files and obvious non-NSMBDS ROM selections."""
    if not path.is_file():
        raise FileNotFoundError(f"Patched seed ROM was not found: {path}")
    with path.open("rb") as rom:
        rom.seek(ROM_GAME_CODE_OFFSET)
        game_code = rom.read(len(ROM_GAME_CODE))
        rom.seek(PATCH_MARKER_OFFSET)
        patch_marker = rom.read(len(PATCH_MARKER))
    if game_code != ROM_GAME_CODE:
        raise ValueError("Selected ROM is not the supported USA NSMBDS ROM (A2DE).")
    if patch_marker != PATCH_MARKER:
        raise ValueError("Selected ROM is a clean or incompatible ROM, not a patched NSMBDS seed ROM.")


def _copy_resource_tree(source, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for entry in source.iterdir():
        target = destination / entry.name
        if entry.is_dir():
            _copy_resource_tree(entry, target)
        elif entry.is_file():
            temporary_target = target.with_name(target.name + ".tmp")
            temporary_target.write_bytes(entry.read_bytes())
            temporary_target.replace(target)


def materialize_lua_runtime() -> Path:
    """Copy bundled Lua files to a stable real directory for BizHawk."""
    global _materialized_bootstrap

    if _materialized_bootstrap and _materialized_bootstrap.is_file():
        return _materialized_bootstrap

    from Utils import user_path

    runtime_dir = Path(user_path("nsmbds", "lua"))
    version_file = runtime_dir / ".runtime-version"
    bootstrap = runtime_dir / BOOTSTRAP_NAME
    package_name = __package__.rsplit(".client", 1)[0]
    source = importlib.resources.files(package_name).joinpath("lua_runtime")
    if not source.is_dir():
        raise FileNotFoundError("The APWorld does not contain the NSMBDS Lua runtime.")
    _copy_resource_tree(source, runtime_dir)
    version_file.write_text(DISPLAY_VERSION + "\n", encoding="utf-8")
    if not bootstrap.is_file():
        raise FileNotFoundError("The bundled NSMBDS Lua bootstrap could not be installed.")
    _materialized_bootstrap = bootstrap
    return bootstrap


def auto_launch_enabled() -> bool:
    return bool(_nsmbds_value("auto_launch_game", False))


def set_auto_launch(enabled: bool) -> None:
    _set_nsmbds_value("auto_launch_game", bool(enabled))


def emulator_feed_config() -> EmulatorFeedConfig:
    """Return validated feed settings suitable for both the client UI and Lua."""
    position = str(_nsmbds_value("emulator_feed_position", "bottom_left"))
    if position not in EMULATOR_FEED_POSITIONS:
        position = "bottom_left"
    try:
        width = int(_nsmbds_value("emulator_feed_width", 500))
    except (TypeError, ValueError):
        width = 500
    try:
        fade_seconds = int(_nsmbds_value("emulator_feed_fade_seconds", 0))
    except (TypeError, ValueError):
        fade_seconds = 0
    return EmulatorFeedConfig(
        enabled=bool(_nsmbds_value("emulator_feed_enabled", True)),
        width=max(200, min(1200, width)),
        position=position,
        fade_seconds=max(0, min(300, fade_seconds)),
    )


def set_emulator_feed_enabled(enabled: bool) -> None:
    _set_nsmbds_value("emulator_feed_enabled", bool(enabled))


def set_emulator_feed_width(width: int) -> None:
    _set_nsmbds_value("emulator_feed_width", max(200, min(1200, int(width))))


def set_emulator_feed_position(position: str) -> None:
    if position not in EMULATOR_FEED_POSITIONS:
        raise ValueError(f"Unknown emulator feed position: {position}")
    _set_nsmbds_value("emulator_feed_position", position)


def set_emulator_feed_fade_seconds(seconds: int) -> None:
    _set_nsmbds_value("emulator_feed_fade_seconds", max(0, min(300, int(seconds))))


def launch_game() -> subprocess.Popen:
    """Start the selected patched ROM with the bundled NSMBDS Lua runtime."""
    global _materialized_bootstrap

    if launch_state.process is not None and launch_state.process.poll() is None:
        raise RuntimeError("BizHawk was already started from this client.")
    emuhawk = find_emuhawk()
    launcher_error = emuhawk_launcher_error(emuhawk)
    if launcher_error:
        if emuhawk is None or not emuhawk.is_file():
            raise FileNotFoundError(launcher_error)
        if sys.platform != "win32" and not os.access(emuhawk, os.X_OK):
            raise PermissionError(launcher_error)
        raise ValueError(launcher_error)
    rom = configured_rom_path()
    if not rom:
        raise FileNotFoundError("No patched NSMBDS seed ROM is selected.")
    validate_seed_rom(rom)
    # Status checks may reuse the path, but a fresh emulator process must load
    # the current Lua sources, including edits made during this client session.
    _materialized_bootstrap = None
    bootstrap = materialize_lua_runtime()
    from Utils import local_path

    environment = os.environ.copy()
    environment["NSMBDS_AP_LUA_DIR"] = str(Path(local_path("data", "lua")).resolve())
    process = subprocess.Popen(
        [str(emuhawk), f"--lua={bootstrap}", str(rom)],
        cwd=str(emuhawk.parent),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=environment,
    )
    launch_state.rom_file = rom
    launch_state.launched = True
    launch_state.process = process
    launch_state.last_message = "BizHawk started. Waiting for the Lua connection."
    _remember_rom(rom)
    return process
