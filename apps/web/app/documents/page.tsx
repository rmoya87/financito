'use client';

import {FormEvent,useEffect,useState} from 'react';
import {useMutation,useQuery,useQueryClient} from '@tanstack/react-query';
import {apiGet,apiMutate} from '@/lib/api';
import {PageHeader} from '@/components/page-header';
import {Card} from '@/components/ui/card';
import {EmptyState,ErrorState,Loading} from '@/components/ui/states';

type ReviewSummary={total:number;pending:number;confirmed:number;ambiguous:number;reviewed:number};
type Doc={id:string;file_name:string;document_type:string;status:string;page_count:number;review:ReviewSummary};
type Fact={id:string;fact_type:string;key:string;value:{value:string;unit?:string};confidence:string;status:string;source_page:number|null;source_section:string|null;user_verified:boolean};

const MATERIAL_FACT_TYPES=new Set(['contract_term','mortgage_term','linked_product']);

export default function DocumentsPage(){
  const qc=useQueryClient();
  const [path,setPath]=useState('');
  const [selected,setSelected]=useState<string|null>(null);

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

  const invalidateEvidence=()=>{
    qc.invalidateQueries({queryKey:['documents']});
    qc.invalidateQueries({queryKey:['facts',selected]});
    qc.invalidateQueries({queryKey:['actions']});
    qc.invalidateQueries({queryKey:['dashboard']});
    qc.invalidateQueries({queryKey:['contracts']});
    qc.invalidateQueries({queryKey:['insurance']});
  };

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

  const selectedDoc=docs.data?.find(d=>d.id===selected);
  const materialFacts=facts.data?.filter(f=>MATERIAL_FACT_TYPES.has(f.fact_type))||[];
  const pending=materialFacts.filter(f=>!f.user_verified&&f.status==='inferred').length;
  const confirmed=materialFacts.filter(f=>f.user_verified&&f.status==='confirmed').length;
  const ambiguous=materialFacts.filter(f=>f.status==='ambiguous'||f.status==='conflicting').length;

  return <>
    <PageHeader
      title="Documentos y evidencia"
      description="El Vault se vigila automáticamente. Los documentos se indexan para búsqueda e IA local; los datos materiales solo pasan a contratos, seguros y cálculos cuando los confirmas."
    />

    <Card>
      <form onSubmit={submit} className="grid gap-3 md:grid-cols-[1fr_auto]">
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

        <div className="mt-4 space-y-3">
          {!selected?<EmptyState>Selecciona un documento.</EmptyState>:
          facts.isLoading?<Loading/>:
          facts.error?<ErrorState error={facts.error}/>:
          facts.data?.length?facts.data.map(f=>{
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
