from __future__ import annotations

from calendar import monthrange
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..domain.engines import MortgageEngine
from ..models import Mortgage
from ..models_analytics import LinkedProduct
from ..models_extended import InsurancePolicy,MortgageProfileExtra
from .contractual_costs import mortgage_contract_context
from ..providers.macro import EcbMacroProvider


def _monthly_irr(principal:Decimal,payment:Decimal,months:int)->Decimal|None:
    if principal<=0 or payment<=0 or months<=0:
        return None
    zero_payment=principal/Decimal(months)
    if payment<=zero_payment:
        return Decimal("0")
    low=Decimal("0")
    high=Decimal("1")
    for _ in range(120):
        mid=(low+high)/Decimal("2")
        factor=(Decimal("1")+mid)**months
        present_value=payment*(Decimal("1")-(Decimal("1")/factor))/mid
        if present_value>principal:
            low=mid
        else:
            high=mid
    return (low+high)/Decimal("2")


def current_remaining_apr_estimate(session:Session,mortgage:Mortgage,annual_rate:Decimal|None=None)->dict:
    """Estimate the effective annual cost of the remaining mortgage cash flows.

    This is deliberately separate from the contractual/original APR (TAE). It
    uses the saved current TIN and only future recurring linked-policy premiums
    that are actually structured in Financito. Sunk origination costs are not
    charged again.
    """
    applied_rate=mortgage.nominal_rate if annual_rate is None else annual_rate
    scenario=MortgageEngine.amortization(
        mortgage.remaining_principal,
        applied_rate,
        mortgage.remaining_months,
    )
    linked_ids=list(session.scalars(select(LinkedProduct.linked_product_id).where(
        LinkedProduct.parent_product_type=="mortgage",
        LinkedProduct.parent_product_id==mortgage.id,
        LinkedProduct.linked_product_type=="insurance_policy",
    )).all())
    policies=session.scalars(select(InsurancePolicy).where(InsurancePolicy.id.in_(linked_ids))).all() if linked_ids else []
    annual_linked_cost=sum((row.annual_premium for row in policies),Decimal("0"))
    monthly_linked=(annual_linked_cost/Decimal("12")).quantize(Decimal("0.01"))
    monthly_outflow=scenario.monthly_payment+monthly_linked
    monthly_rate=_monthly_irr(mortgage.remaining_principal,monthly_outflow,mortgage.remaining_months)
    if monthly_rate is None:
        return {
            "rate":None,
            "status":"not_available",
            "nominal_rate":str(applied_rate),
            "nominal_rate":str(applied_rate),
        "monthly_payment":str(scenario.monthly_payment),
            "known_linked_annual_cost":str(annual_linked_cost.quantize(Decimal("0.01"))),
            "known_linked_monthly_cost":str(monthly_linked),
            "basis":"No se ha podido resolver la tasa efectiva de los flujos restantes.",
        }
    annual=(Decimal("1")+monthly_rate)**Decimal("12")-Decimal("1")
    return {
        "rate":str(annual.quantize(Decimal("0.000001"))),
        "status":"estimated",
        "monthly_payment":str(scenario.monthly_payment),
        "known_linked_annual_cost":str(annual_linked_cost.quantize(Decimal("0.01"))),
        "known_linked_monthly_cost":str(monthly_linked),
        "basis":(
            "Estimación sobre capital y plazo restantes, TIN vigente guardado y primas futuras de seguros "
            "vinculados conocidas. No sustituye la TAE contractual ni incorpora costes ya pagados."
        ),
    }


def rate_review_readiness(session:Session,mortgage:Mortgage)->dict:
    if mortgage.interest_type=="fixed":
        return {"status":"not_applicable","missing":[],"automatic":False}
    extra=session.scalar(select(MortgageProfileExtra).where(MortgageProfileExtra.mortgage_id==mortgage.id))
    context=mortgage_contract_context(session,mortgage.id)
    confirmed=context.get("by_key") or {}

    def pick_extra(field:str):
        return None if extra is None else getattr(extra,field)

    reference_index=pick_extra("reference_index") or (confirmed.get("reference_index") or {}).get("value")
    differential=pick_extra("differential_rate")
    if differential is None and confirmed.get("differential_rate"):
        try:differential=Decimal(str(confirmed["differential_rate"]["value"]).replace(",", "."))/Decimal("100")
        except Exception:differential=None
    review_months=pick_extra("rate_review_months") or (confirmed.get("rate_review_months") or {}).get("value")
    next_review=pick_extra("next_review_date") or (confirmed.get("next_review_date") or {}).get("value")
    lag=(confirmed.get("reference_index_lag_months") or {}).get("value")

    missing=[]
    if not reference_index:missing.append("reference_index")
    if differential is None:missing.append("differential_rate")
    if not review_months:missing.append("rate_review_months")
    if not next_review:missing.append("next_review_date")
    if lag in {None,""}:missing.append("reference_index_lag_months")

    return {
        "status":"ready" if not missing else "needs_more_data",
        "automatic":not missing,
        "missing":missing,
        "reference_index":reference_index,
        "differential_rate":None if differential is None else str(differential),
        "rate_review_months":None if not review_months else int(Decimal(str(review_months))),
        "next_review_date":None if not next_review else str(next_review),
        "reference_index_lag_months":None if lag in {None,""} else int(Decimal(str(lag))),
        "rule":(
            "La actualización automática del tipo solo puede activarse cuando la regla temporal del índice "
            "está confirmada en documentación; nunca se presupone el mes de Euríbor."
        ),
    }


def _shift_month(value:date,months:int)->date:
    index=value.year*12+(value.month-1)+months
    year,month_index=divmod(index,12)
    month=month_index+1
    return date(year,month,min(value.day,monthrange(year,month)[1]))


def _parse_iso_date(value:object)->date|None:
    if isinstance(value,date):
        return value
    try:return date.fromisoformat(str(value))
    except Exception:return None


def _ecb_euribor_12m_for_month(target:date,provider:EcbMacroProvider)->dict:
    period=f"{target.year:04d}-{target.month:02d}"
    rows=provider.series(
        "FM",
        "M.U2.EUR.RT.MM.EURIBOR1YD_.HSTA",
        start=period,
        end=period,
        last_n=None,
    )
    if not rows:
        raise RuntimeError("El BCE no devolvió Euríbor 12 meses para el mes contractual.")
    row=rows[-1]
    raw=row.get("OBS_VALUE") or row.get("Obs Value") or row.get("VALUE")
    if raw in {None,""}:
        raise RuntimeError("La serie oficial del BCE no contiene OBS_VALUE.")
    return {
        "value_percent":Decimal(str(raw)),
        "period":str(row.get("TIME_PERIOD") or row.get("Time period") or period),
        "provider":"ECB",
        "series":"FM.M.U2.EUR.RT.MM.EURIBOR1YD_.HSTA",
    }


def due_rate_review_estimate(
    session:Session,
    mortgage:Mortgage,
    as_of:date|None=None,
    provider:EcbMacroProvider|None=None,
)->dict:
    """Automatically calculate a due variable-rate review without mutating facts.

    The calculation runs only when the contract rule is complete and the review
    date has arrived. It deliberately leaves mortgage.nominal_rate/payment
    unchanged until the bank statement/document or the user confirms the result.
    """
    as_of=as_of or date.today()
    readiness=rate_review_readiness(session,mortgage)
    if readiness["status"]!="ready":
        return {**readiness,"estimate":None}
    review_date=_parse_iso_date(readiness.get("next_review_date"))
    if review_date is None:
        return {**readiness,"status":"needs_more_data","automatic":False,"missing":["next_review_date"],"estimate":None}
    if as_of<review_date:
        return {**readiness,"status":"scheduled","estimate":None}

    index_name=str(readiness.get("reference_index") or "").lower()
    if "eur" not in index_name or not any(token in index_name for token in ("12","año","ano","year")):
        return {
            **readiness,
            "status":"unsupported_index",
            "automatic":False,
            "estimate":None,
            "message":"La actualización automática está implementada de forma segura para Euríbor a 12 meses; otros índices requieren su serie oficial específica.",
        }

    lag=int(readiness["reference_index_lag_months"])
    reference_month=_shift_month(date(review_date.year,review_date.month,1),-lag)
    provider=provider or EcbMacroProvider()
    try:
        index=_ecb_euribor_12m_for_month(reference_month,provider)
    except Exception as exc:
        return {
            **readiness,
            "status":"source_unavailable",
            "estimate":None,
            "message":str(exc)[:300],
        }

    differential=Decimal(str(readiness["differential_rate"]))
    estimated_tin=(index["value_percent"]/Decimal("100")+differential).quantize(Decimal("0.000001"))
    scenario=MortgageEngine.amortization(mortgage.remaining_principal,estimated_tin,mortgage.remaining_months)
    effective=current_remaining_apr_estimate(session,mortgage,estimated_tin)
    return {
        **readiness,
        "status":"estimated_due",
        "estimate":{
            "review_date":review_date.isoformat(),
            "reference_month":reference_month.strftime("%Y-%m"),
            "reference_index_value_percent":str(index["value_percent"]),
            "reference_source":index["provider"],
            "reference_series":index["series"],
            "reference_period":index["period"],
            "estimated_nominal_rate":str(estimated_tin),
            "estimated_monthly_payment":str(scenario.monthly_payment),
            "estimated_remaining_interest":str(scenario.total_interest),
            "estimated_current_apr":effective["rate"],
            "known_linked_annual_cost":effective["known_linked_annual_cost"],
            "confirmation_required":True,
            "notice":"Cálculo automático informativo. No sustituye el TIN/cuota guardados hasta confirmar la revisión comunicada por la entidad.",
        },
    }
