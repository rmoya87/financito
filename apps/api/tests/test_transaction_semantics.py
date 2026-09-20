from datetime import date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select

from financito.db import SessionLocal
from financito.models import Account, Transaction
from financito.models_analytics import TransactionRule
from financito.services.categorization import ensure_categories
from financito.services.financial_analytics import cash_flow
from financito.services.month_end import month_end_projection
from financito.services.tax import estimate as tax_estimate
from financito.services.imports import import_csv
from financito.services.transaction_ops import (
    apply_category_semantics,
    apply_rules_to_unverified,
    detect_internal_transfers,
    pair_internal_transfer_counterpart,
    set_category_for_same_concept,
    synchronize_transaction_semantics,
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


def test_positive_salary_counts_as_income_even_if_legacy_transfer_flag_is_stale():
    with SessionLocal() as db:
        account=_account(db)
        import_csv(db,account.id,_csv("04/01/2040","NOMINA EMPRESA","2500,00","EMPRESA"),"salary.csv")
        categories=ensure_categories(db)
        tx=db.scalar(select(Transaction).where(Transaction.account_id==account.id,Transaction.booking_date==date(2040,1,4)))
        tx.category_id=categories["salary"].id
        tx.categorization_method="learned_merchant"
        tx.is_internal_transfer=True  # simula dato antiguo incoherente
        db.flush()

        flow=cash_flow(db,date(2040,1,4),date(2040,1,4))
        assert flow["income"]==Decimal("2500.00")
        assert flow["expenses"]==Decimal("0.00")
        assert flow["savings"]==Decimal("2500.00")


def test_semantics_repair_clears_stale_transfer_flag_from_salary():
    with SessionLocal() as db:
        account=_account(db)
        import_csv(db,account.id,_csv("05/01/2040","NOMINA EMPRESA","2200,00","EMPRESA"),"salary-repair.csv")
        categories=ensure_categories(db)
        tx=db.scalar(select(Transaction).where(Transaction.account_id==account.id,Transaction.booking_date==date(2040,1,5)))
        tx.category_id=categories["salary"].id
        tx.is_internal_transfer=True
        db.flush()

        assert synchronize_transaction_semantics(db)>=1
        assert tx.is_internal_transfer is False


def test_transfer_detector_does_not_reclassify_salary_pair():
    with SessionLocal() as db:
        salary_account=_account(db);other_account=_account(db)
        import_csv(db,salary_account.id,_csv("06/01/2040","NOMINA EMPRESA","2000,00","EMPRESA"),"salary-protected.csv")
        import_csv(db,other_account.id,_csv("06/01/2040","PAGO EXTRAORDINARIO","-2000,00","OTRO"),"expense-same-amount.csv")
        categories=ensure_categories(db)
        salary=db.scalar(select(Transaction).where(Transaction.account_id==salary_account.id))
        salary.category_id=categories["salary"].id
        salary.categorization_method="deterministic_classifier"
        salary.is_internal_transfer=False
        db.flush()

        assert detect_internal_transfers(db)==0
        assert salary.category_id==categories["salary"].id
        assert salary.is_internal_transfer is False
        flow=cash_flow(db,date(2040,1,6),date(2040,1,6))
        assert flow["income"]==Decimal("2000.00")


def test_salary_semantics_are_consistent_in_month_end_and_tax():
    with SessionLocal() as db:
        account=_account(db)
        import_csv(db,account.id,_csv("07/01/2040","NOMINA EMPRESA","1800,00","EMPRESA"),"salary-cross-sections.csv")
        categories=ensure_categories(db)
        tx=db.scalar(select(Transaction).where(Transaction.account_id==account.id,Transaction.booking_date==date(2040,1,7)))
        tx.category_id=categories["salary"].id
        tx.is_internal_transfer=True
        db.flush()

        closing=month_end_projection(db,date(2040,1,15))
        assert Decimal(closing["actual_to_date"]["income"])==Decimal("1800.00")

        tax=tax_estimate(db,"ES",2040)
        assert Decimal(tax["known_information"]["employment_income"])==Decimal("1800.00")
        assert tax["known_information"]["employment_income_source"]=="nóminas categorizadas"


def test_manual_internal_transfer_category_pairs_the_opposite_account_movement():
    with SessionLocal() as db:
        source=_account(db);target=_account(db)
        import_csv(db,source.id,_csv("08/01/2040","TRASPASO A AHORRO","-500,00","BANCO"),"transfer-out.csv")
        import_csv(db,target.id,_csv("08/01/2040","ABONO ENTRE CUENTAS","500,00","BANCO"),"transfer-in.csv")
        categories=ensure_categories(db)
        outgoing=db.scalar(select(Transaction).where(Transaction.account_id==source.id))
        incoming=db.scalar(select(Transaction).where(Transaction.account_id==target.id))

        outgoing.category_id=categories["internal_transfer"].id
        outgoing.categorization_method="manual"
        outgoing.user_verified=True
        assert apply_category_semantics(db,outgoing)=="internal_transfer"
        assert pair_internal_transfer_counterpart(db,outgoing)==incoming.id
        db.flush()

        assert outgoing.is_internal_transfer is True
        assert incoming.is_internal_transfer is True
        assert incoming.category_id==categories["internal_transfer"].id
        flow=cash_flow(db,date(2040,1,8),date(2040,1,8))
        assert flow["income"]==Decimal("0.00")
        assert flow["expenses"]==Decimal("0.00")
        assert flow["savings"]==Decimal("0.00")


def test_category_change_applies_to_same_concept_past_and_future():
    with SessionLocal() as db:
        account=_account(db)
        import_csv(db,account.id,_csv("09/01/2040","CUOTA CLUB MISMO CONCEPTO","-30,00","CLUB A"),"concept-a.csv")
        import_csv(db,account.id,_csv("10/01/2040","CUOTA CLUB MISMO CONCEPTO","-35,00","CLUB B"),"concept-b.csv")
        categories=ensure_categories(db)
        rows=db.scalars(select(Transaction).where(
            Transaction.account_id==account.id,
            Transaction.description_normalized=="cuota club mismo concepto",
        ).order_by(Transaction.booking_date)).all()
        assert len(rows)==2

        changed=set_category_for_same_concept(db,rows[0],categories["sports"].id)
        db.flush()
        assert changed>=1
        assert all(row.category_id==categories["sports"].id for row in rows)
        assert all(row.user_verified for row in rows)
        rule=db.scalar(select(TransactionRule).where(
            TransactionRule.matcher_type=="description_exact",
            TransactionRule.matcher_value=="cuota club mismo concepto",
        ))
        assert rule is not None
        assert rule.category_id==categories["sports"].id

        import_csv(db,account.id,_csv("11/01/2040","CUOTA CLUB MISMO CONCEPTO","-40,00","CLUB C"),"concept-future.csv")
        future=db.scalar(select(Transaction).where(
            Transaction.account_id==account.id,
            Transaction.booking_date==date(2040,1,11),
        ))
        assert future.category_id==categories["sports"].id
        assert future.categorization_method=="rule"
