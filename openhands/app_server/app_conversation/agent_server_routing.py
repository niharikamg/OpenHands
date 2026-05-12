from collections.abc import Sequence

from openhands.sdk.settings import detect_acp_provider_by_agent_name


def acp_display_name(acp_command: Sequence[str] | None) -> str:
    """Return a display-safe ACP label from the configured command.

    Matches the command's tail against the SDK's ``ACP_PROVIDERS`` registry so
    a known preset surfaces as its brand name ("Claude Code", "Codex",
    "Gemini CLI") rather than the raw package name. Unrecognised commands
    fall back to plain ``"ACP"``.
    """
    if not acp_command:
        return 'ACP'
    # Pass the whole joined command so substring patterns match package names
    # that aren't necessarily the last token (e.g. ``gemini-cli --acp``).
    info = detect_acp_provider_by_agent_name(' '.join(acp_command))
    return info.display_name if info else 'ACP'
