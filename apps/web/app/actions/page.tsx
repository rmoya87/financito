'use client';
import Link from 'next/link';
import {useMutation,useQuery,useQueryClient} from '@tanstack/react-query';
import {CalendarClock,FileText,ShieldCheck} from 'lucide-react';
import {apiGet,apiMutate} from '@/lib/api';
import {PageHeader} from '@/components/page-header';
import {Card} from '@/components/ui/card';
import {EmptyState,ErrorState,Loading} from '@/components/ui/states';

type Action={id:string;title:string;action_type:string;priority:string;status:string;due_date:string|null;notes:string|null;related_entity_type:string|null;related_entity_id:string|null};

export default function ActionsPage(){
  const qc=useQueryClient();
  const q=useQuery({queryKey:['actions'],queryFn:()=>apiGet<Action[]>('/api/v1/actions')});
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
            <div className="text-xs uppercase text-[var(--muted)]">{a.priority} · {a.action_type}</div>
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
  </>;
}
