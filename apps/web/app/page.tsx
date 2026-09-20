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

interface Dashboard{
  period:{start:string;end:string};
  liquidity:string;
  income:string;
  expenses:string;
  savings:string;
  savings_rate:string|null;
  spending_by_category:{category:string;system_key:string;amount:string}[];
  upcoming_commitments:{id:string;title:string;amount:string;due_date:string}[];
  actions:{id:string;title:string;action_type:string;priority:string;due_date:string|null;status:string;notes:string|null;related_entity_type:string|null;related_entity_id:string|null}[];
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
  if(action.related_entity_type==='insurance_policy')return {href:'/insurance/',label:'Revisar la póliza y sus coberturas'};
  return {href:'/actions/?action='+encodeURIComponent(action.id),label:'Abrir la tarea y ver qué falta'};
}

const priorityLabel:Record<string,string>={high:'Prioridad alta',medium:'Prioridad media',low:'Prioridad baja'};

type DashboardRange='month'|'30d'|'90d'|'year'|'12m'|'custom';

function isoDate(value:Date){
  const y=value.getFullYear();
  const m=String(value.getMonth()+1).padStart(2,'0');
  const d=String(value.getDate()).padStart(2,'0');
  return `${y}-${m}-${d}`;
}

function dashboardRange(range:DashboardRange,customStart:string,customEnd:string){
  if(range==='custom'&&customStart&&customEnd)return {start:customStart,end:customEnd};
  const end=new Date();
  const start=new Date(end);
  if(range==='custom')start.setDate(1);
  if(range==='month')start.setDate(1);
  if(range==='30d')start.setDate(start.getDate()-29);
  if(range==='90d')start.setDate(start.getDate()-89);
  if(range==='year'){start.setMonth(0);start.setDate(1)}
  if(range==='12m')start.setFullYear(start.getFullYear()-1);
  return {start:isoDate(start),end:isoDate(end)};
}

function Metric({label,value,detail}:{label:string;value:string;detail?:string}){
  return <Card>
    <div className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">{label}</div>
    <div className="mt-2 text-2xl font-bold"><Money value={value}/></div>
    {detail?<div className="mt-1 text-xs text-[var(--muted)]">{detail}</div>:null}
  </Card>;
}

export default function DashboardPage(){
  const [range,setRange]=useState<DashboardRange>('month');
  const [customStart,setCustomStart]=useState('');
  const [customEnd,setCustomEnd]=useState('');
  const dates=dashboardRange(range,customStart,customEnd);
  const dashboard=useQuery({
    queryKey:['dashboard',range,dates.start,dates.end],
    queryFn:()=>apiGet<Dashboard>('/api/v1/dashboard?start='+dates.start+'&end='+dates.end),
    enabled:true,
  });
  const wealth=useQuery({queryKey:['wealth'],queryFn:()=>apiGet<Wealth>('/api/v1/wealth'),retry:false});

  if(dashboard.isLoading)return <><PageHeader title="Inicio"/><Loading/></>;
  if(dashboard.error)return <><PageHeader title="Inicio"/><ErrorState error={dashboard.error}/></>;

  const d=dashboard.data!;
  const savingsRate=d.savings_rate===null?undefined:`${(Number(d.savings_rate)*100).toFixed(1)}% de los ingresos`;
  const maxCategory=Math.max(1,...d.spending_by_category.map(row=>Number(row.amount)));

  return <>
    <PageHeader
      title="Inicio"
      description="Tu situación financiera, lo que ha cambiado y lo que merece atención ahora."
      action={<div className="flex flex-wrap items-end justify-end gap-2">
        <label className="block text-xs font-medium text-[var(--muted)]">Periodo
          <select className="fin-input mt-1 min-w-[180px]" aria-label="Periodo del resumen de Inicio" value={range} onChange={e=>setRange(e.target.value as DashboardRange)}>
            <option value="month">Este mes</option>
            <option value="30d">Últimos 30 días</option>
            <option value="90d">Últimos 90 días</option>
            <option value="year">Este año</option>
            <option value="12m">Últimos 12 meses</option>
            <option value="custom">Personalizado</option>
          </select>
        </label>
        {range==='custom'&&<>
          <label className="block text-xs font-medium text-[var(--muted)]">Desde<input className="fin-input mt-1 w-auto" type="date" value={customStart} max={customEnd||undefined} onChange={e=>setCustomStart(e.target.value)}/></label>
          <label className="block text-xs font-medium text-[var(--muted)]">Hasta<input className="fin-input mt-1 w-auto" type="date" value={customEnd} min={customStart||undefined} onChange={e=>setCustomEnd(e.target.value)}/></label>
        </>}
      </div>}
    />

    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
      <Metric label="Disponible" value={d.liquidity} detail="Liquidez consolidada"/>
      <Metric label="Ingresos" value={d.income} detail={`${d.period.start} — ${d.period.end}`}/>
      <Metric label="Gasto" value={d.expenses} detail={`${d.period.start} — ${d.period.end}`}/>
      <Metric label="Ahorro" value={d.savings} detail={savingsRate}/>
      {wealth.data?<Metric label="Patrimonio neto" value={wealth.data.net_worth} detail="Activos menos deuda"/>:
        <Card><div className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">Patrimonio neto</div><div className="mt-2 text-2xl font-bold">—</div><div className="mt-1 text-xs text-[var(--muted)]">Calculando patrimonio</div></Card>}
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
          {d.actions.slice(0,4).map(action=>{const destination=actionDestination(action);return <Link key={action.id} href={destination.href} className="fin-card block p-4 transition-transform hover:-translate-y-0.5">
            <div className="flex items-center justify-between gap-2">
              <span className="rounded-full bg-[var(--brand-soft)] px-2 py-1 text-[10px] font-bold uppercase tracking-wide text-[var(--brand)]">{priorityLabel[action.priority]||action.priority}</span>
              <Sparkles size={16} className="text-[var(--brand)]"/>
            </div>
            <div className="mt-3 font-semibold">{action.title}</div>
            <div className="mt-2 text-xs"><strong>Qué hacer:</strong> {destination.label}</div>
            {action.notes&&<div className="mt-1 line-clamp-2 text-xs text-[var(--muted)]">{action.notes}</div>}
            <div className="mt-2 text-xs text-[var(--muted)]">{action.due_date?`Antes de ${action.due_date}`:'Sin fecha límite'}</div>
          </Link>})}
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
            <div><div className="font-medium">{item.title}</div><div className="text-xs text-[var(--muted)]">{item.due_date}</div></div>
            <strong><Money value={item.amount}/></strong>
          </div>):<EmptyState>No hay compromisos próximos registrados.</EmptyState>}
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
          <div><div className="font-semibold">Patrimonio</div><div className="text-xs text-[var(--muted)]">Activos, deuda e inversiones</div></div>
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
  </>;
}
