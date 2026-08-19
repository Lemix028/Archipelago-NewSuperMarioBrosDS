"""Verify checked-in NSMBDS native hook metadata and optional assembly output."""

from __future__ import annotations

import argparse
import hashlib
import json
import runpy
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parent
WORLD_ROOT = SOURCE_ROOT.parent
METADATA_ROOT = SOURCE_ROOT / "native_hooks"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_checked_in_hooks() -> dict[str, bytes]:
    star_metadata = runpy.run_path(METADATA_ROOT / "star_coin_gate_hook.py")
    powerup_metadata = runpy.run_path(METADATA_ROOT / "powerup_license_hook.py")
    return {
        "star_coin_gate_hook": star_metadata["STAR_COIN_GATE_HOOK_BYTES"],
        "star_coin_currency_hook": star_metadata["STAR_COIN_CURRENCY_HOOK_BYTES"],
        "powerup_license_hook": powerup_metadata["POWERUP_LICENSE_HOOK_BYTES"],
    }


def verify(build_directory: Path | None = None) -> list[str]:
    manifest = json.loads(
        (METADATA_ROOT / "native_hooks_manifest.json").read_text(encoding="utf-8")
    )
    hooks = load_checked_in_hooks()
    errors: list[str] = []

    actual_hashes = {
        "star_coin_gate_hook_sha256": sha256(
            hooks["star_coin_gate_hook"] + hooks["star_coin_currency_hook"]
        ),
        "powerup_license_hook_sha256": sha256(hooks["powerup_license_hook"]),
        "native_hooks_bsdiff4_sha256": sha256(
            (WORLD_ROOT / "rom" / "native_hooks.bsdiff4").read_bytes()
        ),
    }
    for name, actual in actual_hashes.items():
        expected = manifest.get(name)
        if expected != actual:
            errors.append(f"{name}: expected {expected}, got {actual}")

    if build_directory is not None:
        for name, expected_bytes in hooks.items():
            binary_path = build_directory / f"{name}.bin"
            if not binary_path.is_file():
                errors.append(f"Missing assembled binary: {binary_path}")
                continue
            actual_bytes = binary_path.read_bytes()
            if actual_bytes != expected_bytes:
                errors.append(
                    f"{name}: assembled bytes differ from checked-in metadata "
                    f"({len(actual_bytes)} bytes versus {len(expected_bytes)} bytes)"
                )

    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--build-directory",
        type=Path,
        help="Also compare generated .bin files with the checked-in hook bytes.",
    )
    args = parser.parse_args()
    errors = verify(args.build_directory)
    if errors:
        raise SystemExit("Native hook verification failed:\n- " + "\n- ".join(errors))
    print("Native hook metadata and runtime patch hashes are consistent.")


if __name__ == "__main__":
    main()
