from __future__ import annotations
import csv,json
from datetime import date
from io import StringIO
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..models import Account,Contract,Document,FinancialGoal,Transaction
from ..models_extended import Asset,Liability
from .rag import search as rag_search
def global_search(
    session:Session,q:str,limit:int=20,start:date|None=None,end:date|None=None,
    account_id:str|None=None,account_type:str|None=None,
)->dict:
    pattern="%"+q[:120]+"%"
    tx_stmt=select(Transaction).where((Transaction.description_raw.ilike(pattern))|(Transaction.merchant_raw.ilike(pattern)))
    if start:
        tx_stmt=tx_stmt.where(Transaction.booking_date>=start)
    if end:
        tx_stmt=tx_stmt.where(Transaction.booking_date<=end)
    if account_id:
        tx_stmt=tx_stmt.where(Transaction.account_id==account_id)
    elif account_type:
        tx_stmt=tx_stmt.where(Transaction.account_id.in_(select(Account.id).where(Account.account_type==account_type)))
    tx=session.scalars(tx_stmt.limit(limit)).all()
    contracts=session.scalars(select(Contract).where(Contract.provider_name.ilike(pattern)).limit(limit)).all()
    docs=rag_search(session,q,min(8,limit),use_vector=False)
    return {"transactions":[{"id":x.id,"date":x.booking_date,"description":x.description_raw,"amount":str(x.amount)} for x in tx],"contracts":[{"id":x.id,"provider":x.provider_name,"type":x.contract_type} for x in contracts],"documents":docs}
def export_json(session:Session)->dict:
    return {"version":1,"accounts":[{"id":x.id,"name":x.name,"currency":x.currency,"balance":str(x.current_balance)} for x in session.scalars(select(Account)).all()],"transactions":[{"id":x.id,"account_id":x.account_id,"date":str(x.booking_date),"amount":str(x.amount),"currency":x.currency,"description":x.description_raw,"category_id":x.category_id} for x in session.scalars(select(Transaction)).all()],"assets":[{"id":x.id,"name":x.name,"type":x.asset_type,"value":str(x.current_value)} for x in session.scalars(select(Asset)).all()],"liabilities":[{"id":x.id,"name":x.name,"type":x.liability_type,"amount":str(x.outstanding_amount)} for x in session.scalars(select(Liability)).all()],"contracts":[{"id":x.id,"provider":x.provider_name,"type":x.contract_type,"renewal":None if x.renewal_date is None else str(x.renewal_date)} for x in session.scalars(select(Contract)).all()],"goals":[{"id":x.id,"name":x.name,"target":str(x.target_amount),"current":str(x.current_amount)} for x in session.scalars(select(FinancialGoal)).all()],"documents":[{"id":x.id,"file_name":x.file_name,"sha256":x.sha256,"type":x.document_type} for x in session.scalars(select(Document)).all()]}
def transactions_csv(session:Session)->str:
    out=StringIO();w=csv.writer(out);w.writerow(["id","account_id","booking_date","amount","currency","description","category_id","source"])
    for x in session.scalars(select(Transaction).order_by(Transaction.booking_date)).all():w.writerow([x.id,x.account_id,x.booking_date,x.amount,x.currency,x.description_raw,x.category_id,x.source])
    return out.getvalue()
