from __future__ import annotations

from datetime import date,datetime,timezone
from decimal import Decimal,ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Category,Mortgage,Transaction
from ..models_extended import CorporateAction,LotDisposal,TaxProfile,Trade

Q=Decimal("0.01")
RULES_VERSION="es-irpf-2026-v1"

# Escala conjunta de la base del ahorro vigente desde 2025.
SAVINGS_SCALE=[
    (Decimal("6000"),Decimal("0.19")),
    (Decimal("50000"),Decimal("0.21")),
    (Decimal("200000"),Decimal("0.23")),
    (Decimal("300000"),Decimal("0.27")),
    (None,Decimal("0.30")),
]
# Escala estatal general (la cuota autonómica se calcula por separado).
STATE_GENERAL_SCALE=[
    (Decimal("12450"),Decimal("0.095")),
    (Decimal("20200"),Decimal("0.12")),
    (Decimal("35200"),Decimal("0.15")),
    (Decimal("60000"),Decimal("0.185")),
    (Decimal("300000"),Decimal("0.225")),
    (None,Decimal("0.24")),
]
MADRID_GENERAL_SCALE=[
    (Decimal("13362.22"),Decimal("0.085")),
    (Decimal("19004.63"),Decimal("0.107")),
    (Decimal("35425.68"),Decimal("0.128")),
    (Decimal("57320.40"),Decimal("0.174")),
    (None,Decimal("0.205")),
]
STATE_CHILD_MINIMUMS=[Decimal("2400"),Decimal("2700"),Decimal("4000"),Decimal("4500")]
MADRID_CHILD_MINIMUMS=[Decimal("2575.85"),Decimal("2897.83"),Decimal("4400"),Decimal("4950")]

NORMATIVE_SOURCES=[
    {
        "name":"Ley 35/2006 del IRPF (texto consolidado)",
        "url":"https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764",
        "scope":"escala estatal y base del ahorro",
    },
    {
        "name":"Tributos cedidos de la Comunidad de Madrid (texto consolidado)",
        "url":"https://www.boe.es/buscar/act.php?id=BOCM-m-2010-90068",
        "scope":"escala y mínimos autonómicos de Madrid",
    },
]

def _money(value:Decimal)->str:
    return str(value.quantize(Q,rounding=ROUND_HALF_UP))

def _progressive(base:Decimal,scale:list[tuple[Decimal|None,Decimal]])->Decimal:
    base=max(Decimal("0"),base)
    lower=Decimal("0");tax=Decimal("0")
    for upper,rate in scale:
        if upper is None:
            tax+=(base-lower)*rate if base>lower else Decimal("0")
            break
        taxable=min(base,upper)-lower
        if taxable>0:tax+=taxable*rate
        if base<=upper:break
        lower=upper
    return tax

def _child_minimum(count:int,under_three:int,regional:bool)->Decimal:
    amounts=MADRID_CHILD_MINIMUMS if regional else STATE_CHILD_MINIMUMS
    total=Decimal("0")
    for i in range(max(0,count)):
        total+=amounts[min(i,len(amounts)-1)]
    total+=Decimal("3005.16" if regional else "2800")*Decimal(max(0,min(under_three,count)))
    # En tributación individual, cuando ambos progenitores tienen derecho al mínimo,
    # el reparto habitual es por mitades. Lo dejamos como supuesto explícito.
    return total*Decimal("0.5")

def get_profile(session:Session,jurisdiction:str,tax_year:int)->TaxProfile|None:
    return session.scalar(select(TaxProfile).where(TaxProfile.jurisdiction==jurisdiction,TaxProfile.tax_year==tax_year))

def upsert_profile(session:Session,values:dict)->TaxProfile:
    jurisdiction=str(values.get("jurisdiction") or "ES").upper()
    tax_year=int(values["tax_year"])
    row=get_profile(session,jurisdiction,tax_year)
    if row is None:
        row=TaxProfile(jurisdiction=jurisdiction,tax_year=tax_year)
        session.add(row)
    for key,value in values.items():
        if key in {"jurisdiction","tax_year"}:continue
        if hasattr(row,key):setattr(row,key,value)
    session.flush()
    return row

def profile_dict(row:TaxProfile|None,jurisdiction:str,tax_year:int)->dict:
    fields=[
        "autonomous_community","filing_status","adults","dependent_children","children_under_three",
        "primary_residence","employment_income","social_security_contributions",
        "employment_deductible_expenses","tax_withholdings","interest_income","other_general_income",
        "carried_forward_savings_losses","pension_contributions",
    ]
    if row is None:
        return {"jurisdiction":jurisdiction,"tax_year":tax_year,**{k:(1 if k=="adults" else 0 if k in {"dependent_children","children_under_three","interest_income","other_general_income","carried_forward_savings_losses","pension_contributions"} else None) for k in fields}}
    out={"jurisdiction":row.jurisdiction,"tax_year":row.tax_year}
    for key in fields:
        value=getattr(row,key)
        out[key]=str(value) if isinstance(value,Decimal) else value
    return out

def _year_data(session:Session,tax_year:int)->dict:
    start=datetime(tax_year,1,1,tzinfo=timezone.utc);end=datetime(tax_year+1,1,1,tzinfo=timezone.utc)
    realized_rows=session.execute(
        select(LotDisposal.realized_pnl).join(Trade,Trade.id==LotDisposal.trade_id).where(Trade.executed_at>=start,Trade.executed_at<end)
    ).scalars().all()
    realized=sum(realized_rows,Decimal("0"))

    dividends=sum(session.scalars(select(CorporateAction.value).where(
        CorporateAction.action_type=="dividend",
        CorporateAction.effective_date>=date(tax_year,1,1),
        CorporateAction.effective_date<=date(tax_year,12,31),
    )).all(),Decimal("0"))

    salary_category=session.scalar(select(Category).where(Category.system_key=="salary"))
    salary=Decimal("0")
    if salary_category:
        salary=sum(session.scalars(select(Transaction.amount).where(
            Transaction.category_id==salary_category.id,
            Transaction.amount>0,
            Transaction.booking_date>=date(tax_year,1,1),
            Transaction.booking_date<=date(tax_year,12,31),
        )).all(),Decimal("0"))
    return {
        "realized_pnl":realized,
        "dividends":dividends,
        "salary_detected":salary,
        "mortgages":session.scalars(select(Mortgage)).all(),
    }

def estimate(session:Session,jurisdiction:str,tax_year:int)->dict:
    jurisdiction=jurisdiction.upper()
    profile=get_profile(session,jurisdiction,tax_year)
    pdata=profile_dict(profile,jurisdiction,tax_year)
    observed=_year_data(session,tax_year)

    employment=Decimal(str(pdata["employment_income"])) if pdata.get("employment_income") not in {None,""} else observed["salary_detected"]
    employment_source="perfil fiscal" if pdata.get("employment_income") not in {None,""} else ("nóminas categorizadas" if observed["salary_detected"]>0 else "pendiente")
    social=None if pdata.get("social_security_contributions") is None else Decimal(str(pdata["social_security_contributions"]))
    work_exp=None if pdata.get("employment_deductible_expenses") is None else Decimal(str(pdata["employment_deductible_expenses"]))
    withholdings=None if pdata.get("tax_withholdings") is None else Decimal(str(pdata["tax_withholdings"]))
    interest=Decimal(str(pdata.get("interest_income") or "0"))
    other_general=Decimal(str(pdata.get("other_general_income") or "0"))
    losses=Decimal(str(pdata.get("carried_forward_savings_losses") or "0"))
    pensions=Decimal(str(pdata.get("pension_contributions") or "0"))

    savings_base=max(Decimal("0"),observed["realized_pnl"]+observed["dividends"]+interest-losses)
    savings_tax=_progressive(savings_base,SAVINGS_SCALE)

    missing=[]
    def need(field,label,why):
        missing.append({"field":field,"label":label,"why":why})
    if not pdata.get("autonomous_community"):need("autonomous_community","Comunidad autónoma","Es necesaria para la escala autonómica del IRPF.")
    if not pdata.get("filing_status"):need("filing_status","Tipo de declaración","Indica si la estimación será individual o conjunta.")
    if employment<=0:need("employment_income","Rendimientos del trabajo","No se han detectado nóminas suficientes para calcular la base general.")
    if social is None:need("social_security_contributions","Cotizaciones a la Seguridad Social","Reducen el rendimiento neto del trabajo.")
    if work_exp is None:need("employment_deductible_expenses","Gastos deducibles del trabajo","Evita asumir automáticamente un importe que podría no corresponder a tu caso.")
    if withholdings is None:need("tax_withholdings","Retenciones soportadas","Son necesarias para estimar un posible resultado a pagar o devolver.")
    if pdata.get("primary_residence") is None:need("primary_residence","Vivienda habitual","Permite decidir qué deducciones o datos de vivienda pueden ser relevantes.")

    community=(pdata.get("autonomous_community") or "").strip().lower()
    madrid=community in {"madrid","comunidad de madrid"}
    regional_supported=madrid
    if pdata.get("autonomous_community") and not regional_supported:
        need("regional_rules","Reglas autonómicas","La primera versión normativa automatizada incluye Madrid; para otra comunidad no se inventa la cuota autonómica.")

    general_base=None;state_general_tax=None;regional_general_tax=None
    if employment>0 and social is not None and work_exp is not None:
        general_base=max(Decimal("0"),employment+other_general-social-work_exp-pensions)
        children=int(pdata.get("dependent_children") or 0);under3=int(pdata.get("children_under_three") or 0)
        state_minimum=Decimal("5550")+_child_minimum(children,under3,False)
        state_general_tax=max(Decimal("0"),_progressive(general_base,STATE_GENERAL_SCALE)-_progressive(min(general_base,state_minimum),STATE_GENERAL_SCALE))
        if madrid:
            madrid_minimum=Decimal("5956.65")+_child_minimum(children,under3,True)
            regional_general_tax=max(Decimal("0"),_progressive(general_base,MADRID_GENERAL_SCALE)-_progressive(min(general_base,madrid_minimum),MADRID_GENERAL_SCALE))

    total_tax=None
    if state_general_tax is not None and regional_general_tax is not None:
        total_tax=state_general_tax+regional_general_tax+savings_tax
    estimated_balance=None if total_tax is None or withholdings is None else total_tax-withholdings

    status="complete_estimate" if total_tax is not None and withholdings is not None and not any(x["field"]=="regional_rules" for x in missing) else "partial_estimate"
    return {
        "jurisdiction":jurisdiction,
        "tax_year":tax_year,
        "rules_version":RULES_VERSION,
        "status":status,
        "profile":pdata,
        "known_information":{
            "employment_income":_money(employment),"employment_income_source":employment_source,
            "realized_investment_pnl":_money(observed["realized_pnl"]),
            "dividends":_money(observed["dividends"]),
            "mortgages_detected":len(observed["mortgages"]),
        },
        "missing_information":missing,
        "calculation":{
            "general_base":None if general_base is None else _money(general_base),
            "state_general_tax":None if state_general_tax is None else _money(state_general_tax),
            "regional_general_tax":None if regional_general_tax is None else _money(regional_general_tax),
            "regional_rules_supported":regional_supported,
            "savings_base":_money(savings_base),
            "savings_tax":_money(savings_tax),
            "estimated_total_tax":None if total_tax is None else _money(total_tax),
            "withholdings":None if withholdings is None else _money(withholdings),
            "estimated_balance":None if estimated_balance is None else _money(estimated_balance),
        },
        "assumptions":[
            "La base del ahorro aplica la escala conjunta vigente y no modela todavía todos los límites de compensación entre rendimientos y ganancias/pérdidas.",
            "El mínimo por descendientes se reparte al 50 % en esta estimación individual; confirma el reparto aplicable a tu unidad familiar.",
            "Aportaciones a pensiones y gastos del trabajo se usan como datos declarados por el usuario; Financito no presume límites o deducciones no confirmados.",
            "La estimación no sustituye al cálculo oficial de la AEAT ni a asesoramiento fiscal profesional.",
        ],
        "normative_sources":NORMATIVE_SOURCES,
    }
