"""Top-level field allowlist. Nested values pass through unchanged."""

VERSION = "1.0.0"


def allowlist_of(clean_state):
    """The allowlist = the clean state's top-level key set."""
    if not isinstance(clean_state, dict):
        raise TypeError("allowlist defense expects a dict state")
    return frozenset(clean_state.keys())


def strip_to_allowlist(state, allowed):
    """Return a new dict containing only allowed top-level keys, order kept."""
    if not isinstance(state, dict):
        raise TypeError("allowlist defense expects a dict state")
    if not isinstance(allowed, (set, frozenset)):
        raise TypeError("allowed must be a set/frozenset of top-level keys")
    return {k: v for k, v in state.items() if k in allowed}


def is_identity(state, allowed):
    """True iff stripping changes nothing (no foreign top-level keys)."""
    return strip_to_allowlist(state, allowed) == state
