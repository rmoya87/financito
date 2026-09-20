'use client';

import {FormEvent,useEffect,useRef,useState} from 'react';
import {useMutation,useQuery,useQueryClient} from '@tanstack/react-query';
import {apiGet,apiMutate,apiUpload} from '@/lib/api';
import {PageHeader} from '@/components/page-header';
import {Card} from '@/components/ui/card';
import {EmptyState,ErrorState,Loading} from '@/components/ui/states';

type ReviewSummary={total:number;pending:number;confirmed:number;ambiguous:number;reviewed:number};
type Doc={id:string;file_name:string;document_type:string;status:string;page_count:number;review:ReviewSummary;ai_analysis:'ready'|'not_analyzed'};
type InsightItem={title:string;detail:string;pages:number[];impact?:string};
type AIAnalysis={id?:string;status?:string;confidence:string;summary:string;advantages:InsightItem[];penalties:InsightItem[];obligations:InsightItem[];risks:InsightItem[];exclusions_or_limits:InsightItem[];linked_products:InsightItem[];optimization_opportunities:InsightItem[];cross_area_impacts:InsightItem[];missing_information:InsightItem[];model_role:string};
type AnalysisResponse={document_id:string;status:'ready'|'not_analyzed';analysis:AIAnalysis|null;ai:{available:boolean;configured_model:string|null;chat_ready?:boolean}};
type UploadResponse={documents:{id:string;file_name:string;document_type:string;facts_created:number;chunks_created:number}[];ai_analysis_scheduled:boolean};
type Fact={id:string;fact_type:string;key:string;value:{value:string;unit?:string};confidence:string;status:string;source_page:number|null;source_section:string|null;user_verified:boolean};

const MATERIAL_FACT_TYPES=new Set(['contract_term','mortgage_term','linked_product']);

export default function DocumentsPage(){
  const qc=useQueryClient();
  const [path,setPath]=useState('');
  const [selected,setSelected]=useState<string|null>(null);
  const [dragging,setDragging]=useState(false);
  const fileInput=useRef<HTMLInputElement|null>(null);

  useEffect(()=>{
    const documentId=new URLSearchParams(window.location.search).get('document');
    if(documentId)setSelected(documentId);
  },[]);

  const docs=useQuery({queryKey:['documents'],queryFn:()=>apiGet<Doc[]>('/api/v1/documents')});
  const facts=useQuery({
    queryKey:['facts',selected],
    queryFn:()=>apiGet<Fact[]>('/api/v1/documents/'+selected+'/facts'),
    enabled:!!selected,
  });
  const analysis=useQuery({
    queryKey:['document-analysis',selected],
    queryFn:()=>apiGet<AnalysisResponse>('/api/v1/documents/'+selected+'/analysis'),
    enabled:!!selected,
    refetchInterval:(query)=>{
      const data=query.state.data as AnalysisResponse|undefined;
      if(data?.status==='ready')return false;
      if(data&&(!data.ai.available||!data.ai.configured_model))return false;
      return 3500;
    },
  });

  const invalidateEvidence=()=>{
    qc.invalidateQueries({queryKey:['documents']});
    qc.invalidateQueries({queryKey:['facts',selected]});
    qc.invalidateQueries({queryKey:['actions']});
    qc.invalidateQueries({queryKey:['dashboard']});
    qc.invalidateQueries({queryKey:['contracts']});
    qc.invalidateQueries({queryKey:['insurance']});
    qc.invalidateQueries({queryKey:['document-insights']});
    qc.invalidateQueries({queryKey:['document-analysis',selected]});
  };

  const upload=useMutation({
    mutationFn:(files:File[])=>{
      const form=new FormData();
      files.forEach(file=>form.append('files',file));
      form.append('document_type','unknown');
      return apiUpload<UploadResponse>('/api/v1/documents/upload',form);
    },
    onSuccess:(data)=>{
      const first=data.documents[0]?.id;
      if(first)setSelected(first);
      invalidateEvidence();
    },
  });
  const analyze=useMutation({
    mutationFn:(id:string)=>apiMutate('/api/v1/documents/'+id+'/analyze','POST'),
    onSuccess:()=>{
      qc.invalidateQueries({queryKey:['document-analysis',selected]});
      qc.invalidateQueries({queryKey:['document-insights']});
      qc.invalidateQueries({queryKey:['actions']});
    },
  });
  const index=useMutation({
    mutationFn:()=>apiMutate('/api/v1/documents/index','POST',{path,document_type:'unknown'}),
    onSuccess:()=>{setPath('');invalidateEvidence()},
  });
  const reprocess=useMutation({
    mutationFn:(id:string)=>apiMutate('/api/v1/documents/'+id+'/reprocess','POST'),
    onSuccess:invalidateEvidence,
  });
  const update=useMutation({
    mutationFn:({id,status}:{id:string;status:string})=>apiMutate('/api/v1/facts/'+id,'PATCH',{status,user_verified:true}),
    onSuccess:invalidateEvidence,
  });

  function submit(e:FormEvent){
    e.preventDefault();
    index.mutate();
  }

  function addFiles(list:FileList|File[]){
    const files=Array.from(list).slice(0,20);
    if(files.length)upload.mutate(files);
  }

  function InsightGroup({title,items}:{title:string;items:InsightItem[]}){
    if(!items?.length)return null;
    return <div>
      <h3 className="text-sm font-semibold">{title}</h3>
      <div className="mt-2 space-y-2">{items.map((item,i)=><div key={title+i} className="rounded-xl bg-[var(--surface-2)] p-3 text-sm">
        <div className="font-medium">{item.title||item.detail}</div>
        {item.title&&item.detail&&<div className="mt-1 text-xs text-[var(--muted)]">{item.detail}</div>}
        {item.impact&&<div className="mt-1 text-xs">{item.impact}</div>}
        {!!item.pages?.length&&selected&&<div className="mt-1 text-[11px] text-[var(--muted)]">Evidencia: {item.pages.map(p=>'pág. '+p).join(', ')}</div>}
      </div>)}</div>
    </div>;
  }

  const selectedDoc=docs.data?.find(d=>d.id===selected);
  const visibleFacts=facts.data?.filter(f=>f.fact_type!=='ai_insight')||[];
  const materialFacts=visibleFacts.filter(f=>MATERIAL_FACT_TYPES.has(f.fact_type));
  const pending=materialFacts.filter(f=>!f.user_verified&&f.status==='inferred').length;
  const confirmed=materialFacts.filter(f=>f.user_verified&&f.status==='confirmed').length;
  const ambiguous=materialFacts.filter(f=>f.status==='ambiguous'||f.status==='conflicting').length;

  return <>
    <PageHeader
      title="Documentos y evidencia"
      description="El Vault se vigila automáticamente. Los documentos se indexan para búsqueda e IA local; los datos materiales solo pasan a contratos, seguros y cálculos cuando los confirmas."
    />

    <Card>
      <div
        className={'rounded-2xl border-2 border-dashed p-6 text-center transition '+(dragging?'border-[var(--brand)] bg-[var(--brand-soft)]':'border-[var(--border)] bg-[var(--surface-2)]')}
        onDragEnter={e=>{e.preventDefault();setDragging(true)}}
        onDragOver={e=>{e.preventDefault();setDragging(true)}}
        onDragLeave={e=>{e.preventDefault();setDragging(false)}}
        onDrop={e=>{e.preventDefault();setDragging(false);addFiles(e.dataTransfer.files)}}
      >
        <input
          ref={fileInput}
          className="sr-only"
          type="file"
          multiple
          accept=".pdf,.png,.jpg,.jpeg,.heic,.tiff,.bmp,.docx,.xlsx,.xlsm,.csv,.txt,.json"
          onChange={e=>{if(e.target.files)addFiles(e.target.files);e.currentTarget.value=''}}
        />
        <div className="font-semibold">Añade documentos desde tu Mac</div>
        <p className="mx-auto mt-1 max-w-2xl text-sm text-[var(--muted)]">Arrastra aquí hipotecas, pólizas, extractos, contratos o facturas. Financito los guarda en su Vault privado, extrae los datos y, si Ollama está disponible, genera un análisis local.</p>
        <button className="fin-button mt-4" type="button" onClick={()=>fileInput.current?.click()} disabled={upload.isPending}>
          {upload.isPending?'Subiendo y procesando…':'Seleccionar documentos'}
        </button>
        <div className="mt-2 text-xs text-[var(--muted)]">PDF, imágenes/HEIC, DOCX, XLSX, CSV, TXT y JSON · máximo 50 MB por archivo · hasta 20 archivos por lote.</div>
      </div>
      {upload.error&&<div className="mt-3"><ErrorState error={upload.error}/></div>}
      {upload.data&&<div className="mt-3 text-sm text-[var(--muted)]">{upload.data.documents.length} documento(s) añadido(s). El análisis de IA local se ejecuta automáticamente en segundo plano.</div>}
      <details className="mt-4">
        <summary className="cursor-pointer text-sm font-medium">Importar manualmente una ruta ya existente en el Vault</summary>
        <form onSubmit={submit} className="mt-3 grid gap-3 md:grid-cols-[1fr_auto]">
        <input
          className="fin-input"
          aria-label="Ruta del documento"
          value={path}
          onChange={e=>setPath(e.target.value)}
          placeholder="Ruta dentro del Financial Knowledge Vault"
          required
        />
        <button className="fin-button" disabled={index.isPending}>
          {index.isPending?'Indexando…':'Indexar archivo'}
        </button>
      </form>
      <div className="mt-2 text-xs text-[var(--muted)]">
        Admite PDF, imágenes/HEIC, DOCX, XLSX, CSV, TXT y JSON. Máximo 50 MB y 500 páginas por PDF.
      </div>
      {index.error&&<div className="mt-3"><ErrorState error={index.error}/></div>}
      </details>
    </Card>

    <div className="mt-4 grid gap-4 xl:grid-cols-2">
      <Card>
        <h2 className="font-bold">Biblioteca</h2>
        <p className="mt-1 text-sm text-[var(--muted)]">
          Los documentos aparecen aquí al copiarlos al Vault; no necesitas indexarlos manualmente.
        </p>
        <div className="mt-4 space-y-2">
          {docs.isLoading?<Loading/>:docs.error?<ErrorState error={docs.error}/>:docs.data?.length?
            docs.data.map(d=><button
              key={d.id}
              onClick={()=>setSelected(d.id)}
              className={'w-full rounded-xl p-3 text-left '+(selected===d.id?'bg-[var(--brand-soft)]':'bg-[var(--surface-2)]')}
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="font-medium">{d.file_name}</div>
                  <div className="text-xs text-[var(--muted)]">{d.document_type} · {d.page_count} pág. · {d.status}</div>
                </div>
                {d.review.pending>0?
                  <span className="rounded-full bg-[var(--brand-soft)] px-2 py-1 text-[10px] font-bold text-[var(--brand)]">{d.review.pending} por revisar</span>:
                  d.review.total>0?<span className="text-xs text-[var(--muted)]">Revisado</span>:null}
              </div>
            </button>):
            <EmptyState>No hay documentos indexados.</EmptyState>}
        </div>
        {selected&&<button
          className="fin-button secondary mt-3"
          onClick={()=>reprocess.mutate(selected)}
          disabled={reprocess.isPending}
        >
          {reprocess.isPending?'Reprocesando…':'Reprocesar clasificación, hechos e índice'}
        </button>}
      </Card>

      <Card>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="font-bold">Evidencia extraída</h2>
            {selectedDoc&&<div className="mt-1 text-sm text-[var(--muted)]">{selectedDoc.file_name}</div>}
          </div>
          {selected&&<a
            className="fin-button secondary py-2 text-xs"
            href={'/api/v1/documents/'+selected+'/file'}
            target="_blank"
            rel="noreferrer"
          >Abrir original</a>}
        </div>

        {selected&&materialFacts.length>0&&<div className="mt-4 rounded-xl bg-[var(--surface-2)] p-3 text-sm">
          <strong>{pending>0?pending+' dato(s) por revisar':'Revisión completada'}</strong>
          <div className="mt-1 text-xs text-[var(--muted)]">
            {confirmed} confirmados · {ambiguous} dudosos. Los confirmados se sincronizan automáticamente con las áreas de Financito que pueden utilizarlos.
          </div>
        </div>}

        {selected&&<div className="mt-4 rounded-xl border border-[var(--border)] p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div><h3 className="font-semibold">Análisis con IA local</h3><p className="mt-1 text-xs text-[var(--muted)]">Interpretación explicativa. Los importes y cláusulas materiales siguen necesitando evidencia confirmada para entrar en cálculos.</p></div>
            <button className="fin-button secondary py-1.5 text-xs" onClick={()=>analyze.mutate(selected)} disabled={analyze.isPending||analysis.isLoading}>
              {analyze.isPending?'Analizando…':analysis.data?.status==='ready'?'Volver a analizar':'Analizar ahora'}
            </button>
          </div>
          {analysis.isLoading?<div className="mt-3"><Loading/></div>:analysis.error?<div className="mt-3"><ErrorState error={analysis.error}/></div>:analysis.data?.status==='ready'&&analysis.data.analysis?<div className="mt-4 space-y-4">
            <div className="rounded-xl bg-[var(--brand-soft)] p-3 text-sm"><strong>Conclusión del documento</strong><div className="mt-1">{analysis.data.analysis.summary}</div><div className="mt-2 text-[11px] text-[var(--muted)]">Confianza interpretativa {Math.round(Number(analysis.data.analysis.confidence)*100)}% · {analysis.data.analysis.model_role}</div></div>
            <div className="grid gap-4 md:grid-cols-2">
              <InsightGroup title="Ventajas y coberturas útiles" items={analysis.data.analysis.advantages}/>
              <InsightGroup title="Penalizaciones y costes de salida" items={analysis.data.analysis.penalties}/>
              <InsightGroup title="Obligaciones" items={analysis.data.analysis.obligations}/>
              <InsightGroup title="Riesgos" items={analysis.data.analysis.risks}/>
              <InsightGroup title="Exclusiones o límites" items={analysis.data.analysis.exclusions_or_limits}/>
              <InsightGroup title="Productos vinculados" items={analysis.data.analysis.linked_products}/>
              <InsightGroup title="Oportunidades de optimización" items={analysis.data.analysis.optimization_opportunities}/>
              <InsightGroup title="Impactos en otras áreas" items={analysis.data.analysis.cross_area_impacts}/>
              <InsightGroup title="Información que falta" items={analysis.data.analysis.missing_information}/>
            </div>
          </div>:<div className="mt-3 text-sm text-[var(--muted)]">{analysis.data?.ai.available&&analysis.data.ai.configured_model?'El documento está indexado y el análisis automático todavía no ha terminado.':'El documento está indexado. Configura y arranca la IA local para obtener el análisis interpretativo.'}</div>}
        </div>}

        <div className="mt-4 space-y-3">
          {!selected?<EmptyState>Selecciona un documento.</EmptyState>:
          facts.isLoading?<Loading/>:
          facts.error?<ErrorState error={facts.error}/>:
          visibleFacts.length?visibleFacts.map(f=>{
            const material=MATERIAL_FACT_TYPES.has(f.fact_type);
            return <div key={f.id} className="rounded-xl border border-[var(--border)] p-4">
              <div className="flex justify-between gap-3">
                <div>
                  <div className="font-medium">{f.key}</div>
                  <div className="text-sm text-[var(--muted)]">
                    {f.value.value} {f.value.unit||''} · confianza {Math.round(Number(f.confidence)*100)}%
                  </div>
                  {f.source_section&&<div className="mt-1 text-xs text-[var(--muted)]">{f.source_section}</div>}
                  {f.source_page&&selected&&<a
                    className="mt-1 inline-block text-xs underline"
                    href={'/api/v1/documents/'+selected+'/file#page='+f.source_page}
                    target="_blank"
                    rel="noreferrer"
                  >Abrir evidencia · pág. {f.source_page}</a>}
                </div>
                <span className="text-xs">{f.status}</span>
              </div>

              {material&&!f.user_verified&&f.status==='inferred'&&<div className="mt-3 flex flex-wrap gap-2">
                <button
                  className="fin-button py-1.5 text-xs"
                  onClick={()=>update.mutate({id:f.id,status:'confirmed'})}
                  disabled={update.isPending}
                >Confirmar</button>
                <button
                  className="fin-button secondary py-1.5 text-xs"
                  onClick={()=>update.mutate({id:f.id,status:'ambiguous'})}
                  disabled={update.isPending}
                >Marcar dudoso</button>
              </div>}

              {material&&f.user_verified&&<div className="mt-3 text-xs font-medium text-[var(--muted)]">
                {f.status==='confirmed'?'Confirmado por ti':'Revisado por ti'}
              </div>}
            </div>;
          }):<EmptyState>No se extrajeron hechos estructurados de este documento.</EmptyState>}
        </div>
      </Card>
    </div>
  </>;
}
