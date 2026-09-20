from __future__ import annotations

from datetime import date,timedelta
from decimal import Decimal
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Category,Contract,Document,ExtractedFact,Transaction
from ..models_analytics import CoverageRequirement,EntityLink
from ..models_extended import CoverageFact,CoverageOverlap,InsurancePolicy
from .contracts import scan_coverage_overlaps
from .evidence import synchronize_all_document_evidence
from .financial_analytics import cash_flow
from .local_ai import generate_json,status as ai_status

def _d(value)->str|None:
    return None if value is None else str(value)

def _payload(fact:ExtractedFact)->dict:
    try:
        value=json.loads(fact.value_json)
        return value if isinstance(value,dict) else {"value":value}
    except Exception:
        return {"value":fact.value_json}

def _coverage_gaps(session:Session,policies:dict[str,InsurancePolicy])->tuple[list[dict],list[dict]]:
    today=date.today()
    requirements=session.scalars(select(CoverageRequirement).where(CoverageRequirement.enabled.is_(True))).all()
    facts=session.scalars(select(CoverageFact).where(CoverageFact.user_verified.is_(True))).all()
    gaps=[];covered=[]
    for req in requirements:
        eligible=[]
        for fact in facts:
            if fact.coverage_type.strip().lower()!=req.coverage_type.strip().lower():continue
            if fact.effective_from and fact.effective_from>today:continue
            if fact.effective_to and fact.effective_to<today:continue
            if req.insurance_type:
                policy=policies.get(fact.insurance_policy_id or "")
                if not policy or policy.insurance_type!=req.insurance_type:continue
            eligible.append(fact)
        limits=[f.limit_amount for f in eligible if f.limit_amount is not None]
        if not eligible:
            gaps.append({"requirement_id":req.id,"coverage_type":req.coverage_type,"insurance_type":req.insurance_type,"reason":"missing_verified_coverage","minimum_limit":_d(req.minimum_limit)})
        elif req.minimum_limit is not None and not limits:
            gaps.append({"requirement_id":req.id,"coverage_type":req.coverage_type,"insurance_type":req.insurance_type,"reason":"limit_unknown","minimum_limit":_d(req.minimum_limit)})
        elif req.minimum_limit is not None and max(limits)<req.minimum_limit:
            gaps.append({"requirement_id":req.id,"coverage_type":req.coverage_type,"insurance_type":req.insurance_type,"reason":"limit_below_requirement","minimum_limit":_d(req.minimum_limit),"best_verified_limit":_d(max(limits))})
        else:
            covered.append({"requirement_id":req.id,"coverage_type":req.coverage_type,"insurance_type":req.insurance_type,"matching_coverages":len(eligible),"best_verified_limit":None if not limits else _d(max(limits))})
    return gaps,covered

def insurance_verdict(session:Session,use_ai:bool=True)->dict:
    synchronize_all_document_evidence(session)
    session.flush()

    documents={d.id:d for d in session.scalars(select(Document)).all()}
    contracts={c.id:c for c in session.scalars(select(Contract)).all()}
    policies_list=session.scalars(select(InsurancePolicy)).all()
    policies={p.id:p for p in policies_list}
    coverage=session.scalars(select(CoverageFact)).all()

    source_links=session.scalars(select(EntityLink).where(
        EntityLink.from_type=="document",
        EntityLink.relation_type=="evidence_for",
        EntityLink.to_type=="insurance_policy",
    )).all()
    source_by_policy:dict[str,list[str]]={}
    for link in source_links:
        source_by_policy.setdefault(link.to_id,[]).append(link.from_id)

    overlaps=scan_coverage_overlaps(session)
    gaps,covered=_coverage_gaps(session,policies)

    today=date.today();start=today-timedelta(days=364)
    insurance_cat=session.scalar(select(Category).where(Category.system_key=="insurance"))
    txs=[]
    if insurance_cat:
        txs=session.scalars(select(Transaction).where(
            Transaction.category_id==insurance_cat.id,
            Transaction.amount<0,
            Transaction.is_internal_transfer.is_(False),
            Transaction.booking_date>=start,
            Transaction.booking_date<=today,
        ).order_by(Transaction.booking_date.desc())).all()
    observed_spend=sum((-t.amount for t in txs),Decimal("0"))
    flow=cash_flow(session,start,today)
    income=flow["income"];expenses=flow["expenses"]
    premiums=sum((p.annual_premium for p in policies_list),Decimal("0"))
    premium_share=None if income<=0 else premiums/income

    by_merchant={}
    for tx in txs:
        merchant=tx.merchant_raw or tx.description_raw or "Sin comercio"
        by_merchant[merchant]=by_merchant.get(merchant,Decimal("0"))+(-tx.amount)

    policy_rows=[];missing=[]
    for policy in policies_list:
        contract=contracts.get(policy.contract_id or "")
        document_ids=source_by_policy.get(policy.id,[])
        document_id=document_ids[0] if document_ids else None
        document=documents.get(document_id or "")
        row_coverage=[f for f in coverage if f.insurance_policy_id==policy.id]
        if document_id is None:
            missing.append({"field":"source_document","label":"Documento origen","policy_id":policy.id,"document_id":None,"why":"La póliza no está vinculada a un documento fuente; no debe tratarse como fuente canónica."})
        if policy.deductible is None:
            missing.append({"field":"deductible","label":"Franquicia","policy_id":policy.id,"document_id":document_id,"why":"No consta una franquicia confirmada. Si la póliza no tiene franquicia, confírmalo explícitamente en su documento."})
        if contract is not None:
            if contract.renewal_date is None:
                missing.append({"field":"renewal_date","label":"Fecha de renovación","policy_id":policy.id,"document_id":document_id,"why":"Hace falta para anticipar renovación y comparar alternativas a tiempo."})
            if contract.cancellation_notice_days is None:
                missing.append({"field":"cancellation_notice_days","label":"Preaviso de cancelación","policy_id":policy.id,"document_id":document_id,"why":"Hace falta para saber hasta cuándo puedes cancelar o negociar."})
        elif document_id is not None:
            missing.append({"field":"contract_projection","label":"Datos contractuales","policy_id":policy.id,"document_id":document_id,"why":"El documento todavía no contiene suficientes hechos confirmados para construir el contrato asociado."})
        policy_rows.append({
            "id":policy.id,
            "insurance_type":policy.insurance_type,
            "annual_premium":str(policy.annual_premium),
            "monthly_equivalent":str((policy.annual_premium/Decimal("12")).quantize(Decimal("0.01"))),
            "deductible":_d(policy.deductible),
            "source_document_id":document_id,
            "source_document_name":None if document is None else document.file_name,
            "source_documents":[{"id":doc_id,"name":documents[doc_id].file_name} for doc_id in document_ids if doc_id in documents],
            "document_count":len(document_ids),
            "source_document_ids":document_ids,
            "source_documents":[{"id":doc_id,"file_name":documents[doc_id].file_name} for doc_id in document_ids if doc_id in documents],
            "contract":None if contract is None else {
                "provider_name":contract.provider_name,
                "renewal_date":None if contract.renewal_date is None else str(contract.renewal_date),
                "cancellation_notice_days":contract.cancellation_notice_days,
                "early_exit_penalty":_d(contract.early_exit_penalty),
                "evidence_status":contract.evidence_status,
            },
            "coverages":[{
                "id":f.id,"coverage_type":f.coverage_type,"limit_amount":_d(f.limit_amount),
                "deductible":_d(f.deductible),"confidence":str(f.confidence),"user_verified":f.user_verified,
                "source_page":f.source_page,
            } for f in row_coverage],
        })

    # Insurance documents that cannot yet project to a policy are first-class missing data.
    insurance_docs=[d for d in documents.values() if d.document_type=="insurance"]
    projected_doc_ids={doc_id for ids in source_by_policy.values() for doc_id in ids}
    for document in insurance_docs:
        if document.id not in projected_doc_ids:
            missing.append({"field":"annual_cost","label":"Prima/coste de la póliza","policy_id":None,"document_id":document.id,"why":"Este documento no ha podido generar una póliza porque falta un coste confirmado. Complétalo en Documentos."})

    linked=[]
    facts=session.scalars(select(ExtractedFact).where(
        ExtractedFact.fact_type=="linked_product",
        ExtractedFact.status=="confirmed",
        ExtractedFact.user_verified.is_(True),
    )).all()
    for fact in facts:
        doc=documents.get(fact.document_id);payload=_payload(fact)
        linked.append({
            "document_id":fact.document_id,
            "document_name":None if doc is None else doc.file_name,
            "key":fact.key,
            "value":payload.get("value"),
            "page":fact.source_page,
        })

    requirements_count=len(gaps)+len(covered)
    issues=[]
    if gaps:issues.append({"code":"coverage_gaps","severity":"high","title":"Hay coberturas requeridas sin acreditar","detail":f"{len(gaps)} requisito(s) no están cubiertos por hechos verificados."})
    if overlaps:issues.append({"code":"coverage_overlap","severity":"medium","title":"Hay coberturas potencialmente duplicadas","detail":f"{len(overlaps)} coincidencia(s) entre pólizas distintas requieren revisión antes de concluir que sobra una cobertura."})
    if missing:issues.append({"code":"missing_evidence","severity":"medium","title":"Faltan datos contractuales para cerrar el análisis","detail":f"{len(missing)} campo(s) pueden completarse en los documentos originales sin crear una fuente paralela."})
    if linked:issues.append({"code":"linked_products","severity":"info","title":"Hay productos vinculados que afectan a otras decisiones","detail":"No conviene cancelar una póliza vinculada sin comprobar el efecto sobre hipoteca u otros contratos."})

    coverage_days=365
    first_tx=session.scalar(select(Transaction.booking_date).order_by(Transaction.booking_date.asc()).limit(1))
    if first_tx:
        coverage_days=max(1,min(365,(today-first_tx).days+1))
    spend_reconciliation={
        "period_start":str(start),"period_end":str(today),"data_coverage_days":coverage_days,
        "observed_insurance_spend":str(observed_spend.quantize(Decimal("0.01"))),
        "documented_annual_premiums":str(premiums.quantize(Decimal("0.01"))),
        "difference":str((observed_spend-premiums).quantize(Decimal("0.01"))) if coverage_days>=330 else None,
        "comparison_reliable":coverage_days>=330,
        "by_merchant":[{"merchant":k,"amount":str(v.quantize(Decimal("0.01")))} for k,v in sorted(by_merchant.items(),key=lambda item:item[1],reverse=True)],
    }
    if coverage_days>=330 and premiums>0:
        delta=abs(observed_spend-premiums)/premiums
        if delta>Decimal("0.15"):
            issues.append({"code":"spend_mismatch","severity":"medium","title":"Lo pagado no cuadra con las primas documentadas","detail":"Revisa si falta categorizar algún recibo, ha cambiado una prima o existe una póliza/documento pendiente."})

    if not policies_list:
        status="insufficient_data";summary="No hay pólizas documentadas y confirmadas suficientes para emitir un veredicto."
    elif gaps:
        status="review_required";summary="Hay al menos una cobertura requerida sin acreditar; conviene resolver esos huecos antes de valorar cambios de póliza."
    elif overlaps or any(x["code"]=="spend_mismatch" for x in issues):
        status="review_required";summary="Las pólizas están estructuradas, pero hay duplicidades o diferencias de coste que conviene conciliar antes de decidir."
    elif missing or requirements_count==0:
        status="partial";summary="Los datos disponibles son coherentes, pero faltan campos o criterios de cobertura para cerrar un veredicto completo."
    else:
        status="consistent";summary="Con los requisitos definidos y la evidencia confirmada, no se detectan huecos ni duplicidades materiales pendientes."

    result={
        "status":status,
        "summary":summary,
        "source_of_truth":"document_evidence",
        "policies":policy_rows,
        "coverage":{"verified":len([f for f in coverage if f.user_verified]),"requirements":requirements_count,"gaps":gaps,"covered":covered,"overlaps":[{"id":o.id,"coverage_type":o.coverage_type,"left_id":o.left_coverage_fact_id,"right_id":o.right_coverage_fact_id,"overlap_type":o.overlap_type,"confidence":str(o.confidence)} for o in overlaps]},
        "finances":{
            "income_last_365_days":str(income.quantize(Decimal("0.01"))),
            "expenses_last_365_days":str(expenses.quantize(Decimal("0.01"))),
            "savings_last_365_days":str(flow["savings"].quantize(Decimal("0.01"))),
            "documented_annual_premiums":str(premiums.quantize(Decimal("0.01"))),
            "premium_share_of_income":None if premium_share is None else str(premium_share.quantize(Decimal("0.0001"))),
            "spend_reconciliation":spend_reconciliation,
        },
        "linked_products":linked,
        "missing_information":missing,
        "issues":issues,
        "ai":None,
    }

    ai=ai_status()
    if use_ai and ai.get("chat_ready"):
        prompt="""Analiza SOLO este JSON de seguros ya calculado por Financito. Devuelve JSON con:
plain_summary (2-4 frases), priorities (array de strings), questions (array de strings).
No recomiendes cancelar, contratar ni cambiar una póliza si los datos no demuestran equivalencia de coberturas.
No inventes datos, requisitos legales, precios de mercado ni efectos de productos vinculados. Si falta evidencia, conviértela en pregunta.
JSON:
"""+json.dumps(result,ensure_ascii=False,default=str)
        try:
            generated=generate_json(prompt,timeout=180)
            result["ai"]={
                "plain_summary":str(generated.get("plain_summary") or ""),
                "priorities":generated.get("priorities") if isinstance(generated.get("priorities"),list) else [],
                "questions":generated.get("questions") if isinstance(generated.get("questions"),list) else [],
                "model":ai.get("configured_model"),
            }
        except Exception as exc:
            result["ai"]={"error":str(exc),"model":ai.get("configured_model")}
    return result
