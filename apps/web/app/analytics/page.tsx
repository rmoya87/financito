'use client';

import Link from 'next/link';
import {FormEvent,useMemo,useState} from 'react';
import {useMutation,useQuery,useQueryClient} from '@tanstack/react-query';
import {Bar,BarChart,CartesianGrid,Cell,Legend,Line,LineChart,ResponsiveContainer,Tooltip,XAxis,YAxis} from 'recharts';
import {apiGet,apiMutate} from '@/lib/api';
import {PageHeader} from '@/components/page-header';
import {Card} from '@/components/ui/card';
import {Money,formatNumber} from '@/components/ui/money';
import {EmptyState,ErrorState,Loading} from '@/components/ui/states';

type Rec={id:string;merchant:string;cadence:string;expected_amount:string;next_expected_date:string;confidence:string};
type Anom={
  id:string;transaction_id:string;type:string;explanation?:string;confidence:string;status:string;
  transaction?:null|{booking_date:string;description:string;merchant:string|null;amount:string;currency:string;category_id:string|null};
  baseline?:{typical_amount?:string;difference?:string;difference_pct?:string|null}
};
type Recon={issues?:{type:string;label?:string;count:number;severity:string;detail?:string;action_href?:string}[]};
type Cal={events?:{date:string;type:string;title:string;amount:string|null;entity_id:string;confidence?:string;basis?:string;category?:string}[]};
type Stress={monthly_income_after_shock:string;monthly_net:string;ending_liquidity:string;cash_runway_months:string|null;portfolio_after_shock:string};
type Overview={
  period?:{start:string;end:string};
  cash_flow?:{income:string;expenses:string;savings:string;savings_rate:string|null};
  by_category?:{category:string;amount:string}[];
  by_merchant?:{merchant:string;amount:string}[];
  fixed_variable?:{fixed:string;variable:string};
  essential_discretionary?:{essential:string;discretionary:string};
  monthly?:{period:string;income:string;expenses:string;savings:string}[];
  budget_vs_actual?:{category:string;budget:string;actual:string;variance:string}[]
};
type MonthEndAccount={id:string;name:string;institution_name:string;currency:string;current_balance:string;projected_change:string;projected_closing_balance:string;method:string};
type MonthEnd={
  as_of?:string;month_end?:string;
  projected_month_end?:{income:string;expenses:string;savings:string;total_balance:string};
  forecast_remaining?:{known_commitments:string;commitment_floor_adjustment:string};
  accuracy?:{months_evaluated:number;expense_wape:string|null;expense_accuracy:string|null;savings_mae:string|null};
  accounts?:MonthEndAccount[]
};

export default function AnalyticsPage(){
  const qc=useQueryClient();
  const recurring=useQuery({queryKey:['recurring'],queryFn:()=>apiGet<Rec[]>('/api/v1/recurring')});
  const anomalies=useQuery({queryKey:['anomalies'],queryFn:()=>apiGet<Anom[]>('/api/v1/anomalies')});
  const recon=useQuery({queryKey:['reconciliation'],queryFn:()=>apiGet<Recon>('/api/v1/reconciliation')});
  const calendar=useQuery({queryKey:['calendar'],queryFn:()=>apiGet<Cal>('/api/v1/calendar')});
  const overview=useQuery({queryKey:['analytics-overview'],queryFn:()=>apiGet<Overview>('/api/v1/analytics/overview')});
  const monthEnd=useQuery({queryKey:['month-end-forecast'],queryFn:()=>apiGet<MonthEnd>('/api/v1/forecast/month-end')});

  const refresh=useMutation({
    mutationFn:()=>apiMutate<{recurring_series:number;anomalies:number}>('/api/v1/analytics/refresh','POST'),
    onSuccess:()=>{['recurring','anomalies','analytics-overview','month-end-forecast','reconciliation','calendar'].forEach(k=>qc.invalidateQueries({queryKey:[k]}))},
  });
  const anomalyAction=useMutation({
    mutationFn:({id,status}:{id:string;status:'normal'|'ignored'|'resolved'})=>apiMutate('/api/v1/anomalies/'+id,'PATCH',{status}),
    onSuccess:()=>qc.invalidateQueries({queryKey:['anomalies']}),
  });
  const [shock,setShock]=useState({income_reduction_pct:'20',extraordinary_expense:'1000',portfolio_drop_pct:'20',months:6});
  const stress=useMutation({mutationFn:()=>apiMutate<Stress>('/api/v1/stress','POST',shock)});

  const monthly=useMemo(()=>Array.isArray(overview.data?.monthly)?overview.data!.monthly!.map(x=>({
    ...x,income:Number(x.income||0),expenses:Number(x.expenses||0),savings:Number(x.savings||0),
  })):[],[overview.data]);
  const mix=useMemo(()=>{
    const fixed=overview.data?.fixed_variable;
    const essential=overview.data?.essential_discretionary;
    if(!fixed&&!essential)return [];
    return [
      {name:'Fijo',amount:Number(fixed?.fixed||0)},
      {name:'Variable',amount:Number(fixed?.variable||0)},
      {name:'Esencial',amount:Number(essential?.essential||0)},
      {name:'Discrecional',amount:Number(essential?.discretionary||0)},
    ];
  },[overview.data]);

  const merchants=Array.isArray(overview.data?.by_merchant)?overview.data!.by_merchant!:[];
  const recurringRows=Array.isArray(recurring.data)?recurring.data:[];
  const anomalyRows=Array.isArray(anomalies.data)?anomalies.data:[];
  const issues=Array.isArray(recon.data?.issues)?recon.data!.issues!:[];
  const events=Array.isArray(calendar.data?.events)?calendar.data!.events!:[];
  const closing=monthEnd.data?.projected_month_end;
  const accounts=Array.isArray(monthEnd.data?.accounts)?monthEnd.data!.accounts!:[];
  const accuracy=monthEnd.data?.accuracy;
  const forecastRemaining=monthEnd.data?.forecast_remaining;

  const cadenceLabel=(value:string)=>({weekly:'semanal',monthly:'mensual',quarterly:'trimestral',annual:'anual'}[value]||value);
  const eventTypeLabel=(value:string)=>({
    commitment:'Compromiso conocido',renewal:'Renovación contractual',goal:'Objetivo',
    recurring:'Recurrente detectado',historical_pattern:'Previsión por histórico',
  }[value]||value);

  return <>
    <PageHeader title="Análisis y resiliencia" description="Ingresos, gasto, ahorro, previsiones y patrones. Si una fuente falla, el resto de la página sigue disponible."/>

    <div className="mb-4 flex flex-wrap gap-2">
      <button className="fin-button" onClick={()=>refresh.mutate()} disabled={refresh.isPending}>{refresh.isPending?'Recalculando…':'Recalcular patrones'}</button>
      <Link href="/cost-centers/" className="fin-button secondary">Organizar por centros de coste</Link>
    </div>
    {refresh.error&&<div className="mb-4"><ErrorState error={refresh.error}/></div>}

    <div className="grid gap-4 xl:grid-cols-2">
      <Card className="xl:col-span-2">
        <h2 className="font-bold">Ingresos, gasto y ahorro</h2>
        {overview.isLoading?<div className="mt-4"><Loading/></div>:overview.error?<div className="mt-4"><ErrorState error={overview.error}/></div>:monthly.length?
          <div className="mt-4 h-72"><ResponsiveContainer width="100%" height="100%"><LineChart data={monthly}><CartesianGrid strokeDasharray="3 3"/><XAxis dataKey="period"/><YAxis tickFormatter={(value)=>formatNumber(value,0,0)}/><Tooltip/><Legend/><Line type="monotone" dataKey="income" name="Ingresos" stroke="var(--chart-income)" strokeWidth={3} dot={false}/><Line type="monotone" dataKey="expenses" name="Gastos" stroke="var(--chart-expenses)" strokeWidth={3} dot={false}/><Line type="monotone" dataKey="savings" name="Ahorro" stroke="var(--chart-savings)" strokeWidth={3} dot={false}/></LineChart></ResponsiveContainer></div>:
          <EmptyState>Importa histórico para ver la evolución.</EmptyState>}
      </Card>

      <Card className="xl:col-span-2">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div><h2 className="font-bold">Previsión de cierre de mes</h2><p className="mt-1 text-sm text-[var(--muted)]">Basada en histórico, ritmo reciente y compromisos conocidos.</p></div>
          {monthEnd.data?.as_of&&<div className="text-xs text-[var(--muted)]">Datos hasta {monthEnd.data.as_of}{monthEnd.data.month_end?' · cierre '+monthEnd.data.month_end:''}</div>}
        </div>
        {monthEnd.isLoading?<div className="mt-4"><Loading/></div>:monthEnd.error?<div className="mt-4"><ErrorState error={monthEnd.error}/></div>:closing?<>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <div className="rounded-2xl bg-[var(--surface-2)] p-4"><div className="text-xs uppercase text-[var(--muted)]">Gasto estimado</div><div className="mt-2 text-2xl font-bold"><Money value={closing.expenses}/></div></div>
            <div className="rounded-2xl bg-[var(--surface-2)] p-4"><div className="text-xs uppercase text-[var(--muted)]">Ahorro estimado</div><div className="mt-2 text-2xl font-bold"><Money value={closing.savings}/></div></div>
            <div className="rounded-2xl bg-[var(--surface-2)] p-4"><div className="text-xs uppercase text-[var(--muted)]">Saldo total estimado</div><div className="mt-2 text-2xl font-bold"><Money value={closing.total_balance}/></div></div>
            <div className="rounded-2xl bg-[var(--surface-2)] p-4"><div className="text-xs uppercase text-[var(--muted)]">Precisión histórica</div><div className="mt-2 text-2xl font-bold">{accuracy?.expense_accuracy==null?'—':(Number(accuracy.expense_accuracy)*100).toFixed(0)+'%'}</div><div className="mt-1 text-xs text-[var(--muted)]">{accuracy?.months_evaluated?accuracy.months_evaluated+' meses evaluados':'Aún sin histórico suficiente'}</div></div>
          </div>
          <div className="mt-5"><h3 className="font-bold">Saldo estimado por cuenta</h3><div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-3">{accounts.length?accounts.map(a=><div key={a.id} className="rounded-2xl border border-[var(--border)] bg-white p-4"><div className="flex justify-between gap-3"><div><strong>{a.name}</strong><div className="text-xs text-[var(--muted)]">{a.institution_name}</div></div><strong><Money value={a.projected_closing_balance} currency={a.currency}/></strong></div><div className="mt-3 grid grid-cols-2 gap-2 text-xs"><div>Actual<br/><strong><Money value={a.current_balance} currency={a.currency}/></strong></div><div>Cambio<br/><strong><Money value={a.projected_change} currency={a.currency}/></strong></div></div><div className="mt-2 text-[11px] text-[var(--muted)]">{a.method}</div></div>):<EmptyState>No hay cuentas para proyectar.</EmptyState>}</div></div>
          {Number(forecastRemaining?.commitment_floor_adjustment||0)>0&&<div className="mt-4 rounded-xl bg-[var(--brand-soft)] p-3 text-sm">Compromisos conocidos pendientes hasta fin de mes: <strong><Money value={forecastRemaining?.known_commitments||'0'}/></strong>.</div>}
        </>:<EmptyState>No hay una previsión disponible todavía.</EmptyState>}
      </Card>

      <Card>
        <h2 className="font-bold">Estructura del gasto</h2>
        {mix.length?<div className="mt-4 h-64"><ResponsiveContainer width="100%" height="100%"><BarChart data={mix}><CartesianGrid strokeDasharray="3 3"/><XAxis dataKey="name"/><YAxis tickFormatter={(value)=>formatNumber(value,0,0)}/><Tooltip/><Bar dataKey="amount" name="€">{mix.map((x,i)=><Cell key={x.name} fill={['var(--chart-fixed)','var(--chart-variable)','var(--chart-essential)','var(--chart-discretionary)'][i%4]}/>)}</Bar></BarChart></ResponsiveContainer></div>:<EmptyState>Sin datos suficientes.</EmptyState>}
      </Card>

      <Card>
        <h2 className="font-bold">Principales comercios</h2>
        <div className="mt-3 space-y-2">{merchants.length?merchants.slice(0,10).map(row=><div key={row.merchant} className="flex justify-between rounded-xl bg-[var(--surface-2)] p-3 text-sm"><span>{row.merchant}</span><strong><Money value={row.amount}/></strong></div>):<EmptyState>Sin gasto por comercio.</EmptyState>}</div>
      </Card>

      <Card>
        <h2 className="font-bold">Recurrentes</h2>
        <p className="mt-1 text-sm text-[var(--muted)]">Se detectan por fechas e importes repetidos. El recálculo completo usa además la IA local para unir conceptos que cambian de referencia o comercio y después valida matemáticamente el patrón.</p>
        {recurring.error?<div className="mt-3"><ErrorState error={recurring.error}/></div>:<div className="mt-3 space-y-2">{recurringRows.length?recurringRows.map(row=><div key={row.id} className="flex justify-between gap-3 rounded-xl bg-[var(--surface-2)] p-3 text-sm"><div><strong>{row.merchant}</strong><div className="text-xs text-[var(--muted)]">{cadenceLabel(row.cadence)} · próxima {row.next_expected_date} · confianza {Math.round(Number(row.confidence||0)*100)}%</div></div><strong><Money value={row.expected_amount}/></strong></div>):<EmptyState>No se han validado patrones recurrentes todavía. Importa histórico suficiente o pulsa “Recalcular patrones”.</EmptyState>}</div>}
      </Card>

      <Card>
        <h2 className="font-bold">Movimientos fuera de tu patrón habitual</h2>
        <p className="mt-1 text-sm text-[var(--muted)]">Una señal estadística no significa fraude ni error. Compara el movimiento con otros importes parecidos para que puedas decidir si merece revisión.</p>
        {anomalies.error?<div className="mt-3"><ErrorState error={anomalies.error}/></div>:<div className="mt-3 space-y-3">{anomalyRows.length?anomalyRows.map(a=>{
          const movement=a.transaction?.merchant||a.transaction?.description||'Movimiento';
          const typical=a.baseline?.typical_amount??'0';
          const difference=a.baseline?.difference??'0';
          return <div key={a.id} className="rounded-xl bg-[var(--surface-2)] p-4 text-sm">
            <div className="flex items-start justify-between gap-3"><div><strong>{movement}</strong><div className="text-xs text-[var(--muted)]">{a.transaction?.booking_date||'Fecha no disponible'}</div></div>{a.transaction&&<strong><Money value={Math.abs(Number(a.transaction.amount||0))} currency={a.transaction.currency}/></strong>}</div>
            <div className="mt-3 rounded-lg bg-white p-3 text-xs"><div>Importe habitual aproximado: <strong><Money value={typical}/></strong>.</div><div className="mt-1">Diferencia: <strong><Money value={difference}/></strong>{a.baseline?.difference_pct!=null?' · '+a.baseline.difference_pct+'%':''}.</div><div className="mt-1 text-[var(--muted)]">Confianza de la señal: {Math.round(Number(a.confidence||0)*100)}%.</div></div>
            <div className="mt-3 flex flex-wrap gap-2"><button className="fin-button py-1.5 text-xs" onClick={()=>anomalyAction.mutate({id:a.id,status:'normal'})}>Es correcto</button><Link className="fin-button secondary py-1.5 text-xs" href={'/transactions/?q='+encodeURIComponent(movement)}>Buscar este movimiento</Link><button className="text-xs underline" onClick={()=>anomalyAction.mutate({id:a.id,status:'ignored'})}>Ignorar aviso</button></div>
          </div>;
        }):<EmptyState>No hay movimientos fuera de tu patrón pendientes.</EmptyState>}</div>}
      </Card>

      <Card>
        <h2 className="font-bold">Calidad de los datos</h2>
        <p className="mt-1 text-sm text-[var(--muted)]">Aquí no se analiza si gastas bien o mal: solo si faltan datos, hay clasificaciones dudosas, documentos conflictivos o cuentas bancarias sin actualizar.</p>
        {recon.error?<div className="mt-3"><ErrorState error={recon.error}/></div>:<div className="mt-3 space-y-2">{issues.length?issues.map(issue=><div key={issue.type} className="rounded-xl bg-[var(--surface-2)] p-3 text-sm"><div className="flex items-start justify-between gap-3"><strong>{issue.label||issue.type.replaceAll('_',' ')}</strong><strong>{formatNumber(issue.count,0,0)}</strong></div>{issue.detail&&<div className="mt-1 text-xs text-[var(--muted)]">{issue.detail}</div>}{issue.action_href&&<Link className="mt-2 inline-block text-xs underline" href={issue.action_href}>Revisar</Link>}</div>):<EmptyState>Los datos necesarios para los análisis principales están coherentes.</EmptyState>}</div>}
      </Card>

      <Card>
        <h2 className="font-bold">Próximos 90 días</h2>
        <p className="mt-1 text-sm text-[var(--muted)]">Incluye obligaciones conocidas, cada próxima ocurrencia de gastos recurrentes y estimaciones mensuales de categorías previsibles como alimentación, colegio, suministros, transporte o suscripciones.</p>
        {calendar.error?<div className="mt-3"><ErrorState error={calendar.error}/></div>:<div className="mt-3 max-h-[560px] space-y-2 overflow-y-auto pr-1" tabIndex={0} role="region" aria-label="Previsión de los próximos 90 días">{events.length?events.slice(0,30).map(e=><div key={e.type+e.entity_id+e.date} className="flex justify-between gap-3 rounded-xl bg-[var(--surface-2)] p-3 text-sm"><div><strong>{e.title}</strong><div className="text-xs text-[var(--muted)]">{e.date} · {eventTypeLabel(e.type)}{e.confidence?' · '+Math.round(Number(e.confidence)*100)+'% confianza':''}</div>{e.basis&&<div className="mt-1 text-[11px] text-[var(--muted)]">{e.basis}</div>}</div>{e.amount&&<strong><Money value={e.amount}/></strong>}</div>):<EmptyState>No hay histórico suficiente ni compromisos registrados para proyectar los próximos 90 días.</EmptyState>}</div>}
      </Card>

      <Card className="xl:col-span-2">
        <h2 className="font-bold">Stress test</h2>
        <form className="mt-3 grid gap-2 md:grid-cols-4" onSubmit={(e:FormEvent)=>{e.preventDefault();stress.mutate()}}>
          <input className="fin-input" aria-label="Reducción de ingresos en porcentaje" type="number" min="0" max="100" step=".1" value={shock.income_reduction_pct} onChange={e=>setShock({...shock,income_reduction_pct:e.target.value})} placeholder="% caída ingresos"/>
          <input className="fin-input" aria-label="Gasto extraordinario" type="number" min="0" step=".01" value={shock.extraordinary_expense} onChange={e=>setShock({...shock,extraordinary_expense:e.target.value})} placeholder="Gasto extraordinario"/>
          <input className="fin-input" aria-label="Caída de cartera en porcentaje" type="number" min="0" max="100" step=".1" value={shock.portfolio_drop_pct} onChange={e=>setShock({...shock,portfolio_drop_pct:e.target.value})} placeholder="% caída cartera"/>
          <button className="fin-button" disabled={stress.isPending}>{stress.isPending?'Calculando…':'Simular '+shock.months+' meses'}</button>
        </form>
        {stress.error&&<div className="mt-3"><ErrorState error={stress.error}/></div>}
        {stress.data&&<div className="mt-4 grid gap-3 sm:grid-cols-3"><div><div className="text-xs text-[var(--muted)]">Liquidez final</div><strong><Money value={stress.data.ending_liquidity}/></strong></div><div><div className="text-xs text-[var(--muted)]">Runway</div><strong>{stress.data.cash_runway_months===null?'Sin consumo neto':stress.data.cash_runway_months+' meses'}</strong></div><div><div className="text-xs text-[var(--muted)]">Cartera tras shock</div><strong><Money value={stress.data.portfolio_after_shock}/></strong></div></div>}
      </Card>
    </div>
  </>;
}
