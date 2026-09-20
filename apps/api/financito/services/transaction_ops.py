from __future__ import annotations
import re
from datetime import timedelta
from decimal import Decimal
from sqlalchemy import delete,select
from sqlalchemy.orm import Session
from ..models import Category,Transaction
from ..models_analytics import EntityLink,TransactionRule,TransactionSplit
from .categorization import normalize_text

def apply_rule(session:Session,tx:Transaction)->bool:
    if tx.user_verified:return False
    text=normalize_text((tx.merchant_raw or "")+" "+tx.description_raw)
    merchant=normalize_text(tx.merchant_raw or "")
    for rule in session.scalars(select(TransactionRule).where(TransactionRule.enabled.is_(True)).order_by(TransactionRule.priority,TransactionRule.id)).all():
        value=normalize_text(rule.matcher_value);matched=False
        if rule.matcher_type=="contains":matched=value in text
        elif rule.matcher_type=="merchant_exact":matched=value==merchant
        elif rule.matcher_type=="regex":
            try:matched=bool(re.search(rule.matcher_value,text,re.I))
            except re.error:matched=False
        if matched:
            tx.category_id=rule.category_id;tx.categorization_method="rule";tx.categorization_confidence=Decimal("1");return True
    return False

def apply_rules_to_unverified(session:Session)->int:
    changed=0
    for tx in session.scalars(select(Transaction).where(Transaction.user_verified.is_(False))).all():
        if apply_rule(session,tx):changed+=1
    return changed

def detect_internal_transfers(session:Session)->int:
    txs=session.scalars(select(Transaction).where(Transaction.is_internal_transfer.is_(False)).order_by(Transaction.booking_date)).all()
    marked=set()
    for i,left in enumerate(txs):
        if left.id in marked:continue
        for right in txs[i+1:]:
            if right.booking_date>left.booking_date+timedelta(days=3):break
            if right.id in marked or right.account_id==left.account_id:continue
            if left.amount+right.amount==0 and abs((right.booking_date-left.booking_date).days)<=3:
                left.is_internal_transfer=True;right.is_internal_transfer=True;marked.update([left.id,right.id]);break
    return len(marked)//2

def set_splits(session:Session,transaction_id:str,splits:list[dict])->list[TransactionSplit]:
    tx=session.get(Transaction,transaction_id)
    if not tx:raise ValueError("Transaction not found")
    total=sum((Decimal(str(x["amount"])) for x in splits),Decimal("0"))
    if total!=abs(tx.amount):raise ValueError("Split total must exactly match absolute transaction amount")
    for item in splits:
        if Decimal(str(item["amount"]))<=0:raise ValueError("Split amounts must be positive")
        if not session.get(Category,item["category_id"]):raise ValueError("Category not found")
    session.execute(delete(TransactionSplit).where(TransactionSplit.transaction_id==transaction_id))
    rows=[TransactionSplit(transaction_id=transaction_id,amount=Decimal(str(x["amount"])),category_id=x["category_id"],note=x.get("note")) for x in splits]
    session.add_all(rows);session.flush();return rows


def detect_refunds(session:Session,lookback_days:int=90)->int:
    positives=session.scalars(select(Transaction).where(Transaction.amount>0,Transaction.is_internal_transfer.is_(False)).order_by(Transaction.booking_date)).all()
    negatives=session.scalars(select(Transaction).where(Transaction.amount<0,Transaction.is_internal_transfer.is_(False)).order_by(Transaction.booking_date)).all()
    created=0
    for refund in positives:
        if not refund.merchant_normalized:
            continue
        existing=session.scalar(select(EntityLink.id).where(EntityLink.from_type=="transaction",EntityLink.from_id==refund.id,EntityLink.relation_type=="refund_of"))
        if existing:
            continue
        matches=[
            expense for expense in negatives
            if expense.merchant_normalized==refund.merchant_normalized
            and expense.booking_date<=refund.booking_date
            and (refund.booking_date-expense.booking_date).days<=lookback_days
            and abs((-expense.amount)-refund.amount)<=Decimal("0.01")
        ]
        if not matches:
            continue
        expense=max(matches,key=lambda x:x.booking_date)
        session.add(EntityLink(from_type="transaction",from_id=refund.id,relation_type="refund_of",to_type="transaction",to_id=expense.id,confidence=Decimal("0.98"),source_type="deterministic_refund_match",source_ref=expense.id))
        refund.category_id=expense.category_id
        refund.categorization_method="refund_match"
        refund.categorization_confidence=Decimal("0.98")
        created+=1
    session.flush()
    return created
