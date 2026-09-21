'use client';

import Link from 'next/link';
import {FormEvent,useMemo,useState} from 'react';
import {useMutation,useQuery,useQueryClient} from '@tanstack/react-query';
import {Bar,BarChart,CartesianGrid,Cell,Legend,Line,LineChart,Pie,PieChart,ResponsiveContainer,Tooltip,XAxis,YAxis} from 'recharts';
import {apiGet,apiMutate} from '@/lib/api';
import {PageHeader} from '@/components/page-header';
import {isoDate} from '@/components/date-range-selector';
import {useFinancialFilters} from '@/components/financial-filters';
import {Card} from '@/components/ui/card';
import {Money,formatMoney,formatNumber} from '@/components/ui/money';
import {EmptyState,ErrorState,Loading} from '@/components/ui/states';
import {DataStatus} from '@/components/data-status';
import {MetricTile,SectionIntro} from '@/components/finance-ui';

type Rec={id:string;merchant:string;cadence:string;expected_amount:string;next_expected_date:string;confidence:string;action:'keep'|'review'|'cancel'|'not_subscription';essential:boolean;essential_override:boolean|null;contract_id:string|null;contract_name:string|null;spending_class:string;projected:boolean};
type ContractRef={id:string;provider_name:string;contract_type:string};
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
  merchant_spending_total?:string;
  fixed_variable?:{fixed:string;variable:string};
  essential_discretionary?:{essential:string;discretionary:string};
  spending_structure?:{total:string;fixed_essential:string;fixed_optional:string;variable_essential:string;discretionary:string};
  monthly?:{period:string;income:string;expenses:string;savings:string}[];
  daily?:{period:string;income:string;expenses:string;savings:string}[];
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

function shiftDate(value:string,days:number){
  const parsed=new Date(value+'T12:00:00');
  parsed.setDate(parsed.getDate()+days);
  return isoDate(parsed);
}

export default function AnalyticsPage(){
  const qc=useQueryClient();
  const {range,start,end}=useFinancialFilters();
  const dates={start,end};
  const periodReady=Boolean(dates.start&&dates.end);
  const forecastStart=periodReady?shiftDate(dates.end,1):'';
  const forecastEnd=periodReady?shiftDate(dates.end,30):'';
  const periodParams=periodReady?'?start='+dates.start+'&end='+dates.end:'';

  const recurring=useQuery({
    queryKey:['recurring'],
    queryFn:()=>apiGet<Rec[]>('/api/v1/recurring'),
  });
  const contracts=useQuery({queryKey:['contracts','recurring'],queryFn:()=>apiGet<ContractRef[]>('/api/v1/contracts')});
  const anomalies=useQuery({
    queryKey:['anomalies',dates.start,dates.end],
    queryFn:()=>apiGet<Anom[]>('/api/v1/anomalies'+periodParams),
    enabled:periodReady,
  });
  const recon=useQuery({queryKey:['reconciliation'],queryFn:()=>apiGet<Recon>('/api/v1/reconciliation')});
  const calendar=useQuery({
    queryKey:['calendar',forecastStart,forecastEnd],
    queryFn:()=>apiGet<Cal>('/api/v1/calendar?start='+forecastStart+'&end='+forecastEnd),
    enabled:periodReady,
  });
  const overview=useQuery({
    queryKey:['analytics-overview',dates.start,dates.end],
    queryFn:()=>apiGet<Overview>('/api/v1/analytics/overview'+periodParams),
    enabled:periodReady,
  });
  const monthEnd=useQuery({
    queryKey:['month-end-forecast',dates.end],
    queryFn:()=>apiGet<MonthEnd>('/api/v1/forecast/month-end?as_of='+dates.end),
    enabled:periodReady,
  });

  const refresh=useMutation({
    mutationFn:()=>apiMutate<{recurring_series:number;anomalies:number}>('/api/v1/analytics/refresh','POST'),
    onSuccess:()=>{['recurring','anomalies','analytics-overview','month-end-forecast','reconciliation','calendar'].forEach(k=>qc.invalidateQueries({queryKey:[k]}))},
  });
  const recurringAction=useMutation({
    mutationFn:({id,action,essential_override,contract_id}:{id:string;action:Rec['action'];essential_override:boolean|null;contract_id:string|null})=>apiMutate<Rec>('/api/v1/recurring/'+id,'PATCH',{action,essential_override,contract_id}),
    onSuccess:()=>{qc.invalidateQueries({queryKey:['recurring']});qc.invalidateQueries({queryKey:['analytics-overview']});qc.invalidateQueries({queryKey:['calendar']});qc.invalidateQueries({queryKey:['dashboard']});qc.invalidateQueries({queryKey:['financial-health']});qc.invalidateQueries({queryKey:['actions']})},
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
  const daily=useMemo(()=>Array.isArray(overview.data?.daily)?overview.data!.daily!.map(x=>({
    ...x,income:Number(x.income||0),expenses:Number(x.expenses||0),savings:Number(x.savings||0),
  })):[],[overview.data]);
  const usesDailyTrend=daily.length>0;
  const trendData=usesDailyTrend?daily:monthly;
  const [merchantView,setMerchantView]=useState<'chart'|'list'>('chart');
  const mix=useMemo(()=>{
    const s=overview.data?.spending_structure;
    if(!s)return [];
    return [
      {name:'Fijo esencial',amount:Number(s.fixed_essential||0)},
      {name:'Fijo prescindible',amount:Number(s.fixed_optional||0)},
      {name:'Variable esencial',amount:Number(s.variable_essential||0)},
      {name:'Discrecional',amount:Number(s.discretionary||0)},
    ];
  },[overview.data]);

  const merchants=Array.isArray(overview.data?.by_merchant)?overview.data!.by_merchant!:[];
  const merchantTotal=Math.max(0,Number(overview.data?.merchant_spending_total||0));
  const listedMerchantTotal=useMemo(()=>merchants.reduce((sum,row)=>sum+Math.max(0,Number(row.amount||0)),0),[merchants]);
  const merchantShareTotal=Math.max(merchantTotal,listedMerchantTotal);
  const merchantChartData=useMemo(()=>{
    if(!merchants.length||merchantShareTotal<=0)return [];
    const top=merchants.slice(0,9).map(row=>({name:row.merchant,amount:Math.max(0,Number(row.amount||0))}));
    const visible=top.reduce((sum,row)=>sum+row.amount,0);
    const other=Math.max(0,merchantShareTotal-visible);
    const rows=other>0?[...top,{name:'Otros',amount:other}]:top;
    const total=rows.reduce((sum,row)=>sum+row.amount,0);
    return rows.map(row=>({...row,percent:total>0?Math.min(100,Math.max(0,row.amount/total*100)):0}));
  },[merchants,merchantShareTotal]);
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
    <PageHeader
      title="Análisis y resiliencia"
      description="Ingresos, gasto, ahorro, previsiones y patrones. El periodo global filtra los datos temporales y sirve como fecha de referencia para las previsiones."
    />
    <div className="mb-4"><DataStatus label="Calculado" detail="movimientos del periodo seleccionado" tone="calculated"/></div>

    {overview.data?.cash_flow&&<>
      <SectionIntro eyebrow="Lectura rápida" title="Qué está pasando en el periodo" description="Primero la foto principal; debajo quedan las gráficas y patrones que explican por qué."/>
      <div className="mb-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <MetricTile label="Ingresos" value={<Money value={overview.data.cash_flow.income}/>} detail="Entradas reales del periodo seleccionado" status="Calculado" statusTone="calculated"/>
        <MetricTile label="Gasto" value={<Money value={overview.data.cash_flow.expenses}/>} detail="Salidas netas de reembolsos" status={Number(overview.data.cash_flow.expenses)>Number(overview.data.cash_flow.income)?'Por encima de ingresos':'Controlado'} statusTone={Number(overview.data.cash_flow.expenses)>Number(overview.data.cash_flow.income)?'pending':'confirmed'}/>
        <MetricTile label="Ahorro" value={<Money value={overview.data.cash_flow.savings}/>} detail="Ingresos menos gasto del periodo" emphasis/>
        <MetricTile label="Tasa de ahorro" value={overview.data.cash_flow.savings_rate===null?'—':(Number(overview.data.cash_flow.savings_rate)*100).toLocaleString('es-ES',{maximumFractionDigits:1})+'%'} detail="Ahorro sobre los ingresos del periodo"/>
      </div>
    </>}

    <div className="mb-4 flex flex-wrap gap-2">
      <button className="fin-button" onClick={()=>refresh.mutate()} disabled={refresh.isPending}>{refresh.isPending?'Recalculando…':'Recalcular patrones'}</button>
      <Link href="/cost-centers/" className="fin-button secondary">Organizar por centros de coste</Link>
    </div>
    {refresh.error&&<div className="mb-4"><ErrorState error={refresh.error}/></div>}

    <SectionIntro eyebrow="Evolución" title="Cómo se mueve tu dinero" description="Tendencia, cierre estimado y composición del gasto con el mismo periodo global."/>
    <div className="grid gap-4 xl:grid-cols-2">
      <Card className="xl:col-span-2">
        <h2 className="font-bold">Ingresos, gasto y ahorro</h2>
        {overview.isLoading?<div className="mt-4"><Loading/></div>:overview.error?<div className="mt-4"><ErrorState error={overview.error}/></div>:trendData.length?
          <div className="mt-4 h-72"><ResponsiveContainer width="100%" height="100%"><LineChart data={trendData}><CartesianGrid strokeDasharray="3 3"/><XAxis dataKey="period" tickFormatter={value=>usesDailyTrend?String(value).slice(8,10):String(value)}/><YAxis tickFormatter={(value)=>formatNumber(value,0,0)}/><Tooltip formatter={value=>formatMoney(Number(value||0))}/><Legend/><Line type="monotone" dataKey="income" name="Ingresos" stroke="var(--chart-income)" strokeWidth={3} dot={usesDailyTrend}/><Line type="monotone" dataKey="expenses" name="Gastos" stroke="var(--chart-expenses)" strokeWidth={3} dot={usesDailyTrend}/><Line type="monotone" dataKey="savings" name="Ahorro" stroke="var(--chart-savings)" strokeWidth={3} dot={usesDailyTrend}/></LineChart></ResponsiveContainer></div>:
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
        <p className="mt-1 text-sm text-[var(--muted)]">Cuatro grupos excluyentes: cada euro aparece una sola vez. Los recurrentes y tus decisiones sobre ellos alimentan automáticamente esta clasificación.</p>
        {mix.length?<><div className="mt-4 h-64"><ResponsiveContainer width="100%" height="100%"><BarChart data={mix}><CartesianGrid strokeDasharray="3 3"/><XAxis dataKey="name" interval={0} tick={{fontSize:11}}/><YAxis tickFormatter={(value)=>formatNumber(value,0,0)}/><Tooltip formatter={value=>formatMoney(Number(value||0))}/><Bar dataKey="amount" name="€">{mix.map((x,i)=><Cell key={x.name} fill={['var(--chart-essential)','var(--chart-fixed)','var(--chart-variable)','var(--chart-discretionary)'][i%4]}/>)}</Bar></BarChart></ResponsiveContainer></div><div className="mt-2 text-xs text-[var(--muted)]">Total clasificado: <strong>{formatMoney(mix.reduce((sum,row)=>sum+row.amount,0))}</strong>.</div></>:<EmptyState>Sin datos suficientes.</EmptyState>}
      </Card>

      <Card>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div><h2 className="font-bold">Principales comercios</h2><p className="mt-1 text-sm text-[var(--muted)]">Peso de cada comercio sobre el gasto total del periodo.</p></div>
          <div className="flex rounded-xl border border-[var(--border)] p-1" role="group" aria-label="Vista de principales comercios">
            <button className={`rounded-lg px-3 py-1.5 text-xs font-semibold ${merchantView==='chart'?'bg-[var(--brand-soft)] text-[var(--brand)]':''}`} onClick={()=>setMerchantView('chart')} aria-pressed={merchantView==='chart'}>Gráfica</button>
            <button className={`rounded-lg px-3 py-1.5 text-xs font-semibold ${merchantView==='list'?'bg-[var(--brand-soft)] text-[var(--brand)]':''}`} onClick={()=>setMerchantView('list')} aria-pressed={merchantView==='list'}>Listado</button>
          </div>
        </div>
        {!merchants.length?<div className="mt-3"><EmptyState>Sin gasto por comercio.</EmptyState></div>:merchantView==='chart'?
          <div className="mt-3 h-96 overflow-visible"><ResponsiveContainer width="100%" height="100%"><PieChart margin={{top:34,right:42,bottom:30,left:42}}><Pie data={merchantChartData} dataKey="amount" nameKey="name" innerRadius={52} outerRadius={88} cy="47%" paddingAngle={2} labelLine label={(props:any)=>{const pct=Number(props?.payload?.percent||0);return pct>=4?`${formatNumber(pct,1,1)}%`:''}}>{merchantChartData.map((row,i)=><Cell key={row.name} fill={['var(--chart-income)','var(--chart-expenses)','var(--chart-savings)','var(--chart-fixed)','var(--chart-variable)','var(--chart-essential)','var(--chart-discretionary)','var(--brand)','var(--muted)','var(--surface-3)'][i%10]}/>)}</Pie><Tooltip formatter={(value)=>formatMoney(Number(value||0))}/><Legend/></PieChart></ResponsiveContainer></div>:
          <div className="mt-3 space-y-2">{merchants.slice(0,10).map(row=>{const pct=merchantShareTotal>0?Math.min(100,Math.max(0,Number(row.amount||0)/merchantShareTotal*100)):0;return <div key={row.merchant} className="flex items-center justify-between gap-3 rounded-xl bg-[var(--surface-2)] p-3 text-sm"><span>{row.merchant}</span><div className="text-right"><strong><Money value={row.amount}/></strong><div className="text-xs text-[var(--muted)]">{formatNumber(pct,1,1)}%</div></div></div>})}</div>}
      </Card>

      <div className="xl:col-span-2"><SectionIntro eyebrow="Patrones" title="Qué se repite y qué se sale de lo normal" description="Recurrentes y anomalías aparecen juntos para decidir qué mantener, revisar o corregir."/></div>
      {(recurring.isLoading||recurring.error||recurringRows.length>0)&&<Card className="xl:col-span-2">
        <h2 className="font-bold">Recurrentes</h2>
        <p className="mt-1 text-sm text-[var(--muted)]">Decide qué hacer con cada patrón. “No es una suscripción” deja de proyectarlo; “Es imprescindible” lo mueve a gasto fijo esencial. Las decisiones persisten aunque recalcules patrones.</p>
        {recurring.isLoading?<div className="mt-3"><Loading/></div>:recurring.error?<div className="mt-3"><ErrorState error={recurring.error}/></div>:<div className="mt-3 grid gap-3 lg:grid-cols-2" role="region" aria-label="Patrones recurrentes">{recurringRows.map(row=><div key={row.id} className="rounded-xl bg-[var(--surface-2)] p-4 text-sm">
          <div className="flex items-start justify-between gap-3"><div><strong>{row.merchant}</strong><div className="mt-1 text-xs text-[var(--muted)]">{cadenceLabel(row.cadence)} · próxima {row.next_expected_date} · confianza {Math.round(Number(row.confidence||0)*100)}%</div></div><div className="text-right"><strong><Money value={row.expected_amount}/></strong><div className="text-[11px] text-[var(--muted)]">{row.spending_class==='fixed_essential'?'Fijo esencial':'Fijo prescindible'}</div></div></div>
          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            <select className="fin-input text-xs" aria-label={'Acción recurrente '+row.merchant} value={row.action} disabled={recurringAction.isPending} onChange={e=>recurringAction.mutate({id:row.id,action:e.target.value as Rec['action'],essential_override:row.essential_override,contract_id:row.contract_id})}>
              <option value="keep">Mantener</option><option value="review">Revisar</option><option value="cancel">Cancelar</option><option value="not_subscription">No es una suscripción</option>
            </select>
            <select className="fin-input text-xs" aria-label={'Contrato recurrente '+row.merchant} value={row.contract_id||''} disabled={recurringAction.isPending} onChange={e=>recurringAction.mutate({id:row.id,action:row.action,essential_override:row.essential_override,contract_id:e.target.value||null})}>
              <option value="">Sin contrato vinculado</option>{contracts.data?.map(c=><option key={c.id} value={c.id}>{c.provider_name} · {c.contract_type}</option>)}
            </select>
          </div>
          <label className="mt-3 flex items-center gap-2 text-xs font-medium"><input type="checkbox" checked={row.essential} onChange={e=>recurringAction.mutate({id:row.id,action:row.action,essential_override:e.target.checked,contract_id:row.contract_id})}/> Es imprescindible</label>
          {!row.projected&&<div className="mt-2 text-xs text-[var(--muted)]">No se proyectará como gasto futuro mientras mantenga esta decisión.</div>}
        </div>)}</div>}
        {recurringAction.error&&<div className="mt-3"><ErrorState error={recurringAction.error}/></div>}
      </Card>}

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
        <p className="mt-1 text-sm text-[var(--muted)]">Aquí no se analiza si gastas bien o mal: solo si faltan datos, hay clasificaciones dudosas, documentos conflictivos o cuentas bancarias sin actualizar. Es una comprobación global y no depende del periodo.</p>
        {recon.error?<div className="mt-3"><ErrorState error={recon.error}/></div>:<div className="mt-3 space-y-2">{issues.length?issues.map(issue=><div key={issue.type} className="rounded-xl bg-[var(--surface-2)] p-3 text-sm"><div className="flex items-start justify-between gap-3"><strong>{issue.label||issue.type.replaceAll('_',' ')}</strong><strong>{formatNumber(issue.count,0,0)}</strong></div>{issue.detail&&<div className="mt-1 text-xs text-[var(--muted)]">{issue.detail}</div>}{issue.action_href&&<Link className="mt-2 inline-block text-xs underline" href={issue.action_href}>Revisar</Link>}</div>):<EmptyState>Los datos necesarios para los análisis principales están coherentes.</EmptyState>}</div>}
      </Card>

      <Card>
        <h2 className="font-bold">Próximos 30 días</h2>
        <p className="mt-1 text-sm text-[var(--muted)]">Incluye los 30 días posteriores al final del periodo seleccionado ({forecastStart||'—'}): obligaciones conocidas, recurrencias y estimaciones de categorías previsibles como alimentación, colegio, suministros, transporte o suscripciones.</p>
        {calendar.error?<div className="mt-3"><ErrorState error={calendar.error}/></div>:<div className="mt-3 max-h-[560px] space-y-2 overflow-y-auto pr-1" tabIndex={0} role="region" aria-label="Previsión de los próximos 30 días">{events.length?events.slice(0,30).map(e=><div key={e.type+e.entity_id+e.date} className="flex justify-between gap-3 rounded-xl bg-[var(--surface-2)] p-3 text-sm"><div><strong>{e.title}</strong><div className="text-xs text-[var(--muted)]">{e.date} · {eventTypeLabel(e.type)}{e.confidence?' · '+Math.round(Number(e.confidence)*100)+'% confianza':''}</div>{e.basis&&<div className="mt-1 text-[11px] text-[var(--muted)]">{e.basis}</div>}</div>{e.amount&&<strong><Money value={e.amount}/></strong>}</div>):<EmptyState>No hay histórico suficiente ni compromisos registrados para proyectar los próximos 30 días.</EmptyState>}</div>}
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
