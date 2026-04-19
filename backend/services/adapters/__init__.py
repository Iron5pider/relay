"""Adapter factory. `get_adapter()` reads `settings.relay_adapter` and returns
a `NavProAdapter` instance. Routes/services only ever see the ABC.

`mock` is the fresh-checkout + Wi-Fi-fallback mode. `navpro` is production.
Field-provenance lives in `API_DOCS/NavPro_integration.md` §1.
"""

from __future__ import annotations

from backend.config import settings

from .base import NavProAdapter


def get_adapter() -> NavProAdapter:
    impl = settings.relay_adapter
    if impl == "mock":
        from .mock_tp import MockTPAdapter

        return MockTPAdapter()
    if impl == "navpro":
        from .navpro import NavProHTTPAdapter

        return NavProHTTPAdapter()
    raise ValueError(f"Unknown RELAY_ADAPTER: {impl!r}. Expected mock|navpro.")


__all__ = ["NavProAdapter", "get_adapter"]
