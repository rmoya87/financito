from datetime import datetime
from decimal import Decimal
from io import BytesIO

from openpyxl import Workbook
from sqlalchemy import select

from financito.db import SessionLocal
from financito.models import Account,Transaction
from financito.services.import_formats import import_statement
from financito.services.imports import parse_date


def _revolut_xlsx(headers,rows)->bytes:
    wb=Workbook()
    ws=wb.active
    ws.append(headers)
    for row in rows:
        ws.append(row)
    out=BytesIO()
    wb.save(out)
    return out.getvalue()


def test_parse_date_accepts_revolut_datetime():
    assert parse_date("2026-09-20 14:31:22").isoformat()=="2026-09-20"
    assert parse_date("2026-09-20T14:31:22+02:00").isoformat()=="2026-09-20"


def test_revolut_xlsx_imports_completed_and_ignores_reverted():
    content=_revolut_xlsx(
        ["Type","Product","Started Date","Completed Date","Description","Amount","Fee","Currency","State","Balance"],
        [
            ["CARD_PAYMENT","Current","2026-09-20 09:00:00","2026-09-20 09:01:00","Mercadona",-45.90,0,"EUR","COMPLETED",1000],
            ["CARD_PAYMENT","Current","2026-09-20 10:00:00","2026-09-20 10:01:00","Reserva revertida",-20,0,"EUR","REVERTED",1000],
        ],
    )
    with SessionLocal() as db:
        account=Account(name="Revolut import",institution_name="Revolut",current_balance=Decimal("0"))
        db.add(account);db.flush()
        result=import_statement(db,account.id,"revolut.xlsx",content)
        assert result.inserted==1
        assert result.ignored==1
        assert result.rejected==0
        tx=db.scalar(select(Transaction).where(Transaction.account_id==account.id))
        assert tx is not None
        assert tx.booking_date.isoformat()=="2026-09-20"
        assert tx.amount==Decimal("-45.90")
        assert tx.currency=="EUR"
        assert tx.description_raw=="Mercadona"


def test_revolut_xlsx_supports_spanish_headers_and_excel_datetime_cells():
    content=_revolut_xlsx(
        ["Tipo","Producto","Fecha de inicio","Fecha de finalización","Descripción","Importe","Comisión","Moneda","Estado","Saldo"],
        [["TRANSFER","Current",datetime(2026,9,18,8,0),datetime(2026,9,18,8,3),"Nómina",2500,0,"EUR","COMPLETED",3500]],
    )
    with SessionLocal() as db:
        account=Account(name="Revolut ES",institution_name="Revolut",current_balance=Decimal("0"))
        db.add(account);db.flush()
        result=import_statement(db,account.id,"revolut-es.xlsx",content)
        assert result.inserted==1
        assert result.rejected==0
        tx=db.scalar(select(Transaction).where(Transaction.account_id==account.id))
        assert tx is not None
        assert tx.booking_date.isoformat()=="2026-09-18"
        assert tx.amount==Decimal("2500")
