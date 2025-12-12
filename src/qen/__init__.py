"""qen - A tiny, extensible tool for organizing multi-repository development work."""

try:
    from importlib.metadata import version

    __version__ = version("qen")
except Exception:
    # Fallback for development/editable installs that might not have metadata
    __version__ = "0.0.0-dev"
