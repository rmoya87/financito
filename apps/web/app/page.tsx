'use client';

import Link from 'next/link';
import {useQuery} from '@tanstack/react-query';
import {useState} from 'react';
import {ArrowRight,CalendarDays,CircleDollarSign,FileText,Sparkles,WalletCards} from 'lucide-react';
import {apiGet} from '@/lib/api';
import {categoryColor} from '@/lib/category-colors';
import {PageHeader} from '@/components/page-header';
import {Card} from '@/components/ui/card';
import {Money} from '@/components/ui/money';
import {EmptyState,ErrorState,Loading} from '@/components/ui/states';
import {DataStatus} from '@/components/data-status';
import {InsurancePolicyDetailModal} from '@/components/insurance-policy-detail-modal';
import {GlobalFinancialFilters} from '@/components/financial-filters';

interface Dashboard{
  period:{start:string;end:string};
  liquidity:string;
  income:string;
  expenses:string;
  savings:string;
  savings_rate:string|null;
  spending_by_category:{category:string;system_key:string;amount:string}[];
  upcoming_commitments:{id:string;title:string;amount:string|null;due_date:string;type:'commitment'|'recurring'|'renewal';confidence:string|null;basis:string|null}[];
  actions:{id:string;title:string;action_type:string;priority:string;due_date:string|null;status:string;notes:string|null;related_entity_type:string|null;related_entity_id:string|null}[];
  financial_health:{
    generated_at:string;
    safe_to_spend:{amount:string;liquidity:string;reserved_goals:string;obligations_until_next_income:string;minimum_buffer:string;buffer_gap:string;horizon_date:string;selected_period_start:string;selected_period_end:string;selected_monthly_spending:string;selected_spending_floor:string;recent_spending_floor:string;seasonal_spending_floor:string;historical_pattern_floor:string;known_future_outflows:string;projection_basis:string;projection_method:string;next_income:null|{date:string;amount:string;label:string;confidence:string;basis:string};explanation:string};
    emergency_fund:{essential_monthly:string;allocated:string;coverage_months:string|null;minimum_buffer:string};
    indicators:{status:'good'|'warning'|'risk'|'unknown';title:string;value:string|null;detail:string|null;rule:string}[];
    changes:{current:{start:string;end:string};previous:{start:string;end:string};expenses_delta:string;income_delta:string;savings_delta:string;categories:{category:string;current:string;previous:string;delta:string;delta_pct:string|null}[]};
    alerts:{id:string;kind:string;severity:'high'|'medium'|'low';title:string;detail:string;action_path:string;source_id:string|null}[];
    data_status:{calculated_at:string;latest_transaction_date:string|null;basis:string};
  };
}
interface Wealth{net_worth:string}

function actionDestination(action:Dashboard['actions'][number]){
  if(action.related_entity_type==='document'&&action.related_entity_id){
    const params=new URLSearchParams({document:action.related_entity_id,action:action.id});
    const label=action.action_type==='review_document_ai_insights'
      ?'Leer la conclusión y marcarla como revisada'
      :'Confirmar en bloque los datos coherentes o revisar los conflictos';
    return {href:'/documents/?'+params.toString(),label};
  }
  if(action.related_entity_type==='contract'||action.action_type==='contract_notice')return {href:'/contracts/',label:'Revisar renovación, coste y condiciones'};
  if(action.related_entity_type==='banking_connection'||action.action_type==='banking_consent_renewal')return {href:'/banking/',label:'Renovar la autorización bancaria'};
  if(action.related_entity_type==='insurance_policy')return {href:'/insurance/?policy='+encodeURIComponent(action.related_entity_id||''),label:'Ver detalle completo de la póliza y sus coberturas'};
  return {href:'/actions/?action='+encodeURIComponent(action.id),label:'Abrir la tarea y ver qué falta'};
}

const priorityLabel:Record<string,string>={high:'Alta',medium:'Media',low:'Baja'};

function Metric({label,value,detail}:{label:string;value:string;detail?:string}){
  return <Card>
    <div className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">{label}</div>
    <div className="mt-2 text-2xl font-bold"><Money value={value}/></div>
    {detail?<div className="mt-1 text-xs text-[var(--muted)]">{detail}</div>:null}
  </Card>;
}

export default function DashboardPage(){
  const [insuranceModalPolicyId,setInsuranceModalPolicyId]=useState<string|null|undefined>(undefined);
  const dashboard=useQuery({
    queryKey:['dashboard'],
    queryFn:()=>apiGet<Dashboard>('/api/v1/dashboard'),
  });
  const wealth=useQuery({queryKey:['wealth'],queryFn:()=>apiGet<Wealth>('/api/v1/wealth'),retry:false});

  if(dashboard.isLoading)return <><PageHeader title="Inicio" action={<GlobalFinancialFilters compact/>}/><Loading/></>;
  if(dashboard.error)return <><PageHeader title="Inicio" action={<GlobalFinancialFilters compact/>}/><ErrorState error={dashboard.error}/></>;

  const d=dashboard.data!;
  const savingsRate=d.savings_rate===null?undefined:`${(Number(d.savings_rate)*100).toFixed(1)}% de los ingresos`;
  const maxCategory=Math.max(1,...d.spending_by_category.map(row=>Number(row.amount)));

  const health=d.financial_health;
  const statusTone=(status:string)=>status==='good'?'confirmed':status==='warning'||status==='risk'?'pending':'neutral' as const;
  const expenseDelta=Number(health.changes.expenses_delta||0);
  const savingsDelta=Number(health.changes.savings_delta||0);

  return <>
    <PageHeader
      title="Inicio"
      description="Tu situación financiera, lo que ha cambiado y lo que merece atención ahora."
      action={<GlobalFinancialFilters compact/>}
    />

    <div className="mb-4 flex flex-wrap gap-2"><DataStatus label="Calculado ahora" detail={health.data_status.latest_transaction_date?'movimientos hasta '+health.data_status.latest_transaction_date:health.data_status.basis} tone="calculated"/></div>

    <section>
      <h2 className="mb-3 text-lg font-bold">Tu situación ahora</h2>
      <div className="grid gap-4 xl:grid-cols-[1.35fr_2fr]">
        <Card className="border-[var(--brand)]">
          <div className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">Disponible para gastar</div>
          <div className="mt-2 text-3xl font-bold"><Money value={health.safe_to_spend.amount}/></div>
          <p className="mt-2 text-sm text-[var(--muted)]">Es una estimación prudente de lo que parece libre <strong>hoy</strong> después de proteger objetivos, gasto probable hasta el siguiente ingreso y tu colchón mínimo.</p>
          <div className="mt-4 rounded-xl border border-[var(--border)] bg-white p-3 text-xs">
            <div className="mb-2 font-semibold">Cómo se calcula</div>
            <div className="grid grid-cols-[1fr_auto] gap-x-3 gap-y-1.5">
              <span>Liquidez actual</span><strong><Money value={health.safe_to_spend.liquidity}/></strong>
              <span>− Objetivos ya reservados</span><strong><Money value={health.safe_to_spend.reserved_goals}/></strong>
              <span>− Gasto protegido hasta {health.safe_to_spend.horizon_date}</span><strong><Money value={health.safe_to_spend.obligations_until_next_income}/></strong>
              <span>− Colchón todavía no cubierto</span><strong><Money value={health.safe_to_spend.buffer_gap}/></strong>
              <span className="border-t border-[var(--border)] pt-2 font-semibold">= Disponible</span><strong className="border-t border-[var(--border)] pt-2"><Money value={health.safe_to_spend.amount}/></strong>
            </div>
          </div>
          <div className="mt-3 grid gap-2 text-xs sm:grid-cols-2">
            <div className="rounded-xl bg-white/70 p-3"><div className="text-[var(--muted)]">Ritmo mensual del periodo</div><strong><Money value={health.safe_to_spend.selected_monthly_spending}/> / mes</strong><div className="mt-1 text-[11px] text-[var(--muted)]">{health.safe_to_spend.selected_period_start} → {health.safe_to_spend.selected_period_end}</div></div>
            <div className="rounded-xl bg-white/70 p-3"><div className="text-[var(--muted)]">Señal que protege más</div><strong>{({
              selected_period:'Periodo seleccionado',
              recent_90_days:'Últimos 90 días',
              same_period_last_year:'Mismo tramo del año anterior',
              known_future:'Cargos futuros conocidos',
              category_patterns:'Patrones por categoría',
              horizon_closed:'Horizonte cerrado',
            } as Record<string,string>)[health.safe_to_spend.projection_basis]||health.safe_to_spend.projection_basis}</strong><div className="mt-1 text-[11px] text-[var(--muted)]">No se suman señales que puedan representar el mismo gasto.</div></div>
          </div>
          <details className="mt-3 rounded-xl border border-[var(--border)] bg-white/70 p-3 text-xs">
            <summary className="cursor-pointer font-semibold">Ver señales de la estimación</summary>
            <div className="mt-3 grid grid-cols-[1fr_auto] gap-x-3 gap-y-1.5 text-[11px]">
              <span>Periodo seleccionado hasta el próximo ingreso</span><strong><Money value={health.safe_to_spend.selected_spending_floor}/></strong>
              <span>Ritmo de los últimos 90 días</span><strong><Money value={health.safe_to_spend.recent_spending_floor}/></strong>
              <span>Mismo tramo del año anterior</span><strong><Money value={health.safe_to_spend.seasonal_spending_floor}/></strong>
              <span>Cargos futuros conocidos</span><strong><Money value={health.safe_to_spend.known_future_outflows}/></strong>
              <span>Patrones históricos por categoría</span><strong><Money value={health.safe_to_spend.historical_pattern_floor}/></strong>
            </div>
            <p className="mt-3 text-[11px] text-[var(--muted)]">{health.safe_to_spend.projection_method}</p>
          </details>
          {health.safe_to_spend.next_income&&<div className="mt-3 text-xs text-[var(--muted)]">Siguiente ingreso estimado: <strong>{health.safe_to_spend.next_income.date}</strong> · <Money value={health.safe_to_spend.next_income.amount}/>. {health.safe_to_spend.next_income.basis}.</div>}
        </Card>
        <div className="grid gap-3 sm:grid-cols-2">
          {health.indicators.map(item=><Card key={item.title}>
            <div className="flex items-start justify-between gap-3"><div className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">{item.title}</div><DataStatus label={item.status==='good'?'Bien':item.status==='warning'?'Atención':item.status==='risk'?'Riesgo':'Sin datos'} tone={statusTone(item.status)}/></div>
            <div className="mt-2 text-xl font-bold">{item.value&&item.title!=='Liquidez'&&item.title!=='Ahorro'&&item.title!=='Deuda'&&item.title!=='Compromisos'?item.value:item.value&&/^[-\d.]+$/.test(item.value)?<Money value={item.value}/>:item.value||'—'}</div>
            {item.detail&&<div className="mt-1 text-xs text-[var(--muted)]">{item.detail}</div>}
            <details className="mt-2 text-[11px] text-[var(--muted)]"><summary className="cursor-pointer">Cómo se interpreta</summary><div className="mt-1">{item.rule}</div></details>
          </Card>)}
        </div>
      </div>
    </section>

    <div className="mt-5 grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
      <Metric label="Disponible" value={d.liquidity} detail="Liquidez consolidada"/>
      <Metric label="Ingresos" value={d.income} detail={`${d.period.start} — ${d.period.end}`}/>
      <Metric label="Gasto" value={d.expenses} detail={`${d.period.start} — ${d.period.end}`}/>
      <Metric label="Ahorro" value={d.savings} detail={savingsRate}/>
      {wealth.data?<Metric label="Patrimonio neto" value={wealth.data.net_worth} detail="Activos menos deuda"/>:
        <Card><div className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">Patrimonio neto</div><div className="mt-2 text-2xl font-bold">—</div><div className="mt-1 text-xs text-[var(--muted)]">Calculando patrimonio</div></Card>}
    </div>

    <div className="mt-5 grid gap-4 xl:grid-cols-2">
      <Card>
        <h2 className="font-bold">Qué ha cambiado</h2>
        <p className="mt-1 text-sm text-[var(--muted)]">Compara el periodo elegido con el periodo inmediatamente anterior de la misma duración.</p>
        <div className="mt-4 space-y-2 text-sm">
          <div className="rounded-xl bg-[var(--surface-2)] p-3">{expenseDelta===0?'Tu gasto es prácticamente igual al periodo anterior.':expenseDelta<0?<>Has gastado <strong><Money value={Math.abs(expenseDelta)}/></strong> menos.</>:<>Has gastado <strong><Money value={expenseDelta}/></strong> más.</>}</div>
          <div className="rounded-xl bg-[var(--surface-2)] p-3">{savingsDelta===0?'Tu ahorro no ha cambiado de forma relevante.':savingsDelta>0?<>Tu ahorro ha mejorado <strong><Money value={savingsDelta}/></strong>.</>:<>Tu ahorro ha bajado <strong><Money value={Math.abs(savingsDelta)}/></strong>.</>}</div>
          {health.changes.categories.slice(0,3).map(row=><div key={row.category} className="flex items-center justify-between gap-3 rounded-xl border border-[var(--border)] p-3"><span>{row.category}</span><strong>{Number(row.delta)>0?'+':''}<Money value={row.delta}/>{row.delta_pct!==null?<span className="ml-1 text-xs text-[var(--muted)]">({Number(row.delta_pct)>0?'+':''}{row.delta_pct}%)</span>:null}</strong></div>)}
        </div>
      </Card>
      <Card>
        <div className="flex items-start justify-between gap-3"><div><h2 className="font-bold">Avisos útiles</h2><p className="mt-1 text-sm text-[var(--muted)]">Solo situaciones que pueden requerir una decisión o revisión.</p></div><CalendarDays size={20} className="text-[var(--brand)]"/></div>
        <div className="mt-4 space-y-2">{health.alerts.length?health.alerts.slice(0,6).map(alert=><Link key={alert.id} href={alert.action_path} className="block rounded-xl bg-[var(--surface-2)] p-3 text-sm hover:outline hover:outline-1 hover:outline-[var(--border)]"><div className="flex items-start justify-between gap-2"><strong>{alert.title}</strong><DataStatus label={alert.severity==='high'?'Prioritario':alert.severity==='medium'?'Revisar':'Datos'} tone={alert.severity==='low'?'neutral':'pending'}/></div><div className="mt-1 text-xs text-[var(--muted)]">{alert.detail}</div></Link>):<EmptyState>No hay avisos relevantes ahora mismo.</EmptyState>}</div>
      </Card>
    </div>

    {d.actions.length>0&&<section className="mt-5">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold">Para ti</h2>
          <p className="text-sm text-[var(--muted)]">Alertas, oportunidades y tareas que requieren atención.</p>
        </div>
        <Link href="/actions/" className="flex items-center gap-1 text-sm font-semibold text-[var(--brand)]">Ver todo <ArrowRight size={16}/></Link>
      </div>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {d.actions.slice(0,4).map(action=>{
            const destination=actionDestination(action);
            const card=<>
              <div className="flex items-center justify-between gap-2">
                <span className="rounded-full bg-[var(--brand-soft)] px-2 py-1 text-[10px] font-bold uppercase tracking-wide text-[var(--brand)]">{priorityLabel[action.priority]||action.priority}</span>
                <Sparkles size={16} className="text-[var(--brand)]"/>
              </div>
              <div className="mt-3 font-semibold">{action.title}</div>
              <div className="mt-2 text-xs"><strong>Qué hacer:</strong> {destination.label}</div>
              {action.notes&&<div className="mt-1 line-clamp-2 text-xs text-[var(--muted)]">{action.notes}</div>}
              <div className="mt-2 text-xs text-[var(--muted)]">{action.due_date?`Antes de ${action.due_date}`:'Sin fecha límite'}</div>
            </>;
            const insuranceAction=action.related_entity_type==='insurance_policy'||action.action_type.startsWith('insurance_')||action.title.toLowerCase().includes('seguro');
            if(insuranceAction){
              const policyId=action.related_entity_type==='insurance_policy'?action.related_entity_id:null;
              return <button key={action.id} type="button" className="fin-card block w-full p-4 text-left transition-transform hover:-translate-y-0.5" onClick={()=>setInsuranceModalPolicyId(policyId||null)}>{card}</button>;
            }
            return <Link key={action.id} href={destination.href} className="fin-card block p-4 transition-transform hover:-translate-y-0.5">{card}</Link>;
          })}
        </div>
    </section>}

    <div className="mt-5 grid gap-4 xl:grid-cols-2">
      <Card>
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="font-bold">En qué se está yendo tu dinero</h2>
            <p className="mt-1 text-sm text-[var(--muted)]">Principales categorías del periodo actual.</p>
          </div>
          <CircleDollarSign size={20} className="text-[var(--brand)]"/>
        </div>
        <div className="mt-4 flex flex-col gap-3">
          {d.spending_by_category.length?d.spending_by_category.slice(0,7).map(row=>{
            const color=categoryColor(row.system_key);
            return <div key={row.system_key}>
              <div className="flex justify-between gap-3 text-sm">
                <span className="flex items-center gap-2"><span aria-hidden="true" className="size-2.5 rounded-full" style={{backgroundColor:color}}/>{row.category}</span>
                <strong><Money value={row.amount}/></strong>
              </div>
              <div className="mt-1 h-2 rounded-full bg-[var(--surface-2)]" role="img" aria-label={`${row.category}: ${row.amount} euros`}>
                <div className="h-2 rounded-full" style={{width:`${Math.max(5,Number(row.amount)/maxCategory*100)}%`,backgroundColor:color}}/>
              </div>
            </div>;
          }):<EmptyState>Importa movimientos para ver la distribución de gasto.</EmptyState>}
        </div>
        <Link href="/analytics/" className="mt-4 inline-flex items-center gap-1 text-sm font-semibold text-[var(--brand)]">Ver análisis <ArrowRight size={16}/></Link>
      </Card>

      <Card>
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="font-bold">Próximamente</h2>
            <p className="mt-1 text-sm text-[var(--muted)]">Compromisos y pagos que ya conocemos.</p>
          </div>
          <CalendarDays size={20} className="text-[var(--brand)]"/>
        </div>
        <div className="mt-4 flex flex-col gap-2">
          {d.upcoming_commitments.length?d.upcoming_commitments.slice(0,7).map(item=><div key={item.id} className="flex items-center justify-between gap-4 rounded-xl bg-[var(--surface-2)] p-3 text-sm">
            <div>
              <div className="flex flex-wrap items-center gap-2"><div className="font-medium">{item.title}</div><span className="rounded-full bg-[var(--brand-soft)] px-2 py-0.5 text-[10px] font-semibold text-[var(--brand)]">{item.type==='recurring'?'Recurrente':item.type==='renewal'?'Renovación':'Compromiso'}</span></div>
              <div className="text-xs text-[var(--muted)]">{item.due_date}{item.basis?' · '+item.basis:''}</div>
            </div>
            <strong>{item.amount===null?'—':<Money value={item.amount}/>}</strong>
          </div>):<EmptyState>No hay compromisos, renovaciones ni gastos recurrentes previstos en los próximos 45 días.</EmptyState>}
        </div>
        <Link href="/forecast/" className="mt-4 inline-flex items-center gap-1 text-sm font-semibold text-[var(--brand)]">Ver previsión <ArrowRight size={16}/></Link>
      </Card>
    </div>

    <section className="mt-5">
      <h2 className="mb-3 text-lg font-bold">Explorar</h2>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <Link href="/transactions/" className="fin-card flex items-center gap-4 p-4 hover:border-[var(--brand)]">
          <div className="grid size-10 place-items-center rounded-xl bg-[var(--brand-soft)] text-[var(--brand)]"><CircleDollarSign size={20}/></div>
          <div><div className="font-semibold">Movimientos</div><div className="text-xs text-[var(--muted)]">Gastos, cuentas y análisis</div></div>
        </Link>
        <Link href="/wealth/" className="fin-card flex items-center gap-4 p-4 hover:border-[var(--brand)]">
          <div className="grid size-10 place-items-center rounded-xl bg-[var(--brand-soft)] text-[var(--brand)]"><WalletCards size={20}/></div>
          <div><div className="font-semibold">Patrimonio</div><div className="text-xs text-[var(--muted)]">Casa, hipoteca y seguros</div></div>
        </Link>
        <Link href="/actions/" className="fin-card flex items-center gap-4 p-4 hover:border-[var(--brand)]">
          <div className="grid size-10 place-items-center rounded-xl bg-[var(--brand-soft)] text-[var(--brand)]"><Sparkles size={20}/></div>
          <div><div className="font-semibold">Decisiones</div><div className="text-xs text-[var(--muted)]">Oportunidades, objetivos y simulaciones</div></div>
        </Link>
        <Link href="/documents/" className="fin-card flex items-center gap-4 p-4 hover:border-[var(--brand)]">
          <div className="grid size-10 place-items-center rounded-xl bg-[var(--brand-soft)] text-[var(--brand)]"><FileText size={20}/></div>
          <div><div className="font-semibold">Añadir documentos</div><div className="text-xs text-[var(--muted)]">Hipoteca, seguros y contratos; análisis local automático</div></div>
        </Link>
      </div>
    </section>

    <InsurancePolicyDetailModal
      open={insuranceModalPolicyId!==undefined}
      onClose={()=>setInsuranceModalPolicyId(undefined)}
      policyId={insuranceModalPolicyId??null}
    />
  </>;
}
