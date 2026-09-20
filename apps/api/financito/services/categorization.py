from __future__ import annotations

import re
import unicodedata
from collections import Counter
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Category, Transaction


# Stable system keys are part of the persisted categorization contract.
# New keys are additive so existing transactions, rules and budgets remain valid.
DEFAULT_CATEGORIES={
    "income":"Ingresos",
    "salary":"Nómina",
    "refunds":"Reembolsos",
    "housing":"Vivienda",
    "groceries":"Supermercado",
    "restaurants":"Restaurantes",
    "transport":"Transporte",
    "vehicle":"Vehículo",
    "utilities":"Suministros",
    "telecom":"Telecomunicaciones",
    "insurance":"Seguros",
    "health":"Salud",
    "personal_care":"Cuidado personal",
    "education":"Educación",
    "family":"Familia",
    "pets":"Mascotas",
    "sports":"Deporte",
    "leisure":"Ocio",
    "technology":"Tecnología",
    "shopping":"Compras",
    "subscriptions":"Suscripciones",
    "travel":"Viajes",
    "taxes":"Impuestos",
    "bank_fees":"Comisiones bancarias",
    "debt":"Préstamos y deuda",
    "donations":"Donaciones",
    "investments":"Inversión",
    "savings":"Ahorro",
    "transfers":"Transferencias",
    "other":"Otros",
}

KEYWORDS=[
    ("groceries",("mercadona","carrefour","lidl","aldi","supermercado","alcampo","dia ","ahorramas","hipercor alimentacion")),
    ("restaurants",("restaurant","restaurante","bar ","cafeteria","cafetería","just eat","glovo","uber eats","deliveroo")),
    ("vehicle",("repsol","cepsa","bp ","shell ","gasolinera","combustible","itv","taller ","parking","aparcamiento","peaje","supercharger","carga vehiculo","carga vehículo")),
    ("transport",("renfe","metro","autobus","autobús","emt ","uber","cabify","taxi","bolt ")),
    ("utilities",("iberdrola","endesa","naturgy","agua","canal de isabel","electricidad","gas ")),
    ("telecom",("movistar","vodafone","orange","digi","o2 ","pepephone","masmovil","másmóvil","jazztel","lowi","finetwork","telefono","teléfono","internet","fibra")),
    ("insurance",("seguro","mapfre","axa","allianz","mutua madrilena","mutua madrileña","linea directa","línea directa")),
    ("subscriptions",("netflix","spotify","apple.com/bill","disney","hbo","max.com","amazon prime","youtube premium","icloud","dropbox")),
    ("housing",("hipoteca","alquiler","comunidad propietarios","comunidad de propietarios","reparacion hogar","reparación hogar","muebles","ikea")),
    ("health",("farmacia","hospital","clinica","clínica","dentista","fisioterapia","fisioterapeuta","optica","óptica")),
    ("personal_care",("peluqueria","peluquería","barberia","barbería","estetica","estética","perfumeria","perfumería")),
    ("education",("colegio","academia","universidad","libros texto","material escolar","matricula","matrícula")),
    ("family",("guarderia","guardería","jugueteria","juguetería","juguetes","pañales","campamento infantil")),
    ("pets",("veterinario","veterinaria","kiwoko","tiendanimal","zooplus","mascota","pienso perro","pienso gato")),
    ("sports",("gimnasio","crossfit","padel","pádel","deporte","decathlon","basic-fit","basic fit","go fit","futbol","fútbol","natacion","natación")),
    ("leisure",("cine","teatro","ticketmaster","entradas","ocio","bowling","parque tematico","parque temático","steam ","playstation","nintendo")),
    ("technology",("mediamarkt","media markt","pccomponentes","apple store","microsoft store","electronica","electrónica")),
    ("travel",("booking","airbnb","hotel","ryanair","iberia","vueling","easyjet","hostal","parador")),
    ("taxes",("agencia tributaria","ayuntamiento","ibi","impuesto","tasa municipal")),
    ("bank_fees",("comision bancaria","comisión bancaria","comision mantenimiento","comisión mantenimiento","cuota tarjeta","bank fee","service fee")),
    ("debt",("prestamo","préstamo","cuota credito","cuota crédito","financiacion","financiación")),
    ("donations",("donativo","donacion","donación","cruz roja","unicef","medicos sin fronteras","médicos sin fronteras")),
    ("investments",("broker","degiro","trade republic","interactive brokers","myinvestor inversion","myinvestor inversión")),
    ("savings",("aportacion ahorro","aportación ahorro","plan de ahorro","cuenta ahorro")),
]

SALARY_KEYWORDS=("nomina","nómina","payroll","salario","sueldo")
REFUND_KEYWORDS=("devolucion","devolución","reembolso","refund","retrocesion","retrocesión")
TRANSFER_KEYWORDS=("transferencia","traspaso","bizum enviado","bizum recibido")


def normalize_text(value:str)->str:
    value=unicodedata.normalize("NFKD",value).encode("ascii","ignore").decode("ascii")
    return re.sub(r"\s+"," ",value.lower()).strip()


def ensure_categories(session:Session)->dict[str,Category]:
    existing={c.system_key:c for c in session.scalars(select(Category)).all()}
    for key,name in DEFAULT_CATEGORIES.items():
        if key not in existing:
            category=Category(name=name,system_key=key);session.add(category);session.flush();existing[key]=category
    return existing


def _merchant_value(tx:Transaction)->str:
    merchant=tx.merchant_normalized or normalize_text(tx.merchant_raw or "")
    if merchant and not tx.merchant_normalized:tx.merchant_normalized=merchant
    return merchant


def learned_merchant_category(session:Session,tx:Transaction)->tuple[str,Decimal]|None:
    merchant=_merchant_value(tx)
    if not merchant:return None
    stmt=select(Transaction.category_id).where(Transaction.user_verified.is_(True),Transaction.merchant_normalized==merchant,Transaction.category_id.is_not(None))
    if tx.id:stmt=stmt.where(Transaction.id!=tx.id)
    ids=[x for x in session.scalars(stmt.limit(100)).all() if x]
    if not ids:return None
    counts=Counter(ids);category_id,n=counts.most_common(1)[0];total=sum(counts.values())
    if len(counts)==1:return category_id,Decimal("0.98")
    if total>=5 and Decimal(n)/Decimal(total)>=Decimal("0.90"):return category_id,Decimal("0.94")
    return None


def propagate_verified_merchant(session:Session,source:Transaction)->int:
    merchant=_merchant_value(source)
    if not merchant or not source.category_id:return 0
    verified=[x for x in session.scalars(select(Transaction.category_id).where(Transaction.user_verified.is_(True),Transaction.merchant_normalized==merchant,Transaction.category_id.is_not(None))).all() if x]
    if len(set(verified))!=1:return 0
    changed=0
    rows=session.scalars(select(Transaction).where(Transaction.user_verified.is_(False),Transaction.merchant_normalized==merchant)).all()
    for tx in rows:
        if tx.categorization_method=="rule":continue
        if tx.category_id!=source.category_id or tx.categorization_confidence<Decimal("0.98"):
            tx.category_id=source.category_id;tx.categorization_method="learned_merchant";tx.categorization_confidence=Decimal("0.98");changed+=1
    session.flush();return changed


def categorize_transaction(session:Session,tx:Transaction)->None:
    if tx.user_verified:return
    from .transaction_ops import apply_rule
    if apply_rule(session,tx):return
    categories=ensure_categories(session)
    learned=learned_merchant_category(session,tx)
    if learned:
        tx.category_id,tx.categorization_confidence=learned;tx.categorization_method="learned_merchant";return

    text=normalize_text(f"{tx.merchant_raw or ''} {tx.description_raw}")
    if tx.amount>0:
        if any(k in text for k in SALARY_KEYWORDS):category=categories["salary"];confidence=Decimal("0.92")
        elif any(k in text for k in REFUND_KEYWORDS):category=categories["refunds"];confidence=Decimal("0.88")
        elif any(k in text for k in TRANSFER_KEYWORDS):category=categories["transfers"];confidence=Decimal("0.85")
        else:category=categories["income"];confidence=Decimal("0.90")
    elif any(k in text for k in TRANSFER_KEYWORDS):
        category=categories["transfers"];confidence=Decimal("0.85")
    else:
        category=categories["other"];confidence=Decimal("0.30")
        for key,words in KEYWORDS:
            if any(word in text for word in words):category=categories[key];confidence=Decimal("0.85");break

    tx.category_id=category.id;tx.categorization_method="deterministic_classifier";tx.categorization_confidence=confidence
