from __future__ import annotations

from collections import defaultdict
from datetime import date,datetime,timedelta,timezone
from decimal import Decimal
from statistics import median

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Account,ActionItem,Budget,Category,Commitment,Contract,ExtractedFact,FinancialGoal,Mortgage,Transaction
from ..models_extended import Liability
from ..models_analytics import RecurringPreference
from .calendar import events as calendar_events
from .financial_analytics import cash_flow,category_spending,essential_monthly_average,spending_structure
from .forecast import forecast


CENT=Decimal("0.01")


def _account_balance(row:Account)->Decimal:
    return row.available_balance if row.available_balance is not None else row.current_balance


def _scope_accounts(session:Session,account_id:str|None=None,account_type:str|None=None)->list[Account]:
    stmt=select(Account)
    if account_id:
        stmt=stmt.where(Account.id==account_id)
    elif account_type:
        stmt=stmt.where(Account.account_type==account_type)
    return list(session.scalars(stmt).all())


def _goal_allocations(session:Session,account_ids:set[str]|None=None)->tuple[Decimal,Decimal]:
    stmt=select(FinancialGoal).where(FinancialGoal.status=="active")
    if account_ids is not None:
        stmt=stmt.where(FinancialGoal.account_id.in_(account_ids))
    goals=session.scalars(stmt).all()
    reserved=sum((g.allocated_amount or Decimal("0") for g in goals),Decimal("0"))
    emergency=sum((g.allocated_amount or Decimal("0") for g in goals if g.goal_type=="emergency_fund"),Decimal("0"))
    return reserved,emergency


def _predict_expected_incomes(
    session:Session,as_of:date,account_ids:set[str]|None=None,horizon_days:int=45,
)->list[dict]:
    """Detect monthly recurring positive cash flows such as salary or pension.

    Refunds and transfers are excluded. Each recurring source is projected once
    to its next expected occurrence so money already received is never added a
    second time to current liquidity.
    """
    start=as_of-timedelta(days=240)
    stmt=select(Transaction).where(
        Transaction.booking_date>=start,
        Transaction.booking_date<=as_of,
        Transaction.amount>0,
        Transaction.is_internal_transfer.is_(False),
    )
    if account_ids is not None:
        stmt=stmt.where(Transaction.account_id.in_(account_ids))
    categories={c.id:c for c in session.scalars(select(Category)).all()}
    groups=defaultdict(list)
    for tx in session.scalars(stmt).all():
        category=categories.get(tx.category_id or "")
        if category and category.system_key in {"refunds","internal_transfer"}:
            continue
        key=(tx.merchant_normalized or tx.description_normalized or tx.description_raw or "").strip().lower()
        if not key:
            continue
        groups[key].append(tx)
    candidates=[]
    for key,items in groups.items():
        ordered=sorted(items,key=lambda x:x.booking_date)
        unique_dates=[]
        for tx in ordered:
            if not unique_dates or tx.booking_date!=unique_dates[-1]:
                unique_dates.append(tx.booking_date)
        if len(unique_dates)<2:
            continue
        gaps=[(unique_dates[i]-unique_dates[i-1]).days for i in range(1,len(unique_dates))]
        gap=int(round(median(gaps)))
        if gap<20 or gap>40:
            continue
        amounts=[tx.amount for tx in ordered[-4:]]
        expected=Decimal(str(median(amounts))).quantize(CENT)
        next_date=unique_dates[-1]+timedelta(days=gap)
        guard=0
        while next_date<=as_of and guard<12:
            next_date+=timedelta(days=gap);guard+=1
        if next_date>as_of+timedelta(days=horizon_days):
            continue
        count=len(unique_dates)
        confidence=Decimal("0.90") if count>=5 else Decimal("0.85") if count>=4 else Decimal("0.75") if count>=3 else Decimal("0.70")
        last_date=unique_dates[-1]
        candidates.append({
            "date":str(next_date),"amount":str(expected),"label":key,
            "confidence":str(confidence),
            "basis":f"Patrón de ingreso mensual detectado en {count} movimientos",
            "occurrences":count,
            "last_received_date":str(last_date),
            "received_this_month":last_date.year==as_of.year and last_date.month==as_of.month,
        })
    return sorted(candidates,key=lambda x:(x["date"],-Decimal(x["amount"])))


def _predict_next_income(
    session:Session,as_of:date,account_ids:set[str]|None=None
)->dict|None:
    candidates=_predict_expected_incomes(session,as_of,account_ids)
    if not candidates:
        return None
    # Prefer the strongest cash-flow source (normally salary/pension) instead of
    # a tiny earlier monthly credit that would shorten the planning horizon.
    return max(candidates,key=lambda x:(Decimal(x["amount"]),int(x["occurrences"])))


def _budget_rows(
    session:Session,as_of:date,account_id:str|None=None,account_type:str|None=None
)->list[dict]:
    stmt=select(Budget)
    if account_id:
        stmt=stmt.where(Budget.account_id==account_id)
    elif account_type:
        ids=select(Account.id).where(Account.account_type==account_type)
        stmt=stmt.where(Budget.account_id.in_(ids))
    else:
        stmt=stmt.where(Budget.account_id.is_(None))
    categories={c.id:c for c in session.scalars(select(Category)).all()}
    cache={}
    rows=[]
    for b in session.scalars(stmt).all():
        start=date(as_of.year,1,1) if b.period_type=="annual" else as_of.replace(day=1)
        scope_id=b.account_id
        key=(start,scope_id)
        if key not in cache:
            cache[key]={x["category_id"]:x["amount"] for x in category_spending(session,start,as_of,scope_id,None)}
        actual=cache[key].get(b.category_id,Decimal("0"))
        category=categories.get(b.category_id)
        utilization=Decimal("0") if b.amount<=0 else actual/b.amount
        rows.append({
            "id":b.id,"category_id":b.category_id,
            "category":category.name if category else "Categoría",
            "system_key":category.system_key if category else "other",
            "account_id":b.account_id,
            "scope":"account" if b.account_id else "household",
            "period_type":b.period_type,"budget":str(b.amount),
            "actual":str(actual.quantize(CENT)),
            "remaining":str((b.amount-actual).quantize(CENT)),
            "utilization":str(utilization.quantize(Decimal("0.0001"))),
            "alert_threshold":str(b.alert_threshold),"currency":b.currency,
        })
    return rows


def _goal_alerts(session:Session,essential_monthly:Decimal)->list[dict]:
    out=[]
    today=date.today()
    for g in session.scalars(select(FinancialGoal).where(FinancialGoal.status=="active")).all():
        current=g.allocated_amount or Decimal("0") if g.account_id else g.current_amount
        target=(
            essential_monthly*Decimal(g.emergency_months_target or 6)
            if g.goal_type=="emergency_fund" and essential_monthly>0
            else g.target_amount
        )
        if not g.target_date or current>=target:
            continue
        months=max(1,(g.target_date.year-today.year)*12+g.target_date.month-today.month+(1 if g.target_date.day>today.day else 0))
        required=max(Decimal("0"),target-current)/Decimal(months)
        planned=g.planned_monthly_contribution or Decimal("0")
        if planned+Decimal("0.01")<required:
            out.append({
                "id":"goal:"+g.id,"kind":"goal","severity":"medium",
                "title":"Objetivo fuera de ritmo · "+g.name,
                "detail":f"Aportación prevista {planned.quantize(CENT)} €; necesaria aproximada {required.quantize(CENT)} €/mes.",
                "action_path":"/goals/","source_id":g.id,
            })
    return out


def useful_alerts(
    session:Session,as_of:date,account_id:str|None=None,account_type:str|None=None,
    essential_monthly:Decimal|None=None,
)->list[dict]:
    accounts=_scope_accounts(session,account_id,account_type)
    ids={a.id for a in accounts}
    alerts=[]
    for b in _budget_rows(session,as_of,account_id,account_type):
        util=Decimal(b["utilization"])
        threshold=Decimal(b["alert_threshold"])
        if util>=threshold:
            alerts.append({
                "id":"budget:"+b["id"],"kind":"budget",
                "severity":"high" if util>1 else "medium",
                "title":("Presupuesto superado · " if util>1 else "Presupuesto cerca del límite · ")+b["category"],
                "detail":f'{b["actual"]} € de {b["budget"]} €.',
                "action_path":"/budgets/","source_id":b["id"],
            })
    horizon=as_of+timedelta(days=30)
    for c in session.scalars(select(Contract).where(Contract.renewal_date>=as_of,Contract.renewal_date<=horizon)).all():
        alerts.append({
            "id":"renewal:"+c.id,"kind":"insurance_or_contract_renewal","severity":"medium",
            "title":"Renovación próxima · "+c.provider_name,
            "detail":f"Renueva el {c.renewal_date}. Revisa coste, cobertura y preaviso antes de esa fecha.",
            "action_path":"/insurance/" if "insurance" in (c.contract_type or "").lower() or "seguro" in (c.contract_type or "").lower() else "/contracts/","source_id":c.id,
        })
    for account in accounts:
        due=sum((c.amount for c in session.scalars(select(Commitment).where(
            Commitment.status=="active",Commitment.account_id==account.id,
            Commitment.due_date>=as_of,Commitment.due_date<=horizon,Commitment.mandatory.is_(True),
        )).all()),Decimal("0"))
        balance=_account_balance(account)
        if due>balance:
            alerts.append({
                "id":"account_shortfall:"+account.id,"kind":"account_shortfall","severity":"high",
                "title":"La cuenta puede quedarse corta · "+account.name,
                "detail":f"Saldo disponible {balance.quantize(CENT)} € frente a {due.quantize(CENT)} € de compromisos conocidos en 30 días.",
                "action_path":"/forecast/","source_id":account.id,
            })
    essential=essential_monthly if essential_monthly is not None else essential_monthly_average(session,as_of,account_id,account_type)
    alerts.extend(_goal_alerts(session,essential))
    for action in session.scalars(select(ActionItem).where(
        ActionItem.action_type=="recurring_price_increase",
        ActionItem.status.in_(["pending","in_progress"]),
    ).order_by(ActionItem.created_at.desc()).limit(20)).all():
        alerts.append({
            "id":"price_increase:"+action.id,"kind":"recurring_price_increase","severity":"medium",
            "title":action.title,
            "detail":action.notes or "El último cargo recurrente se ha separado de su importe histórico habitual.",
            "action_path":"/analytics/","source_id":action.id,
        })
    pending=int(session.query(ExtractedFact).filter(
        ExtractedFact.user_verified.is_(False),
        ExtractedFact.status.in_(["inferred","ambiguous","conflicting"]),
    ).count())
    if pending:
        alerts.append({
            "id":"evidence_pending","kind":"data_quality","severity":"low",
            "title":"Documentación pendiente de confirmar",
            "detail":f"Hay {pending} dato(s) contractual(es) encontrados que aún necesitan confirmación.",
            "action_path":"/documents/","source_id":None,
        })
    return sorted(alerts,key=lambda x:{"high":0,"medium":1,"low":2}.get(x["severity"],3))


def period_changes(
    session:Session,start:date,end:date,account_id:str|None=None,account_type:str|None=None
)->dict:
    days=(end-start).days+1
    previous_end=start-timedelta(days=1)
    previous_start=previous_end-timedelta(days=days-1)
    current=cash_flow(session,start,end,account_id,account_type)
    previous=cash_flow(session,previous_start,previous_end,account_id,account_type)
    current_categories={x["category"]:x["amount"] for x in category_spending(session,start,end,account_id,account_type)}
    previous_categories={x["category"]:x["amount"] for x in category_spending(session,previous_start,previous_end,account_id,account_type)}
    categories=[]
    for name in set(current_categories)|set(previous_categories):
        cur=current_categories.get(name,Decimal("0"));prev=previous_categories.get(name,Decimal("0"))
        delta=cur-prev
        if delta:
            pct=None if prev==0 else delta/prev*Decimal("100")
            categories.append({"category":name,"current":str(cur),"previous":str(prev),"delta":str(delta.quantize(CENT)),"delta_pct":None if pct is None else str(pct.quantize(Decimal("0.1")))})
    categories.sort(key=lambda x:abs(Decimal(x["delta"])),reverse=True)
    return {
        "current":{"start":str(start),"end":str(end)},
        "previous":{"start":str(previous_start),"end":str(previous_end)},
        "expenses_delta":str((current["expenses"]-previous["expenses"]).quantize(CENT)),
        "income_delta":str((current["income"]-previous["income"]).quantize(CENT)),
        "savings_delta":str((current["savings"]-previous["savings"]).quantize(CENT)),
        "categories":categories[:5],
    }


def _projectable_expenses(
    session:Session,start:date,end:date,account_id:str|None=None,account_type:str|None=None,
)->Decimal:
    """Real expenses excluding explicitly extraordinary outflows that should not be extrapolated."""
    if end<start:
        return Decimal("0")
    expenses=cash_flow(session,start,end,account_id,account_type)["expenses"]
    stmt=select(Transaction).where(
        Transaction.booking_date>=start,
        Transaction.booking_date<=end,
        Transaction.amount<0,
        Transaction.is_extraordinary.is_(True),
    )
    if account_id:
        stmt=stmt.where(Transaction.account_id==account_id)
    elif account_type:
        stmt=stmt.where(Transaction.account_id.in_(select(Account.id).where(Account.account_type==account_type)))
    internal_id=session.scalar(select(Category.id).where(Category.system_key=="internal_transfer"))
    extraordinary=Decimal("0")
    for tx in session.scalars(stmt).all():
        if tx.is_internal_transfer or (internal_id is not None and tx.category_id==internal_id):
            continue
        extraordinary+=-tx.amount
    return max(Decimal("0"),expenses-extraordinary).quantize(CENT)


def _selected_monthly_spending(
    session:Session,start:date,end:date,account_id:str|None=None,account_type:str|None=None
)->Decimal:
    """Normalize projectable expenses in the selected period to a 30-day rate."""
    days=max(1,(end-start).days+1)
    observed=_projectable_expenses(session,start,end,account_id,account_type)
    return (observed*Decimal("30")/Decimal(days)).quantize(CENT)


def _previous_year(value:date)->date:
    try:
        return value.replace(year=value.year-1)
    except ValueError:
        return value.replace(year=value.year-1,day=28)


def _future_spending_projection(
    session:Session,as_of:date,horizon_date:date,selected_start:date,selected_end:date,
    account_id:str|None=None,account_type:str|None=None,
)->dict:
    """Prudent near-term spend estimate using several independent local signals.

    No signal is added blindly to another: the largest credible signal becomes the
    protected amount. This avoids both double counting fixed bills and the old
    failure mode where a quiet partial month was extrapolated as if spending were
    evenly distributed across every day.
    """
    future_start=as_of+timedelta(days=1)
    horizon_days=max(0,(horizon_date-as_of).days)
    selected_days=max(1,(selected_end-selected_start).days+1)
    selected_expenses=_projectable_expenses(session,selected_start,selected_end,account_id,account_type)
    selected_monthly=(selected_expenses*Decimal("30")/Decimal(selected_days)).quantize(CENT)

    recent_start=as_of-timedelta(days=89)
    recent_days=max(1,(as_of-recent_start).days+1)
    recent_expenses=_projectable_expenses(session,recent_start,as_of,account_id,account_type)

    if horizon_days<=0:
        return {
            "protected":Decimal("0"),"selected_monthly":selected_monthly,
            "selected_estimate":Decimal("0"),"recent_estimate":Decimal("0"),
            "seasonal_estimate":Decimal("0"),"pattern_estimate":Decimal("0"),
            "known_estimate":Decimal("0"),"basis":"horizon_closed",
        }

    selected_daily=selected_expenses/Decimal(selected_days)
    recent_daily=recent_expenses/Decimal(recent_days)
    # Short current/custom periods are noisy. Shrink them towards the recent
    # 90-day pace until roughly a full month of observations is available.
    selected_weight=min(Decimal("1"),Decimal(selected_days)/Decimal("30"))
    smoothed_selected_daily=(
        selected_daily*selected_weight+recent_daily*(Decimal("1")-selected_weight)
        if recent_expenses>0 else selected_daily
    )
    selected_estimate=(smoothed_selected_daily*Decimal(horizon_days)).quantize(CENT)
    recent_estimate=(recent_daily*Decimal(horizon_days)).quantize(CENT)

    seasonal_start=_previous_year(future_start)
    seasonal_end=_previous_year(horizon_date)
    seasonal_estimate=_projectable_expenses(session,seasonal_start,seasonal_end,account_id,account_type)

    explicit=Decimal("0")
    pattern=Decimal("0")
    for event in calendar_events(session,future_start,horizon_date,account_id,account_type):
        if event.get("amount") is None:
            continue
        try:
            amount=Decimal(str(event["amount"]))
        except Exception:
            continue
        if event.get("type") in {"commitment","recurring"}:
            explicit+=amount
        elif event.get("type")=="historical_pattern":
            pattern+=amount
    known_estimate=explicit.quantize(CENT)
    pattern_estimate=pattern.quantize(CENT)

    signals={
        "selected_period":selected_estimate,
        "recent_90_days":recent_estimate,
        "same_period_last_year":seasonal_estimate,
        "known_future":known_estimate,
        "category_patterns":pattern_estimate,
    }
    basis=max(signals,key=lambda key:signals[key])
    protected=max(signals.values()).quantize(CENT)
    return {
        "protected":protected,
        "selected_monthly":selected_monthly,
        "selected_estimate":selected_estimate,
        "recent_estimate":recent_estimate,
        "seasonal_estimate":seasonal_estimate,
        "pattern_estimate":pattern_estimate,
        "known_estimate":known_estimate,
        "basis":basis,
    }


def financial_health_summary(
    session:Session,as_of:date|None=None,start:date|None=None,end:date|None=None,
    account_id:str|None=None,account_type:str|None=None,
)->dict:
    as_of=as_of or date.today()
    end=end or as_of
    start=start or end.replace(day=1)
    accounts=_scope_accounts(session,account_id,account_type)
    ids={a.id for a in accounts}
    liquidity=sum((_account_balance(a) for a in accounts),Decimal("0"))
    reserved,emergency_allocated=_goal_allocations(session,ids if (account_id or account_type) else None)
    essential_monthly=essential_monthly_average(session,as_of,account_id,account_type)
    income_candidates=_predict_expected_incomes(session,as_of,ids if (account_id or account_type) else None)
    next_income=_predict_next_income(session,as_of,ids if (account_id or account_type) else None)
    horizon_date=date.fromisoformat(next_income["date"]) if next_income else as_of+timedelta(days=30)
    horizon_date=min(horizon_date,as_of+timedelta(days=30))
    expected_incomes=[
        row for row in income_candidates
        if as_of<date.fromisoformat(row["date"])<=horizon_date
        and not bool(row.get("received_this_month"))
    ]
    expected_income=sum((Decimal(row["amount"]) for row in expected_incomes),Decimal("0")).quantize(CENT)
    spend_projection=_future_spending_projection(
        session,as_of,horizon_date,start,end,account_id,account_type,
    )
    selected_monthly_spending=Decimal(spend_projection["selected_monthly"])
    selected_spending_floor=Decimal(spend_projection["selected_estimate"])
    known=Decimal(spend_projection["known_estimate"])
    obligations=Decimal(spend_projection["protected"])
    minimum_buffer=essential_monthly
    buffer_gap=max(Decimal("0"),minimum_buffer-emergency_allocated)
    free_after_goals=max(Decimal("0"),liquidity-reserved)
    projected_resources=free_after_goals+expected_income
    safe=max(Decimal("0"),projected_resources-obligations-buffer_gap).quantize(CENT)
    coverage=None if essential_monthly<=0 else (emergency_allocated/essential_monthly)
    liquidity_coverage=None if essential_monthly<=0 else (liquidity/essential_monthly)
    selected=cash_flow(session,start,end,account_id,account_type)
    historical_outcome=None
    if end<as_of:
        historical_forecast=forecast(session,start,end,account_id,account_type)
        income_variance=(selected["income"]-historical_forecast.predicted_income).quantize(CENT)
        expense_variance=(selected["expenses"]-historical_forecast.predicted_expenses).quantize(CENT)
        savings_variance=(selected["savings"]-historical_forecast.predicted_savings).quantize(CENT)
        historical_outcome={
            "actual_income":str(selected["income"]),
            "actual_expenses":str(selected["expenses"]),
            "actual_savings":str(selected["savings"]),
            "forecast_income":str(historical_forecast.predicted_income),
            "forecast_expenses":str(historical_forecast.predicted_expenses),
            "forecast_savings":str(historical_forecast.predicted_savings),
            "income_variance":str(income_variance),
            "expense_variance":str(expense_variance),
            "savings_variance":str(savings_variance),
            "status":"above" if savings_variance>Decimal("1") else "below" if savings_variance<Decimal("-1") else "on_track",
            "forecast_kind":"reconstructed",
            "model_version":historical_forecast.model_version,
            "baseline_start":str(historical_forecast.baseline_start),
            "baseline_end":str(historical_forecast.baseline_end),
            "note":"Previsión reconstruida con el histórico disponible anterior al periodo; no es una captura de forecast guardada en aquel momento.",
        }
    trailing=cash_flow(session,as_of-timedelta(days=89),as_of,account_id,account_type)
    avg_income=trailing["income"]/Decimal("3")
    mortgages=session.scalars(select(Mortgage).where(*( [Mortgage.account_id.in_(ids)] if (account_id or account_type) else [] ))).all()
    debt_service=sum((m.monthly_payment for m in mortgages),Decimal("0"))
    debt_ratio=None if avg_income<=0 else debt_service/avg_income
    liabilities=session.scalars(select(Liability)).all()
    total_debt=sum((m.remaining_principal for m in mortgages),Decimal("0"))+sum((x.outstanding_amount for x in liabilities),Decimal("0"))

    def indicator(status,title,value,detail,rule):
        return {"status":status,"title":title,"value":value,"detail":detail,"rule":rule}
    liq_status="unknown" if liquidity_coverage is None else "good" if liquidity_coverage>=3 else "warning" if liquidity_coverage>=1 else "risk"
    rate=selected["savings_rate"]
    save_status="unknown" if rate is None else "good" if rate>=Decimal("0.20") else "warning" if rate>=0 else "risk"
    debt_status="unknown" if debt_ratio is None else "good" if debt_ratio<=Decimal("0.30") else "warning" if debt_ratio<=Decimal("0.40") else "risk"
    commit_status="good" if safe>0 else "warning" if free_after_goals>=obligations else "risk"
    indicators=[
        indicator(liq_status,"Liquidez",None if liquidity_coverage is None else f"{liquidity_coverage.quantize(Decimal('0.1'))} meses",f"{liquidity.quantize(CENT)} € disponibles y {essential_monthly.quantize(CENT)} €/mes de gasto esencial.","Verde ≥ 3 meses; ámbar 1–3; rojo < 1."),
        indicator(save_status,"Ahorro",str(selected["savings"]),None if rate is None else f"{(rate*100).quantize(Decimal('0.1'))}% de los ingresos del periodo.","Verde ≥ 20%; ámbar entre 0% y 20%; rojo si gastas más de lo que ingresas."),
        indicator(debt_status,"Deuda",str(total_debt),None if debt_ratio is None else f"Cuotas hipotecarias equivalen al {(debt_ratio*100).quantize(Decimal('0.1'))}% del ingreso mensual reciente.","Verde ≤ 30%; ámbar 30–40%; rojo > 40%."),
        indicator(commit_status,"Compromisos",str(obligations.quantize(CENT)),f"Obligaciones estimadas hasta {horizon_date}. Disponible para gastar: {safe} €.","Rojo si el dinero no reservado no cubre los compromisos previstos."),
    ]
    latest_tx=session.scalar(select(Transaction.booking_date).order_by(Transaction.booking_date.desc()).limit(1))
    return {
        "generated_at":datetime.now(timezone.utc).isoformat(),
        "safe_to_spend":{
            "mode":"historical" if end<as_of else "current",
            "amount":str(safe),"liquidity":str(liquidity.quantize(CENT)),
            "reserved_goals":str(reserved.quantize(CENT)),"obligations_until_next_income":str(obligations.quantize(CENT)),
            "expected_income_before_horizon":str(expected_income),
            "expected_incomes":expected_incomes,
            "projected_resources_after_goals":str(projected_resources.quantize(CENT)),
            "minimum_buffer":str(minimum_buffer.quantize(CENT)),"buffer_gap":str(buffer_gap.quantize(CENT)),
            "horizon_date":str(horizon_date),"next_income":next_income,
            "historical_outcome":historical_outcome,
            "selected_period_start":str(start),"selected_period_end":str(end),
            "selected_monthly_spending":str(selected_monthly_spending),
            "selected_spending_floor":str(selected_spending_floor),
            "recent_spending_floor":str(Decimal(spend_projection["recent_estimate"])),
            "seasonal_spending_floor":str(Decimal(spend_projection["seasonal_estimate"])),
            "historical_pattern_floor":str(Decimal(spend_projection["pattern_estimate"])),
            "known_future_outflows":str(known.quantize(CENT)),
            "projection_basis":str(spend_projection["basis"]),
            "projection_method":"Estimación prudente: se protege la mayor señal creíble entre periodo seleccionado, últimos 90 días, mismo tramo del año anterior, cargos futuros conocidos y patrones por categoría. Los extraordinarios marcados no se extrapolan.",
            "explanation":"Liquidez actual más ingresos recurrentes previstos antes del horizonte, menos objetivos reservados, una estimación prudente de gasto y el colchón mínimo aún no cubierto.",
        },
        "emergency_fund":{
            "essential_monthly":str(essential_monthly.quantize(CENT)),
            "allocated":str(emergency_allocated.quantize(CENT)),
            "coverage_months":None if coverage is None else str(coverage.quantize(Decimal("0.1"))),
            "minimum_buffer":str(minimum_buffer.quantize(CENT)),
        },
        "spending_structure":spending_structure(session,start,end,account_id,account_type),
        "indicators":indicators,
        "changes":period_changes(session,start,end,account_id,account_type),
        "alerts":useful_alerts(session,as_of,account_id,account_type,essential_monthly),
        "budgets":_budget_rows(session,as_of,account_id,account_type),
        "data_status":{
            "calculated_at":datetime.now(timezone.utc).isoformat(),
            "latest_transaction_date":None if latest_tx is None else str(latest_tx),
            "basis":"Calculado con movimientos, cuentas, objetivos, compromisos y evidencia guardada.",
        },
    }
