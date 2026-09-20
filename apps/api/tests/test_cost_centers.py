from datetime import date
from decimal import Decimal
from uuid import uuid4

from financito.db import SessionLocal
from financito.models import Account, Category, Transaction
from financito.models_extended import CostCenter, CostCenterLink
from financito.routes_domain import cost_center_summary
from financito.services.imports import import_csv


def test_cost_center_category_link_sums_last_twelve_months():
    with SessionLocal() as db:
        suffix=uuid4().hex[:8]
        account=Account(name=f"Cost center {suffix}")
        category=Category(name=f"Proyecto {suffix}",system_key=f"project_{suffix}")
        center=CostCenter(name=f"Proyecto {suffix}",center_type="life_area",metadata_json="{}")
        db.add_all([account,category,center]);db.flush()

        today=date.today()
        day=today.strftime("%d/%m/%Y")
        content=(
            "Fecha;Concepto;Importe;Moneda;Comercio;Referencia\n"
            f"{day};COSTE PROYECTO;-123,45;EUR;PROYECTO;{suffix}\n"
        ).encode()
        import_csv(db,account.id,content,"project.csv")
        tx=db.query(Transaction).filter(Transaction.account_id==account.id).one()
        tx.category_id=category.id
        tx.categorization_method="manual"
        tx.user_verified=True
        db.add(CostCenterLink(
            cost_center_id=center.id,
            entity_type="category",
            entity_id=category.id,
            allocation_percentage=Decimal("100"),
        ))
        db.flush()

        summary=cost_center_summary(center.id,db)
        assert Decimal(summary["observed_linked_spend"])==Decimal("123.45")
        assert Decimal(summary["monthly_average_spend"])==Decimal("10.29")
