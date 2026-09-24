"""
response_style.py
------------------
Maps a small set of user-facing "Response Style" options to LLM temperature
values, instead of exposing raw temperature directly to the end user.

Why not raw temperature: every analysis agent is prompted to show its
arithmetic explicitly (DCF's WACC build, DuPont decomposition, CAGR
formulas). Higher temperature increases wording variation *and* the risk
of small numeric drift or inconsistent figure citation, which undermines
the quantitative-rigor promise of this product. A small, named set of
styles gives the user real, meaningful control without a dial that can
silently degrade correctness.

    Precise      -> near-deterministic. Best for numeric-heavy reports
                    (DCF, ratios, valuation) where consistency matters most.
    Balanced     -> default. Mild natural variation in phrasing.
    Exploratory  -> more discursive. Better for open-ended strategy
                    questions where some creative framing is welcome.
"""

RESPONSE_STYLES = {
    "precise":     0.1,
    "balanced":    0.4,
    "exploratory": 0.7,
}

DEFAULT_RESPONSE_STYLE = "balanced"


def resolve_temperature(response_style: str | None) -> float:
    """
    Converts a response_style string into a temperature float.

    Falls back to the balanced default if the style is missing, empty,
    or not one of the three recognized names — an unrecognized style
    should never crash a request, it should just degrade gracefully to
    the safe default.
    """
    if not response_style:
        return RESPONSE_STYLES[DEFAULT_RESPONSE_STYLE]
    return RESPONSE_STYLES.get(response_style.strip().lower(), RESPONSE_STYLES[DEFAULT_RESPONSE_STYLE])
