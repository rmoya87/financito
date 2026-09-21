from __future__ import annotations

from decimal import Decimal, InvalidOperation
import json
import re

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..models import ActionItem, Document, ExtractedFact
from ..models_analytics import EntityLink
from ..models_extended import DocumentChunk
from .local_ai import generate_json, status as ai_status


ANALYSIS_FACT_TYPE = "ai_insight"
ANALYSIS_KEY = "document_analysis"
ANALYSIS_SCHEMA_VERSION = 3
MAX_CONTEXT_CHARS = 48000
MAX_CHUNKS = 18

CONTRACT_FACT_KEYS = {
    "cancellation_notice_days","early_exit_penalty","annual_cost","monthly_cost","deductible",
    "start_date","permanence_end_date","renewal_date","automatic_renewal",
    "provider_name","insurance_type","policy_number","contract_number","insured_object",
    "insured_value","cancellation_condition","waiting_period",
    "promotional_price","standard_price","promotion_end_date","financed_device_balance",
}
MORTGAGE_FACT_KEYS = {
    "nominal_rate","apr_rate","reference_index","interest_type","differential_rate",
    "start_date","maturity_date","mortgage_term_years","rate_review_months","next_review_date",
    "reference_index_lag_months","default_interest_rate_percent","opening_fee_percent",
    "early_repayment_fee_percent","subrogation_fee_percent","cancellation_fee_percent",
    "remaining_principal","monthly_payment","remaining_months",
}
LINKED_FACT_KEYS = {
    "linked_salary","linked_home_insurance","linked_life_insurance","linked_card","linked_pension_plan",
    "linked_home_insurance_rate_penalty_pp","linked_life_insurance_rate_penalty_pp","linked_salary_rate_penalty_pp",
}
INVESTMENT_FACT_KEYS = {
    "product_name","isin","management_fee_percent","ongoing_costs_percent","custody_fee",
    "subscription_fee_percent","redemption_fee_percent",
}
ALLOWED_MATERIAL_FACT_KEYS = CONTRACT_FACT_KEYS | MORTGAGE_FACT_KEYS | LINKED_FACT_KEYS | INVESTMENT_FACT_KEYS

EXPECTED_MATERIAL_KEYS_BY_TYPE = {
    "insurance": {
        "provider_name","policy_number","insurance_type","annual_cost","monthly_cost","deductible",
        "renewal_date","cancellation_notice_days","early_exit_penalty","insured_object","insured_value",
        "cancellation_condition","waiting_period",
    },
    "mortgage": (
        MORTGAGE_FACT_KEYS
        | LINKED_FACT_KEYS
        | {"provider_name","contract_number","early_exit_penalty"}
    ),
    "loan": {
        "provider_name","contract_number","nominal_rate","apr_rate","remaining_principal",
        "monthly_payment","remaining_months","early_repayment_fee_percent","early_exit_penalty",
        "renewal_date","cancellation_notice_days",
    },
    "energy": {
        "provider_name","contract_number","annual_cost","monthly_cost","renewal_date",
        "cancellation_notice_days","early_exit_penalty","permanence_end_date",
        "promotional_price","standard_price","promotion_end_date","automatic_renewal",
    },
    "telecom": {
        "provider_name","contract_number","annual_cost","monthly_cost","renewal_date",
        "cancellation_notice_days","early_exit_penalty","permanence_end_date",
        "promotional_price","standard_price","promotion_end_date","financed_device_balance",
    },
    "contract": {
        "provider_name","contract_number","annual_cost","monthly_cost","start_date","renewal_date",
        "cancellation_notice_days","early_exit_penalty","permanence_end_date","automatic_renewal",
    },
    "investment_statement": INVESTMENT_FACT_KEYS | {"provider_name"},
}

TYPE_FOCUS = {
    "insurance": (
        "Analiza especialmente coberturas, límites, franquicias, exclusiones, carencias, renovaciones, "
        "preavisos, penalizaciones, prima, servicios incluidos, ventajas reales, obligaciones y posibles "
        "solapamientos o carencias. Detecta si está vinculado a una hipoteca y el efecto de cancelarlo."
    ),
    "mortgage": (
        "Analiza especialmente TIN/TAE, tipo fijo/variable/mixto, índice y diferencial, capital/plazo, "
        "comisiones, amortización anticipada, subrogación, novación, productos vinculados, bonificaciones, "
        "coste de perder cada bonificación, obligaciones y cláusulas que afecten a cambiar de entidad."
    ),
    "loan": (
        "Analiza especialmente TIN/TAE, plazo, cuota, amortización anticipada, cancelación, comisiones, "
        "garantías, seguros vinculados y cualquier coste de refinanciación."
    ),
    "energy": (
        "Analiza especialmente precio fijo/variable, potencia, permanencia, penalización, revisión de precio, "
        "servicios adicionales y condiciones de cancelación."
    ),
    "telecom": (
        "Analiza especialmente permanencia, penalización, precio promocional y posterior, servicios incluidos, "
        "financiación de dispositivos y condiciones de cancelación."
    ),
    "contract": (
        "Analiza costes, renovaciones, preavisos, penalizaciones, permanencias, obligaciones, ventajas y "
        "condiciones que afecten a una decisión de mantener, renegociar o cambiar."
    ),
    "bank_statement": (
        "Analiza comisiones, intereses, cargos recurrentes, servicios cobrados, posibles duplicidades y "
        "condiciones visibles. No reclasifiques movimientos ni inventes saldos; señala qué podría alimentar "
        "Cuentas, Movimientos o una revisión de costes bancarios."
    ),
    "investment_statement": (
        "Analiza comisiones de custodia/gestión, costes explícitos, posiciones, liquidez, dividendos y "
        "condiciones del producto. Señala impactos en Patrimonio e Inversiones sin inferir rentabilidades futuras."
    ),
    "tax": (
        "Resume únicamente datos fiscales explícitos, importes, fechas, bases y conceptos visibles. Señala "
        "posibles datos útiles para planificación o revisión, pero no presentes una interpretación como asesoramiento "
        "fiscal ni inventes deducciones o reglas que no figuren en la documentación."
    ),
}


def _payload(row: ExtractedFact) -> dict:
    try:
        value = json.loads(row.value_json)
        return value if isinstance(value, dict) else {"value": value}
    except Exception:
        return {"value": row.value_json}


def latest_analysis(session: Session, document_id: str) -> dict | None:
    row = session.scalar(
        select(ExtractedFact)
        .where(
            ExtractedFact.document_id == document_id,
            ExtractedFact.fact_type == ANALYSIS_FACT_TYPE,
            ExtractedFact.key == ANALYSIS_KEY,
        )
        .order_by(ExtractedFact.updated_at.desc())
    )
    if row is None:
        return None
    payload = _payload(row)
    return {
        "id": row.id,
        "status": row.status,
        "confidence": str(row.confidence),
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        **payload,
    }


def _relevant_chunks(session: Session, document: Document) -> list[DocumentChunk]:
    chunks = session.scalars(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document.id)
        .order_by(DocumentChunk.chunk_index)
    ).all()
    if len(chunks) <= MAX_CHUNKS:
        return chunks

    focus_terms = {
        "insurance": ["cobertura","exclus","franqu","prima","cancel","renov","preaviso","carencia","capital","límite","limite","hipoteca"],
        "mortgage": ["tin","tae","amort","subrog","comisi","bonific","seguro","nómina","nomina","euribor","diferencial","novaci","cancel"],
        "loan": ["tin","tae","amort","cancel","comisi","seguro","cuota","vencimiento"],
        "energy": ["precio","kwh","potencia","permanencia","penal","cancel","revisi"],
        "telecom": ["permanencia","penal","cancel","precio","promoci","renov","terminal"],
    }.get(document.document_type, ["penal","cancel","renov","precio","coste","comisi","oblig","ventaja"])

    scored = []
    for chunk in chunks:
        lowered = chunk.text.lower()
        score = sum(lowered.count(term) for term in focus_terms)
        scored.append((score, chunk.chunk_index, chunk))
    selected = sorted(scored, key=lambda item: (-item[0], item[1]))[:MAX_CHUNKS]
    return [item[2] for item in sorted(selected, key=lambda item: item[1])]


def _structured_facts(session: Session, document_id: str) -> list[dict]:
    rows = session.scalars(
        select(ExtractedFact)
        .where(
            ExtractedFact.document_id == document_id,
            ExtractedFact.fact_type != ANALYSIS_FACT_TYPE,
        )
        .order_by(ExtractedFact.source_page, ExtractedFact.created_at)
    ).all()
    out = []
    for row in rows[:180]:
        payload = _payload(row)
        out.append({
            "key": row.key,
            "fact_type": row.fact_type,
            "value": payload.get("value"),
            "unit": payload.get("unit"),
            "status": row.status,
            "user_verified": row.user_verified,
            "confidence": str(row.confidence),
            "page": row.source_page,
        })
    return out


def _context(session: Session, document: Document) -> str:
    parts = []
    total = 0
    for chunk in _relevant_chunks(session, document):
        prefix = f"[PÁGINA {chunk.page_start or '?'}]\n"
        text = prefix + chunk.text.strip()
        remaining = MAX_CONTEXT_CHARS - total
        if remaining <= 0:
            break
        text = text[:remaining]
        parts.append(text)
        total += len(text)
    if not parts and document.extracted_text:
        parts.append(document.extracted_text[:MAX_CONTEXT_CHARS])
    return "\n\n---\n\n".join(parts)


def _clean_list(value) -> list[dict]:
    if not isinstance(value, list):
        return []
    out = []
    for item in value[:16]:
        if isinstance(item, str):
            out.append({"title": item[:180], "detail": "", "pages": []})
            continue
        if not isinstance(item, dict):
            continue
        pages = item.get("pages")
        if not isinstance(pages, list):
            pages = []
        normalized_pages = []
        for page in pages[:8]:
            try:
                normalized_pages.append(int(page))
            except Exception:
                pass
        out.append({
            "title": str(item.get("title") or item.get("name") or "")[:180],
            "detail": str(item.get("detail") or item.get("description") or "")[:1200],
            "pages": normalized_pages,
            "impact": str(item.get("impact") or "")[:300],
        })
    return [x for x in out if x["title"] or x["detail"]]


def _clean_material_facts(value) -> list[dict]:
    if not isinstance(value,list):
        return []
    out=[]
    for item in value[:30]:
        if not isinstance(item,dict):
            continue
        key=str(item.get("key") or "").strip()
        if key not in ALLOWED_MATERIAL_FACT_KEYS:
            continue
        raw=item.get("value")
        if raw in {None,""}:
            continue
        try:page=int(item.get("page"))
        except Exception:page=None
        if page is None or page<1:
            continue
        try:confidence=float(item.get("confidence",0.65))
        except Exception:confidence=0.65
        out.append({
            "key":key,
            "value":str(raw)[:500],
            "unit":str(item.get("unit") or "")[:80],
            "page":page,
            "confidence":max(0.0,min(0.85,confidence)),
        })
    return out


def _clean_coverage_facts(value) -> list[dict]:
    if not isinstance(value,list):
        return []
    out=[]
    for item in value[:40]:
        if not isinstance(item,dict):
            continue
        coverage_type=str(item.get("coverage_type") or "").strip()
        if not coverage_type:
            continue
        try:page=int(item.get("page"))
        except Exception:page=None
        if page is None or page<1:
            continue
        try:confidence=float(item.get("confidence",0.65))
        except Exception:confidence=0.65
        out.append({
            "coverage_type":coverage_type[:100],
            "limit_amount":None if item.get("limit_amount") in {None,""} else str(item.get("limit_amount"))[:80],
            "deductible":None if item.get("deductible") in {None,""} else str(item.get("deductible"))[:80],
            "conditions":str(item.get("conditions") or "")[:1000],
            "exclusions":str(item.get("exclusions") or "")[:1000],
            "page":page,
            "confidence":max(0.0,min(0.85,confidence)),
        })
    return out


def _replace_ai_proposals(session:Session,document:Document,analysis:dict)->None:
    session.execute(
        delete(ExtractedFact).where(
            ExtractedFact.document_id==document.id,
            ExtractedFact.user_verified.is_(False),
            ExtractedFact.source_section.like("IA local:%"),
        )
    )
    for fact in analysis.get("proposed_material_facts") or []:
        key=fact["key"];page=fact["page"]
        existing=session.scalar(select(ExtractedFact.id).where(
            ExtractedFact.document_id==document.id,
            ExtractedFact.key==key,
            ExtractedFact.source_page==page,
        ))
        if existing:
            continue
        if key in LINKED_FACT_KEYS:
            fact_type="linked_product"
        elif document.document_type=="mortgage" and key in MORTGAGE_FACT_KEYS:
            fact_type="mortgage_term"
        elif document.document_type=="investment_statement" and key in INVESTMENT_FACT_KEYS:
            fact_type="investment_term"
        else:
            fact_type="contract_term"
        session.add(ExtractedFact(
            document_id=document.id,
            fact_type=fact_type,
            key=key,
            value_json=json.dumps({"value":fact["value"],"unit":fact["unit"],"source":"local_ai_proposal"},ensure_ascii=False),
            confidence=Decimal(str(fact["confidence"])),
            status="inferred",
            source_page=page,
            source_section=f"IA local: propuesta para revisar en pág. {page}",
            user_verified=False,
        ))
    for index,coverage in enumerate(analysis.get("coverage_facts") or []):
        page=coverage["page"]
        coverage_name=coverage["coverage_type"].strip()
        existing_coverages=session.scalars(select(ExtractedFact).where(
            ExtractedFact.document_id==document.id,
            ExtractedFact.fact_type=="coverage_fact",
            ExtractedFact.source_page==page,
        )).all()
        if any(str(_payload(row).get("coverage_type") or _payload(row).get("value") or "").strip().lower()==coverage_name.lower() for row in existing_coverages):
            continue
        slug=re.sub(r"[^a-z0-9]+","_",coverage_name.lower()).strip("_")[:45] or "coverage"
        session.add(ExtractedFact(
            document_id=document.id,
            fact_type="coverage_fact",
            key=f"coverage:{slug}:{page}:{index}",
            value_json=json.dumps({
                "value":coverage["coverage_type"],
                "coverage_type":coverage["coverage_type"],
                "limit_amount":coverage["limit_amount"],
                "deductible":coverage["deductible"],
                "conditions":coverage["conditions"],
                "exclusions":coverage["exclusions"],
                "source":"local_ai_proposal",
            },ensure_ascii=False),
            confidence=Decimal(str(coverage["confidence"])),
            status="inferred",
            source_page=page,
            source_section=f"IA local: cobertura propuesta para revisar en pág. {page}",
            user_verified=False,
        ))
    session.flush()


def _normalize(result: dict, document: Document) -> dict:
    if not isinstance(result, dict):
        raise RuntimeError("La IA local no devolvió un objeto JSON")
    try:
        confidence = Decimal(str(result.get("confidence", "0.55")))
    except (InvalidOperation, ValueError):
        confidence = Decimal("0.55")
    confidence = max(Decimal("0"), min(Decimal("1"), confidence))
    return {
        "analysis_schema_version": ANALYSIS_SCHEMA_VERSION,
        "document_type": document.document_type,
        "summary": str(result.get("summary") or "")[:3000],
        "advantages": _clean_list(result.get("advantages")),
        "penalties": _clean_list(result.get("penalties")),
        "obligations": _clean_list(result.get("obligations")),
        "risks": _clean_list(result.get("risks")),
        "exclusions_or_limits": _clean_list(result.get("exclusions_or_limits")),
        "linked_products": _clean_list(result.get("linked_products")),
        "optimization_opportunities": _clean_list(result.get("optimization_opportunities")),
        "negotiation_points": _clean_list(result.get("negotiation_points")),
        "comparison_requirements": _clean_list(result.get("comparison_requirements")),
        "cross_area_impacts": _clean_list(result.get("cross_area_impacts")),
        "missing_information": _clean_list(result.get("missing_information")),
        "proposed_material_facts": _clean_material_facts(result.get("proposed_material_facts")),
        "coverage_facts": _clean_coverage_facts(result.get("coverage_facts")),
        "confidence": str(confidence),
        "model_role": (
            "Interpretación local. No sustituye hechos contractuales confirmados ni se usa por sí sola "
            "para cálculos deterministas."
        ),
    }


def _document_group_ids(session: Session, document: Document) -> list[str]:
    links = session.scalars(
        select(EntityLink).where(
            EntityLink.from_type == "document",
            EntityLink.from_id == document.id,
            EntityLink.relation_type == "evidence_for",
        )
    ).all()
    preferred = next((x for x in links if x.to_type == "insurance_policy"), None)
    preferred = preferred or next((x for x in links if x.to_type == "mortgage"), None)
    preferred = preferred or next((x for x in links if x.to_type == "contract"), None)
    if preferred is None:
        return [document.id]
    ids = list(session.scalars(
        select(EntityLink.from_id).where(
            EntityLink.from_type == "document",
            EntityLink.relation_type == "evidence_for",
            EntityLink.to_type == preferred.to_type,
            EntityLink.to_id == preferred.to_id,
        )
    ).all())
    return sorted(set(ids or [document.id]))


def _upsert_action(session: Session, document: Document, analysis: dict) -> None:
    opportunities = analysis.get("optimization_opportunities") or []
    risks = analysis.get("risks") or []
    group_ids = _document_group_ids(session, document)

    if not opportunities and not risks:
        existing = session.scalar(
            select(ActionItem).where(
                ActionItem.action_type == "review_document_ai_insights",
                ActionItem.related_entity_type == "document",
                ActionItem.related_entity_id == document.id,
                ActionItem.status.in_(["pending", "in_progress"]),
            )
        )
        if existing is not None:
            existing.status = "done"
        return

    existing = session.scalar(
        select(ActionItem).where(
            ActionItem.action_type == "review_document_ai_insights",
            ActionItem.related_entity_type == "document",
            ActionItem.related_entity_id.in_(group_ids),
            ActionItem.status.in_(["pending", "in_progress"]),
        )
        .order_by(ActionItem.created_at.asc())
    )
    if len(group_ids) > 1:
        title = f"Revisar conclusiones de {len(group_ids)} documentos del mismo producto"
        notes = (
            "Financito ha detectado conclusiones que conviene revisar en la documentación agrupada. "
            "Abre la evidencia, revisa el análisis y marca el aviso como revisado cuando hayas terminado."
        )
    else:
        title = f"Revisar conclusiones de {document.file_name}"
        notes = (
            "Financito ha detectado conclusiones que conviene revisar. Abre la evidencia, "
            "lee el análisis y marca el aviso como revisado cuando hayas terminado."
        )

    if existing is None:
        session.add(ActionItem(
            action_type="review_document_ai_insights",
            title=title,
            priority="medium",
            related_entity_type="document",
            related_entity_id=document.id,
            source_type="document_ai",
            source_ref=document.id,
            notes=notes,
        ))
    else:
        existing.title = title
        existing.notes = notes
        existing.source_ref = document.id



def analyze_document(session: Session, document: Document) -> dict:
    ai = ai_status()
    if not (ai.get("available") and ai.get("configured_model") and ai.get("chat_ready", True)):
        return {
            "status": "ai_unavailable",
            "analysis": None,
            "message": "Configura y arranca un modelo local de Ollama para generar el análisis interpretativo.",
        }

    context = _context(session, document)
    facts = _structured_facts(session, document.id)
    focus = TYPE_FOCUS.get(document.document_type, TYPE_FOCUS["contract"])
    represented_keys = {str(item.get("key") or "") for item in facts}
    expected_keys = EXPECTED_MATERIAL_KEYS_BY_TYPE.get(document.document_type, set())
    search_keys = sorted(key for key in expected_keys if key not in represented_keys)
    prompt = f"""
Analiza un documento financiero personal en español. Documento: {document.file_name}
Tipo detectado: {document.document_type}

{focus}

REGLAS OBLIGATORIAS:
- Usa exclusivamente el texto y los hechos suministrados.
- No inventes importes, porcentajes, fechas, coberturas, normativa ni condiciones.
- Si una conclusión depende de algo no visible, colócala en missing_information.
- Cita páginas solo cuando el contexto incluya una página concreta.
- Distingue ventajas comerciales de derechos contractuales.
- Señala impactos cruzados: por ejemplo, quitar un seguro puede encarecer una hipoteca.
- En negotiation_points incluye cláusulas o condiciones concretas que convenga usar al renegociar o pedir ofertas.
- En comparison_requirements indica qué condiciones deben igualarse para comparar alternativas de forma equivalente (coberturas, franquicias, bonificaciones, plazo, comisiones, etc.).
- No decidas por el usuario. Explica oportunidades y riesgos de forma neutral.
- Los hechos con status=confirmed y user_verified=true son confirmados. Los demás son indicios pendientes de revisión.
- Si una clave ya aparece en HECHOS ESTRUCTURADOS, aunque esté inferred/ambiguous, NO digas que falta: indica que está pendiente de validar si es material.
- Busca de forma sistemática en todo el contexto disponible estas claves todavía no representadas para este tipo de documento: {', '.join(search_keys) if search_keys else 'ninguna; ya hay un hecho estructurado para todas las claves esperadas'}.
- Si una de esas claves no aparece explícitamente, no la inventes ni generes un fact vacío; puedes indicarla en missing_information.
- En proposed_material_facts incluye SOLO condiciones numéricas/textuales explícitas de estas claves: {', '.join(sorted(ALLOWED_MATERIAL_FACT_KEYS))}.
- Si utilizas en advantages/penalties/obligations/risks/comparison_requirements un TIN, TAE, índice, diferencial, fecha de inicio/vencimiento, plazo, periodicidad de revisión, próxima revisión o comisión que encaje en una clave permitida y aparece explícitamente, DEBES reflejarlo también en proposed_material_facts.
- Cada proposed_material_fact requiere una página concreta; si no puedes citarla, no lo propongas.
- REGLA ESPECIAL PARA NOTAS SIMPLES/INFORMACIÓN REGISTRAL: distingue responsabilidad hipotecaria registral de coste contractual actual. Importes garantizados por intereses ordinarios, intereses de demora, costas/gastos o valor de subasta NO son cuotas, comisiones, penalizaciones de salida, gastos ya pagados ni capital pendiente.
- En penalties incluye SOLO penalizaciones/comisiones reales de salida, cancelación, amortización anticipada, subrogación o novación expresamente descritas. Intereses de demora y costas de ejecución deben ir a risks/obligations y deben llamarse claramente responsabilidad o condición por incumplimiento, nunca coste de salida.
- Si el documento dice un porcentaje máximo registral de demora, puedes proponer default_interest_rate_percent solo cuando el porcentaje aplicable/máximo esté explícito; nunca conviertas el importe de responsabilidad por intereses en una tasa.
- Si aparece una fecha de vencimiento contractual explícita, propón maturity_date. Si aparece duración explícita, propón mortgage_term_years solo si el texto ya expresa años o la conversión desde meses es exacta e inequívoca.
- Si el contrato especifica qué mes/publicación del índice se usa antes de la revisión (por ejemplo, el Euríbor publicado dos meses antes), propón reference_index_lag_months con ese número de meses. No lo deduzcas por práctica bancaria general.
- No infieras TAE, diferencial, índice de referencia, comisión de amortización o subrogación a partir de una nota simple cuando no consten expresamente: deben quedar en missing_information.
- En coverage_facts incluye SOLO coberturas explícitas del seguro, con página concreta. No inventes límites, franquicias, condiciones ni exclusiones ausentes.
- Devuelve SOLO JSON válido.

HECHOS ESTRUCTURADOS:
{json.dumps(facts, ensure_ascii=False)}

TEXTO RELEVANTE:
{context}

SCHEMA JSON:
{{
  "summary": "resumen ejecutivo",
  "advantages": [{{"title":"","detail":"","pages":[1],"impact":""}}],
  "penalties": [{{"title":"","detail":"","pages":[1],"impact":""}}],
  "obligations": [{{"title":"","detail":"","pages":[1],"impact":""}}],
  "risks": [{{"title":"","detail":"","pages":[1],"impact":""}}],
  "exclusions_or_limits": [{{"title":"","detail":"","pages":[1],"impact":""}}],
  "linked_products": [{{"title":"","detail":"","pages":[1],"impact":""}}],
  "optimization_opportunities": [{{"title":"","detail":"","pages":[1],"impact":""}}],
  "negotiation_points": [{{"title":"","detail":"","pages":[1],"impact":""}}],
  "comparison_requirements": [{{"title":"","detail":"","pages":[1],"impact":""}}],
  "cross_area_impacts": [{{"title":"","detail":"","pages":[1],"impact":""}}],
  "missing_information": [{{"title":"","detail":"","pages":[],"impact":""}}],
  "proposed_material_facts": [{{"key":"cancellation_notice_days","value":"30","unit":"days","page":1,"confidence":0.75}}],
  "coverage_facts": [{{"coverage_type":"Responsabilidad civil","limit_amount":null,"deductible":null,"conditions":"","exclusions":"","page":1,"confidence":0.75}}],
  "confidence": 0.0
}}
"""
    result = _normalize(generate_json(prompt, timeout=180), document)
    confidence = Decimal(result["confidence"])
    _replace_ai_proposals(session,document,result)

    session.execute(
        delete(ExtractedFact).where(
            ExtractedFact.document_id == document.id,
            ExtractedFact.fact_type == ANALYSIS_FACT_TYPE,
            ExtractedFact.key == ANALYSIS_KEY,
        )
    )
    row = ExtractedFact(
        document_id=document.id,
        fact_type=ANALYSIS_FACT_TYPE,
        key=ANALYSIS_KEY,
        value_json=json.dumps(result, ensure_ascii=False),
        confidence=confidence,
        status="inferred",
        source_page=None,
        source_section="Análisis interpretativo generado por IA local",
        user_verified=False,
    )
    session.add(row)
    # Identity proposals must be grouped before creating "Para ti" actions so
    # several files from one product produce one review item, not one per file.
    from .evidence import synchronize_document_evidence
    synchronize_document_evidence(session, document)
    _upsert_action(session, document, result)
    session.flush()
    return {"status": "ready", "analysis": result, "message": None}


def stale_analysis_document_ids(session: Session) -> list[str]:
    """Documents that need the current extraction/search strategy.

    Missing analyses and analyses created with an older schema are refreshed when
    the local model is available. The refresh never confirms material facts.
    """
    ids=[]
    for document in session.scalars(select(Document).order_by(Document.updated_at.desc())).all():
        analysis=latest_analysis(session,document.id)
        try:
            version=int((analysis or {}).get("analysis_schema_version") or 0)
        except (TypeError,ValueError):
            version=0
        if version<ANALYSIS_SCHEMA_VERSION:
            ids.append(document.id)
    return ids


def analyze_document_by_id(session: Session, document_id: str) -> dict:
    document = session.get(Document, document_id)
    if document is None:
        raise ValueError("Document not found")
    return analyze_document(session, document)


def domain_insights(session: Session, document_type: str | None = None) -> list[dict]:
    stmt = select(Document).order_by(Document.updated_at.desc())
    if document_type:
        stmt = stmt.where(Document.document_type == document_type)
    out = []
    for document in session.scalars(stmt).all():
        analysis = latest_analysis(session, document.id)
        if analysis is None:
            continue
        out.append({
            "document_id": document.id,
            "file_name": document.file_name,
            "document_type": document.document_type,
            "analysis": analysis,
        })
    return out
