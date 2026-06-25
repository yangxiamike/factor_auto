"""Compute engine v1 metadata."""

ENGINE_NAME = "v1"
ENGINE_DESCRIPTION = "Compute engine v1 with explicit routing and parallel helpers."


def get_engine_info() -> dict[str, str]:
    """Return a small descriptor for routing and diagnostics."""
    return {
        "name": ENGINE_NAME,
        "description": ENGINE_DESCRIPTION,
    }
