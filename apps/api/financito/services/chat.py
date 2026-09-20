from __future__ import annotations
import json
from datetime import date
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..models import Account,Contract,Transaction
from .local_ai import ask,status
from .financial_analytics import cash_flow
from .rag import search
from .evidence import structured_evidence_context
from .wealth import summary as wealth_summary

def answer(session:Session,question:str)->dict:
    today=date.today();start=today.replace(day=1)
    flow=cash_flow(session,start,today)
    wealth=wealth_summary(session)
    contracts=session.scalars(select(Contract)).all()
    evidence=search(session,question,limit=6)
    structured={
        "period":{"start":str(start),"end":str(today)},
        "cash_flow":{"income":str(flow["income"]),"expenses":str(flow["expenses"]),"savings":str(flow["savings"])},
        "wealth":wealth,
        "contracts":[{"provider":c.provider_name,"type":c.contract_type,"renewal":None if c.renewal_date is None else str(c.renewal_date),"penalty":None if c.early_exit_penalty is None else str(c.early_exit_penalty),"evidence_status":c.evidence_status} for c in contracts],
        "document_evidence":structured_evidence_context(session),
    }
    context=json.dumps(structured,ensure_ascii=False)+"\nFRAGMENTOS DOCUMENTALES RECUPERADOS (pueden requerir revisión):\n"+"\n\n".join(f"[{i+1}] {e['document_name']}: {e['text'][:1200]}" for i,e in enumerate(evidence))
    ai=status()
    if ai["available"] and ai["configured_model"]:
        try:result=ask(question,context)
        except Exception as exc:result=f"No se pudo consultar el modelo local: {exc}. Los datos estructurados sí están disponibles."
    else:
        result=f"IA local no configurada. Datos verificables del mes: ingresos {flow['income']} €, gastos {flow['expenses']} €, ahorro {flow['savings']} €. Patrimonio neto calculado: {wealth['net_worth']} €. Configura un modelo local para obtener una explicación conversacional."
    return {"result":result,"sources":[{"document_id":e["document_id"],"document_name":e["document_name"],"chunk_id":e["chunk_id"],"page_start":e["page_start"],"excerpt":e["text"][:400]} for e in evidence],"calculations":structured,"confidence":None,"data_freshness":{"calculated_at":str(today)}}
