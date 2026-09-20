from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from io import StringIO
from pathlib import Path
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


def import_csv(session: Session, account_id: str, content: bytes, source_ref: str) -> ImportResult:
    text = content.decode("utf-8-sig", errors="strict")
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
        dialect.delimiter = ";"
    reader = csv.DictReader(StringIO(text), dialect=dialect)
    inserted = duplicates = rejected = ignored = 0
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
            fingerprint = sha256(f"{account_id}|{booking_date.isoformat()}|{amount}|{normalized}".encode()).hexdigest()
            existing = session.scalar(select(Transaction.id).where(
                Transaction.account_id == account_id,
                Transaction.duplicate_fingerprint == fingerprint,
            ))
            if existing:
                duplicates += 1
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
    return ImportResult(inserted, duplicates, rejected, ignored)
