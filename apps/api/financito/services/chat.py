from __future__ import annotations

import json
from datetime import date

from sqlalchemy.orm import Session

from .decision_context import live_decision_context
from .local_ai import ask, status
from .rag import search


def _deterministic_fallback(structured:dict,reason:str)->str:
    flow=structured["cash_flow_current_period"]
    return (
        reason+" "
        f"En el periodo seleccionado constan ingresos por {flow['income']} €, "
        f"gastos por {flow['expenses']} € y ahorro por {flow['savings']} €. "
        f"El patrimonio neto calculado para el ámbito actual es {structured['wealth']['net_worth']} €. "
        f"Hay {len(structured['decision_alerts'])} alerta(s) determinista(s) y "
        f"{len(structured['actions'])} acción(es) pendiente(s). "
        "Puedes revisar Configuración > IA local para probar el modelo."
    )


def answer(
    session:Session,
    question:str,
    *,
    start=None,
    end=None,
    account_id:str|None=None,
    account_type:str|None=None,
)->dict:
    today=date.today()
    structured=live_decision_context(
        session,
        start=start,
        end=end,
        account_id=account_id,
        account_type=account_type,
    )
    current_flow=structured["cash_flow_current_period"]
    structured["period"]={"start":current_flow["start"],"end":current_flow["end"]}
    structured["cash_flow"]={
        "income":current_flow["income"],
        "expenses":current_flow["expenses"],
        "savings":current_flow["savings"],
    }

    evidence=search(session,question,limit=6)
    fragments="\n\n".join(
        f"[{index+1}] {item['document_name']}: {item['text'][:1200]}"
        for index,item in enumerate(evidence)
    )
    context=(
        json.dumps(structured,ensure_ascii=False)
        +"\nFRAGMENTOS DOCUMENTALES RECUPERADOS (pueden requerir revisión):\n"
        +fragments
    )

    ai=status()
    ai_meta={
        "available":bool(ai.get("available")),
        "ready":bool(ai.get("chat_ready")),
        "model":ai.get("configured_model"),
        "used":False,
        "error":ai.get("error"),
    }

    if ai_meta["available"] and ai_meta["ready"] and ai_meta["model"]:
        try:
            result=ask(question,context)
            ai_meta["used"]=True
            ai_meta["error"]=None
        except Exception as exc:
            ai_meta["error"]=f"{type(exc).__name__}: {exc}"
            result=_deterministic_fallback(
                structured,
                "La IA local estaba configurada pero no pudo completar esta pregunta.",
            )
    elif not ai_meta["available"]:
        result=_deterministic_fallback(
            structured,
            "Ollama no está disponible, así que esta respuesta usa solo cálculos y datos estructurados.",
        )
    elif not ai_meta["model"]:
        result=_deterministic_fallback(
            structured,
            "No hay un modelo local de chat configurado, así que esta respuesta usa solo cálculos y datos estructurados.",
        )
    else:
        result=_deterministic_fallback(
            structured,
            f"El modelo local {ai_meta['model']} está configurado pero no aparece disponible en Ollama; no se ha usado IA generativa.",
        )

    return {
        "result":result,
        "sources":[
            {
                "document_id":item["document_id"],
                "document_name":item["document_name"],
                "chunk_id":item["chunk_id"],
                "page_start":item["page_start"],
                "excerpt":item["text"][:400],
            }
            for item in evidence
        ],
        "calculations":structured,
        "confidence":None,
        "ai":ai_meta,
        "data_freshness":{
            "calculated_at":str(today),
            "context_generated_at":structured["generated_at"],
        },
    }
