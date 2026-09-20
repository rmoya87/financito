'use client';

import Link from 'next/link';
import {useQuery} from '@tanstack/react-query';
import {ArrowRight,CalendarDays,CircleDollarSign,Sparkles,WalletCards} from 'lucide-react';
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
  actions:{id:string;title:string;priority:string;due_date:string|null;status:string}[];
}
interface Wealth{net_worth:string}

function Metric({label,value,detail}:{label:string;value:string;detail?:string}){
  return <Card>
    <div className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">{label}</div>
    <div className="mt-2 text-2xl font-bold"><Money value={value}/></div>
    {detail?<div className="mt-1 text-xs text-[var(--muted)]">{detail}</div>:null}
  </Card>;
}

export default function DashboardPage(){
  const dashboard=useQuery({queryKey:['dashboard'],queryFn:()=>apiGet<Dashboard>('/api/v1/dashboard')});
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
    />

    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <Metric label="Disponible" value={d.liquidity} detail="Liquidez consolidada"/>
      <Metric label="Gasto este mes" value={d.expenses} detail={`${d.period.start} — ${d.period.end}`}/>
      <Metric label="Ahorro este mes" value={d.savings} detail={savingsRate}/>
      {wealth.data?<Metric label="Patrimonio neto" value={wealth.data.net_worth} detail="Activos menos deuda"/>:
        <Card><div className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">Patrimonio neto</div><div className="mt-2 text-2xl font-bold">—</div><div className="mt-1 text-xs text-[var(--muted)]">Calculando patrimonio</div></Card>}
    </div>

    <section className="mt-5">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold">Para ti</h2>
          <p className="text-sm text-[var(--muted)]">Alertas, oportunidades y tareas que requieren atención.</p>
        </div>
        <Link href="/actions/" className="flex items-center gap-1 text-sm font-semibold text-[var(--brand)]">Ver todo <ArrowRight size={16}/></Link>
      </div>
      {d.actions.length?
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {d.actions.slice(0,4).map(action=><Link key={action.id} href="/actions/" className="fin-card block p-4 transition-transform hover:-translate-y-0.5">
            <div className="flex items-center justify-between gap-2">
              <span className="rounded-full bg-[var(--brand-soft)] px-2 py-1 text-[10px] font-bold uppercase tracking-wide text-[var(--brand)]">{action.priority}</span>
              <Sparkles size={16} className="text-[var(--brand)]"/>
            </div>
            <div className="mt-3 font-semibold">{action.title}</div>
            <div className="mt-2 text-xs text-[var(--muted)]">{action.due_date?`Antes de ${action.due_date}`:'Sin fecha límite'}</div>
          </Link>)}
        </div>:
        <Card><EmptyState>No hay nada que requiera tu atención ahora mismo.</EmptyState></Card>}
    </section>

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
      <div className="grid gap-3 md:grid-cols-3">
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
      </div>
    </section>
  </>;
}
