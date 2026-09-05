"""Optional local Keystone assembler for the block hook (no network service).

The standard build_native_hooks.ps1 uses devkitARM. This alternative only
requires keystone-engine and writes the same flat binary for verification.
"""
import argparse
from pathlib import Path

from keystone import Ks, KS_ARCH_ARM, KS_MODE_ARM

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
source = Path(__file__).parent / "asm" / "block_hit_hook.s"
assembly = source.read_text(encoding="utf-8").split(".org 0x200", 1)[0]
assembly = "\n".join(
    line for line in assembly.splitlines()
    if not line.startswith((".section", ".global", ".type", ".size"))
)
encoded, _ = Ks(KS_ARCH_ARM, KS_MODE_ARM).asm(assembly, addr=0x02001A00)
if encoded is None:
    raise SystemExit("The assembler did not produce a binary.")
code = bytes(encoded)
if len(code) > 0x200:
    raise SystemExit("Block hook code overlaps its producer header.")
binary = (code.ljust(0x200, b"\0") + b"APBH" + (1).to_bytes(4, "little")
          + bytes(24) + bytes(4) + (1).to_bytes(4, "little") + bytes(24 + 4096))
if len(binary) != 0x1240:
    raise SystemExit(f"Unexpected native block binary size: {len(binary):#x}")
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_bytes(binary)
print(f"Built {len(binary)} bytes: {args.output}")
print("Code (including literal pool):", code.hex())
