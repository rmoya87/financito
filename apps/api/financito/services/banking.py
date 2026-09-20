from __future__ import annotations

from datetime import date,datetime,timezone,timedelta
from decimal import Decimal
from hashlib import sha256
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Account,ActionItem,AuditEvent,Transaction
from ..models_analytics import BankingAccountLink,BankingConnection
from ..providers.enable_banking import EnableBankingProvider
from .categorization import categorize_transaction,normalize_text

def _dt(value:str|None)->datetime|None:
    if not value:
        return None
    try:
        parsed=datetime.fromisoformat(value.replace("Z","+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None

def _masked_iban(resource:dict)->str|None:
    account_id=resource.get("account_id") or {}
    iban=account_id.get("iban") if isinstance(account_id,dict) else None
    if not iban:
        return None
    cleaned=str(iban).replace(" ","")
    return cleaned[:4]+"…"+cleaned[-4:] if len(cleaned)>=8 else "…"+cleaned[-4:]

def _account_name(resource:dict,bank_name:str)->str:
    return resource.get("name") or resource.get("product") or resource.get("details") or f"Cuenta {bank_name}"

def _find_existing_account(session:Session,identification_hash:str|None)->str|None:
    if not identification_hash:
        return None
    link=session.scalar(select(BankingAccountLink).where(BankingAccountLink.identification_hash==identification_hash).order_by(BankingAccountLink.created_at.desc()))
    return link.local_account_id if link else None

def complete_authorization(session:Session,code:str,provider:EnableBankingProvider|None=None)->dict:
    provider=provider or EnableBankingProvider()
    data=provider.authorize_session(code)
    session_id=data.get("session_id")
    if not session_id:
        raise RuntimeError("Enable Banking did not return a session_id")
    aspsp=data.get("aspsp") or {}
    access=data.get("access") or {}
    row=BankingConnection(
        provider="enable_banking",
        session_id=session_id,
        bank_name=aspsp.get("name") or "Banco",
        country=aspsp.get("country") or "ES",
        consent_expires_at=_dt(access.get("valid_until")),
        status="active",
        metadata_json=json.dumps({"psu_type":data.get("psu_type"),"authorized_at":data.get("authorized")},ensure_ascii=False),
    )
    session.add(row);session.flush()
    linked=[]
    for resource in data.get("accounts") or []:
        uid=resource.get("uid")
        if not uid:
            continue
        ih=resource.get("identification_hash")
        local_id=_find_existing_account(session,ih)
        account=session.get(Account,local_id) if local_id else None
        if account is None:
            account=Account(
                institution_name=row.bank_name,
                name=_account_name(resource,row.bank_name),
                account_type=resource.get("cash_account_type") or "checking",
                currency=resource.get("currency") or "EUR",
                iban_masked=_masked_iban(resource),
                current_balance=Decimal("0"),
                source="enable_banking",
                sync_status="connected",
            )
            session.add(account);session.flush()
        link=BankingAccountLink(
            connection_id=row.id,
            local_account_id=account.id,
            provider_account_uid=uid,
            identification_hash=ih,
            metadata_json=json.dumps({"identification_hashes":resource.get("identification_hashes") or []},ensure_ascii=False),
        )
        session.add(link);linked.append({"local_account_id":account.id,"provider_account_uid":uid})
    session.add(AuditEvent(event_type="banking_connection_created",entity_type="banking_connection",entity_id=row.id,metadata_json=json.dumps({"bank":row.bank_name,"accounts":len(linked)})))
    _ensure_consent_action(session,row)
    session.flush()
    return {"connection_id":row.id,"session_id":row.session_id,"bank_name":row.bank_name,"country":row.country,"consent_expires_at":row.consent_expires_at,"accounts":linked}

def _balance_value(data:dict)->tuple[Decimal|None,str|None]:
    balances=data.get("balances") or []
    if not balances:
        return None,None
    preferred=next((b for b in balances if b.get("balance_type") in {"CLAV","ITAV","CLBD"}),balances[0])
    amount=preferred.get("balance_amount") or {}
    try:
        return Decimal(str(amount.get("amount"))),amount.get("currency")
    except Exception:
        return None,amount.get("currency")

def _description(item:dict)->str:
    rem=item.get("remittance_information")
    if isinstance(rem,list) and rem:
        return " · ".join(str(x) for x in rem if x)
    if isinstance(rem,str) and rem:
        return rem
    btc=item.get("bank_transaction_code") or {}
    if btc.get("description"):
        return str(btc["description"])
    creditor=(item.get("creditor") or {}).get("name")
    debtor=(item.get("debtor") or {}).get("name")
    return creditor or debtor or "Movimiento bancario"

def _merchant(item:dict)->str|None:
    indicator=item.get("credit_debit_indicator")
    if indicator=="DBIT":
        return (item.get("creditor") or {}).get("name")
    return (item.get("debtor") or {}).get("name")

def _tx_fingerprint(provider_uid:str,item:dict)->str:
    stable=item.get("entry_reference")
    if not stable:
        amount=item.get("transaction_amount") or {}
        stable="|".join([
            str(item.get("booking_date") or item.get("transaction_date") or ""),
            str(amount.get("amount") or ""),
            str(amount.get("currency") or ""),
            _description(item),
        ])
    return sha256(f"enable_banking|{provider_uid}|{stable}".encode()).hexdigest()

def _insert_transactions(session:Session,link:BankingAccountLink,items:list[dict])->tuple[int,int]:
    inserted=skipped=0
    for item in items:
        if item.get("status") not in {None,"BOOK"}:
            skipped+=1;continue
        amount_data=item.get("transaction_amount") or {}
        try:
            amount=Decimal(str(amount_data.get("amount")))
        except Exception:
            skipped+=1;continue
        if item.get("credit_debit_indicator")=="DBIT":
            amount=-abs(amount)
        elif item.get("credit_debit_indicator")=="CRDT":
            amount=abs(amount)
        booking=item.get("booking_date") or item.get("transaction_date")
        try:
            booking_date=date.fromisoformat(str(booking))
        except Exception:
            skipped+=1;continue
        fp=_tx_fingerprint(link.provider_account_uid,item)
        exists=session.scalar(select(Transaction.id).where(Transaction.account_id==link.local_account_id,Transaction.duplicate_fingerprint==fp))
        if exists:
            skipped+=1;continue
        description=_description(item)
        merchant=_merchant(item)
        tx=Transaction(
            account_id=link.local_account_id,
            booking_date=booking_date,
            value_date=date.fromisoformat(item["value_date"]) if item.get("value_date") else None,
            amount=amount,
            currency=amount_data.get("currency") or "EUR",
            base_amount=amount,
            base_currency=amount_data.get("currency") or "EUR",
            description_raw=description,
            description_normalized=normalize_text(description),
            merchant_raw=merchant,
            merchant_normalized=normalize_text(merchant) if merchant else None,
            duplicate_fingerprint=fp,
            source="enable_banking",
            source_ref=item.get("entry_reference") or item.get("transaction_id"),
        )
        categorize_transaction(session,tx);session.add(tx);inserted+=1
    return inserted,skipped

def sync_connection(session:Session,connection_id:str,provider:EnableBankingProvider|None=None)->dict:
    provider=provider or EnableBankingProvider()
    connection=session.get(BankingConnection,connection_id)
    if not connection:
        raise ValueError("Banking connection not found")
    remote=provider.session(connection.session_id)
    status=str(remote.get("status") or "UNKNOWN")
    connection.status=status.lower()
    valid_until=(remote.get("access") or {}).get("valid_until")
    if valid_until:
        connection.consent_expires_at=_dt(valid_until)
    if status!="AUTHORIZED":
        session.flush()
        return {"connection_id":connection.id,"status":connection.status,"inserted":0,"skipped":0,"accounts":0}
    links=session.scalars(select(BankingAccountLink).where(BankingAccountLink.connection_id==connection.id)).all()
    inserted=skipped=0
    for link in links:
        account=session.get(Account,link.local_account_id)
        if account is None:
            continue
        try:
            details=provider.account_details(link.provider_account_uid)
            account.name=_account_name(details,connection.bank_name)
            account.currency=details.get("currency") or account.currency
            account.iban_masked=_masked_iban(details) or account.iban_masked
        except Exception:
            pass
        balances=provider.balances(link.provider_account_uid)
        balance,currency=_balance_value(balances)
        if balance is not None:
            account.current_balance=balance
            account.available_balance=balance
        if currency:
            account.currency=currency
        continuation=None
        for _ in range(100):
            payload=provider.transactions(link.provider_account_uid,continuation_key=continuation)
            a,b=_insert_transactions(session,link,payload.get("transactions") or [])
            inserted+=a;skipped+=b
            continuation=payload.get("continuation_key")
            if not continuation:
                break
        account.sync_status="synced"
        link.last_sync_at=datetime.now(timezone.utc)
    session.add(AuditEvent(event_type="banking_connection_synced",entity_type="banking_connection",entity_id=connection.id,metadata_json=json.dumps({"inserted":inserted,"skipped":skipped,"accounts":len(links)})))
    _ensure_consent_action(session,connection)
    session.flush()
    return {"connection_id":connection.id,"status":connection.status,"inserted":inserted,"skipped":skipped,"accounts":len(links),"consent_expires_at":connection.consent_expires_at}

def close_connection(session:Session,connection_id:str,provider:EnableBankingProvider|None=None)->dict:
    provider=provider or EnableBankingProvider()
    connection=session.get(BankingConnection,connection_id)
    if not connection:
        raise ValueError("Banking connection not found")
    try:
        provider.close_session(connection.session_id)
    finally:
        connection.status="closed"
        for link in session.scalars(select(BankingAccountLink).where(BankingAccountLink.connection_id==connection.id)).all():
            account=session.get(Account,link.local_account_id)
            if account:
                account.sync_status="disconnected"
        session.add(AuditEvent(event_type="banking_connection_closed",entity_type="banking_connection",entity_id=connection.id))
        session.flush()
    return {"connection_id":connection.id,"status":"closed"}

def list_connections(session:Session)->list[dict]:
    rows=session.scalars(select(BankingConnection).order_by(BankingConnection.created_at.desc())).all()
    out=[]
    for row in rows:
        links=session.scalars(select(BankingAccountLink).where(BankingAccountLink.connection_id==row.id)).all()
        out.append({
            "id":row.id,
            "provider":row.provider,
            "bank_name":row.bank_name,
            "country":row.country,
            "status":row.status,
            "consent_expires_at":row.consent_expires_at,
            "accounts":[{"local_account_id":l.local_account_id,"provider_account_uid":l.provider_account_uid,"last_sync_at":l.last_sync_at} for l in links],
        })
    return out


def _ensure_consent_action(session:Session,connection:BankingConnection)->None:
    expires=connection.consent_expires_at
    if not expires or connection.status in {"closed","deleted"}:
        return
    aware=expires if expires.tzinfo else expires.replace(tzinfo=timezone.utc)
    if aware>datetime.now(timezone.utc)+timedelta(days=14):
        return
    exists=session.scalar(select(ActionItem.id).where(ActionItem.action_type=="banking_consent_renewal",ActionItem.related_entity_id==connection.id,ActionItem.status.in_(["pending","in_progress"])))
    if not exists:
        session.add(ActionItem(action_type="banking_consent_renewal",title=f"Renovar consentimiento bancario de {connection.bank_name}",related_entity_type="banking_connection",related_entity_id=connection.id,due_date=aware.date(),priority="high",source_type="banking",source_ref=connection.id,notes="La renovación requiere volver a autorizar el acceso con el banco; Financito no puede renovar el consentimiento sin interacción del usuario."))
