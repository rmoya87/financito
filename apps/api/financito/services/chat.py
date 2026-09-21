from __future__ import annotations

import json
from datetime import date

from sqlalchemy.orm import Session

from .decision_context import live_decision_context
from .local_ai import ask, status
from .rag import search


def answer(session: Session, question: str) -> dict:
    today = date.today()
    structured = live_decision_context(session)
    current_flow = structured["cash_flow_current_month"]
    # Alias de compatibilidad para clientes y tests anteriores: el contenido
    # procede del mismo contexto común, no de un cálculo paralelo.
    structured["period"] = {"start": current_flow["start"], "end": current_flow["end"]}
    structured["cash_flow"] = {
        "income": current_flow["income"],
        "expenses": current_flow["expenses"],
        "savings": current_flow["savings"],
    }

    evidence = search(session, question, limit=6)
    fragments = "\n\n".join(
        f"[{index + 1}] {item['document_name']}: {item['text'][:1200]}"
        for index, item in enumerate(evidence)
    )
    context = (
        json.dumps(structured, ensure_ascii=False)
        + "\nFRAGMENTOS DOCUMENTALES RECUPERADOS (pueden requerir revisión):\n"
        + fragments
    )
    ai = status()
    if ai["available"] and ai["configured_model"]:
        try:
            result = ask(question, context)
        except Exception as exc:
            result = (
                f"No se pudo consultar el modelo local: {exc}. "
                "Los datos estructurados y cálculos deterministas sí están disponibles."
            )
    else:
        result = (
            "IA local no configurada. "
            f"Datos verificables del mes: ingresos {current_flow['income']} €, "
            f"gastos {current_flow['expenses']} €, ahorro {current_flow['savings']} €. "
            f"Patrimonio neto calculado: {structured['wealth']['net_worth']} €. "
            f"Hay {len(structured['decision_alerts'])} alerta(s) determinista(s) y "
            f"{len(structured['actions'])} acción(es) pendiente(s). "
            "Configura un modelo local para obtener una explicación conversacional."
        )
    return {
        "result": result,
        "sources": [
            {
                "document_id": item["document_id"],
                "document_name": item["document_name"],
                "chunk_id": item["chunk_id"],
                "page_start": item["page_start"],
                "excerpt": item["text"][:400],
            }
            for item in evidence
        ],
        "calculations": structured,
        "confidence": None,
        "data_freshness": {"calculated_at": str(today), "context_generated_at": structured["generated_at"]},
    }
