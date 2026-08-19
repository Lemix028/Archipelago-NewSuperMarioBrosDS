"""Read-only verification for the clean NSMBDS A2DE ROM used by the patcher."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


HEADER_TITLE_OFFSET = 0x0000
HEADER_TITLE_SIZE = 12
HEADER_GAME_CODE_OFFSET = 0x000C
HEADER_GAME_CODE_SIZE = 4
EXPECTED_GAME_CODE = b"A2DE"
EXPECTED_SIZE = 33_554_432
EXPECTED_MD5 = "A2DDBA012E5C3C2096D0BE57CC273BE5"
EXPECTED_SHA256 = "9F67FEF1B4C73E966767F6153431ADA3751DC1B0DA2C70F386C14A5E3017F354"


def _hash_file(path: Path, algorithm: str) -> str:
    """Return an uppercase digest without loading the full ROM into memory."""
    digest = hashlib.new(algorithm)
    with path.open("rb") as rom_file:
        while chunk := rom_file.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest().upper()


def read_rom_identity(path: Path) -> dict[str, str | int]:
    """Return the ROM header fields and stable hashes needed by the patch format."""
    with path.open("rb") as rom_file:
        title = rom_file.read(HEADER_TITLE_SIZE).rstrip(b"\0").decode("ascii", "replace")
        rom_file.seek(HEADER_GAME_CODE_OFFSET)
        game_code = rom_file.read(HEADER_GAME_CODE_SIZE)

    return {
        "path": str(path.resolve()),
        "size": path.stat().st_size,
        "title": title,
        "game_code": game_code.decode("ascii", "replace"),
        "md5": _hash_file(path, "md5"),
        "sha256": _hash_file(path, "sha256"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path, help="Path to an unmodified .nds ROM")
    args = parser.parse_args()
    identity = read_rom_identity(args.rom)

    print("=== NSMBDS Base ROM Verification ===")
    for key in ("path", "size", "title", "game_code", "md5", "sha256"):
        print(f"{key}: {identity[key]}")
    if identity["game_code"] != EXPECTED_GAME_CODE.decode("ascii"):
        raise SystemExit(
            f"Expected game code {EXPECTED_GAME_CODE.decode('ascii')}, got {identity['game_code']}."
        )
    if identity["size"] != EXPECTED_SIZE:
        raise SystemExit(f"Expected ROM size {EXPECTED_SIZE}, got {identity['size']}.")
    if identity["md5"] != EXPECTED_MD5:
        raise SystemExit(f"Expected MD5 {EXPECTED_MD5}, got {identity['md5']}.")
    if identity["sha256"] != EXPECTED_SHA256:
        raise SystemExit(f"Expected SHA-256 {EXPECTED_SHA256}, got {identity['sha256']}.")
    print("Supported clean A2DE base ROM verified.")


if __name__ == "__main__":
    main()
