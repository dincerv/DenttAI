"""
Adapter registry — provider adına göre doğru adaptörü döner.
"""
from __future__ import annotations

from app.adapters.base import PMSAdapter
from app.adapters.dentsoft import DentSoftAdapter
from app.adapters.drdentes import DrDentesAdapter

_REGISTRY: dict[str, type[PMSAdapter]] = {
    "dentsoft": DentSoftAdapter,
    "drdentes": DrDentesAdapter,
}


def get_adapter(provider: str, config: dict) -> PMSAdapter:
    """Provider adına göre adaptör instance'ı oluştur."""
    cls = _REGISTRY.get(provider)
    if cls is None:
        raise ValueError(f"Bilinmeyen PMS sağlayıcısı: {provider}. Desteklenen: {list(_REGISTRY.keys())}")
    return cls(config)


def list_providers() -> list[str]:
    """Desteklenen provider listesini döner."""
    return list(_REGISTRY.keys())
