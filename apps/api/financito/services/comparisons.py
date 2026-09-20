from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlparse

from ..providers.comparisons import CommercialOffer


def _safe_source_url(url: str | None) -> bool:
    if not url:
        return True
    parsed = urlparse(url)
    return parsed.scheme == "https" and bool(parsed.netloc)


def comparison_matrix(
    offers: list[CommercialOffer],
    required_fields: list[str] | None = None,
    *,
    max_age_days: int = 31,
) -> dict:
    required = tuple(dict.fromkeys(x.strip() for x in (required_fields or []) if x.strip()))
    now = datetime.now(timezone.utc)
    categories = {o.category for o in offers}
    currencies = {o.currency for o in offers}
    rows = []
    for offer in offers:
        fetched = offer.fetched_at if offer.fetched_at.tzinfo else offer.fetched_at.replace(tzinfo=timezone.utc)
        age_days = max(0, (now - fetched.astimezone(timezone.utc)).days)
        missing = list(dict.fromkeys([
            *offer.missing_fields,
            *(field for field in required if not str(offer.attributes.get(field, "")).strip()),
        ]))
        source_ok = bool(offer.source.strip()) and _safe_source_url(offer.source_url)
        expired = offer.valid_until is not None and offer.valid_until < now.date()
        fresh = age_days <= max_age_days and not expired
        rows.append({
            "category": offer.category,
            "provider_name": offer.provider_name,
            "product_name": offer.product_name,
            "source": offer.source,
            "source_url": offer.source_url,
            "fetched_at": fetched.isoformat(),
            "valid_until": None if offer.valid_until is None else offer.valid_until.isoformat(),
            "currency": offer.currency,
            "attributes": offer.attributes,
            "missing_fields": missing,
            "source_valid": source_ok,
            "fresh": fresh,
            "comparable": source_ok and fresh and not missing,
        })

    warnings = []
    if len(categories) > 1:
        warnings.append("Hay categorías distintas; no deben compararse entre sí.")
    if len(currencies) > 1:
        warnings.append("Hay divisas distintas; hace falta una conversión trazable antes de comparar importes.")
    if any(not row["source_valid"] for row in rows):
        warnings.append("Alguna oferta carece de procedencia válida o usa una URL no HTTPS.")
    if any(not row["fresh"] for row in rows):
        warnings.append("Alguna oferta está caducada o supera el umbral de frescura.")
    if any(row["missing_fields"] for row in rows):
        warnings.append("Hay condiciones materiales desconocidas; desconocido no equivale a cero.")

    return {
        "offers": rows,
        "required_fields": list(required),
        "all_same_category": len(categories) <= 1,
        "all_same_currency": len(currencies) <= 1,
        "ready_for_domain_comparison": bool(rows) and len(categories) == 1 and len(currencies) == 1 and all(row["comparable"] for row in rows),
        "warnings": warnings,
        "notice": "Matriz de evidencia comercial; no sustituye el cálculo del motor específico ni una oferta personalizada.",
    }
