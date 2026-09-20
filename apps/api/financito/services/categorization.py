from __future__ import annotations

import re
import unicodedata
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Category, Transaction


DEFAULT_CATEGORIES = {
    "income": "Ingresos",
    "housing": "Vivienda",
    "groceries": "Supermercado",
    "restaurants": "Restaurantes",
    "transport": "Transporte",
    "utilities": "Suministros",
    "insurance": "Seguros",
    "health": "Salud",
    "education": "Educación",
    "shopping": "Compras",
    "subscriptions": "Suscripciones",
    "travel": "Viajes",
    "taxes": "Impuestos",
    "investments": "Inversión",
    "transfers": "Transferencias",
    "other": "Otros",
}

KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("groceries", ("mercadona", "carrefour", "lidl", "aldi", "supermercado", "alcampo")),
    ("restaurants", ("restaurant", "restaurante", "bar ", "cafeteria", "just eat", "glovo", "uber eats")),
    ("transport", ("repsol", "cepsa", "bp ", "renfe", "metro", "uber", "cabify", "parking", "peaje")),
    ("utilities", ("iberdrola", "endesa", "naturgy", "agua", "canal de isabel", "electricidad", "gas ")),
    ("insurance", ("seguro", "mapfre", "axa", "allianz", "mutua madrilena", "linea directa")),
    ("subscriptions", ("netflix", "spotify", "apple.com/bill", "disney", "hbo", "amazon prime")),
    ("housing", ("hipoteca", "alquiler", "comunidad propietarios")),
    ("health", ("farmacia", "hospital", "clinica", "dentista")),
    ("education", ("colegio", "academia", "universidad", "libros")),
    ("travel", ("booking", "airbnb", "hotel", "ryanair", "iberia", "vueling")),
    ("taxes", ("agencia tributaria", "ayuntamiento", "ibi", "impuesto")),
    ("investments", ("broker", "degiro", "trade republic", "interactive brokers")),
]


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"\s+", " ", value.lower()).strip()
    return value


def ensure_categories(session: Session) -> dict[str, Category]:
    existing = {c.system_key: c for c in session.scalars(select(Category)).all()}
    for key, name in DEFAULT_CATEGORIES.items():
        if key not in existing:
            category = Category(name=name, system_key=key)
            session.add(category)
            session.flush()
            existing[key] = category
    return existing


def categorize_transaction(session: Session, tx: Transaction) -> None:
    if tx.user_verified:
        return
    from .transaction_ops import apply_rule
    if apply_rule(session, tx):
        return
    categories = ensure_categories(session)
    text = normalize_text(f"{tx.merchant_raw or ''} {tx.description_raw}")
    if tx.amount > 0:
        category = categories["income"]
        confidence = Decimal("0.95")
    elif any(k in text for k in ("transferencia", "traspaso", "bizum enviado", "bizum recibido")):
        category = categories["transfers"]
        confidence = Decimal("0.85")
    else:
        category = categories["other"]
        confidence = Decimal("0.30")
        for key, words in KEYWORDS:
            if any(word in text for word in words):
                category = categories[key]
                confidence = Decimal("0.85")
                break
    tx.category_id = category.id
    tx.categorization_method = "deterministic_classifier"
    tx.categorization_confidence = confidence
