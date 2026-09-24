"""
risk_appetite.py
-----------------
Validates the investor risk appetite a Deep Research user selects and
resolves it to one of the three profiles investment_brief_agent.txt's
Section 7 already defines in full (Conservative / Moderate / Aggressive).

Same defensive-fallback pattern as response_style.py: an unrecognized
or missing value never crashes a request — it silently resolves to the
safe default instead.
"""

RISK_APPETITES = ["conservative", "moderate", "aggressive"]

DEFAULT_RISK_APPETITE = "moderate"


def resolve_risk_appetite(risk_appetite: str | None) -> str:
    """
    Normalizes and validates a risk_appetite string. Falls back to the
    default if missing, empty, or not one of the three recognized
    profiles.
    """
    if not risk_appetite:
        return DEFAULT_RISK_APPETITE
    normalized = risk_appetite.strip().lower()
    return normalized if normalized in RISK_APPETITES else DEFAULT_RISK_APPETITE
