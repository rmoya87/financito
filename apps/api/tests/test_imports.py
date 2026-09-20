from decimal import Decimal
from uuid import uuid4

from financito.db import SessionLocal
from financito.models import Account, Transaction
from financito.services.imports import import_csv, parse_decimal, parse_date
from financito.services.import_formats import import_statement


def test_spanish_decimal():
    assert parse_decimal("1.234,56 €")==Decimal("1234.56")


def test_spanish_date():
    assert parse_date("20/09/2026").isoformat()=="2026-09-20"


def _account(db):
    row=Account(name=f"Import {uuid4().hex[:8]}")
    db.add(row);db.flush()
    return row


def _csv(rows:list[str])->bytes:
    return ("Fecha;Concepto;Importe;Moneda;Comercio;Referencia\n"+"\n".join(rows)+"\n").encode()


def test_overlapping_month_import_only_adds_new_transactions():
    with SessionLocal() as db:
        account=_account(db)
        first=_csv([
            "01/09/2026;SUPERMERCADO A;-10,00;EUR;SUPERMERCADO;",
            "02/09/2026;CAFETERIA B;-5,00;EUR;CAFETERIA;",
        ])
        second=_csv([
            "02/09/2026;CAFETERIA B;-5,00;EUR;CAFETERIA;",
            "03/09/2026;GASOLINERA C;-40,00;EUR;GASOLINERA;",
        ])
        r1=import_csv(db,account.id,first,"septiembre-parcial.csv")
        db.commit()
        r2=import_csv(db,account.id,second,"septiembre-completo.csv")
        db.commit()
        assert r1.inserted==2
        assert r2.inserted==1
        assert r2.duplicates==1
        assert r2.duplicates_exact==1
        assert db.query(Transaction).filter(Transaction.account_id==account.id).count()==3


def test_changed_bank_description_is_deduplicated_tolerantly():
    with SessionLocal() as db:
        account=_account(db)
        original=_csv([
            "10/09/2026;MERCADONA 1234;-42,50;EUR;MERCADONA;",
        ])
        changed=_csv([
            "10/09/2026;COMPRA TARJETA MERCADONA TERMINAL 9988;-42,50;EUR;MERCADONA;",
        ])
        assert import_csv(db,account.id,original,"extracto-a.csv").inserted==1
        db.commit()
        result=import_csv(db,account.id,changed,"extracto-b.csv")
        db.commit()
        assert result.inserted==0
        assert result.duplicates==1
        assert result.duplicates_similar==1
        assert db.query(Transaction).filter(Transaction.account_id==account.id).count()==1


def test_external_bank_reference_wins_even_if_text_or_date_changes():
    with SessionLocal() as db:
        account=_account(db)
        first=_csv([
            "11/09/2026;COMPRA COMERCIO;-19,95;EUR;COMERCIO;ABC-123456",
        ])
        second=_csv([
            "12/09/2026;PAGO TARJETA COMERCIO CENTRAL;-19,95;EUR;COMERCIO;ABC-123456",
        ])
        assert import_csv(db,account.id,first,"a.csv").inserted==1
        db.commit()
        result=import_csv(db,account.id,second,"b.csv")
        db.commit()
        assert result.inserted==0
        assert result.duplicates_reference==1
        assert db.query(Transaction).filter(Transaction.account_id==account.id).count()==1


def test_identical_real_transactions_in_same_file_are_preserved_as_a_multiset():
    with SessionLocal() as db:
        account=_account(db)
        content=_csv([
            "15/09/2026;PARKING;-3,50;EUR;PARKING;",
            "15/09/2026;PARKING;-3,50;EUR;PARKING;",
        ])
        first=import_csv(db,account.id,content,"parking.csv")
        db.commit()
        second=import_csv(db,account.id,content,"parking.csv")
        db.commit()
        assert first.inserted==2
        assert first.duplicates==0
        assert second.inserted==0
        assert second.duplicates==2
        assert db.query(Transaction).filter(Transaction.account_id==account.id).count()==2


def test_same_amount_and_merchant_are_not_enough_to_drop_a_distinct_purchase():
    with SessionLocal() as db:
        account=_account(db)
        first=_csv([
            "18/09/2026;CAFETERIA DESAYUNO;-4,50;EUR;CAFETERIA;",
        ])
        distinct=_csv([
            "18/09/2026;CAFETERIA MERIENDA;-4,50;EUR;CAFETERIA;",
        ])
        assert import_csv(db,account.id,first,"morning.csv").inserted==1
        db.commit()
        result=import_csv(db,account.id,distinct,"afternoon.csv")
        db.commit()
        assert result.inserted==1
        assert result.duplicates==0
        assert db.query(Transaction).filter(Transaction.account_id==account.id).count()==2


def test_ofx_fitid_prevents_duplicate_across_changed_exports():
    with SessionLocal() as db:
        account=_account(db)
        first=b"""<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS><BANKTRANLIST>
<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20260919120000<TRNAMT>-25.00<FITID>FIT-999<MEMO>COMPRA ORIGINAL<NAME>TIENDA</STMTTRN>
</BANKTRANLIST></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>"""
        second=b"""<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS><BANKTRANLIST>
<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20260920120000<TRNAMT>-25.00<FITID>FIT-999<MEMO>PAGO TARJETA TIENDA<NAME>TIENDA CENTRAL</STMTTRN>
</BANKTRANLIST></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>"""
        r1=import_statement(db,account.id,"a.ofx",first)
        db.commit()
        r2=import_statement(db,account.id,"b.ofx",second)
        db.commit()
        assert r1.inserted==1
        assert r2.inserted==0
        assert r2.duplicates_reference==1
