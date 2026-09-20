from datetime import date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select

from financito.db import SessionLocal
from financito.models import Account, Transaction
from financito.models_analytics import TransactionRule
from financito.services.categorization import ensure_categories
from financito.services.financial_analytics import cash_flow
from financito.services.imports import import_csv
from financito.services.transaction_ops import (
    apply_category_semantics,
    apply_rules_to_unverified,
    detect_internal_transfers,
)


def _account(db):
    row=Account(name=f"Semantics {uuid4().hex[:8]}")
    db.add(row);db.flush()
    return row


def _csv(day:str,concept:str,amount:str,merchant:str)->bytes:
    return (
        "Fecha;Concepto;Importe;Moneda;Comercio;Referencia\n"
        f"{day};{concept};{amount};EUR;{merchant};{uuid4().hex}\n"
    ).encode()


def test_refund_category_reduces_expense_instead_of_counting_as_income():
    with SessionLocal() as db:
        account=_account(db)
        import_csv(db,account.id,_csv("01/01/2040","COMPRA TEST","-100,00","TIENDA TEST"),"expense.csv")
        import_csv(db,account.id,_csv("01/01/2040","ABONO TEST","40,00","OTRO TEST"),"refund.csv")
        categories=ensure_categories(db)
        refund=db.scalar(
            select(Transaction).where(
                Transaction.account_id==account.id,
                Transaction.amount>0,
            )
        )
        refund.category_id=categories["refunds"].id
        refund.categorization_method="manual"
        refund.user_verified=True
        apply_category_semantics(db,refund)
        db.flush()

        flow=cash_flow(db,date(2040,1,1),date(2040,1,1))
        assert flow["income"]==Decimal("0.00")
        assert flow["expenses"]==Decimal("60.00")
        assert flow["savings"]==Decimal("-60.00")


def test_internal_transfer_pair_is_excluded_from_income_and_expense():
    with SessionLocal() as db:
        left=_account(db);right=_account(db)
        import_csv(db,left.id,_csv("02/01/2040","TRASPASO PROPIO","-75,00","CUENTA PROPIA"),"left.csv")
        import_csv(db,right.id,_csv("02/01/2040","TRASPASO PROPIO","75,00","CUENTA PROPIA"),"right.csv")
        assert detect_internal_transfers(db)==1
        db.flush()
        rows=db.query(Transaction).filter(Transaction.account_id.in_([left.id,right.id])).all()
        assert all(row.is_internal_transfer for row in rows)
        flow=cash_flow(db,date(2040,1,2),date(2040,1,2))
        assert flow["income"]==Decimal("0.00")
        assert flow["expenses"]==Decimal("0.00")


def test_rule_targeting_internal_transfer_uses_special_accounting_semantics():
    with SessionLocal() as db:
        account=_account(db)
        import_csv(db,account.id,_csv("03/01/2040","MOVIMIENTO AHORRO CASA","-25,00","BANCO"),"rule.csv")
        categories=ensure_categories(db)
        db.add(TransactionRule(
            priority=1,
            matcher_type="contains",
            matcher_value="movimiento ahorro casa",
            category_id=categories["internal_transfer"].id,
            enabled=True,
        ))
        db.flush()
        assert apply_rules_to_unverified(db)>=1
        tx=db.scalar(
            select(Transaction).where(
                Transaction.account_id==account.id,
                Transaction.booking_date==date(2040,1,3),
            )
        )
        assert tx.is_internal_transfer is True
        flow=cash_flow(db,date(2040,1,3),date(2040,1,3))
        assert flow["expenses"]==Decimal("0.00")
