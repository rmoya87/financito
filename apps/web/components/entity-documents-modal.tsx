'use client';

import {useEffect,useRef,useState} from 'react';
import {useMutation,useQuery,useQueryClient} from '@tanstack/react-query';
import {apiGet,apiMutate,apiUpload} from '@/lib/api';
import {Card} from '@/components/ui/card';
import {EmptyState,ErrorState,Loading} from '@/components/ui/states';

type EntityType='mortgage'|'insurance_policy';
type Review={total:number;pending:number;confirmed:number;ambiguous:number;reviewed:number};
type Doc={id:string;file_name:string;document_type:string;status:string;page_count:number;review:Review;ai_analysis:'ready'|'not_analyzed'};
type Insight={title:string;detail:string;pages:number[];impact?:string};
type Analysis={confidence:string;summary:string;advantages:Insight[];penalties:Insight[];obligations:Insight[];risks:Insight[];exclusions_or_limits:Insight[];linked_products:Insight[];optimization_opportunities:Insight[];negotiation_points:Insight[];comparison_requirements:Insight[];cross_area_impacts:Insight[];missing_information:Insight[]};
type AnalysisResponse={document_id:string;status:'ready'|'not_analyzed';analysis:Analysis|null;ai:{available:boolean;configured_model:string|null;chat_ready?:boolean}};
type UploadResponse={documents:{id:string;file_name:string}[];ai_analysis_scheduled:boolean};

function InsightList({title,items,documentId}:{title:string;items:Insight[];documentId:string}){
  if(!items.length)return null;
  return <div className="rounded-xl bg-[var(--surface-2)] p-3">
    <div className="text-xs font-semibold">{title}</div>
    <div className="mt-2 space-y-2">{items.slice(0,4).map((item,index)=><div key={index} className="text-xs">
      <div className="font-medium">{item.title||item.detail}</div>
      {item.detail&&item.detail!==item.title&&<div className="mt-0.5 text-[var(--muted)]">{item.detail}</div>}
      {item.pages?.length?<a className="mt-1 inline-block underline" target="_blank" rel="noreferrer" href={'/api/v1/documents/'+documentId+'/file#page='+item.pages[0]}>Ver en el documento · pág. {item.pages[0]}</a>:null}
    </div>)}</div>
  </div>;
}

export function EntityDocumentsModal({
  open,onClose,entityType,entityId,title,documentType
}:{
  open:boolean;onClose:()=>void;entityType:EntityType;entityId:string;title:string;documentType:'mortgage'|'insurance'
}){
  const qc=useQueryClient();
  const inputRef=useRef<HTMLInputElement|null>(null);
  const [selected,setSelected]=useState<string|null>(null);
  const docs=useQuery({
    queryKey:['entity-documents',entityType,entityId],
    queryFn:()=>apiGet<Doc[]>('/api/v1/documents?entity_type='+encodeURIComponent(entityType)+'&entity_id='+encodeURIComponent(entityId)),
    enabled:open&&!!entityId,
  });
  useEffect(()=>{
    if(open&&!selected&&docs.data?.[0])setSelected(docs.data[0].id);
    if(!open)setSelected(null);
  },[open,docs.data,selected]);
  const analysis=useQuery({
    queryKey:['entity-document-analysis',selected],
    queryFn:()=>apiGet<AnalysisResponse>('/api/v1/documents/'+selected+'/analysis'),
    enabled:open&&!!selected,
    refetchInterval:query=>{
      const data=query.state.data as AnalysisResponse|undefined;
      if(data?.status==='ready')return false;
      if(data&&(!data.ai.available||!data.ai.configured_model))return false;
      return 3000;
    },
  });
  const invalidate=()=>{
    qc.invalidateQueries({queryKey:['entity-documents',entityType,entityId]});
    qc.invalidateQueries({queryKey:['documents']});
    qc.invalidateQueries({queryKey:['document-insights']});
    qc.invalidateQueries({queryKey:['wealth-home']});
    qc.invalidateQueries({queryKey:['insurance-verdict']});
  };
  const upload=useMutation({
    mutationFn:(files:File[])=>{
      const form=new FormData();
      files.forEach(file=>form.append('files',file));
      form.append('document_type',documentType);
      form.append('entity_type',entityType);
      form.append('entity_id',entityId);
      return apiUpload<UploadResponse>('/api/v1/documents/upload',form);
    },
    onSuccess:data=>{if(data.documents[0])setSelected(data.documents[0].id);invalidate()},
  });
  const analyzeAll=useMutation({
    mutationFn:()=>apiMutate('/api/v1/evidence-groups/'+entityType+'/'+entityId+'/analyze','POST'),
    onSuccess:()=>{invalidate();if(selected)qc.invalidateQueries({queryKey:['entity-document-analysis',selected]})},
  });
  if(!open)return null;
  const selectedDoc=docs.data?.find(x=>x.id===selected);
  const ai=analysis.data?.analysis;
  return <div className="fixed inset-0 z-50 overflow-y-auto bg-black/45 p-4 md:p-8" role="dialog" aria-modal="true" aria-label={title}>
    <div className="mx-auto max-w-6xl">
      <Card>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div><div className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">Documentación</div><h2 className="mt-1 text-xl font-bold">{title}</h2><p className="mt-1 text-sm text-[var(--muted)]">Añade, consulta y analiza únicamente los documentos asociados a este producto.</p></div>
          <button className="fin-button secondary py-2 text-xs" type="button" onClick={onClose}>Cerrar</button>
        </div>
        <input ref={inputRef} className="hidden" type="file" multiple accept=".pdf,image/*,.heic,.docx,.xlsx,.xlsm,.csv,.txt,.json" onChange={e=>{if(e.target.files?.length)upload.mutate(Array.from(e.target.files));e.currentTarget.value=''}}/>
        <div className="mt-4 flex flex-wrap gap-2">
          <button className="fin-button" type="button" onClick={()=>inputRef.current?.click()} disabled={upload.isPending}>{upload.isPending?'Añadiendo…':'Añadir documentos'}</button>
          <button className="fin-button secondary" type="button" onClick={()=>analyzeAll.mutate()} disabled={analyzeAll.isPending||!docs.data?.length}>{analyzeAll.isPending?'Analizando…':'Actualizar resúmenes con IA local'}</button>
        </div>
        {(upload.error||analyzeAll.error)&&<div className="mt-3"><ErrorState error={(upload.error||analyzeAll.error)!}/></div>}
        <div className="mt-5 grid gap-4 lg:grid-cols-[320px_1fr]">
          <div className="space-y-2">
            {docs.isLoading?<Loading/>:docs.error?<ErrorState error={docs.error}/>:docs.data?.length?docs.data.map(doc=><button key={doc.id} type="button" onClick={()=>setSelected(doc.id)} className={'w-full rounded-xl p-3 text-left '+(selected===doc.id?'bg-[var(--brand-soft)]':'bg-[var(--surface-2)]')}>
              <div className="font-medium">{doc.file_name}</div>
              <div className="mt-1 text-xs text-[var(--muted)]">{doc.page_count} pág. · {doc.ai_analysis==='ready'?'resumen IA disponible':'sin resumen IA'}{doc.review.pending?' · '+doc.review.pending+' dato(s) por revisar':''}</div>
            </button>):<EmptyState>No hay documentos asociados.</EmptyState>}
          </div>
          <div>
            {!selectedDoc?<EmptyState>Selecciona un documento para consultarlo.</EmptyState>:<>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div><h3 className="font-semibold">{selectedDoc.file_name}</h3><div className="mt-1 text-xs text-[var(--muted)]">{selectedDoc.document_type} · {selectedDoc.page_count} pág.</div></div>
                <a className="fin-button secondary py-1.5 text-xs" target="_blank" rel="noreferrer" href={'/api/v1/documents/'+selectedDoc.id+'/file'}>Visualizar documento</a>
              </div>
              <div className="mt-4">
                {analysis.isLoading?<Loading/>:analysis.error?<ErrorState error={analysis.error}/>:analysis.data?.status!=='ready'||!ai?<div className="rounded-xl bg-[var(--surface-2)] p-4 text-sm">Todavía no hay un resumen de IA local para este documento. Usa “Actualizar resúmenes con IA local”.</div>:<>
                  <div className="rounded-xl bg-[var(--brand-soft)] p-4"><div className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">Resumen</div><p className="mt-2 text-sm">{ai.summary}</p></div>
                  <div className="mt-3 grid gap-3 md:grid-cols-2">
                    <InsightList title="Qué cubre / ventajas" items={ai.advantages} documentId={selectedDoc.id}/>
                    <InsightList title="Penalizaciones" items={ai.penalties} documentId={selectedDoc.id}/>
                    <InsightList title="Riesgos y límites" items={[...ai.risks,...ai.exclusions_or_limits]} documentId={selectedDoc.id}/>
                    <InsightList title="Obligaciones y puntos a revisar" items={[...ai.obligations,...ai.negotiation_points,...ai.comparison_requirements]} documentId={selectedDoc.id}/>
                  </div>
                </>}
              </div>
            </>}
          </div>
        </div>
      </Card>
    </div>
  </div>;
}
