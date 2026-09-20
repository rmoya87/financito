from __future__ import annotations
import csv,re
from datetime import date,datetime
from io import BytesIO,StringIO
from pathlib import Path
from defusedxml import ElementTree as ET
from openpyxl import load_workbook
from sqlalchemy.orm import Session
from .imports import canonical_key,import_csv

NORMALIZED_FIELDS=["Fecha","Concepto","Importe","Moneda","Comercio","Estado","Referencia"]

def _csv_bytes(rows:list[dict])->bytes:
    if not rows:return b""
    out=StringIO();w=csv.DictWriter(out,fieldnames=NORMALIZED_FIELDS,delimiter=";");w.writeheader()
    for r in rows:w.writerow({k:r.get(k,"") for k in NORMALIZED_FIELDS})
    return out.getvalue().encode()

def _cell_date(value)->str:
    if isinstance(value,datetime):return value.date().isoformat()
    if isinstance(value,date):return value.isoformat()
    return str(value or "").strip()

_XLSX_DATE_FIELDS={
    "completeddate","transactioncompleted","transactioncompletedutc",
    "fechadefinalizacion","fechadecompletado","fechacompletada",
    "fecha","date","bookingdate","fechacontable",
    "starteddate","transactionstarted","transactionstartedutc","fechadeinicio",
}
_XLSX_AMOUNT_FIELDS={"amount","amountpaymentcurrency","importe","cantidad"}
_XLSX_DESCRIPTION_FIELDS={"description","transactiondescription","descripcion","descripciondelatransaccion","concepto","detalle"}
_XLSX_CURRENCY_FIELDS={"currency","paymentcurrency","moneda","divisa"}

def _xlsx_header_score(values:tuple|list)->int:
    canonical=[canonical_key(str(x or "").strip()) for x in values]
    keys={x for x in canonical if x}
    if not (keys&_XLSX_DATE_FIELDS and keys&_XLSX_AMOUNT_FIELDS and keys&_XLSX_DESCRIPTION_FIELDS):
        return -1
    score=9
    # Prefer the booked/settled transaction table over summary or pending
    # sections. Bankinter exports both "MOVIMIENTOS PENDIENTES" and, later,
    # the real ledger headed by Fecha contable/Fecha valor/.../Saldo.
    if "fechacontable" in keys:score+=6
    if "fechavalor" in keys or "valuedate" in keys:score+=3
    if "saldo" in keys or "balance" in keys:score+=3
    if keys&_XLSX_CURRENCY_FIELDS:score+=2
    if {"state","status","transactionstatus","estado"}&keys:score+=2
    if {"completeddate","transactioncompleted","transactioncompletedutc","fechadefinalizacion"}&keys:score+=3
    return score

def _xlsx(content:bytes)->bytes:
    wb=load_workbook(BytesIO(content),read_only=True,data_only=True)
    best=None
    for ws in wb.worksheets:
        preview=list(ws.iter_rows(min_row=1,max_row=min(ws.max_row or 1,100),values_only=True))
        for row_index,row in enumerate(preview,start=1):
            score=_xlsx_header_score(row)
            if score<0:continue
            previous=preview[max(0,row_index-4):row_index-1]
            context="".join(canonical_key(str(value or "")) for ctx_row in previous for value in ctx_row if value not in (None,""))
            if "movimientospendientes" in context:
                score-=20
            if score<0:continue
            candidate=(score,-row_index,ws,row_index,row)
            if best is None or candidate[:2]>best[:2]:best=candidate
    if best is None:
        return b""

    _,_,ws,header_row,header_values=best
    headers=[str(x or "").strip() for x in header_values]
    canonical=[canonical_key(h) for h in headers]
    rows=[]
    for row in ws.iter_rows(min_row=header_row+1,values_only=True):
        if not any(value not in (None,"") for value in row):
            continue
        d={canonical[i]:row[i] for i in range(min(len(canonical),len(row))) if canonical[i]}
        def pick(*names):
            for name in names:
                value=d.get(name)
                if value not in (None,""):return value
            return ""
        raw_date=pick(
            "completeddate","transactioncompleted","transactioncompletedutc",
            "fechadefinalizacion","fechadecompletado","fechacompletada",
            "fecha","date","bookingdate","fechacontable",
            "starteddate","transactionstarted","transactionstartedutc","fechadeinicio",
        )
        amount=pick("amount","amountpaymentcurrency","importe","cantidad")
        description=pick("description","transactiondescription","descripcion","descripciondelatransaccion","concepto","detalle")
        # Do not turn footer/filter rows into rejected transactions.
        if raw_date in (None,"") or amount in (None,"") or description in (None,""):
            continue
        rows.append({
            "Fecha":_cell_date(raw_date),
            "Concepto":description,
            "Importe":amount,
            "Moneda":pick("currency","paymentcurrency","moneda","divisa") or "EUR",
            "Comercio":pick("merchant","beneficiario","payer","comercio"),
            "Estado":pick("state","status","transactionstatus","estado"),
            "Referencia":pick("transactionid","transactionidentifier","transactionreference","banktransactionid","movementid","operationid","paymentid","fitid","endtoendid","txid","ntryref","acctsvcrref","bankreference","referencia","reference"),
        })
    return _csv_bytes(rows)

def _qif(text:str)->bytes:
    rows=[];cur={}
    for line in text.splitlines():
        if not line:continue
        code,val=line[:1],line[1:].strip()
        if code=="D":cur["Fecha"]=val
        elif code=="T":cur["Importe"]=val
        elif code=="P":cur["Comercio"]=val
        elif code=="M":cur["Concepto"]=val
        elif code=="N":cur["Referencia"]=val
        elif code=="^":
            if cur:cur.setdefault("Concepto",cur.get("Comercio","Movimiento"));cur.setdefault("Moneda","EUR");rows.append(cur)
            cur={}
    return _csv_bytes(rows)

def _ofx(text:str)->bytes:
    rows=[]
    for block in re.findall(r"<STMTTRN>(.*?)(?:</STMTTRN>|<STMTTRN>)",text,re.S|re.I):
        def tag(name):
            m=re.search(fr"<{name}>([^<\r\n]+)",block,re.I);return m.group(1).strip() if m else ""
        dt=tag("DTPOSTED")[:8]
        if len(dt)==8:dt=f"{dt[6:8]}/{dt[4:6]}/{dt[:4]}"
        rows.append({"Fecha":dt,"Importe":tag("TRNAMT"),"Concepto":tag("MEMO") or tag("NAME") or "Movimiento","Comercio":tag("NAME"),"Moneda":"EUR","Referencia":tag("FITID") or tag("REFNUM")})
    return _csv_bytes(rows)

def _local(el,tag):return [x for x in el.iter() if x.tag.rsplit("}",1)[-1]==tag]
def _camt(content:bytes)->bytes:
    root=ET.fromstring(content);rows=[]
    for entry in _local(root,"Ntry"):
        amts=_local(entry,"Amt");dates=_local(entry,"Dt");infos=_local(entry,"AddtlNtryInf");cd=_local(entry,"CdtDbtInd")
        if not amts or not dates:continue
        amount=amts[0].text or "0"
        if cd and (cd[0].text or "").upper()=="DBIT":amount="-"+amount.lstrip("-")
        refs=[]
        for tag_name in ("AcctSvcrRef","NtryRef","TxId","EndToEndId"):
            refs.extend(_local(entry,tag_name))
        reference=next(((x.text or "").strip() for x in refs if (x.text or "").strip()),"")
        rows.append({"Fecha":dates[0].text or "","Importe":amount,"Concepto":infos[0].text if infos else "Movimiento","Comercio":"","Moneda":amts[0].attrib.get("Ccy","EUR"),"Referencia":reference})
    return _csv_bytes(rows)

def _mt940(text:str)->bytes:
    rows=[];current=None
    for line in text.splitlines():
        if line.startswith(":61:"):
            m=re.match(r":61:(\d{6})(?:\d{4})?([CD])([\d,\.]+)",line)
            if m:
                yy=int(m.group(1)[:2]);year=2000+yy if yy<70 else 1900+yy;dt=f"{m.group(1)[4:6]}/{m.group(1)[2:4]}/{year}"
                amount=m.group(3).replace(",",".");amount=("-" if m.group(2)=="D" else "")+amount
                current={"Fecha":dt,"Importe":amount,"Concepto":"Movimiento","Comercio":"","Moneda":"EUR","Referencia":line[4:].strip()};rows.append(current)
        elif line.startswith(":86:") and current:current["Concepto"]=line[4:].strip()
    return _csv_bytes(rows)

def import_statement(session:Session,account_id:str,filename:str,content:bytes):
    ext=Path(filename).suffix.lower()
    if ext==".csv":normalized=content
    elif ext in {".xlsx",".xlsm"}:normalized=_xlsx(content)
    elif ext==".qif":normalized=_qif(content.decode("utf-8",errors="replace"))
    elif ext==".ofx":normalized=_ofx(content.decode("utf-8",errors="replace"))
    elif ext in {".xml",".camt",".053"}:normalized=_camt(content)
    elif ext in {".mt940",".sta"}:normalized=_mt940(content.decode("utf-8",errors="replace"))
    else:raise ValueError(f"Unsupported statement format: {ext}")
    return import_csv(session,account_id,normalized,filename)
