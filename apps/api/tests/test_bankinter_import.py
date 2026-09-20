from io import BytesIO
from datetime import date
from decimal import Decimal

from openpyxl import Workbook
from sqlalchemy import select

from financito.db import SessionLocal
from financito.models import Account, Transaction
from financito.services.import_formats import import_statement
from financito.services.financial_analytics import cash_flow


def _bankinter_xlsx()->bytes:
    wb=Workbook()
    ws=wb.active
    ws.title="Movimientos"
    ws.append(["MOVIMIENTOS DE LA CUENTA ES00TEST"])
    ws.append([])
    ws.append(["MOVIMIENTOS PENDIENTES -90,09 EUR"])
    ws.append([])
    ws.append(["Fecha","Descripción","Importe","Divisa"])
    ws.append(["21/09/2026","PENDIENTE COMERCIO A",-13,"EUR"])
    ws.append(["21/09/2026","PENDIENTE COMERCIO B",-5.10,"EUR"])
    ws.append([])
    ws.append(["MOVIMIENTOS"])
    ws.append(["Concepto","-"])
    ws.append(["Fecha","20/03/2026 - 20/09/2026"])
    ws.append(["Tipo de movimiento","-"])
    ws.append(["Importe","Desde 0,00 hasta -"])
    ws.append([])
    ws.append(["Fecha contable","Fecha valor","Descripción","Importe","Saldo","Divisa"])
    ws.append(["21/09/2026","19/09/2026","PAGO BIZUM DE PERSONA",11,42124.35,"EUR"])
    ws.append(["17/09/2026","16/09/2026","MERCADONA",-114.26,42124.14,"EUR"])
    ws.append(["17/09/2026","17/09/2026","RECIBO AGUA",-21.70,42238.40,"EUR"])
    out=BytesIO()
    wb.save(out)
    return out.getvalue()


def test_bankinter_xlsx_uses_booked_ledger_not_pending_section():
    with SessionLocal() as db:
        account=Account(name="Bankinter XLSX",institution_name="Bankinter",current_balance=Decimal("0"))
        db.add(account);db.flush()
        result=import_statement(db,account.id,"Movimientos de la cuenta.xlsx",_bankinter_xlsx())
        db.commit()

        assert result.inserted==3
        assert result.rejected==0
        assert result.detected_inflows==1
        assert result.detected_outflows==2
        assert result.detected_inflow_amount=="11.00"
        assert result.detected_outflow_amount=="135.96"
        rows=db.scalars(select(Transaction).where(Transaction.account_id==account.id).order_by(Transaction.booking_date.desc(),Transaction.amount.desc())).all()
        assert len(rows)==3
        assert {row.description_raw for row in rows}=={"PAGO BIZUM DE PERSONA","MERCADONA","RECIBO AGUA"}
        assert all("PENDIENTE" not in row.description_raw for row in rows)
        assert all(row.currency=="EUR" for row in rows)
        bizum=next(row for row in rows if row.description_raw=="PAGO BIZUM DE PERSONA")
        assert bizum.booking_date.isoformat()=="2026-09-19"
        assert bizum.amount==Decimal("11")
        flow=cash_flow(db,date(2026,9,14),date(2026,9,19))
        assert flow["income"]==Decimal("11.00")
        assert flow["expenses"]==Decimal("135.96")
        assert flow["savings"]==Decimal("-124.96")


def test_bankinter_xlsx_reimport_is_idempotent():
    content=_bankinter_xlsx()
    with SessionLocal() as db:
        account=Account(name="Bankinter repeat",institution_name="Bankinter",current_balance=Decimal("0"))
        db.add(account);db.flush()
        first=import_statement(db,account.id,"bankinter-1.xlsx",content)
        db.commit()
        second=import_statement(db,account.id,"bankinter-2.xlsx",content)
        db.commit()
        assert first.inserted==3
        assert second.inserted==0
        assert second.duplicates==3
        assert db.query(Transaction).filter(Transaction.account_id==account.id).count()==3



def test_bankinter_pending_only_xlsx_is_not_imported_as_booked():
    wb=Workbook()
    ws=wb.active
    ws.title="Movimientos"
    ws.append(["MOVIMIENTOS DE LA CUENTA ES00TEST"])
    ws.append([])
    ws.append(["MOVIMIENTOS PENDIENTES -18,10 EUR"])
    ws.append([])
    ws.append(["Fecha","Descripción","Importe","Divisa"])
    ws.append(["21/09/2026","PENDIENTE COMERCIO A",-13,"EUR"])
    ws.append(["21/09/2026","PENDIENTE COMERCIO B",-5.10,"EUR"])
    out=BytesIO();wb.save(out)

    with SessionLocal() as db:
        account=Account(name="Bankinter pending",institution_name="Bankinter",current_balance=Decimal("0"))
        db.add(account);db.flush()
        result=import_statement(db,account.id,"bankinter-pendientes.xlsx",out.getvalue())
        db.commit()
        assert result.inserted==0
        assert result.rejected==0
        assert db.query(Transaction).filter(Transaction.account_id==account.id).count()==0
