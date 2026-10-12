"""Short, local deathcounter report for players."""

from __future__ import annotations


def _single_line(value) -> str:
    return " ".join(str(value).split())


def format_death_counter(ctx) -> str:
    handler = ctx.client_handler
    lines = [
        "Deathcounter",
        f"You: {handler._death_count} ({handler._death_link_death_count} deathlink)",
    ]
    rows = handler._other_death_counter_rows(ctx)
    if rows:
        heading = "Others (observed while connected):" if any(not row[3] for row in rows) else "Others:"
        lines.extend(("", heading))
    for name, total, linked, exact in rows:
        if exact:
            detail = f" ({linked} deathlink)" if linked is not None else ""
            lines.append(f"{_single_line(name)}: {total}{detail}")
        else:
            lines.append(f"{_single_line(name)}: {total}")
    return "\n".join(lines)


def death_counter_command(ctx, output, argument: str = "") -> bool:
    """Show counts locally without sending a deathlink or changing settings."""
    if argument.strip():
        output("Usage: /deathcounter")
        return False
    handler = getattr(ctx, "client_handler", None)
    if (getattr(ctx, "slot_data", None) is None or getattr(ctx, "slot", None) is None
            or not callable(getattr(handler, "_other_death_counter_rows", None))):
        output("Connect to an NSMBDS seed first.")
        return False
    output(format_death_counter(ctx))
    return True
