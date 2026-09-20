'use client';
import Link from 'next/link';
import {useQuery} from '@tanstack/react-query';
import {apiGet} from '@/lib/api';
import {PageHeader} from '@/components/page-header';
import {Card} from '@/components/ui/card';
import {Money} from '@/components/ui/money';
import {EmptyState,ErrorState,Loading} from '@/components/ui/states';

type Contract={id:string;provider_name:string;contract_type:string;renewal_date:string|null;cancellation_notice_days:number|null;early_exit_penalty:string|null;annual_cost:string|null;evidence_status:string;source_document_id:string|null};
type InsightItem={title:string;detail:string;pages:number[];impact?:string};
type DocInsight={document_id:string;file_name:string;document_type:string;analysis:{summary:string;confidence:string;penalties:InsightItem[];risks:InsightItem[];optimization_opportunities:InsightItem[];negotiation_points:InsightItem[];comparison_requirements:InsightItem[];cross_area_impacts:InsightItem[];missing_information?:InsightItem[]}};

const typeLabel:Record<string,string>={contract:'Contrato',loan:'Préstamo',energy:'Energía',telecom:'Telecomunicaciones',insurance:'Seguro',mortgage:'Hipoteca',service:'Servicio'};
const evidenceLabel:Record<string,string>={confirmed:'Evidencia confirmada',needs_more_data:'Faltan datos',manual:'Registro antiguo/manual'};

export default function ContractsPage(){
  const q=useQuery({queryKey:['contracts'],queryFn:()=>apiGet<Contract[]>('/api/v1/contracts')});
  const insights=useQuery({queryKey:['document-insights','contracts'],queryFn:()=>apiGet<DocInsight[]>('/api/v1/document-insights')});
  const contractInsights=insights.data?.filter(x=>['contract','loan','energy','telecom'].includes(x.document_type))||[];

  return <>
    <PageHeader title="Contratos" description="Una sola fuente de verdad: las condiciones contractuales se extraen y confirman en Documentos; desde ahí alimentan renovaciones, costes, decisiones y simulaciones."/>

    <Card>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div><h2 className="font-bold">Contratos estructurados desde documentación</h2><p className="mt-1 text-sm text-[var(--muted)]">Si un importe, fecha, preaviso o penalización no aparece, complétalo dentro del documento origen. No se mantiene una ficha paralela que pueda quedar desactualizada.</p></div>
        <Link className="fin-button" href="/documents/">Añadir o revisar documentos</Link>
      </div>

      <div className="mt-4 space-y-3">
        {q.isLoading?<Loading/>:q.error?<ErrorState error={q.error}/>:q.data?.length?q.data.map(c=><div key={c.id} className="rounded-xl bg-[var(--surface-2)] p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div><div className="font-bold">{c.provider_name}</div><div className="text-sm text-[var(--muted)]">{typeLabel[c.contract_type]||c.contract_type} · {evidenceLabel[c.evidence_status]||'Requiere revisión'}</div></div>
            <div className="text-right text-sm">{c.annual_cost!==null?<div className="font-semibold"><Money value={c.annual_cost}/>/año</div>:<div className="text-[var(--muted)]">Coste pendiente</div>}</div>
          </div>
          <div className="mt-3 grid gap-2 text-xs sm:grid-cols-3">
            <div className="rounded-lg bg-white p-3"><span className="text-[var(--muted)]">Renovación</span><div className="mt-1 font-medium">{c.renewal_date?new Date(c.renewal_date).toLocaleDateString('es-ES'):'Sin dato confirmado'}</div></div>
            <div className="rounded-lg bg-white p-3"><span className="text-[var(--muted)]">Preaviso</span><div className="mt-1 font-medium">{c.cancellation_notice_days===null?'Sin dato confirmado':c.cancellation_notice_days+' días'}</div></div>
            <div className="rounded-lg bg-white p-3"><span className="text-[var(--muted)]">Penalización de salida</span><div className="mt-1 font-medium"><Money value={c.early_exit_penalty}/></div></div>
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {c.source_document_id?<Link className="fin-button secondary py-2 text-xs" href={'/documents/?document='+encodeURIComponent(c.source_document_id)}>Ver o completar evidencia</Link>:<Link className="fin-button secondary py-2 text-xs" href="/documents/">Vincular a documentación</Link>}
            {!c.source_document_id&&<span className="self-center text-xs text-[var(--muted)]">Registro anterior sin documento canónico asociado.</span>}
          </div>
        </div>):<EmptyState>No hay contratos estructurados. Añade la documentación para que Financito extraiga y reutilice sus condiciones.</EmptyState>}
      </div>
    </Card>

    <Card className="mt-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div><h2 className="font-bold">Conclusiones de contratos</h2><p className="mt-1 text-sm text-[var(--muted)]">La IA local interpreta permanencias, penalizaciones, riesgos y relaciones. Los cálculos materiales siguen usando únicamente hechos confirmados.</p></div>
        <Link className="text-xs underline" href="/documents/">Revisar evidencia</Link>
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        {insights.isLoading?<Loading/>:insights.error?<ErrorState error={insights.error}/>:contractInsights.length?contractInsights.map(x=><div key={x.document_id} className="rounded-xl bg-[var(--surface-2)] p-4 text-sm">
          <div className="flex items-start justify-between gap-3"><div><strong>{x.file_name}</strong><div className="mt-1 text-xs text-[var(--muted)]">Confianza interpretativa {Math.round(Number(x.analysis.confidence)*100)}%</div></div><Link className="text-xs underline" href={'/documents/?document='+encodeURIComponent(x.document_id)}>Evidencia</Link></div>
          <p className="mt-3 text-xs">{x.analysis.summary}</p>
          {x.analysis.penalties.length>0&&<div className="mt-3 text-xs"><strong>Salida:</strong> {x.analysis.penalties.slice(0,3).map(i=>i.title||i.detail).join(' · ')}</div>}
          {x.analysis.optimization_opportunities.length>0&&<div className="mt-3 rounded-lg bg-[var(--brand-soft)] p-2 text-xs"><strong>Oportunidad a revisar:</strong> {x.analysis.optimization_opportunities.slice(0,3).map(i=>i.title||i.detail).join(' · ')}</div>}
          {x.analysis.negotiation_points?.length>0&&<div className="mt-3 text-xs"><strong>Para negociar:</strong> {x.analysis.negotiation_points.slice(0,3).map(i=>i.title||i.detail).join(' · ')}</div>}
          {x.analysis.comparison_requirements?.length>0&&<div className="mt-3 text-xs"><strong>Una alternativa debería mantener:</strong> {x.analysis.comparison_requirements.slice(0,3).map(i=>i.title||i.detail).join(' · ')}</div>}
          {x.analysis.cross_area_impacts?.length>0&&<div className="mt-3 text-xs text-[var(--muted)]"><strong>Impacto en otras áreas:</strong> {x.analysis.cross_area_impacts.slice(0,3).map(i=>i.title||i.detail).join(' · ')}</div>}
          {(x.analysis.missing_information?.length??0)>0&&<div className="mt-3 text-xs"><strong>Falta confirmar:</strong> {(x.analysis.missing_information??[]).slice(0,3).map(i=>i.title||i.detail).join(' · ')}</div>}
        </div>):<EmptyState>Añade contratos para analizarlos automáticamente.</EmptyState>}
      </div>
    </Card>
  </>;
}
