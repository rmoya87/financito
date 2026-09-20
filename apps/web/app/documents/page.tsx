'use client';

import {FormEvent,useEffect,useRef,useState} from 'react';
import {useMutation,useQuery,useQueryClient} from '@tanstack/react-query';
import {apiGet,apiMutate,apiUpload} from '@/lib/api';
import {PageHeader} from '@/components/page-header';
import {Card} from '@/components/ui/card';
import {EmptyState,ErrorState,Loading} from '@/components/ui/states';

type ReviewSummary={total:number;pending:number;confirmed:number;ambiguous:number;reviewed:number};
type EvidenceLink={entity_type:'insurance_policy'|'contract'|'mortgage'|string;entity_id:string;confidence:string;source_type:string};
type Doc={id:string;file_name:string;document_type:string;status:string;page_count:number;review:ReviewSummary;ai_analysis:'ready'|'not_analyzed';mortgage_id:string|null;evidence_links:EvidenceLink[]};
type InsightItem={title:string;detail:string;pages:number[];impact?:string};
type AIAnalysis={id?:string;status?:string;confidence:string;summary:string;advantages:InsightItem[];penalties:InsightItem[];obligations:InsightItem[];risks:InsightItem[];exclusions_or_limits:InsightItem[];linked_products:InsightItem[];optimization_opportunities:InsightItem[];negotiation_points:InsightItem[];comparison_requirements:InsightItem[];cross_area_impacts:InsightItem[];missing_information:InsightItem[];model_role:string};
type AnalysisResponse={document_id:string;status:'ready'|'not_analyzed';analysis:AIAnalysis|null;ai:{available:boolean;configured_model:string|null;chat_ready?:boolean}};
type UploadResponse={documents:{id:string;file_name:string;document_type:string;facts_created:number;chunks_created:number}[];ai_analysis_scheduled:boolean};
type Fact={id:string;fact_type:string;key:string;value:{value:string;unit?:string;coverage_type?:string;limit_amount?:string|null;deductible?:string|null;conditions?:string;exclusions?:string;source?:string};confidence:string;status:string;source_page:number|null;source_section:string|null;user_verified:boolean};
type EvidenceGroup={entity_type:'insurance_policy'|'contract'|'mortgage';entity_id:string;kind:string;label:string;provider:string;document_count:number;documents:{id:string;file_name:string}[]};
type ActionItem={id:string;title:string;action_type:string;status:string;notes:string|null;related_entity_type:string|null;related_entity_id:string|null};
type BulkConfirmResult={documents:number;confirmed:number;conflicts:number};

const MATERIAL_FACT_TYPES=new Set(['contract_term','mortgage_term','linked_product','coverage_fact','investment_term']);

export default function DocumentsPage(){
  const qc=useQueryClient();
  const [path,setPath]=useState('');
  const [selected,setSelected]=useState<string|null>(null);
  const [actionId,setActionId]=useState<string|null>(null);
  const [dragging,setDragging]=useState(false);
  const [manualFact,setManualFact]=useState({fact_type:'contract_term',key:'',value:'',unit:'',coverage_type:'',limit_amount:'',deductible:'',conditions:'',exclusions:'',source_page:''});
  const fileInput=useRef<HTMLInputElement|null>(null);

  useEffect(()=>{
    const params=new URLSearchParams(window.location.search);
    const documentId=params.get('document');
    if(documentId)setSelected(documentId);
    setActionId(params.get('action'));
  },[]);

  const docs=useQuery({queryKey:['documents'],queryFn:()=>apiGet<Doc[]>('/api/v1/documents')});
  const groups=useQuery({queryKey:['evidence-groups'],queryFn:()=>apiGet<EvidenceGroup[]>('/api/v1/evidence-groups')});
  const actions=useQuery({queryKey:['actions'],queryFn:()=>apiGet<ActionItem[]>('/api/v1/actions'),enabled:!!actionId});
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
    qc.invalidateQueries({queryKey:['evidence-groups']});
    qc.invalidateQueries({queryKey:['facts',selected]});
    qc.invalidateQueries({queryKey:['actions']});
    qc.invalidateQueries({queryKey:['dashboard']});
    qc.invalidateQueries({queryKey:['contracts']});
    qc.invalidateQueries({queryKey:['insurance']});
    qc.invalidateQueries({queryKey:['coverage']});
    qc.invalidateQueries({queryKey:['coverage-gaps']});
    qc.invalidateQueries({queryKey:['coverage-overlaps']});
    qc.invalidateQueries({queryKey:['mortgages']});
    qc.invalidateQueries({queryKey:['switching-readiness']});
    qc.invalidateQueries({queryKey:['decision-lab-context']});
    qc.invalidateQueries({queryKey:['wealth']});
    qc.invalidateQueries({queryKey:['portfolios']});
    qc.invalidateQueries({queryKey:['tracked-assets']});
    qc.invalidateQueries({queryKey:['tax-profile']});
    qc.invalidateQueries({queryKey:['decisions']});
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
  const analyzeAll=useMutation({
    mutationFn:()=>apiMutate<{scheduled:number}>('/api/v1/documents/analyze-all','POST'),
    onSuccess:()=>{
      qc.invalidateQueries({queryKey:['documents']});
      qc.invalidateQueries({queryKey:['document-analysis',selected]});
      qc.invalidateQueries({queryKey:['document-insights']});
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
  const linkEntity=useMutation({
    mutationFn:({documentId,entityType,entityId}:{documentId:string;entityType:'insurance_policy'|'contract'|'mortgage';entityId:string|null})=>
      apiMutate('/api/v1/documents/'+documentId+'/entity-link','PUT',{entity_type:entityType,entity_id:entityId}),
    onSuccess:invalidateEvidence,
  });
  const createGroup=useMutation({
    mutationFn:(documentId:string)=>apiMutate<{entity_type:'contract';entity_id:string}>('/api/v1/documents/'+documentId+'/evidence-group','POST'),
    onSuccess:invalidateEvidence,
  });
  const confirmCoherent=useMutation({
    mutationFn:({documentId,group}:{documentId:string;group:EvidenceGroup|null})=>
      group
        ?apiMutate<BulkConfirmResult>('/api/v1/evidence-groups/'+group.entity_type+'/'+group.entity_id+'/confirm-coherent','POST')
        :apiMutate<BulkConfirmResult>('/api/v1/documents/'+documentId+'/confirm-coherent','POST'),
    onSuccess:invalidateEvidence,
  });
  const closeAction=useMutation({
    mutationFn:({id,status}:{id:string;status:'done'|'dismissed'})=>apiMutate('/api/v1/actions/'+id,'PATCH',{status}),
    onSuccess:()=>{qc.invalidateQueries({queryKey:['actions']});qc.invalidateQueries({queryKey:['dashboard']})},
  });
  const addManualFact=useMutation({
    mutationFn:()=>{
      if(!selected)throw new Error('Selecciona un documento');
      return apiMutate('/api/v1/documents/'+selected+'/facts','POST',{
        fact_type:manualFact.fact_type,
        key:manualFact.key.trim(),
        value:manualFact.value.trim(),
        unit:manualFact.unit.trim()||null,
        coverage_type:manualFact.coverage_type.trim()||null,
        limit_amount:manualFact.limit_amount.trim()||null,
        deductible:manualFact.deductible.trim()||null,
        conditions:manualFact.conditions.trim()||null,
        exclusions:manualFact.exclusions.trim()||null,
        source_page:manualFact.source_page?Number(manualFact.source_page):null,
      });
    },
    onSuccess:()=>{
      setManualFact({...manualFact,key:'',value:'',unit:'',coverage_type:'',limit_amount:'',deductible:'',conditions:'',exclusions:'',source_page:''});
      invalidateEvidence();
    },
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
  const currentAction=actions.data?.find(a=>a.id===actionId);
  const currentLink=selectedDoc?.evidence_links?.find(link=>
    selectedDoc.document_type==='insurance'?link.entity_type==='insurance_policy':
    selectedDoc.document_type==='mortgage'?link.entity_type==='mortgage':
    link.entity_type==='contract'
  )||selectedDoc?.evidence_links?.find(link=>['insurance_policy','mortgage','contract'].includes(link.entity_type));
  const currentGroup=groups.data?.find(g=>g.entity_type===currentLink?.entity_type&&g.entity_id===currentLink?.entity_id)||null;
  const compatibleGroups=(groups.data||[]).filter(g=>
    selectedDoc?.document_type==='insurance'?(g.entity_type==='insurance_policy'||g.kind==='insurance_pending'):
    selectedDoc?.document_type==='mortgage'?g.entity_type==='mortgage':
    ['contract','loan','energy','telecom'].includes(selectedDoc?.document_type||'')?g.entity_type==='contract':
    true
  );
  const visibleFacts=facts.data?.filter(f=>f.fact_type!=='ai_insight')||[];
  const materialFacts=visibleFacts.filter(f=>MATERIAL_FACT_TYPES.has(f.fact_type));
  const pending=materialFacts.filter(f=>!f.user_verified&&['inferred','ambiguous','conflicting'].includes(f.status)).length;
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
          aria-label="Seleccionar documentos financieros"
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
      <details className="mt-4" open>
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
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div><h2 className="font-bold">Biblioteca</h2><p className="mt-1 text-sm text-[var(--muted)]">Los documentos aparecen aquí al copiarlos al Vault; no necesitas indexarlos manualmente.</p></div>
          <button className="fin-button secondary py-1.5 text-xs" onClick={()=>analyzeAll.mutate()} disabled={analyzeAll.isPending||!docs.data?.length}>{analyzeAll.isPending?'Programando…':'Analizar todos con IA'}</button>
        </div>
        {analyzeAll.data&&<div className="mt-2 text-xs text-[var(--muted)]">{analyzeAll.data.scheduled} documento(s) programados para análisis local.</div>}
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

        {currentAction&&currentAction.status!=='done'&&currentAction.status!=='dismissed'&&<div className="mt-4 rounded-xl border border-[var(--brand)] bg-[var(--brand-soft)] p-4 text-sm">
          <div className="font-semibold">Esto es lo que te pidió “Para ti”</div>
          <div className="mt-1">{currentAction.title}</div>
          {currentAction.action_type==='review_document_ai_insights'?<>
            <p className="mt-2 text-xs text-[var(--muted)]">Lee la conclusión del análisis local de este documento. No cambia ningún dato financiero por sí sola. Si ya la has comprobado y no requiere otra acción, márcala como revisada.</p>
            <div className="mt-3 flex flex-wrap gap-2">
              <button className="fin-button py-1.5 text-xs" onClick={()=>closeAction.mutate({id:currentAction.id,status:'done'})} disabled={closeAction.isPending}>Marcar como revisada</button>
              <button className="fin-button secondary py-1.5 text-xs" onClick={()=>closeAction.mutate({id:currentAction.id,status:'dismissed'})} disabled={closeAction.isPending}>Ocultar este aviso</button>
            </div>
          </>:<p className="mt-2 text-xs text-[var(--muted)]">Revisa los datos estructurados. Puedes validarlos en bloque: Financito confirmará solo los coherentes y dejará como conflicto cualquier dato incompatible.</p>}
          {closeAction.error&&<div className="mt-3"><ErrorState error={closeAction.error}/></div>}
        </div>}

        {selected&&materialFacts.length>0&&<div className="mt-4 rounded-xl bg-[var(--surface-2)] p-3 text-sm">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <strong>{pending>0?pending+' dato(s) por revisar':'Revisión completada'}</strong>
              <div className="mt-1 text-xs text-[var(--muted)]">{confirmed} confirmados · {ambiguous} dudosos. Los confirmados se sincronizan automáticamente con las áreas de Financito que pueden utilizarlos.</div>
            </div>
            {pending>0&&selected&&<button className="fin-button py-1.5 text-xs" onClick={()=>confirmCoherent.mutate({documentId:selected,group:currentGroup})} disabled={confirmCoherent.isPending}>
              {confirmCoherent.isPending?'Validando…':currentGroup&&currentGroup.document_count>1?'Validar los '+currentGroup.document_count+' documentos juntos':'Validar datos coherentes'}
            </button>}
          </div>
          {confirmCoherent.data&&<div className="mt-2 text-xs font-medium">{confirmCoherent.data.confirmed} dato(s) confirmados · {confirmCoherent.data.conflicts} conflicto(s) separados para revisión.</div>}
          {confirmCoherent.error&&<div className="mt-3"><ErrorState error={confirmCoherent.error}/></div>}
        </div>}

        {selectedDoc&&<div className="mt-4 rounded-xl border border-[var(--border)] p-4">
          <h3 className="font-semibold">¿A qué producto pertenece este documento?</h3>
          <p className="mt-1 text-xs text-[var(--muted)]">Vincula todos los PDFs, anexos, recibos y condiciones del mismo seguro, hipoteca o servicio a una única ficha. Financito combinará su evidencia y la tratará como un solo producto.</p>
          <select className="fin-input mt-3" aria-label="Producto financiero asociado al documento"
            value={currentGroup?currentGroup.entity_type+':'+currentGroup.entity_id:''}
            onChange={e=>{
              const raw=e.target.value;
              const defaultType:'insurance_policy'|'contract'|'mortgage'=selectedDoc.document_type==='insurance'?'insurance_policy':selectedDoc.document_type==='mortgage'?'mortgage':'contract';
              const unlinkType=(currentGroup?.entity_type||defaultType) as 'insurance_policy'|'contract'|'mortgage';
              if(!raw){linkEntity.mutate({documentId:selectedDoc.id,entityType:unlinkType,entityId:null});return}
              const [entityType,entityId]=raw.split(':');
              linkEntity.mutate({documentId:selectedDoc.id,entityType:entityType as 'insurance_policy'|'contract'|'mortgage',entityId});
            }} disabled={linkEntity.isPending}>
            <option value="">Sin vincular a una ficha existente</option>
            {compatibleGroups.map(g=><option key={g.entity_type+g.entity_id} value={g.entity_type+':'+g.entity_id}>{g.label} · {g.document_count} documento(s)</option>)}
          </select>
          {currentGroup&&<div className="mt-3 rounded-xl bg-[var(--surface-2)] p-3 text-xs">
            <strong>{currentGroup.label}</strong>
            <div className="mt-1 text-[var(--muted)]">{currentGroup.document_count} documento(s) forman esta única ficha.</div>
            {currentGroup.documents.length>1&&<div className="mt-2">{currentGroup.documents.map(d=><div key={d.id}>• {d.file_name}</div>)}</div>}
          </div>}
          {!currentGroup&&selectedDoc.document_type==='insurance'&&<div className="mt-2 text-xs text-[var(--muted)]">Si la póliza contiene un número identificador claro, Financito crea una agrupación provisional y reúne automáticamente los siguientes documentos que compartan ese número, aunque todavía falte confirmar la prima.</div>}
          {!currentGroup&&['insurance','contract','loan','energy','telecom'].includes(selectedDoc.document_type)&&<button className="fin-button secondary mt-3 py-1.5 text-xs" onClick={()=>createGroup.mutate(selectedDoc.id)} disabled={createGroup.isPending}>
            {createGroup.isPending?'Creando ficha…':'Crear una ficha para este producto'}
          </button>}
          {createGroup.error&&<div className="mt-3"><ErrorState error={createGroup.error}/></div>}
          {linkEntity.error&&<div className="mt-3"><ErrorState error={linkEntity.error}/></div>}
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
              <InsightGroup title="Puntos para negociar" items={analysis.data.analysis.negotiation_points}/>
              <InsightGroup title="Qué exigir para comparar ofertas" items={analysis.data.analysis.comparison_requirements}/>
              <InsightGroup title="Impactos en otras áreas" items={analysis.data.analysis.cross_area_impacts}/>
              <InsightGroup title="Información que falta" items={analysis.data.analysis.missing_information}/>
            </div>
          </div>:<div className="mt-3 text-sm text-[var(--muted)]">{analysis.data?.ai.available&&analysis.data.ai.configured_model?'El documento está indexado y el análisis automático todavía no ha terminado.':'El documento está indexado. Configura y arranca la IA local para obtener el análisis interpretativo.'}</div>}
        </div>}

        {selected&&<div className="mt-4 rounded-xl border border-[var(--border)] p-4">
          <h3 className="font-semibold">Completar un dato que no se haya reconocido</h3>
          <p className="mt-1 text-xs text-[var(--muted)]">El dato se guarda como evidencia confirmada dentro de este mismo documento. No crea una segunda fuente paralela: contratos, hipoteca, seguros, inversiones, decisiones y simulaciones reutilizan esta evidencia cuando corresponda.</p>
          <form className="mt-3 grid gap-2 md:grid-cols-2" onSubmit={e=>{e.preventDefault();addManualFact.mutate()}}>
            <select className="fin-input" aria-label="Tipo de dato documental" value={manualFact.fact_type} onChange={e=>setManualFact({...manualFact,fact_type:e.target.value})}>
              <option value="contract_term">Dato de contrato / póliza</option>
              <option value="mortgage_term">Dato de hipoteca</option>
              <option value="coverage_fact">Cobertura de seguro</option>
              <option value="linked_product">Producto vinculado</option>
              <option value="investment_term">Dato de inversión</option>
            </select>
            <input className="fin-input" placeholder="Campo, ej. annual_cost o deductible" value={manualFact.key} onChange={e=>setManualFact({...manualFact,key:e.target.value})} required/>
            {manualFact.fact_type==='coverage_fact'?<>
              <input className="fin-input" placeholder="Cobertura, ej. daños por agua" value={manualFact.coverage_type} onChange={e=>setManualFact({...manualFact,coverage_type:e.target.value,value:e.target.value})} required/>
              <input className="fin-input" placeholder="Límite (€), si consta" value={manualFact.limit_amount} onChange={e=>setManualFact({...manualFact,limit_amount:e.target.value})}/>
              <input className="fin-input" placeholder="Franquicia (€), si consta" value={manualFact.deductible} onChange={e=>setManualFact({...manualFact,deductible:e.target.value})}/>
              <input className="fin-input" placeholder="Condiciones" value={manualFact.conditions} onChange={e=>setManualFact({...manualFact,conditions:e.target.value})}/>
              <input className="fin-input md:col-span-2" placeholder="Exclusiones" value={manualFact.exclusions} onChange={e=>setManualFact({...manualFact,exclusions:e.target.value})}/>
            </>:<>
              <input className="fin-input" placeholder="Valor" value={manualFact.value} onChange={e=>setManualFact({...manualFact,value:e.target.value})} required/>
              <input className="fin-input" placeholder="Unidad opcional, ej. €, %, días" value={manualFact.unit} onChange={e=>setManualFact({...manualFact,unit:e.target.value})}/>
            </>}
            <input className="fin-input" type="number" min="1" placeholder="Página de origen (opcional)" value={manualFact.source_page} onChange={e=>setManualFact({...manualFact,source_page:e.target.value})}/>
            <button className="fin-button" disabled={addManualFact.isPending}>{addManualFact.isPending?'Guardando…':'Guardar como dato confirmado'}</button>
          </form>
          {addManualFact.error&&<div className="mt-3"><ErrorState error={addManualFact.error}/></div>}
          <div className="mt-2 text-[11px] text-[var(--muted)]">Claves habituales: provider_name, annual_cost, monthly_cost, renewal_date, cancellation_notice_days, early_exit_penalty, insurance_type, deductible, remaining_principal, nominal_rate, monthly_payment, remaining_months, interest_type, early_repayment_fee.</div>
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
                  {f.fact_type==='coverage_fact'&&<div className="mt-1 text-xs text-[var(--muted)]">{f.value.limit_amount?'Límite '+f.value.limit_amount+' € · ':''}{f.value.deductible?'Franquicia '+f.value.deductible+' € · ':''}{f.value.conditions||''}{f.value.exclusions?(' · Exclusiones: '+f.value.exclusions):''}</div>}
                  {f.value.source==='local_ai_proposal'&&<div className="mt-1 text-[11px] font-medium text-[var(--muted)]">Propuesto por IA local; confirma solo si coincide con el documento.</div>}
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

              {material&&!f.user_verified&&['inferred','ambiguous','conflicting'].includes(f.status)&&<div className="mt-3">
                {f.status==='conflicting'&&<div className="mb-2 text-xs font-medium">Este valor entra en conflicto con otro documento del mismo producto. Confirma este valor solo si has comprobado que es el vigente/correcto.</div>}
                <div className="flex flex-wrap gap-2">
                  <button
                    className="fin-button py-1.5 text-xs"
                    onClick={()=>update.mutate({id:f.id,status:'confirmed'})}
                    disabled={update.isPending}
                  >{f.status==='conflicting'?'Confirmar este valor':'Confirmar'}</button>
                  <button
                    className="fin-button secondary py-1.5 text-xs"
                    onClick={()=>update.mutate({id:f.id,status:'ambiguous'})}
                    disabled={update.isPending}
                  >Mantener como dudoso</button>
                </div>
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
