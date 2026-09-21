'use client';

import Link from 'next/link';
import {useQuery} from '@tanstack/react-query';
import {apiGet} from '@/lib/api';
import {Card} from '@/components/ui/card';
import {Money} from '@/components/ui/money';
import {EmptyState,ErrorState,Loading} from '@/components/ui/states';

type InsightItem={title:string;detail:string;pages:number[];impact?:string};
type InsightAnalysis={
  summary:string;confidence:string;
  advantages:InsightItem[];penalties:InsightItem[];obligations:InsightItem[];risks:InsightItem[];
  exclusions_or_limits:InsightItem[];linked_products:InsightItem[];optimization_opportunities:InsightItem[];
  negotiation_points:InsightItem[];comparison_requirements:InsightItem[];cross_area_impacts:InsightItem[];missing_information:InsightItem[];
};
type DocInsight={document_id:string;file_name:string;document_type:string;analysis:InsightAnalysis};
type Policy={
  id:string;insurance_type:string;annual_premium:string;monthly_equivalent:string;deductible:string|null;
  policy_number_masked?:string|null;insured_object?:any;
  source_document_ids?:string[];source_documents?:{id:string;file_name:string}[];
  contract:null|{provider_name:string;start_date?:string|null;renewal_date:string|null;cancellation_notice_days:number|null;permanence_end_date?:string|null;early_exit_penalty:string|null;annual_cost?:string|null;evidence_status:string};
  coverages:{id:string;coverage_type:string;limit_amount:string|null;deductible:string|null;confidence:string;user_verified:boolean;effective_from?:string|null;effective_to?:string|null;conditions?:any;exclusions?:any;source_document_id?:string|null;source_page:number|null}[];
};
type Missing={field:string;label:string;policy_id:string|null;document_id:string|null;why:string};
type Pending=Missing&{value:any;unit?:string|null};
type Verdict={status:string;summary:string;policies:Policy[];pending_review:Pending[];missing_information:Missing[]};

const insuranceLabel:Record<string,string>={home:'Hogar',car:'Coche',life:'Vida',health:'Salud',pet:'Mascota',travel:'Viaje',other:'Otro',unknown:'Seguro'};
type InsightKey='advantages'|'penalties'|'obligations'|'risks'|'exclusions_or_limits'|'linked_products'|'optimization_opportunities'|'negotiation_points'|'comparison_requirements'|'cross_area_impacts'|'missing_information';

function readable(value:any):string{
  if(value===null||value===undefined||value==='')return '—';
  if(Array.isArray(value))return value.length?value.map(readable).join(' · '):'—';
  if(typeof value==='object')return Object.entries(value).map(([key,item])=>key.replaceAll('_',' ')+': '+readable(item)).join(' · ')||'—';
  return String(value);
}

function InsightBlock({title,rows,field}:{title:string;rows:DocInsight[];field:InsightKey}){
  const items=rows.flatMap(row=>(row.analysis[field]||[]).map(item=>({item,documentId:row.document_id}))).slice(0,10);
  return <div className="rounded-xl bg-[var(--surface-2)] p-3 text-sm">
    <h4 className="font-semibold">{title}</h4>
    <div className="mt-2 space-y-2">{items.length?items.map(({item,documentId},i)=><div key={field+i} className="text-xs">
      <div><strong>{item.title||item.detail}</strong>{item.detail&&item.title?<span> · {item.detail}</span>:null}</div>
      {item.impact&&<div className="mt-1 text-[var(--muted)]">{item.impact}</div>}
      {!!item.pages?.length&&<a className="mt-1 inline-block underline" target="_blank" rel="noreferrer" href={'/api/v1/documents/'+documentId+'/file#page='+item.pages[0]}>Ver evidencia · pág. {item.pages[0]}</a>}
    </div>):<span className="text-xs text-[var(--muted)]">Sin información específica extraída.</span>}</div>
  </div>;
}

export function InsurancePolicyDetailModal({open,onClose,policyId}:{open:boolean;onClose:()=>void;policyId:string|null}){
  const verdict=useQuery({queryKey:['insurance-verdict-modal'],queryFn:()=>apiGet<Verdict>('/api/v1/insurance/verdict'),enabled:open});
  const insights=useQuery({queryKey:['document-insights-modal'],queryFn:()=>apiGet<DocInsight[]>('/api/v1/document-insights'),enabled:open});
  if(!open)return null;

  const policy=policyId?verdict.data?.policies.find(item=>item.id===policyId)||null:null;
  const rows=policy? (insights.data||[]).filter(item=>new Set(policy.source_document_ids||[]).has(item.document_id)) : [];
  const pending=policy?verdict.data?.pending_review.filter(item=>item.policy_id===policy.id)||[]:[];
  const missing=policy?verdict.data?.missing_information.filter(item=>item.policy_id===policy.id)||[]:[];

  return <div className="fixed inset-0 z-[70] overflow-y-auto bg-black/45 p-4 md:p-8" role="dialog" aria-modal="true" aria-label="Detalle de Seguros y coberturas">
    <div className="mx-auto max-w-6xl">
      <Card>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">Seguros y coberturas</div>
            <h2 className="mt-1 text-xl font-bold">{policy?insuranceLabel[policy.insurance_type]||policy.insurance_type:'Detalle completo'}</h2>
            {policy?<div className="mt-1 text-sm text-[var(--muted)]">{policy.contract?.provider_name||'Proveedor pendiente'}{policy.policy_number_masked?' · póliza '+policy.policy_number_masked:''}</div>:<p className="mt-1 text-sm text-[var(--muted)]">{verdict.data?.summary||'Cargando situación global de seguros…'}</p>}
          </div>
          <button className="fin-button secondary py-2 text-xs" type="button" onClick={onClose}>Cerrar</button>
        </div>

        {verdict.isLoading||insights.isLoading?<div className="mt-4"><Loading/></div>:verdict.error||insights.error?<div className="mt-4"><ErrorState error={(verdict.error||insights.error)!}/></div>:policy?<>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-xl bg-[var(--surface-2)] p-3"><div className="text-xs text-[var(--muted)]">Prima anual</div><strong><Money value={policy.annual_premium}/></strong></div>
            <div className="rounded-xl bg-[var(--surface-2)] p-3"><div className="text-xs text-[var(--muted)]">Equivalente mensual</div><strong><Money value={policy.monthly_equivalent}/></strong></div>
            <div className="rounded-xl bg-[var(--surface-2)] p-3"><div className="text-xs text-[var(--muted)]">Renovación</div><strong>{policy.contract?.renewal_date||'—'}</strong></div>
            <div className="rounded-xl bg-[var(--surface-2)] p-3"><div className="text-xs text-[var(--muted)]">Penalización salida</div><strong><Money value={policy.contract?.early_exit_penalty}/></strong></div>
          </div>

          <div className="mt-5 grid gap-4 lg:grid-cols-2">
            <div className="rounded-xl border border-[var(--border)] p-4">
              <h3 className="font-semibold">Condiciones contractuales</h3>
              <div className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
                <div>Inicio: <strong>{policy.contract?.start_date||'—'}</strong></div>
                <div>Renovación: <strong>{policy.contract?.renewal_date||'—'}</strong></div>
                <div>Preaviso: <strong>{policy.contract?.cancellation_notice_days==null?'—':policy.contract.cancellation_notice_days+' días'}</strong></div>
                <div>Fin permanencia: <strong>{policy.contract?.permanence_end_date||'—'}</strong></div>
                <div>Franquicia: <strong><Money value={policy.deductible}/></strong></div>
                <div>Coste anual: <strong><Money value={policy.contract?.annual_cost||policy.annual_premium}/></strong></div>
                <div className="sm:col-span-2">Objeto asegurado: <strong>{readable(policy.insured_object)}</strong></div>
              </div>
            </div>
            <div className="rounded-xl border border-[var(--border)] p-4">
              <h3 className="font-semibold">Documentos asociados</h3>
              <div className="mt-3 space-y-2">{policy.source_documents?.length?policy.source_documents.map(doc=><a key={doc.id} target="_blank" rel="noreferrer" href={'/api/v1/documents/'+doc.id+'/file'} className="block rounded-xl bg-[var(--surface-2)] p-3 text-sm underline">{doc.file_name}</a>):<EmptyState>Sin documentos asociados.</EmptyState>}</div>
            </div>
          </div>

          <div className="mt-5">
            <h3 className="font-semibold">Coberturas, límites y exclusiones</h3>
            <div className="mt-3 space-y-2">{policy.coverages.length?policy.coverages.map(c=><div key={c.id} className="rounded-xl bg-[var(--surface-2)] p-3 text-sm"><strong>{c.coverage_type}</strong><div className="mt-1 text-xs">Límite: <Money value={c.limit_amount}/> · Franquicia: <Money value={c.deductible}/></div><div className="mt-1 text-xs text-[var(--muted)]">Condiciones: {readable(c.conditions)} · Exclusiones: {readable(c.exclusions)}</div></div>):<EmptyState>Sin coberturas verificadas.</EmptyState>}</div>
          </div>

          <div className="mt-5">
            <h3 className="font-semibold">Todo lo indicado por la documentación</h3>
            <p className="mt-1 text-xs text-[var(--muted)]">Misma lectura interpretativa que aparece en Detalle del documento, agrupada aquí para esta póliza.</p>
            <div className="mt-3 grid gap-3 md:grid-cols-2">
              <InsightBlock title="Ventajas y coberturas útiles" rows={rows} field="advantages"/>
              <InsightBlock title="Penalizaciones y costes de salida" rows={rows} field="penalties"/>
              <InsightBlock title="Obligaciones" rows={rows} field="obligations"/>
              <InsightBlock title="Riesgos" rows={rows} field="risks"/>
              <InsightBlock title="Exclusiones o límites" rows={rows} field="exclusions_or_limits"/>
              <InsightBlock title="Productos vinculados" rows={rows} field="linked_products"/>
              <InsightBlock title="Oportunidades de optimizar" rows={rows} field="optimization_opportunities"/>
              <InsightBlock title="Puntos para negociar" rows={rows} field="negotiation_points"/>
              <InsightBlock title="Qué exigir para comparar ofertas" rows={rows} field="comparison_requirements"/>
              <InsightBlock title="Impactos en otras áreas" rows={rows} field="cross_area_impacts"/>
              <InsightBlock title="Información que falta" rows={rows} field="missing_information"/>
            </div>
          </div>

          {(pending.length>0||missing.length>0)&&<div className="mt-5 grid gap-3 md:grid-cols-2">
            <div className="rounded-xl bg-[var(--brand-soft)] p-3 text-sm"><strong>Datos pendientes de confirmar</strong><div className="mt-2 space-y-1 text-xs">{pending.length?pending.map((item,i)=><div key={i}>{item.label}: {readable(item.value)}{item.unit?' '+item.unit:''}</div>):'Ninguno'}</div></div>
            <div className="rounded-xl bg-[var(--surface-2)] p-3 text-sm"><strong>Información que falta</strong><div className="mt-2 space-y-1 text-xs">{missing.length?missing.map((item,i)=><div key={i}>{item.label}: {item.why}</div>):'Ninguna'}</div></div>
          </div>}

          <Link className="fin-button mt-5 inline-flex" href={'/insurance/?policy='+encodeURIComponent(policy.id)}>Abrir en Seguros y coberturas</Link>
        </>:<div className="mt-4">
          <p className="text-sm">{verdict.data?.summary}</p>
          <div className="mt-3 grid gap-2 md:grid-cols-2">{verdict.data?.policies.length?verdict.data.policies.map(item=><div key={item.id} className="rounded-xl bg-[var(--surface-2)] p-3 text-sm"><strong>{insuranceLabel[item.insurance_type]||item.insurance_type}</strong><div className="mt-1 text-xs text-[var(--muted)]">{item.contract?.provider_name||'Proveedor pendiente'} · <Money value={item.annual_premium}/> / año</div></div>):<EmptyState>Sin pólizas consolidadas.</EmptyState>}</div>
          <Link className="fin-button mt-4 inline-flex" href="/insurance/">Abrir Seguros y coberturas</Link>
        </div>}
      </Card>
    </div>
  </div>;
}
