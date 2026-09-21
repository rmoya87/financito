from __future__ import annotations

from sqlalchemy import func,select
from sqlalchemy.orm import Session

from ..models import Account,Document,ExtractedFact,Transaction
from ..models_extended import RepairIssue


def reconciliation(session:Session)->list[dict]:
    items=[]
    unc=session.scalar(select(func.count()).select_from(Transaction).where(Transaction.category_id.is_(None))) or 0
    if unc:
        items.append({
            "type":"uncategorized_transactions","label":"Movimientos sin categoría","count":unc,"severity":"medium",
            "detail":"No entran correctamente en análisis por categoría ni en algunas previsiones.","action_href":"/transactions/",
        })
    low=session.scalar(select(func.count()).select_from(Transaction).where(Transaction.categorization_confidence<0.5,Transaction.user_verified.is_(False))) or 0
    if low:
        items.append({
            "type":"low_confidence_transactions","label":"Clasificaciones con poca confianza","count":low,"severity":"medium",
            "detail":"Conviene revisar estos movimientos o ejecutar la categorización con IA local.","action_href":"/transactions/",
        })
    pending_sync=session.scalar(select(func.count()).select_from(Account).where(Account.sync_status=="pending_sync")) or 0
    if pending_sync:
        items.append({
            "type":"bank_accounts_pending_sync","label":"Cuentas bancarias pendientes de sincronizar","count":pending_sync,"severity":"high",
            "detail":"Hasta sincronizarlas, el saldo mostrado puede no ser el saldo bancario actual.","action_href":"/accounts/",
        })
    disconnected=session.scalar(select(func.count()).select_from(Account).where(Account.sync_status=="disconnected")) or 0
    if disconnected:
        items.append({
            "type":"bank_accounts_disconnected","label":"Cuentas bancarias desconectadas","count":disconnected,"severity":"medium",
            "detail":"Sus saldos dejan de actualizarse automáticamente hasta volver a autorizar el banco.","action_href":"/banking/",
        })
    facts=session.scalar(select(func.count()).select_from(ExtractedFact).where(ExtractedFact.status.in_(["ambiguous","conflicting"]))) or 0
    if facts:
        items.append({
            "type":"contract_evidence_conflicts","label":"Datos documentales que necesitan revisión","count":facts,"severity":"high",
            "detail":"Hay valores ambiguos o contradictorios; no se usan como hechos confirmados.","action_href":"/documents/",
        })
    failed=session.scalar(select(func.count()).select_from(Document).where(Document.status=="failed")) or 0
    if failed:
        items.append({
            "type":"failed_documents","label":"Documentos que no se pudieron procesar","count":failed,"severity":"high",
            "detail":"Revisa esos archivos para que sus condiciones puedan utilizarse en el análisis.","action_href":"/documents/",
        })
    return items
