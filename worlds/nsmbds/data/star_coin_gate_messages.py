"""Seed-specific text and patch sites for the version-two gate hook."""

GATE_HOOK_CAVE = 0x020EDFC4
GATE_GAP_CHECK_OFFSET = 0x74
GATE_PRICE_OFFSET = 0x1B0
GATE_GAP_CHECK_WORD = 0xE35C0005  # cmp ip, #5
GATE_PRICE_WORD = 0xE3A01005  # mov r1, #5
GATE_MESSAGE_BASE = 16
GATE_MESSAGE_COUNT = 96


def gate_tier_messages(gap: int = 5) -> tuple[str, ...]:
    if isinstance(gap, bool) or not isinstance(gap, int) or not 1 <= gap <= 5:
        raise ValueError("Star Coin Gate Gap must be an integer from 1 through 5.")
    price = f"Opening costs {gap} Star Coin{'s' if gap != 1 else ''}."
    vanilla = tuple(
        f"Requires {tier * gap} total received\nStar Coins.\n{price}"
        for tier in range(1, 33)
    )
    progressive = tuple(
        f"Requires {tier} Progressive\n"
        f"{'Gate Pass' if tier == 1 else 'Gate Passes'} and {tier * gap} total\n"
        f"received Star Coins.\n{price}"
        for tier in range(1, 33)
    )
    individual = tuple(
        "Requires this gate's Gate Pass\n"
        f"and {tier * gap} total received\nStar Coins.\n{price}"
        for tier in range(1, 33)
    )
    return vanilla + progressive + individual
