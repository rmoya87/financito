from datetime import date
from decimal import Decimal
from sqlalchemy import select

from financito.db import SessionLocal
from financito.models import Account,Transaction
from financito.models_analytics import BankingAccountLink,BankingConnection
from financito.services.banking import complete_authorization,sync_connection,close_connection

class FakeProvider:
    def __init__(self):
        self.closed=False
    def authorize_session(self,code):
        assert code=="ok"
        return {
            "session_id":"session-demo",
            "aspsp":{"name":"Banco Demo","country":"ES"},
            "psu_type":"personal",
            "access":{"valid_until":"2026-10-20T12:00:00+00:00"},
            "accounts":[{
                "uid":"provider-account-1",
                "identification_hash":"stable-account-hash",
                "identification_hashes":["stable-account-hash"],
                "name":"Cuenta principal",
                "currency":"EUR",
                "cash_account_type":"CACC",
                "account_id":{"iban":"ES0012345678901234567890"},
            }],
        }
    def session(self,session_id):
        return {
            "status":"AUTHORIZED",
            "access":{"valid_until":"2026-10-20T12:00:00+00:00"},
            "accounts":["provider-account-1"],
            "accounts_data":[{"uid":"provider-account-1","identification_hash":"stable-account-hash"}],
            "aspsp":{"name":"Banco Demo","country":"ES"},
        }
    def account_details(self,uid):
        return {"uid":uid,"name":"Cuenta principal","currency":"EUR","cash_account_type":"CACC","account_id":{"iban":"ES0012345678901234567890"}}
    def balances(self,uid):
        return {"balances":[{"balance_type":"CLAV","balance_amount":{"amount":"1250.50","currency":"EUR"}}]}
    def transactions(self,uid,date_from=None,date_to=None,continuation_key=None):
        if continuation_key=="next":
            return {"transactions":[{
                "entry_reference":"tx-2","status":"BOOK","booking_date":"2026-09-19","transaction_amount":{"amount":"50.00","currency":"EUR"},
                "credit_debit_indicator":"CRDT","debtor":{"name":"Empresa Demo"},"remittance_information":["Ingreso demo"],
            }],"continuation_key":None}
        return {"transactions":[{
            "entry_reference":"tx-1","status":"BOOK","booking_date":"2026-09-18","value_date":"2026-09-18",
            "transaction_amount":{"amount":"25.30","currency":"EUR"},"credit_debit_indicator":"DBIT",
            "creditor":{"name":"Comercio Demo"},"remittance_information":["Compra demo"],
        }],"continuation_key":"next"}
    def close_session(self,session_id):
        self.closed=True
        return {"message":"OK"}

def test_banking_authorize_sync_deduplicate_and_close():
    provider=FakeProvider()
    with SessionLocal() as db:
        result=complete_authorization(db,"ok",provider)
        db.commit()
        connection_id=result["connection_id"]
        assert result["bank_name"]=="Banco Demo"
        link=db.scalar(select(BankingAccountLink).where(BankingAccountLink.connection_id==connection_id))
        assert link is not None
        account=db.get(Account,link.local_account_id)
        assert account is not None
        assert account.iban_masked=="ES00…7890"

        first=sync_connection(db,connection_id,provider)
        db.commit()
        assert first["inserted"]==2
        assert isinstance(first["transfer_pairs"],int) and first["transfer_pairs"]>=0
        assert isinstance(first["refunds"],int) and first["refunds"]>=0
        db.refresh(account)
        assert account.current_balance==Decimal("1250.5000")
        txs=db.scalars(select(Transaction).where(Transaction.account_id==account.id).order_by(Transaction.booking_date)).all()
        assert [t.amount for t in txs]==[Decimal("-25.3000"),Decimal("50.0000")]
        assert txs[0].merchant_raw=="Comercio Demo"

        second=sync_connection(db,connection_id,provider)
        db.commit()
        assert second["inserted"]==0
        assert second["skipped"]==2

        closed=close_connection(db,connection_id,provider)
        db.commit()
        assert closed["status"]=="closed"
        assert provider.closed is True
        row=db.get(BankingConnection,connection_id)
        assert row.status=="closed"
        db.refresh(account)
        assert account.sync_status=="disconnected"
