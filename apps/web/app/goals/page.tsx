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

type Account={id:string;name:string;institution_name:string;current_balance:string;available_balance:string|null};
type Health={emergency_fund:{essential_monthly:string;allocated:string;coverage_months:string|null;minimum_buffer:string}};
type G={
  id:string;type:string;name:string;target_amount:string;current_amount:string;allocated_amount:string;current_amount_source:string;
  account_id:string|null;account_name:string|null;account_institution:string|null;account_balance:string|null;account_reserved_total:string|null;available_to_allocate:string|null;
  target_date:string|null;priority:string;status:string;planned_monthly_contribution:string;remaining_amount:string;months_left:number|null;monthly_required:string|null;projected_months:number|null;
  emergency_months_target:number|null;essential_monthly:string|null;coverage_months:string|null
};

export default function GoalsPage(){
  const qc=useQueryClient();
  const q=useQuery({queryKey:['goals'],queryFn:()=>apiGet<G[]>('/api/v1/goals')});
  const accounts=useQuery({queryKey:['accounts','goals'],queryFn:()=>apiGet<Account[]>('/api/v1/accounts')});
  const health=useQuery({queryKey:['financial-health','goals'],queryFn:()=>apiGet<Health>('/api/v1/financial-health')});
  const [f,setF]=useState({name:'',goal_type:'emergency_fund',target_amount:'',allocated_amount:'0',account_id:'',target_date:'',planned_monthly_contribution:'0',priority:'medium',emergency_months_target:'6'});
  const emergencyTarget=useMemo(()=>Number(health.data?.emergency_fund.essential_monthly||0)*Number(f.emergency_months_target||6),[health.data,f.emergency_months_target]);
  const goalSummary=useMemo(()=>{
    const rows=q.data||[];
    return {
      count:rows.length,
      reserved:rows.reduce((sum,row)=>sum+Number(row.current_amount||0),0),
      target:rows.reduce((sum,row)=>sum+Number(row.target_amount||0),0),
      offTrack:rows.filter(row=>row.monthly_required!==null&&Number(row.planned_monthly_contribution)<Number(row.monthly_required)).length,
    };
  },[q.data]);
  const add=useMutation({
    mutationFn:()=>apiMutate<G>('/api/v1/goals','POST',{
      ...f,target_amount:f.goal_type==='emergency_fund'?String(emergencyTarget):f.target_amount,
      allocated_amount:f.allocated_amount||'0',current_amount:'0',target_date:f.target_date||null,
      emergency_months_target:f.goal_type==='emergency_fund'?Number(f.emergency_months_target):null,
    }),
    onSuccess:()=>{setF({...f,name:'',target_amount:'',allocated_amount:'0',target_date:'',planned_monthly_contribution:'0'});qc.invalidateQueries({queryKey:['goals']});qc.invalidateQueries({queryKey:['financial-health']});qc.invalidateQueries({queryKey:['dashboard']})},
  });
  const update=useMutation({
    mutationFn:({id,account_id,allocated_amount,planned_monthly_contribution,emergency_months_target}:{id:string;account_id:string|null;allocated_amount:string;planned_monthly_contribution:string;emergency_months_target:number|null})=>
      apiMutate<G>('/api/v1/goals/'+id,'PATCH',{account_id,allocated_amount,planned_monthly_contribution,emergency_months_target}),
    onSuccess:()=>{qc.invalidateQueries({queryKey:['goals']});qc.invalidateQueries({queryKey:['financial-health']});qc.invalidateQueries({queryKey:['dashboard']})},
  });
  const remove=useMutation({mutationFn:(id:string)=>apiMutate('/api/v1/goals/'+id,'DELETE'),onSuccess:()=>{qc.invalidateQueries({queryKey:['goals']});qc.invalidateQueries({queryKey:['financial-health']});qc.invalidateQueries({queryKey:['dashboard']})}});

  return <>
    <PageHeader title="Objetivos" description="Reserva dinero de forma explícita. Dos objetivos nunca pueden apropiarse del mismo saldo: la suma de bolsas de una cuenta no puede superar su liquidez real."/>
    {q.data&&<>
      <SectionIntro eyebrow="Lectura rápida" title="Tus metas de ahorro" description="Cuánto has reservado de verdad, cuánto falta y qué objetivos necesitan ajustar el ritmo."/>
      <div className="mb-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <MetricTile label="Objetivos activos" value={goalSummary.count} detail="Bolsas con dinero reservado o meta pendiente"/>
        <MetricTile label="Reservado" value={<Money value={goalSummary.reserved}/>} detail="Dinero que ya no se considera libre para gastar" status="Protegido" statusTone="confirmed"/>
        <MetricTile label="Meta total" value={<Money value={goalSummary.target}/>} detail="Suma de los importes objetivo" status="Definido por ti" statusTone="confirmed"/>
        <MetricTile label="Fuera de ritmo" value={goalSummary.offTrack} detail="Necesitarían una aportación mensual mayor" status={goalSummary.offTrack?'Revisar':'En ritmo'} statusTone={goalSummary.offTrack?'pending':'confirmed'} emphasis={goalSummary.offTrack>0}/>
      </div>
    </>}
    {health.data&&<VisualPanel title="Fondo de emergencia" description="El colchón se calcula a partir de tu gasto esencial reciente y del dinero realmente reservado." status="Calculado" statusTone="calculated" className="mb-4">
      <div className="text-2xl font-bold">{health.data.emergency_fund.coverage_months||'0'} meses de cobertura</div>
      <div className="mt-3 grid gap-3 sm:grid-cols-3 text-sm"><div className="rounded-xl bg-[var(--surface-2)] p-3"><div className="text-xs text-[var(--muted)]">Gasto esencial mensual</div><strong><Money value={health.data.emergency_fund.essential_monthly}/></strong></div><div className="rounded-xl bg-[var(--surface-2)] p-3"><div className="text-xs text-[var(--muted)]">Reservado como colchón</div><strong><Money value={health.data.emergency_fund.allocated}/></strong></div><div className="rounded-xl bg-[var(--surface-2)] p-3"><div className="text-xs text-[var(--muted)]">Colchón mínimo operativo</div><strong><Money value={health.data.emergency_fund.minimum_buffer}/></strong></div></div>
    </VisualPanel>}

    <VisualPanel title="Nuevo objetivo" description="Crea una bolsa y decide cuánto dinero de una cuenta queda reservado exclusivamente para ella.">
      <form className="mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-4" onSubmit={(e:FormEvent)=>{e.preventDefault();add.mutate()}}>
        <select className="fin-input" aria-label="Tipo de objetivo" value={f.goal_type} onChange={e=>setF({...f,goal_type:e.target.value})}>
          <option value="emergency_fund">Fondo de emergencia</option><option value="home">Vivienda</option><option value="debt">Amortizar deuda</option><option value="travel">Viaje</option><option value="car">Coche</option><option value="investment">Inversión</option><option value="saving">Ahorro</option><option value="other">Otro</option>
        </select>
        <input className="fin-input" placeholder="Nombre del objetivo" value={f.name} onChange={e=>setF({...f,name:e.target.value})} required/>
        {f.goal_type==='emergency_fund'?<select className="fin-input" aria-label="Meses de fondo de emergencia" value={f.emergency_months_target} onChange={e=>setF({...f,emergency_months_target:e.target.value})}>{[3,6,9,12].map(x=><option key={x} value={x}>{x} meses · {emergencyTarget?Math.round(Number(health.data?.emergency_fund.essential_monthly||0)*x).toLocaleString('es-ES')+' €':'calculado con tu gasto'}</option>)}</select>:<input className="fin-input" type="number" min="0.01" step=".01" placeholder="Importe objetivo" value={f.target_amount} onChange={e=>setF({...f,target_amount:e.target.value})} required/>}
        <select className="fin-input" aria-label="Cuenta bancaria del objetivo" value={f.account_id} onChange={e=>setF({...f,account_id:e.target.value})} required><option value="">Cuenta donde reservar…</option>{accounts.data?.map(a=><option key={a.id} value={a.id}>{a.institution_name} · {a.name}</option>)}</select>
        <input className="fin-input" aria-label="Importe reservado inicial" type="number" min="0" step=".01" placeholder="Reservar ahora (€)" value={f.allocated_amount} onChange={e=>setF({...f,allocated_amount:e.target.value})}/>
        <label className="text-sm text-[var(--muted)]">Fecha objetivo<input className="fin-input mt-1" type="date" value={f.target_date} onChange={e=>setF({...f,target_date:e.target.value})}/></label>
        <label className="text-sm text-[var(--muted)]">Aportación mensual prevista<input className="fin-input mt-1" type="number" min="0" step=".01" value={f.planned_monthly_contribution} onChange={e=>setF({...f,planned_monthly_contribution:e.target.value})}/></label>
        <button className="fin-button self-end" disabled={add.isPending||!f.account_id}>{add.isPending?'Reservando…':'Crear objetivo'}</button>
      </form>
      {add.error&&<div className="mt-3"><ErrorState error={add.error}/></div>}
    </VisualPanel>

    <div className="mt-6"><SectionIntro eyebrow="Detalle" title="Objetivos y reservas" description="Cada tarjeta separa dinero reservado, saldo todavía asignable y ritmo necesario para llegar a la fecha."/></div>
    {q.isLoading?<div className="mt-4"><Loading/></div>:<div className="mt-4 grid gap-4 md:grid-cols-2">{q.data?.length?q.data.map(g=>{
      const pct=Math.min(100,Number(g.current_amount)/Math.max(1,Number(g.target_amount))*100);
      const onTrack=g.monthly_required===null||Number(g.planned_monthly_contribution)>=Number(g.monthly_required);
      return <Card key={g.id}>
        <div className="flex items-start justify-between gap-3"><div><div className="font-bold">{g.name}</div><div className="text-xs text-[var(--muted)]">{g.type==='emergency_fund'?'Fondo de emergencia':g.type.replaceAll('_',' ')} · {g.status==='completed'?'Completado':'En curso'}</div></div><div className="text-right"><div className="font-semibold">{Math.round(pct)}%</div><div className="text-xs text-[var(--muted)]">reservado</div></div></div>
        <div className="mt-3 h-2 rounded-full bg-[var(--surface-2)]"><div className="h-2 rounded-full bg-[var(--brand)]" style={{width:String(pct)+'%'}}/></div>
        <div className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
          <div className="rounded-xl bg-[var(--surface-2)] p-3"><div className="text-xs text-[var(--muted)]">Reservado / objetivo</div><strong><Money value={g.current_amount}/> / <Money value={g.target_amount}/></strong><div className="mt-1 text-[11px] text-[var(--muted)]">Dinero asignado exclusivamente a esta bolsa.</div></div>
          <div className="rounded-xl bg-[var(--surface-2)] p-3"><div className="text-xs text-[var(--muted)]">Sin asignar en esta cuenta</div><strong>{g.available_to_allocate===null?'—':<Money value={g.available_to_allocate}/>}</strong><div className="mt-1 text-[11px] text-[var(--muted)]">Saldo que todavía puede repartirse entre objetivos.</div></div>
          {g.type==='emergency_fund'&&<div className="rounded-xl bg-[var(--surface-2)] p-3"><div className="text-xs text-[var(--muted)]">Cobertura actual</div><strong>{g.coverage_months||'0'} meses</strong><div className="text-[11px] text-[var(--muted)]">Meta {g.emergency_months_target||6} meses.</div></div>}
          {g.monthly_required!==null&&<div className="rounded-xl bg-[var(--surface-2)] p-3"><div className="text-xs text-[var(--muted)]">Necesario al mes</div><strong><Money value={g.monthly_required}/></strong></div>}
        </div>
        {g.target_date&&<div className={'mt-3 rounded-xl p-3 text-sm '+(onTrack?'bg-[var(--brand-soft)]':'bg-amber-50')}>{onTrack?'Con este ritmo llegas al objetivo.':'Con el ritmo actual no llegas a la fecha objetivo.'}</div>}
        <div className="mt-3 grid gap-2 sm:grid-cols-2">
          <select className="fin-input" aria-label={'Cuenta del objetivo '+g.name} defaultValue={g.account_id||''} id={'goal-account-'+g.id}><option value="">Sin cuenta</option>{accounts.data?.map(a=><option key={a.id} value={a.id}>{a.institution_name} · {a.name}</option>)}</select>
          <input className="fin-input" aria-label={'Reserva '+g.name} type="number" min="0" step=".01" defaultValue={g.allocated_amount} id={'goal-allocation-'+g.id}/>
          <input className="fin-input" aria-label={'Aportación '+g.name} type="number" min="0" step=".01" defaultValue={g.planned_monthly_contribution} id={'goal-plan-'+g.id}/>
          {g.type==='emergency_fund'?<select className="fin-input" aria-label={'Meses '+g.name} defaultValue={g.emergency_months_target||6} id={'goal-months-'+g.id}>{[3,6,9,12].map(x=><option key={x} value={x}>{x} meses</option>)}</select>:<div/>}
        </div>
        <div className="mt-3 flex gap-3"><button className="fin-button secondary" onClick={()=>{
          const account=(document.getElementById('goal-account-'+g.id) as HTMLSelectElement)?.value||'';
          const allocation=(document.getElementById('goal-allocation-'+g.id) as HTMLInputElement)?.value||'0';
          const plan=(document.getElementById('goal-plan-'+g.id) as HTMLInputElement)?.value||g.planned_monthly_contribution;
          const monthsEl=document.getElementById('goal-months-'+g.id) as HTMLSelectElement|null;
          update.mutate({id:g.id,account_id:account||null,allocated_amount:allocation,planned_monthly_contribution:plan,emergency_months_target:monthsEl?Number(monthsEl.value):null});
        }}>Actualizar</button><button className="text-xs underline" onClick={()=>remove.mutate(g.id)}>Eliminar objetivo</button></div>
      </Card>
    }):<EmptyState>No hay objetivos. Crea una bolsa y reserva solo el dinero que realmente quieras apartar.</EmptyState>}</div>}
    {(update.error||remove.error)&&<div className="mt-4"><ErrorState error={(update.error||remove.error)!}/></div>}
  </>;
}
