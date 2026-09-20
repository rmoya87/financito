from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol


@dataclass(frozen=True)
class CommercialOffer:
    category: str
    provider_name: str
    product_name: str
    source: str
    source_url: str | None
    fetched_at: datetime
    valid_until: date | None
    currency: str
    attributes: dict[str, str]
    missing_fields: tuple[str, ...] = ()


class CommercialComparisonProvider(Protocol):
    """Contract for explicitly configured external commercial sources."""

    name: str

    def fetch_offers(self, category: str, query: dict[str, str]) -> list[CommercialOffer]:
        ...
