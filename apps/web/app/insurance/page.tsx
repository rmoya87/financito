'use client';

import Link from 'next/link';
import {FormEvent,useState} from 'react';
import {useMutation,useQuery,useQueryClient} from '@tanstack/react-query';
import {apiGet,apiMutate} from '@/lib/api';
import {PageHeader} from '@/components/page-header';
import {Card} from '@/components/ui/card';
import {Money} from '@/components/ui/money';
import {EmptyState,ErrorState,Loading} from '@/components/ui/states';

type CoverageRequirement={id:string;insurance_type:string|null;coverage_type:string;minimum_limit:string|null;currency:string;notes:string|null;enabled:boolean};
type Policy={
  id:string;insurance_type:string;annual_premium:string;monthly_equivalent:string;deductible:string|null;
  source_document_id:string|null;source_document_name:string|null;
  contract:null|{provider_name:string;renewal_date:string|null;cancellation_notice_days:number|null;early_exit_penalty:string|null;evidence_status:string};
  coverages:{id:string;coverage_type:string;limit_amount:string|null;deductible:string|null;confidence:string;user_verified:boolean;source_page:number|null}[];
};
type Missing={field:string;label:string;policy_id:string|null;document_id:string|null;why:string};
type Issue={code:string;severity:string;title:string;detail:string};
type Verdict={
  status:'insufficient_data'|'review_required'|'partial'|'consistent';summary:string;source_of_truth:string;
  policies:Policy[];
  coverage:{verified:number;requirements:number;gaps:{requirement_id:string;coverage_type:string;insurance_type:string|null;reason:string;minimum_limit:string|null;best_verified_limit?:string}[];covered:any[];overlaps:{id:string;coverage_type:string;left_id:string;right_id:string;overlap_type:string;confidence:string}[]};
  finances:{income_last_365_days:string;expenses_last_365_days:string;savings_last_365_days:string;documented_annual_premiums:string;premium_share_of_income:string|null;spend_reconciliation:{period_start:string;period_end:string;data_coverage_days:number;observed_insurance_spend:string;documented_annual_premiums:string;difference:string|null;comparison_reliable:boolean;by_merchant:{merchant:string;amount:string}[]}};
  linked_products:{document_id:string;document_name:string|null;key:string;value:any;page:number|null}[];
  missing_information:Missing[];issues:Issue[];
  ai:null|{plain_summary?:string;priorities?:string[];questions?:string[];model?:string;error?:string};
};
type InsightItem={title:string;detail:string;pages:number[];impact?:string};
type DocInsight={document_id:string;file_name:string;document_type:string;analysis:{summary:string;confidence:string;advantages:InsightItem[];penalties:InsightItem[];risks:InsightItem[];exclusions_or_limits:InsightItem[];optimization_opportunities:InsightItem[];negotiation_points:InsightItem[];comparison_requirements:InsightItem[];cross_area_impacts:InsightItem[];missing_information:InsightItem[]}};

const statusText:Record<Verdict['status'],{title:string;detail:string}>={
  consistent:{title:'Datos consistentes',detail:'No hay huecos ni duplicidades materiales pendientes respecto a tus requisitos confirmados.'},
  review_required:{title:'Revisión necesaria',detail:'Hay diferencias, duplicidades o huecos que conviene resolver antes de tomar una decisión.'},
  partial:{title:'Análisis parcial',detail:'Los datos disponibles son útiles, pero faltan campos o criterios para cerrar la comparación.'},
  insufficient_data:{title:'Falta información',detail:'Aún no hay evidencia documental suficiente para analizar tus seguros.'},
};
const insuranceLabel:Record<string,string>={home:'Hogar',car:'Coche',life:'Vida',health:'Salud',pet:'Mascota',unknown:'Seguro'};

export default function InsurancePage(){
  const qc=useQueryClient();
  const verdict=useQuery({queryKey:['insurance-verdict'],queryFn:()=>apiGet<Verdict>('/api/v1/insurance/verdict')});
  const requirements=useQuery({queryKey:['coverage-requirements'],queryFn:()=>apiGet<CoverageRequirement[]>('/api/v1/coverage-requirements')});
  const insights=useQuery({queryKey:['document-insights','insurance'],queryFn:()=>apiGet<DocInsight[]>('/api/v1/document-insights?document_type=insurance')});
  const analyze=useMutation({
    mutationFn:()=>apiMutate<Verdict>('/api/v1/insurance/verdict/analyze','POST'),
    onSuccess:data=>qc.setQueryData(['insurance-verdict'],data),
  });

  const [req,setReq]=useState({insurance_type:'',coverage_type:'',minimum_limit:'',notes:''});
  const addReq=useMutation({
    mutationFn:()=>apiMutate('/api/v1/coverage-requirements','POST',{insurance_type:req.insurance_type||null,coverage_type:req.coverage_type,minimum_limit:req.minimum_limit||null,currency:'EUR',notes:req.notes||null,enabled:true}),
    onSuccess:()=>{setReq({insurance_type:'',coverage_type:'',minimum_limit:'',notes:''});qc.invalidateQueries({queryKey:['coverage-requirements']});qc.invalidateQueries({queryKey:['insurance-verdict']})},
  });
  const delReq=useMutation({
    mutationFn:(id:string)=>apiMutate('/api/v1/coverage-requirements/'+id,'DELETE'),
    onSuccess:()=>{qc.invalidateQueries({queryKey:['coverage-requirements']});qc.invalidateQueries({queryKey:['insurance-verdict']})},
  });

  const data=verdict.data;
  const status=data?statusText[data.status]:null;

  return <>
    <PageHeader title="Seguros y coberturas" description="La fuente de verdad son tus documentos confirmados. Financito los cruza con movimientos, ingresos, coste, coberturas, duplicidades y productos vinculados antes de darte una conclusión."/>

    {verdict.isLoading?<Loading/>:verdict.error?<ErrorState error={verdict.error}/>:data&&<>
      <Card>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="max-w-3xl">
            <div className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">Veredicto basado en evidencia</div>
            <h2 className="mt-1 text-xl font-bold">{status?.title}</h2>
            <p className="mt-2 text-sm">{data.summary}</p>
            <p className="mt-2 text-xs text-[var(--muted)]">{status?.detail} La IA, cuando se usa, solo explica el resultado; no sustituye los hechos confirmados.</p>
          </div>
          <div className="flex gap-2">
            <Link className="fin-button secondary" href="/documents/">Revisar documentos</Link>
            <button className="fin-button" onClick={()=>analyze.mutate()} disabled={analyze.isPending}>{analyze.isPending?'Analizando con IA…':'Explicar con IA local'}</button>
          </div>
        </div>
        {analyze.error&&<div className="mt-3"><ErrorState error={analyze.error}/></div>}
        {data.ai?.plain_summary&&<div className="mt-4 rounded-xl bg-[var(--brand-soft)] p-4 text-sm"><strong>Lectura de la IA local</strong><p className="mt-1">{data.ai.plain_summary}</p>{data.ai.priorities?.length?<div className="mt-2 text-xs"><strong>Prioridades:</strong> {data.ai.priorities.join(' · ')}</div>:null}{data.ai.questions?.length?<div className="mt-2 text-xs"><strong>Preguntas pendientes:</strong> {data.ai.questions.join(' · ')}</div>:null}<div className="mt-2 text-[11px] text-[var(--muted)]">Modelo: {data.ai.model}</div></div>}
        {data.ai?.error&&<div className="mt-3 text-xs text-[var(--muted)]">La IA local no pudo ampliar el análisis: {data.ai.error}. El veredicto determinista sigue disponible.</div>}
      </Card>

      <div className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Card><div className="text-xs uppercase text-[var(--muted)]">Primas documentadas</div><div className="mt-2 text-2xl font-bold"><Money value={data.finances.documented_annual_premiums}/>/año</div><div className="mt-1 text-xs text-[var(--muted)]">{data.policies.length} póliza(s) proyectadas desde documentos</div></Card>
        <Card><div className="text-xs uppercase text-[var(--muted)]">Pagos clasificados como seguros</div><div className="mt-2 text-2xl font-bold"><Money value={data.finances.spend_reconciliation.observed_insurance_spend}/></div><div className="mt-1 text-xs text-[var(--muted)]">Últimos {data.finances.spend_reconciliation.data_coverage_days} días disponibles</div></Card>
        <Card><div className="text-xs uppercase text-[var(--muted)]">Peso sobre ingresos</div><div className="mt-2 text-2xl font-bold">{data.finances.premium_share_of_income===null?'—':(Number(data.finances.premium_share_of_income)*100).toLocaleString('es-ES',{maximumFractionDigits:1})+'%'}</div><div className="mt-1 text-xs text-[var(--muted)]">Primas documentadas / ingresos observados en 365 días</div></Card>
        <Card><div className="text-xs uppercase text-[var(--muted)]">Coberturas verificadas</div><div className="mt-2 text-2xl font-bold">{data.coverage.verified}</div><div className="mt-1 text-xs text-[var(--muted)]">{data.coverage.gaps.length} hueco(s) · {data.coverage.overlaps.length} posible(s) duplicidad(es)</div></Card>
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        <Card>
          <h2 className="font-bold">Pólizas desde documentación</h2>
          <p className="mt-1 text-sm text-[var(--muted)]">No se crean pólizas paralelas aquí. Si falta un dato, complétalo en el documento original y se propagará automáticamente.</p>
          <div className="mt-4 space-y-3">{data.policies.length?data.policies.map(p=><div key={p.id} className="rounded-xl bg-[var(--surface-2)] p-4">
            <div className="flex items-start justify-between gap-3"><div><strong>{insuranceLabel[p.insurance_type]||p.insurance_type}</strong><div className="text-xs text-[var(--muted)]">{p.contract?.provider_name||p.source_document_name||'Proveedor pendiente'}</div></div><div className="text-right"><strong><Money value={p.annual_premium}/>/año</strong><div className="text-xs text-[var(--muted)]"><Money value={p.monthly_equivalent}/>/mes equivalente</div></div></div>
            <div className="mt-3 grid gap-2 text-xs sm:grid-cols-2">
              <div>Franquicia: <strong><Money value={p.deductible}/></strong></div>
              <div>Renovación: <strong>{p.contract?.renewal_date?new Date(p.contract.renewal_date).toLocaleDateString('es-ES'):'—'}</strong></div>
              <div>Preaviso: <strong>{p.contract?.cancellation_notice_days===null||p.contract?.cancellation_notice_days===undefined?'—':p.contract.cancellation_notice_days+' días'}</strong></div>
              <div>Penalización: <strong><Money value={p.contract?.early_exit_penalty}/></strong></div>
            </div>
            {p.coverages.length>0&&<div className="mt-3 flex flex-wrap gap-1">{p.coverages.map(c=><span key={c.id} className="rounded-full bg-white px-2 py-1 text-[11px]">{c.coverage_type}{c.limit_amount?' · '+new Intl.NumberFormat('es-ES',{style:'currency',currency:'EUR'}).format(Number(c.limit_amount)):''}</span>)}</div>}
            {p.source_document_id&&<Link className="mt-3 inline-block text-xs underline" href={'/documents/?document='+encodeURIComponent(p.source_document_id)}>Ver y completar evidencia</Link>}
          </div>):<EmptyState>Añade tus pólizas en Documentos y confirma los datos extraídos.</EmptyState>}</div>
        </Card>

        <Card>
          <h2 className="font-bold">Qué requiere atención</h2>
          <div className="mt-3 space-y-2">{data.issues.length?data.issues.map(i=><div key={i.code} className="rounded-xl bg-[var(--surface-2)] p-3 text-sm"><strong>{i.title}</strong><div className="mt-1 text-xs text-[var(--muted)]">{i.detail}</div></div>):<EmptyState>No hay incidencias materiales detectadas con los datos actuales.</EmptyState>}</div>
          {data.linked_products.length>0&&<div className="mt-4"><h3 className="text-sm font-semibold">Relaciones con hipoteca u otros productos</h3><div className="mt-2 space-y-2">{data.linked_products.map((x,i)=><div key={x.document_id+x.key+i} className="rounded-xl border border-[var(--border)] p-3 text-xs"><strong>{x.key.replaceAll('_',' ')}</strong><div className="mt-1">{typeof x.value==='string'||typeof x.value==='number'?String(x.value):'Dato vinculado confirmado en la documentación'}</div><Link className="mt-1 inline-block underline" href={'/documents/?document='+encodeURIComponent(x.document_id)}>Ver evidencia{x.page?' · pág. '+x.page:''}</Link></div>)}</div></div>}
        </Card>
      </div>

      <Card className="mt-4">
        <h2 className="font-bold">Conciliación con tus movimientos</h2>
        <p className="mt-1 text-sm text-[var(--muted)]">Compara lo que dicen las pólizas con lo que realmente aparece cargado en tus cuentas. Una diferencia no se interpreta automáticamente como error: puede ser una prima fraccionada, un cambio de precio o un movimiento mal categorizado.</p>
        <div className="mt-4 grid gap-3 md:grid-cols-3">
          <div className="rounded-xl bg-[var(--surface-2)] p-3"><div className="text-xs text-[var(--muted)]">Primas documentadas</div><strong><Money value={data.finances.spend_reconciliation.documented_annual_premiums}/></strong></div>
          <div className="rounded-xl bg-[var(--surface-2)] p-3"><div className="text-xs text-[var(--muted)]">Pagos observados</div><strong><Money value={data.finances.spend_reconciliation.observed_insurance_spend}/></strong></div>
          <div className="rounded-xl bg-[var(--surface-2)] p-3"><div className="text-xs text-[var(--muted)]">Diferencia comparable</div><strong><Money value={data.finances.spend_reconciliation.difference}/></strong><div className="text-[11px] text-[var(--muted)]">{data.finances.spend_reconciliation.comparison_reliable?'Histórico suficiente para conciliación anual':'Aún no hay 330 días de movimientos; no se fuerza una comparación anual'}</div></div>
        </div>
        {data.finances.spend_reconciliation.by_merchant.length>0&&<div className="mt-4 grid gap-2 md:grid-cols-2">{data.finances.spend_reconciliation.by_merchant.slice(0,8).map(x=><div key={x.merchant} className="flex justify-between rounded-xl bg-[var(--surface-2)] p-3 text-sm"><span>{x.merchant}</span><strong><Money value={x.amount}/></strong></div>)}</div>}
      </Card>

      <Card className="mt-4">
        <div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="font-bold">Información que falta</h2><p className="mt-1 text-sm text-[var(--muted)]">Completa estos campos en el documento correspondiente. Así el mismo dato alimenta Seguros, Para ti, Decisiones, hipoteca y cualquier simulación relacionada.</p></div><Link className="text-xs underline" href="/documents/">Abrir Documentos</Link></div>
        <div className="mt-4 grid gap-3 md:grid-cols-2">{data.missing_information.length?data.missing_information.map((m,i)=><div key={(m.document_id||m.policy_id||'x')+m.field+i} className="rounded-xl bg-[var(--surface-2)] p-3 text-sm"><strong>{m.label}</strong><div className="mt-1 text-xs text-[var(--muted)]">{m.why}</div>{m.document_id&&<Link className="mt-2 inline-block text-xs underline" href={'/documents/?document='+encodeURIComponent(m.document_id)}>Completar en el documento</Link>}</div>):<EmptyState>No faltan campos documentales básicos para las pólizas proyectadas.</EmptyState>}</div>
      </Card>
    </>}

    <Card className="mt-4">
      <h2 className="font-bold">Qué cobertura consideras necesaria</h2>
      <p className="mt-1 text-sm text-[var(--muted)]">Estos requisitos son criterios tuyos, no una segunda fuente de hechos sobre la póliza. Sirven para que Financito pueda decir si la documentación acredita lo que necesitas.</p>
      <form className="mt-3 grid gap-2 md:grid-cols-4" onSubmit={(e:FormEvent)=>{e.preventDefault();addReq.mutate()}}>
        <select className="fin-input" aria-label="Tipo de seguro requerido" value={req.insurance_type} onChange={e=>setReq({...req,insurance_type:e.target.value})}><option value="">Cualquier póliza</option><option value="home">Hogar</option><option value="car">Coche</option><option value="life">Vida</option><option value="health">Salud</option><option value="pet">Mascota</option></select>
        <input className="fin-input" placeholder="Cobertura requerida" value={req.coverage_type} onChange={e=>setReq({...req,coverage_type:e.target.value})} required/>
        <input className="fin-input" placeholder="Límite mínimo opcional" value={req.minimum_limit} onChange={e=>setReq({...req,minimum_limit:e.target.value})}/>
        <input className="fin-input" placeholder="Notas" value={req.notes} onChange={e=>setReq({...req,notes:e.target.value})}/>
        <button className="fin-button md:col-span-4">Añadir criterio</button>
      </form>
      <div className="mt-4 grid gap-2 md:grid-cols-2">{requirements.data?.length?requirements.data.map(r=><div key={r.id} className="flex justify-between rounded-xl bg-[var(--surface-2)] p-3 text-sm"><div><strong>{r.coverage_type}</strong><div className="text-xs text-[var(--muted)]">{r.insurance_type?insuranceLabel[r.insurance_type]||r.insurance_type:'cualquier póliza'}{r.minimum_limit?' · mínimo '+new Intl.NumberFormat('es-ES',{style:'currency',currency:r.currency}).format(Number(r.minimum_limit)):''}</div></div><button className="text-xs underline" onClick={()=>delReq.mutate(r.id)}>Eliminar</button></div>):<EmptyState>Sin criterios definidos. Mientras estén vacíos, Financito puede detectar incoherencias y duplicidades, pero no afirmar que tu cobertura sea suficiente.</EmptyState>}</div>
    </Card>

    <Card className="mt-4">
      <div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="font-bold">Lectura de cada póliza</h2><p className="mt-1 text-sm text-[var(--muted)]">Resumen interpretativo de la IA local sobre cada documento; nunca sustituye los campos confirmados de arriba.</p></div><Link className="text-xs underline" href="/documents/">Añadir o revisar documentos</Link></div>
      <div className="mt-4 grid gap-3 md:grid-cols-2">{insights.data?.length?insights.data.map(x=><div key={x.document_id} className="rounded-xl border border-[var(--border)] p-4"><div className="flex items-start justify-between gap-3"><div><strong>{x.file_name}</strong><div className="mt-1 text-xs text-[var(--muted)]">Confianza interpretativa {Math.round(Number(x.analysis.confidence)*100)}%</div></div><Link className="text-xs underline" href={'/documents/?document='+encodeURIComponent(x.document_id)}>Evidencia</Link></div><p className="mt-3 text-sm">{x.analysis.summary}</p>{x.analysis.exclusions_or_limits.length>0&&<div className="mt-3 text-xs"><strong>Límites:</strong> {x.analysis.exclusions_or_limits.slice(0,3).map(i=>i.title||i.detail).join(' · ')}</div>}{x.analysis.optimization_opportunities.length>0&&<div className="mt-3 rounded-xl bg-[var(--brand-soft)] p-3 text-xs"><strong>A revisar:</strong> {x.analysis.optimization_opportunities.slice(0,3).map(i=>i.title||i.detail).join(' · ')}</div>}{x.analysis.cross_area_impacts.length>0&&<div className="mt-3 text-xs text-[var(--muted)]"><strong>Impactos en otras áreas:</strong> {x.analysis.cross_area_impacts.slice(0,3).map(i=>i.title||i.detail).join(' · ')}</div>}</div>):<EmptyState>Añade tus pólizas en Documentos para obtener conclusiones locales.</EmptyState>}</div>
    </Card>
  </>;
}
