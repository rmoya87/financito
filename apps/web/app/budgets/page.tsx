'use client';

import {FormEvent,useMemo,useState} from 'react';
import {useMutation,useQuery,useQueryClient} from '@tanstack/react-query';
import {apiGet,apiMutate} from '@/lib/api';
import {PageHeader} from '@/components/page-header';
import {Card} from '@/components/ui/card';
import {Money} from '@/components/ui/money';
import {EmptyState,ErrorState,Loading} from '@/components/ui/states';
import {DataStatus} from '@/components/data-status';
import {MetricTile,SectionIntro,VisualPanel} from '@/components/finance-ui';

type Account={id:string;name:string;institution_name:string};
type Category={id:string;name:string;system_key:string};
type Budget={
  id:string;category_id:string;category:string;system_key:string;account_id:string|null;account_name:string|null;account_institution:string|null;
  scope:'household'|'account';amount:string;actual:string;remaining:string;utilization:string;period_type:string;currency:string;alert_threshold:string;updated_at:string|null
};

export default function BudgetsPage(){
  const qc=useQueryClient();
  const budgets=useQuery({queryKey:['budgets','management'],queryFn:()=>apiGet<Budget[]>('/api/v1/budgets?management=true')});
  const categories=useQuery({queryKey:['categories'],queryFn:()=>apiGet<Category[]>('/api/v1/categories')});
  const accounts=useQuery({queryKey:['accounts','budgets'],queryFn:()=>apiGet<Account[]>('/api/v1/accounts')});
  const [scope,setScope]=useState('household');
  const [form,setForm]=useState({category_id:'',amount:'',period_type:'monthly',alert_threshold:'80'});
  const add=useMutation({
    mutationFn:()=>apiMutate<Budget>('/api/v1/budgets','POST',{
      category_id:form.category_id,account_id:scope==='household'?null:scope,
      amount:form.amount,period_type:form.period_type,alert_threshold:String(Number(form.alert_threshold)/100),currency:'EUR',
    }),
    onSuccess:()=>{setForm({...form,category_id:'',amount:''});qc.invalidateQueries({queryKey:['budgets']});qc.invalidateQueries({queryKey:['dashboard']});qc.invalidateQueries({queryKey:['decision-overview']})},
  });
  const update=useMutation({
    mutationFn:({id,amount}:{id:string;amount:string})=>apiMutate('/api/v1/budgets/'+id,'PATCH',{amount}),
    onSuccess:()=>{qc.invalidateQueries({queryKey:['budgets']});qc.invalidateQueries({queryKey:['dashboard']})},
  });
  const remove=useMutation({
    mutationFn:(id:string)=>apiMutate('/api/v1/budgets/'+id,'DELETE'),
    onSuccess:()=>{qc.invalidateQueries({queryKey:['budgets']});qc.invalidateQueries({queryKey:['dashboard']})},
  });
  const rows=budgets.data||[];
  const household=useMemo(()=>rows.filter(x=>x.scope==='household'),[rows]);
  const byAccount=useMemo(()=>rows.filter(x=>x.scope==='account'),[rows]);
  const totals=useMemo(()=>rows.reduce((acc,row)=>{
    acc.budget+=Number(row.amount||0);acc.actual+=Number(row.actual||0);
    if(Number(row.utilization||0)>=Number(row.alert_threshold||0))acc.alerts+=1;
    return acc;
  },{budget:0,actual:0,alerts:0}),[rows]);

  function BudgetCard({b}:{b:Budget}){
    const pct=Math.max(0,Number(b.utilization||0)*100);
    const status=pct>100?'Superado':pct>=Number(b.alert_threshold||0)*100?'Cerca del límite':'Dentro del presupuesto';
    return <div className="rounded-2xl border border-[var(--border)] bg-white p-4">
      <div className="flex items-start justify-between gap-3">
        <div><strong>{b.category}</strong><div className="mt-1 text-xs text-[var(--muted)]">{b.scope==='household'?'Hogar':(b.account_institution||'Banco')+' · '+(b.account_name||'Cuenta')} · {b.period_type==='annual'?'anual':'mensual'}</div></div>
        <DataStatus label={status} tone={pct>100?'pending':pct>=Number(b.alert_threshold||0)*100?'pending':'confirmed'}/>
      </div>
      <div className="mt-4 flex items-end justify-between gap-3"><div><div className="text-xs text-[var(--muted)]">Gastado / presupuesto</div><strong className="text-lg"><Money value={b.actual}/> / <Money value={b.amount}/></strong></div><div className="text-right text-sm">{Math.round(pct)}%</div></div>
      <div className="mt-2 h-2 overflow-hidden rounded-full bg-[var(--surface-2)]"><div className="h-full rounded-full bg-[var(--brand)]" style={{width:Math.min(100,pct)+'%'}}/></div>
      <div className="mt-3 text-xs text-[var(--muted)]">{Number(b.remaining)>=0?'Quedan ':'Exceso '}<Money value={Math.abs(Number(b.remaining))}/>.</div>
      <div className="mt-3 grid grid-cols-[1fr_auto_auto] gap-2">
        <input id={'budget-'+b.id} className="fin-input" aria-label={'Presupuesto '+b.category} type="number" min=".01" step=".01" defaultValue={b.amount}/>
        <button className="fin-button secondary" type="button" onClick={()=>update.mutate({id:b.id,amount:(document.getElementById('budget-'+b.id) as HTMLInputElement).value})}>Guardar</button>
        <button className="text-xs underline" type="button" onClick={()=>remove.mutate(b.id)}>Eliminar</button>
      </div>
    </div>;
  }

  return <>
    <PageHeader title="Presupuestos" description="Define límites para todo el hogar o para una cuenta concreta. Un presupuesto de hogar nunca se compara contra una sola cuenta, y viceversa."/>
    {rows.length>0&&<>
      <SectionIntro eyebrow="Lectura rápida" title="Cómo van tus límites" description="Primero el total, después cada categoría. Los importes respetan el ámbito Hogar o Cuenta."/>
      <div className="mb-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <MetricTile label="Presupuestado" value={<Money value={totals.budget}/>} detail={rows.length+' presupuesto(s) activos'} status="Definido por ti" statusTone="confirmed"/>
        <MetricTile label="Gastado" value={<Money value={totals.actual}/>} detail="Movimientos reales del periodo de cada presupuesto" status="Calculado" statusTone="calculated"/>
        <MetricTile label="Margen" value={<Money value={totals.budget-totals.actual}/>} detail="Presupuesto total menos gasto observado" emphasis/>
        <MetricTile label="Necesitan atención" value={totals.alerts} detail="Cerca del umbral o ya superados" status={totals.alerts?'Revisar':'Sin alertas'} statusTone={totals.alerts?'pending':'confirmed'}/>
      </div>
    </>}
    <VisualPanel title="Nuevo presupuesto" description="Elige si el límite pertenece a todo el hogar o solo a una cuenta. Así nunca se comparan importes incompatibles." status="Movimientos reales" statusTone="calculated">
      <div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="font-bold">Nuevo presupuesto</h2><p className="mt-1 text-sm text-[var(--muted)]">El ámbito evita comparar importes que no representan lo mismo.</p></div><DataStatus label="Calculado con movimientos reales" tone="calculated"/></div>
      <form className="mt-4 grid gap-2 md:grid-cols-2 xl:grid-cols-5" onSubmit={(e:FormEvent)=>{e.preventDefault();add.mutate()}}>
        <select className="fin-input" aria-label="Ámbito del presupuesto" value={scope} onChange={e=>setScope(e.target.value)}>
          <option value="household">Hogar · todas las cuentas</option>
          {accounts.data?.map(a=><option key={a.id} value={a.id}>{a.institution_name} · {a.name}</option>)}
        </select>
        <select className="fin-input" aria-label="Categoría del presupuesto" value={form.category_id} onChange={e=>setForm({...form,category_id:e.target.value})} required><option value="">Categoría…</option>{categories.data?.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</select>
        <input className="fin-input" aria-label="Importe del presupuesto" type="number" min=".01" step=".01" placeholder="Límite €" value={form.amount} onChange={e=>setForm({...form,amount:e.target.value})} required/>
        <select className="fin-input" aria-label="Periodo del presupuesto" value={form.period_type} onChange={e=>setForm({...form,period_type:e.target.value})}><option value="monthly">Mensual</option><option value="annual">Anual</option></select>
        <button className="fin-button" disabled={add.isPending}>{add.isPending?'Guardando…':'Crear presupuesto'}</button>
      </form>
      {add.error&&<div className="mt-3"><ErrorState error={add.error}/></div>}
    </VisualPanel>

    {budgets.isLoading?<div className="mt-4"><Loading/></div>:budgets.error?<div className="mt-4"><ErrorState error={budgets.error}/></div>:<>
      <section className="mt-6"><SectionIntro eyebrow="Hogar" title="Presupuestos compartidos" description="Se comparan contra el gasto consolidado de todas las cuentas."/><div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">{household.length?household.map(b=><BudgetCard key={b.id} b={b}/>):<EmptyState>No hay presupuestos de hogar.</EmptyState>}</div></section>
      <section className="mt-6"><SectionIntro eyebrow="Cuenta" title="Presupuestos específicos" description="Solo se comparan con los movimientos de la cuenta vinculada."/><div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">{byAccount.length?byAccount.map(b=><BudgetCard key={b.id} b={b}/>):<EmptyState>No hay presupuestos ligados a cuentas concretas.</EmptyState>}</div></section>
    </>}
    {(update.error||remove.error)&&<div className="mt-4"><ErrorState error={(update.error||remove.error)!}/></div>}
  </>;
}
