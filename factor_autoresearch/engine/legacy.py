"""Legacy compute engine metadata."""

ENGINE_NAME = "legacy"
ENGINE_DESCRIPTION = "Legacy single-process compute path."


def get_engine_info() -> dict[str, str]:
    """Return a small descriptor for routing and diagnostics."""
    return {
        "name": ENGINE_NAME,
        "description": ENGINE_DESCRIPTION,
    }
