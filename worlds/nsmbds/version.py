"""Central version metadata for the NSMBDS APWorld release."""

APWORLD_VERSION = "0.4.2"
RELEASE_CHANNEL = "alpha"


def format_display_version(apworld_version: str, release_channel: str) -> str:
    """Add a channel suffix to non-stable APWorld releases."""
    normalized_channel = release_channel.strip().lower()
    if not normalized_channel:
        raise ValueError("The APWorld release channel must not be empty.")
    if normalized_channel == "stable":
        return apworld_version
    return f"{apworld_version}-{normalized_channel}"


DISPLAY_VERSION = format_display_version(APWORLD_VERSION, RELEASE_CHANNEL)
