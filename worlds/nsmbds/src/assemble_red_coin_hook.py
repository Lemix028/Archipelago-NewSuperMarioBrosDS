"""Assemble the Overlay 54 Red Coin call wrapper in reserved ARM9 padding."""

from __future__ import annotations

import argparse
from pathlib import Path

from keystone import KS_ARCH_ARM, KS_MODE_ARM, Ks


SOURCE_ROOT = Path(__file__).resolve().parent
HOOK_CAVE = 0x02002C80
HOOK_CAVE_END = 0x02002DE0


def assemble() -> bytes:
    source = SOURCE_ROOT / "asm" / "red_coin_hook.s"
    assembly = "\n".join(
        line.split("@", 1)[0]
        for line in source.read_text(encoding="utf-8").splitlines()
    )
    encoded, _ = Ks(KS_ARCH_ARM, KS_MODE_ARM).asm(assembly, addr=HOOK_CAVE)
    if encoded is None:
        raise ValueError("Keystone did not assemble the Red Coin hook")
    code = bytes(encoded)
    if len(code) > HOOK_CAVE_END - HOOK_CAVE:
        raise ValueError(f"Red Coin hook exceeds its {HOOK_CAVE_END - HOOK_CAVE} byte cave: {len(code)}")
    return code


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    code = assemble()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(code)
    print(f"Built {len(code)} bytes at {HOOK_CAVE:#010x}: {args.output}")


if __name__ == "__main__":
    main()
