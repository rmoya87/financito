'use client';
import Link from 'next/link';
import {useMutation,useQuery,useQueryClient} from '@tanstack/react-query';
import {CalendarClock,FileText,ShieldCheck} from 'lucide-react';
import {apiGet,apiMutate} from '@/lib/api';
import {PageHeader} from '@/components/page-header';
import {Card} from '@/components/ui/card';
import {EmptyState,ErrorState,Loading} from '@/components/ui/states';
import {Money} from '@/components/ui/money';

type Action={id:string;title:string;action_type:string;priority:string;status:string;due_date:string|null;notes:string|null;related_entity_type:string|null;related_entity_id:string|null};
type Contract={id:string;provider_name:string;contract_type:string;renewal_date:string|null;cancellation_notice_days:number|null;early_exit_penalty:string|null;annual_cost:string|null;evidence_status:string;source_document_id:string|null};
type Insurance={id:string;insurance_type:string;annual_premium:string;deductible:string|null;contract_id:string|null;source_document_id:string|null};
type Coverage={id:string;coverage_type:string;contract_id:string|null;insurance_policy_id:string|null;limit_amount:string|null;deductible:string|null;confidence:string;user_verified:boolean};
const priorityLabel:Record<string,string>={critical:'Urgente',high:'Alta prioridad',medium:'Prioridad media',low:'Baja prioridad'};
const actionLabel:Record<string,string>={banking_consent_renewal:'Renovar acceso bancario',review_document_evidence:'Confirmar datos de un documento',review_document_ai_insights:'Revisar conclusiones del documento',contract_renewal:'Revisar renovación',contract_cancellation_notice:'Revisar plazo de cancelación'};

export default function ActionsPage(){
  const qc=useQueryClient();
  const q=useQuery({queryKey:['actions'],queryFn:()=>apiGet<Action[]>('/api/v1/actions')});
  const contracts=useQuery({queryKey:['contracts'],queryFn:()=>apiGet<Contract[]>('/api/v1/contracts')});
  const insurance=useQuery({queryKey:['insurance'],queryFn:()=>apiGet<Insurance[]>('/api/v1/insurance')});
  const coverage=useQuery({queryKey:['coverage'],queryFn:()=>apiGet<Coverage[]>('/api/v1/coverage')});
  const update=useMutation({
    mutationFn:({id,status}:{id:string;status:string})=>apiMutate(`/api/v1/actions/${id}`,'PATCH',{status}),
    onSuccess:()=>{qc.invalidateQueries({queryKey:['actions']});qc.invalidateQueries({queryKey:['dashboard']})},
  });

  const active=(q.data||[]).filter(a=>a.status==="pending"||a.status==="in_progress");

  return <>
    <PageHeader title="Para ti" description="Alertas, oportunidades y próximos pasos construidos a partir de tus datos, contratos y objetivos."/>

    <div className="mb-5 grid gap-3 md:grid-cols-3">
      <Link href="/forecast/" className="fin-card flex items-center gap-4 p-4 hover:border-[var(--brand)]">
        <div className="grid size-10 place-items-center rounded-xl bg-[var(--brand-soft)] text-[var(--brand)]"><CalendarClock size={20}/></div>
        <div><div className="font-semibold">Previsión</div><div className="text-xs text-[var(--muted)]">Qué viene y cómo afecta a tu liquidez</div></div>
      </Link>
      <Link href="/contracts/" className="fin-card flex items-center gap-4 p-4 hover:border-[var(--brand)]">
        <div className="grid size-10 place-items-center rounded-xl bg-[var(--brand-soft)] text-[var(--brand)]"><FileText size={20}/></div>
        <div><div className="font-semibold">Contratos</div><div className="text-xs text-[var(--muted)]">Renovaciones, preavisos y costes</div></div>
      </Link>
      <Link href="/insurance/" className="fin-card flex items-center gap-4 p-4 hover:border-[var(--brand)]">
        <div className="grid size-10 place-items-center rounded-xl bg-[var(--brand-soft)] text-[var(--brand)]"><ShieldCheck size={20}/></div>
        <div><div className="font-semibold">Seguros</div><div className="text-xs text-[var(--muted)]">Coberturas, duplicidades y huecos</div></div>
      </Link>
    </div>

    <Card>
      <div className="mb-4">
        <h2 className="font-bold">Pendiente de ti</h2>
        <p className="mt-1 text-sm text-[var(--muted)]">Financito propone y organiza; las acciones externas siguen bajo tu control.</p>
      </div>
      {q.isLoading?<Loading/>:q.error?<ErrorState error={q.error}/>:active.length?
        <div className="flex flex-col gap-3">{active.map(a=><div key={a.id} className="flex flex-col gap-3 rounded-xl bg-[var(--surface-2)] p-4 md:flex-row md:items-center md:justify-between">
          <div>
            <div className="text-xs uppercase text-[var(--muted)]">{priorityLabel[a.priority]||"Revisar"} · {actionLabel[a.action_type]||a.action_type.replaceAll("_"," ")}</div>
            <div className="mt-1 font-semibold">{a.title}</div>
            {a.notes?<div className="mt-1 max-w-2xl text-xs text-[var(--muted)]">{a.notes}</div>:null}
            {a.due_date?<div className="text-xs text-[var(--muted)]">Antes de {a.due_date}</div>:null}
          </div>
          <div className="flex flex-wrap gap-2">
            {a.related_entity_type==="document"&&a.related_entity_id&&["review_document_evidence","review_document_ai_insights"].includes(a.action_type)?
              <Link className="fin-button py-2 text-xs" href={`/documents/?document=${encodeURIComponent(a.related_entity_id)}`}>{a.action_type==="review_document_ai_insights"?"Revisar conclusiones":"Revisar documento"}</Link>:
              <button className="fin-button py-2 text-xs" onClick={()=>update.mutate({id:a.id,status:'done'})}>Hecho</button>}
            <button className="fin-button secondary py-2 text-xs" onClick={()=>update.mutate({id:a.id,status:'dismissed'})}>Descartar</button>
          </div>
        </div>)}</div>:
        <EmptyState>No hay acciones pendientes.</EmptyState>}
    </Card>

    <div className="mt-4 grid gap-4 xl:grid-cols-2">
      <Card>
        <div className="flex items-start justify-between gap-3"><div><h2 className="font-bold">Contratos extraídos de tus documentos</h2><p className="mt-1 text-sm text-[var(--muted)]">Coste, renovación, preaviso y penalizaciones confirmadas o pendientes de confirmar.</p></div><Link className="text-xs underline" href="/contracts/">Ver todos</Link></div>
        <div className="mt-4 space-y-3">{contracts.data?.length?contracts.data.map(x=><div key={x.id} className="rounded-xl bg-[var(--surface-2)] p-3 text-sm"><div className="flex items-start justify-between gap-3"><div><strong>{x.provider_name}</strong><div className="text-xs text-[var(--muted)]">{x.contract_type}</div></div>{x.annual_cost!==null&&<strong><Money value={x.annual_cost}/>/año</strong>}</div><div className="mt-2 grid gap-1 text-xs text-[var(--muted)]">{x.renewal_date&&<div>Renovación: {new Date(x.renewal_date).toLocaleDateString('es-ES')}</div>}{x.cancellation_notice_days!==null&&<div>Preaviso de cancelación: {x.cancellation_notice_days} días</div>}<div>Penalización de salida: {x.early_exit_penalty===null?'pendiente de confirmar':<Money value={x.early_exit_penalty}/>}</div><div>Evidencia: {x.evidence_status==='confirmed'?'confirmada':'requiere revisión'}</div></div>{x.source_document_id&&<Link className="mt-2 inline-block text-xs underline" href={'/documents/?document='+encodeURIComponent(x.source_document_id)}>Ver evidencia</Link>}</div>):<EmptyState>Aún no hay contratos estructurados. Añade sus documentos para que Financito extraiga sus condiciones.</EmptyState>}</div>
      </Card>
      <Card>
        <div className="flex items-start justify-between gap-3"><div><h2 className="font-bold">Seguros y coberturas</h2><p className="mt-1 text-sm text-[var(--muted)]">Prima, franquicia y coberturas estructuradas a partir de tus pólizas.</p></div><Link className="text-xs underline" href="/insurance/">Ver todos</Link></div>
        <div className="mt-4 space-y-3">{insurance.data?.length?insurance.data.map(x=>{const cov=(coverage.data||[]).filter(c=>c.insurance_policy_id===x.id);return <div key={x.id} className="rounded-xl bg-[var(--surface-2)] p-3 text-sm"><div className="flex items-start justify-between gap-3"><strong>{x.insurance_type}</strong><strong><Money value={x.annual_premium}/>/año</strong></div><div className="mt-1 text-xs text-[var(--muted)]">Franquicia: {x.deductible===null?'sin dato':<Money value={x.deductible}/>}</div>{cov.length>0&&<div className="mt-2 flex flex-wrap gap-1">{cov.map(c=><span key={c.id} className="rounded-full bg-white px-2 py-1 text-[11px]">{c.coverage_type}{c.limit_amount?' · '+new Intl.NumberFormat('es-ES',{style:'currency',currency:'EUR'}).format(Number(c.limit_amount)):''}{c.user_verified?'':' · por verificar'}</span>)}</div>}{x.source_document_id&&<Link className="mt-2 inline-block text-xs underline" href={'/documents/?document='+encodeURIComponent(x.source_document_id)}>Ver póliza</Link>}</div>}):<EmptyState>Aún no hay pólizas estructuradas. Añade la documentación para ver coberturas y condiciones aquí.</EmptyState>}</div>
      </Card>
    </div>
  </>;
}
