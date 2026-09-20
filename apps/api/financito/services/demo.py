from __future__ import annotations
from datetime import date,timedelta
from decimal import Decimal
from hashlib import sha256
from sqlalchemy import func,select
from sqlalchemy.orm import Session
from ..models import Account,Transaction
from .categorization import categorize_transaction
def seed(session:Session)->dict:
    if (session.scalar(select(func.count()).select_from(Account)) or 0)>0:raise ValueError("Demo mode can only seed an empty database")
    a=Account(name="Cuenta demo",institution_name="Banco ficticio",current_balance=Decimal("6200"),source="demo",sync_status="demo");session.add(a);session.flush()
    today=date.today();samples=[("Nómina Empresa Demo",Decimal("3200")),("Mercadona Demo",Decimal("-410.25")),("Hipoteca Demo",Decimal("-850")),("Iberdrola Demo",Decimal("-82.40")),("Restaurante Demo",Decimal("-65.30")),("Seguro Hogar Demo",Decimal("-39.90")),("Spotify Demo",Decimal("-10.99"))]
    for months in range(4):
        base=today-timedelta(days=30*months)
        for i,(desc,amount) in enumerate(samples):
            d=base-timedelta(days=i*2);fp=sha256((str(d)+desc+str(amount)).encode()).hexdigest();t=Transaction(account_id=a.id,booking_date=d,amount=amount,currency="EUR",base_amount=amount,base_currency="EUR",description_raw=desc,description_normalized=desc.lower(),merchant_raw=desc,merchant_normalized=desc.lower(),duplicate_fingerprint=fp,source="demo");categorize_transaction(session,t);session.add(t)
    return {"account_id":a.id,"transactions":len(samples)*4,"demo":True}
