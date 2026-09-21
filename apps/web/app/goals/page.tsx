'use client';
import {FormEvent,useState} from 'react';
import {useMutation,useQuery,useQueryClient} from '@tanstack/react-query';
import {apiGet,apiMutate} from '@/lib/api';
import {PageHeader} from '@/components/page-header';
import {Card} from '@/components/ui/card';
import {Money} from '@/components/ui/money';
import {EmptyState,ErrorState} from '@/components/ui/states';

type Account={id:string;name:string;institution_name:string;account_type:string;current_balance:string;available_balance:string|null};
type G={
  id:string;type:string;name:string;target_amount:string;current_amount:string;current_amount_source:string;
  account_id:string|null;account_name:string|null;account_institution:string|null;
  target_date:string|null;priority:string;status:string;planned_monthly_contribution:string;
  remaining_amount:string;months_left:number|null;monthly_required:string|null;projected_months:number|null
};

export default function GoalsPage(){
  const qc=useQueryClient();
  const q=useQuery({queryKey:['goals'],queryFn:()=>apiGet<G[]>('/api/v1/goals')});
  const accounts=useQuery({queryKey:['accounts','goals'],queryFn:()=>apiGet<Account[]>('/api/v1/accounts')});
  const [f,setF]=useState({name:'',goal_type:'emergency_fund',target_amount:'',account_id:'',target_date:'',planned_monthly_contribution:'0',priority:'medium'});
  const add=useMutation({
    mutationFn:()=>apiMutate<G>('/api/v1/goals','POST',{...f,current_amount:'0',target_date:f.target_date||null}),
    onSuccess:()=>{setF({...f,name:'',target_amount:'',target_date:'',planned_monthly_contribution:'0'});qc.invalidateQueries({queryKey:['goals']})},
  });
  const update=useMutation({
    mutationFn:({id,account_id,planned_monthly_contribution}:{id:string;account_id:string|null;planned_monthly_contribution:string})=>
      apiMutate<G>('/api/v1/goals/'+id,'PATCH',{account_id,planned_monthly_contribution}),
    onSuccess:()=>qc.invalidateQueries({queryKey:['goals']}),
  });

  return <>
    <PageHeader title="Objetivos" description="Cada objetivo se vincula a una cuenta bancaria. El importe actual usa la liquidez real de esa cuenta y se actualiza cuando cambia su saldo."/>
    <Card>
      <h2 className="font-bold">Nuevo objetivo</h2>
      <form className="mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-4" onSubmit={(e:FormEvent)=>{e.preventDefault();add.mutate()}}>
        <select className="fin-input" aria-label="Tipo de objetivo" value={f.goal_type} onChange={e=>setF({...f,goal_type:e.target.value})}>
          <option value="emergency_fund">Fondo de emergencia</option><option value="home">Vivienda</option><option value="debt">Amortizar deuda</option><option value="travel">Viaje</option><option value="car">Coche</option><option value="investment">Inversión</option><option value="saving">Ahorro</option><option value="other">Otro</option>
        </select>
        <input className="fin-input" placeholder="Nombre del objetivo" value={f.name} onChange={e=>setF({...f,name:e.target.value})} required/>
        <input className="fin-input" type="number" min="0.01" step=".01" placeholder="Importe objetivo" value={f.target_amount} onChange={e=>setF({...f,target_amount:e.target.value})} required/>
        <select className="fin-input" aria-label="Cuenta bancaria del objetivo" value={f.account_id} onChange={e=>setF({...f,account_id:e.target.value})} required>
          <option value="">Cuenta bancaria…</option>
          {accounts.data?.map(a=><option key={a.id} value={a.id}>{a.institution_name} · {a.name}</option>)}
        </select>
        <label className="text-sm text-[var(--muted)]">Fecha objetivo<input className="fin-input mt-1" type="date" value={f.target_date} onChange={e=>setF({...f,target_date:e.target.value})}/></label>
        <label className="text-sm text-[var(--muted)]">Aportación mensual prevista<input className="fin-input mt-1" type="number" min="0" step=".01" value={f.planned_monthly_contribution} onChange={e=>setF({...f,planned_monthly_contribution:e.target.value})}/></label>
        <select className="fin-input self-end" aria-label="Prioridad" value={f.priority} onChange={e=>setF({...f,priority:e.target.value})}><option value="high">Alta prioridad</option><option value="medium">Prioridad media</option><option value="low">Baja prioridad</option></select>
        <button className="fin-button self-end" disabled={add.isPending||!f.account_id}>Crear objetivo</button>
      </form>
      {add.error&&<div className="mt-3"><ErrorState error={add.error}/></div>}
    </Card>

    <div className="mt-4 grid gap-4 md:grid-cols-2">{q.data?.length?q.data.map(g=>{
      const pct=Math.min(100,Number(g.current_amount)/Math.max(1,Number(g.target_amount))*100);
      const onTrack=g.monthly_required===null||Number(g.planned_monthly_contribution)>=Number(g.monthly_required);
      return <Card key={g.id}>
        <div className="flex items-start justify-between gap-3">
          <div><div className="font-bold">{g.name}</div><div className="text-xs text-[var(--muted)]">{g.type.replaceAll('_',' ')} · {g.status==='completed'?'Completado':'En curso'}</div></div>
          <div className="text-right"><div className="font-semibold">{Math.round(pct)}%</div><div className="text-xs text-[var(--muted)]">completado</div></div>
        </div>
        <div className="mt-3 h-2 rounded-full bg-[var(--surface-2)]"><div className="h-2 rounded-full bg-[var(--brand)]" style={{width:String(pct)+'%'}}/></div>
        <div className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
          <div className="rounded-xl bg-[var(--surface-2)] p-3"><div className="text-xs text-[var(--muted)]">Actual / objetivo</div><strong><Money value={g.current_amount}/> / <Money value={g.target_amount}/></strong><div className="mt-1 text-[11px] text-[var(--muted)]">{g.account_id?'Liquidez de la cuenta vinculada':'Valor manual heredado'}</div></div>
          <div className="rounded-xl bg-[var(--surface-2)] p-3"><div className="text-xs text-[var(--muted)]">Falta</div><strong><Money value={g.remaining_amount}/></strong></div>
          {g.monthly_required!==null&&<div className="rounded-xl bg-[var(--surface-2)] p-3"><div className="text-xs text-[var(--muted)]">Necesario al mes</div><strong><Money value={g.monthly_required}/></strong></div>}
          <div className="rounded-xl bg-[var(--surface-2)] p-3"><div className="text-xs text-[var(--muted)]">Tu aportación prevista</div><strong><Money value={g.planned_monthly_contribution}/></strong></div>
        </div>
        <div className="mt-3 rounded-xl border border-[var(--border)] p-3">
          <div className="text-xs font-medium text-[var(--muted)]">Cuenta vinculada</div>
          <select className="fin-input mt-2" aria-label={'Cuenta del objetivo '+g.name} defaultValue={g.account_id||''} id={'goal-account-'+g.id}>
            <option value="">Sin cuenta vinculada</option>
            {accounts.data?.map(a=><option key={a.id} value={a.id}>{a.institution_name} · {a.name}</option>)}
          </select>
          {g.account_id&&<div className="mt-1 text-xs text-[var(--muted)]">{g.account_institution} · {g.account_name}</div>}
        </div>
        {g.target_date&&<div className={'mt-3 rounded-xl p-3 text-sm '+(onTrack?'bg-[var(--brand-soft)]':'bg-[var(--surface-2)]')}>{onTrack?'Con este ritmo llegas al objetivo según los datos actuales.':'Con el ritmo actual no llegas a la fecha objetivo.'} {g.monthly_required!==null&&!onTrack&&<>Necesitarías aumentar la aportación en <strong><Money value={Math.max(0,Number(g.monthly_required)-Number(g.planned_monthly_contribution))}/>/mes</strong>.</>}</div>}
        {!g.target_date&&g.projected_months!==null&&<div className="mt-3 text-sm text-[var(--muted)]">A este ritmo quedarían aproximadamente {g.projected_months} meses.</div>}
        <div className="mt-3 grid grid-cols-[1fr_auto] gap-2">
          <input className="fin-input" aria-label={'Aportación '+g.name} type="number" min="0" step=".01" defaultValue={g.planned_monthly_contribution} id={'goal-plan-'+g.id}/>
          <button className="fin-button secondary" onClick={()=>{
            const account=(document.getElementById('goal-account-'+g.id) as HTMLSelectElement)?.value||'';
            const plan=(document.getElementById('goal-plan-'+g.id) as HTMLInputElement)?.value||g.planned_monthly_contribution;
            update.mutate({id:g.id,account_id:account||null,planned_monthly_contribution:plan});
          }}>Actualizar</button>
        </div>
      </Card>
    }):<EmptyState>No hay objetivos. Crea uno y vincúlalo a la cuenta cuya liquidez representa ese objetivo.</EmptyState>}</div>
    {update.error&&<div className="mt-4"><ErrorState error={update.error}/></div>}
  </>;
}
