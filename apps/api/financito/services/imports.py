from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher
from hashlib import sha256
from io import StringIO
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Transaction
from .categorization import categorize_transaction, normalize_text


@dataclass(frozen=True)
class ImportResult:
    inserted: int
    duplicates: int
    rejected: int
    ignored: int = 0
    duplicates_reference: int = 0
    duplicates_exact: int = 0
    duplicates_similar: int = 0


def parse_decimal(raw: str) -> Decimal:
    value = raw.strip().replace("€", "").replace(" ", "")
    if not value:
        raise InvalidOperation("empty")
    if "," in value and "." in value:
        if value.rfind(",") > value.rfind("."):
            value = value.replace(".", "").replace(",", ".")
        else:
            value = value.replace(",", "")
    elif "," in value:
        value = value.replace(".", "").replace(",", ".")
    return Decimal(value)


def parse_date(raw: str):
    raw = raw.strip()
    if not raw:
        raise ValueError("Empty date")
    iso = raw.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(iso).date()
    except ValueError:
        pass
    for fmt in (
        "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d",
        "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S",
        "%Y-%m-%d %H:%M", "%d/%m/%Y %H:%M",
    ):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unsupported date: {raw}")


def canonical_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", normalize_text(name))


_REFERENCE_KEYS = (
    "transactionid", "transactionidentifier", "transactionreference",
    "banktransactionid", "movementid", "movementidentifier",
    "operationid", "operationreference", "paymentid", "paymentreference",
    "fitid", "endtoendid", "txid", "ntryref", "entryreference",
    "acctsvcrref", "accountservicerreference",
    "bankreference", "referencia", "reference",
)

_VOLATILE_WORDS = {
    "compra", "pago", "tarjeta", "card", "operacion", "operation", "movimiento",
    "transaction", "transaccion", "cargo", "abono", "debito", "credito",
    "fecha", "date", "ref", "referencia", "terminal", "tpv",
}


def _stable_reference(mapped: dict[str, str]) -> str | None:
    for key in _REFERENCE_KEYS:
        raw = (mapped.get(key) or "").strip()
        if not raw:
            continue
        normalized = re.sub(r"\s+", "", raw).lower()
        if normalized in {"na", "n/a", "none", "null", "-", "0", "0000"}:
            continue
        if len(normalized) >= 4:
            return normalized
    return None


def _fingerprint(
    account_id: str,
    booking_date,
    amount: Decimal,
    currency: str,
    normalized_description: str,
    external_reference: str | None,
    occurrence: int,
) -> str:
    if external_reference:
        raw = f"{account_id}|external|{external_reference}"
    else:
        raw = f"{account_id}|{booking_date.isoformat()}|{amount}|{currency}|{normalized_description}"
        if occurrence > 1:
            raw += f"|occurrence:{occurrence}"
    return sha256(raw.encode()).hexdigest()


def _clean_descriptor(value: str | None) -> str:
    text = normalize_text(value or "")
    tokens = []
    for token in re.findall(r"[a-z0-9]+", text):
        if token in _VOLATILE_WORDS:
            continue
        if token.isdigit() and len(token) >= 3:
            continue
        if len(token) == 1:
            continue
        tokens.append(token)
    return " ".join(tokens)


def _similarity(left: str | None, right: str | None) -> tuple[float, float]:
    a = _clean_descriptor(left)
    b = _clean_descriptor(right)
    if not a or not b:
        return 0.0, 0.0
    sequence = SequenceMatcher(None, a, b).ratio()
    sa, sb = set(a.split()), set(b.split())
    union = sa | sb
    jaccard = 0.0 if not union else len(sa & sb) / len(union)
    return sequence, jaccard


def _merchant_compatible(
    incoming_merchant: str | None,
    incoming_description: str,
    existing: Transaction,
) -> bool:
    left = _clean_descriptor(incoming_merchant)
    right = _clean_descriptor(existing.merchant_normalized or existing.merchant_raw)
    if left and right:
        seq, jac = _similarity(left, right)
        return left == right or seq >= 0.90 or jac >= 0.80

    merchant = left or right
    if not merchant:
        return False
    other_description = existing.description_normalized if left else incoming_description
    desc = _clean_descriptor(other_description)
    return len(merchant) >= 4 and (merchant in desc or desc in merchant)


def _looks_like_same_transaction(
    *,
    booking_date,
    description: str,
    merchant: str | None,
    candidate: Transaction,
) -> bool:
    day_gap = abs((candidate.booking_date - booking_date).days)
    if day_gap > 1:
        return False

    seq, jac = _similarity(description, candidate.description_normalized or candidate.description_raw)
    merchant_ok = _merchant_compatible(merchant, description, candidate)

    # Same-day matching may tolerate bank-added prefixes/suffixes when the
    # merchant is independently consistent. Without merchant evidence, require
    # a very high text match.
    if day_gap == 0:
        if merchant_ok and (seq >= 0.72 or jac >= 0.60):
            return True
        return seq >= 0.92 or jac >= 0.88

    # A one-day booking shift is common between pending/completed exports, but
    # requires stronger evidence to avoid merging two real purchases.
    if merchant_ok and (seq >= 0.84 or jac >= 0.75):
        return True
    return seq >= 0.97 and jac >= 0.90


def _find_tolerant_duplicate(
    session: Session,
    *,
    account_id: str,
    booking_date,
    amount: Decimal,
    currency: str,
    description: str,
    merchant: str | None,
    preexisting_ids: set[str],
    matched_existing_ids: set[str],
) -> Transaction | None:
    candidates = session.scalars(
        select(Transaction).where(
            Transaction.account_id == account_id,
            Transaction.amount == amount,
            Transaction.currency == currency,
            Transaction.booking_date >= booking_date - timedelta(days=1),
            Transaction.booking_date <= booking_date + timedelta(days=1),
        )
    ).all()

    ranked: list[tuple[float, Transaction]] = []
    for candidate in candidates:
        if candidate.id not in preexisting_ids or candidate.id in matched_existing_ids:
            continue
        if not _looks_like_same_transaction(
            booking_date=booking_date,
            description=description,
            merchant=merchant,
            candidate=candidate,
        ):
            continue
        seq, jac = _similarity(description, candidate.description_normalized or candidate.description_raw)
        merchant_bonus = 0.15 if _merchant_compatible(merchant, description, candidate) else 0.0
        date_bonus = 0.10 if candidate.booking_date == booking_date else 0.0
        ranked.append((max(seq, jac) + merchant_bonus + date_bonus, candidate))

    if not ranked:
        return None
    ranked.sort(key=lambda item: item[0], reverse=True)
    return ranked[0][1]


def import_csv(session: Session, account_id: str, content: bytes, source_ref: str) -> ImportResult:
    text = content.decode("utf-8-sig", errors="strict")
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
        dialect.delimiter = ";"
    reader = csv.DictReader(StringIO(text), dialect=dialect)

    preexisting_ids = set(
        session.scalars(select(Transaction.id).where(Transaction.account_id == account_id)).all()
    )
    matched_existing_ids: set[str] = set()
    occurrence_by_identity: dict[str, int] = defaultdict(int)

    inserted = duplicates = rejected = ignored = 0
    duplicates_reference = duplicates_exact = duplicates_similar = 0

    for row in reader:
        try:
            mapped = {canonical_key(k or ""): (v or "") for k, v in row.items()}
            state = next((mapped[k] for k in ("state", "status", "transactionstatus", "estado") if mapped.get(k)), "")
            state_key = canonical_key(state)
            if state_key in {
                "pending","pendiente","reverted","revertido","revertida","reversed",
                "declined","rechazado","rechazada","failed","fallido","fallida",
                "cancelled","canceled","cancelado","cancelada",
            }:
                ignored += 1
                continue

            raw_date = next(mapped[k] for k in (
                "completeddate","transactioncompleted","transactioncompletedutc",
                "fechadefinalizacion","fechadecompletado","fechacompletada",
                "fecha","date","bookingdate","fechacontable",
                "starteddate","transactionstarted","transactionstartedutc","fechadeinicio",
            ) if k in mapped and mapped[k])
            raw_amount = next(mapped[k] for k in (
                "importe","amount","amountpaymentcurrency","cantidad",
            ) if k in mapped and mapped[k])
            description = next((mapped[k] for k in (
                "concepto","descripcion","description","transactiondescription",
                "descripciondelatransaccion","detalle",
            ) if mapped.get(k)), "Movimiento")
            merchant = next((mapped[k] for k in ("comercio", "merchant", "beneficiario", "payer") if mapped.get(k)), None)
            currency = next((mapped[k].upper() for k in ("moneda", "currency", "paymentcurrency") if mapped.get(k)), "EUR")

            booking_date = parse_date(raw_date)
            amount = parse_decimal(raw_amount)
            normalized = normalize_text(description)
            external_reference = _stable_reference(mapped)

            identity = (
                f"external:{external_reference}" if external_reference
                else f"{booking_date.isoformat()}|{amount}|{currency}|{normalized}"
            )
            occurrence_by_identity[identity] += 1
            occurrence = occurrence_by_identity[identity]
            fingerprint = _fingerprint(
                account_id, booking_date, amount, currency, normalized,
                external_reference, occurrence,
            )

            existing = session.scalar(select(Transaction).where(
                Transaction.account_id == account_id,
                Transaction.duplicate_fingerprint == fingerprint,
            ))
            if existing:
                duplicates += 1
                matched_existing_ids.add(existing.id)
                if external_reference:
                    duplicates_reference += 1
                else:
                    duplicates_exact += 1
                continue

            tolerant = _find_tolerant_duplicate(
                session,
                account_id=account_id,
                booking_date=booking_date,
                amount=amount,
                currency=currency,
                description=description,
                merchant=merchant,
                preexisting_ids=preexisting_ids,
                matched_existing_ids=matched_existing_ids,
            )
            if tolerant:
                duplicates += 1
                duplicates_similar += 1
                matched_existing_ids.add(tolerant.id)
                continue

            tx = Transaction(
                account_id=account_id,
                booking_date=booking_date,
                amount=amount,
                currency=currency,
                base_amount=amount,
                base_currency=currency,
                description_raw=description.strip(),
                description_normalized=normalized,
                merchant_raw=merchant,
                merchant_normalized=normalize_text(merchant) if merchant else None,
                duplicate_fingerprint=fingerprint,
                source="csv",
                source_ref=source_ref,
            )
            categorize_transaction(session, tx)
            session.add(tx)
            session.flush()
            inserted += 1
        except Exception:
            rejected += 1

    return ImportResult(
        inserted=inserted,
        duplicates=duplicates,
        rejected=rejected,
        ignored=ignored,
        duplicates_reference=duplicates_reference,
        duplicates_exact=duplicates_exact,
        duplicates_similar=duplicates_similar,
    )
