from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime,timezone
from decimal import Decimal
from hashlib import sha256
from io import StringIO

from sqlalchemy import func,select
from sqlalchemy.orm import Session

from ..models import Portfolio,Security
from ..models_extended import Trade
from ..domain.portfolio import apply_trade

ALIASES={
    "date":("date","fecha","executed_at","datetime","timestamp"),
    "side":("side","type","operacion","operación","accion","acción"),
    "symbol":("symbol","ticker","símbolo","simbolo"),
    "name":("name","nombre","security","instrument"),
    "asset_class":("asset_class","clase","tipo_activo"),
    "quantity":("quantity","cantidad","qty","shares","participaciones"),
    "price":("price","precio","unit_price"),
    "fees":("fees","fee","comision","comisión","commissions"),
    "currency":("currency","divisa","moneda"),
    "fx_rate":("fx_rate","fx","tipo_cambio"),
}
BUY={"buy","compra","comprar","b"}
SELL={"sell","venta","vender","s"}

def _key(row:dict,name:str)->str|None:
    lowered={str(k).strip().lower():v for k,v in row.items()}
    for alias in ALIASES[name]:
        if alias in lowered and lowered[alias] not in (None,""):return str(lowered[alias]).strip()
    return None

def _decimal(value:str|None,default:str="0")->Decimal:
    raw=(value or default).replace(" ","")
    if "," in raw and "." not in raw:raw=raw.replace(",",".")
    elif "," in raw and "." in raw:
        if raw.rfind(",")>raw.rfind("."):raw=raw.replace(".","").replace(",",".")
        else:raw=raw.replace(",","")
    return Decimal(raw)

def _datetime(value:str)->datetime:
    raw=value.strip().replace("Z","+00:00")
    try:
        d=datetime.fromisoformat(raw)
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except ValueError:
        for fmt in ("%d/%m/%Y","%d-%m-%Y","%Y/%m/%d"):
            try:return datetime.strptime(raw,fmt).replace(tzinfo=timezone.utc)
            except ValueError:pass
    raise ValueError("Unsupported trade date: "+value)

def import_broker_csv(session:Session,portfolio_id:str,content:bytes,file_name:str)->dict:
    if not session.get(Portfolio,portfolio_id):raise ValueError("Portfolio not found")
    text=content.decode("utf-8-sig",errors="replace")
    sample=text[:8192]
    try:delimiter=csv.Sniffer().sniff(sample,delimiters=",;\t").delimiter
    except csv.Error:delimiter=","
    reader=csv.DictReader(StringIO(text),delimiter=delimiter)
    parsed=[]
    for index,row in enumerate(reader,start=2):
        date_raw=_key(row,"date");side_raw=(_key(row,"side") or "").lower();symbol=(_key(row,"symbol") or "").upper()
        if not date_raw or not symbol or side_raw not in BUY|SELL:raise ValueError(f"Invalid broker row {index}: date, side and symbol are required")
        side="buy" if side_raw in BUY else "sell"
        quantity=_decimal(_key(row,"quantity"));price=_decimal(_key(row,"price"))
        if quantity<=0 or price<=0:raise ValueError(f"Invalid broker row {index}: quantity and price must be positive")
        executed=_datetime(date_raw)
        fees=_decimal(_key(row,"fees"),"0");fx=_decimal(_key(row,"fx_rate"),"1")
        currency=(_key(row,"currency") or "EUR").upper()
        name=_key(row,"name") or symbol;asset_class=(_key(row,"asset_class") or "stock").lower()
        canonical="|".join([portfolio_id,executed.isoformat(),side,symbol,str(quantity),str(price),str(fees),currency,str(fx)])
        parsed.append((executed,index,{"side":side,"symbol":symbol,"name":name,"asset_class":asset_class,"quantity":quantity,"price":price,"fees":fees,"currency":currency,"fx_rate":fx,"source_ref":sha256(canonical.encode()).hexdigest()}))
    parsed.sort(key=lambda x:(x[0],x[1]))
    inserted=skipped=created_securities=0
    realized=Decimal("0")
    for executed,index,data in parsed:
        if session.scalar(select(Trade.id).where(Trade.portfolio_id==portfolio_id,Trade.source_type=="broker_csv",Trade.source_ref==data["source_ref"])):
            skipped+=1;continue
        security=session.scalar(select(Security).where(func.upper(Security.symbol)==data["symbol"]))
        if security is None:
            security=Security(asset_class=data["asset_class"],name=data["name"],symbol=data["symbol"],currency=data["currency"])
            session.add(security);session.flush();created_securities+=1
        trade=Trade(portfolio_id=portfolio_id,security_id=security.id,side=data["side"],quantity=data["quantity"],price=data["price"],fees=data["fees"],currency=data["currency"],fx_rate=data["fx_rate"],executed_at=executed,source_type="broker_csv",source_ref=data["source_ref"])
        session.add(trade);session.flush()
        try:result=apply_trade(session,trade)
        except ValueError as exc:raise ValueError(f"Broker row {index}: {exc}") from exc
        realized+=Decimal(result["realized_pnl"]);inserted+=1
    session.flush()
    return {"file_name":file_name,"inserted":inserted,"skipped":skipped,"created_securities":created_securities,"realized_pnl":str(realized)}
