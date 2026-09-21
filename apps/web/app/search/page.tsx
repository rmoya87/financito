'use client';

import {FormEvent,useState} from 'react';
import {useMutation} from '@tanstack/react-query';
import {apiGet} from '@/lib/api';
import {PageHeader} from '@/components/page-header';
import {Card} from '@/components/ui/card';
import {Money} from '@/components/ui/money';
import {EmptyState,ErrorState,Loading} from '@/components/ui/states';

type Result={
  transactions:{id:string;date:string;description:string;amount:string}[];
  contracts:{id:string;provider:string;type:string}[];
  documents:{chunk_id:string;document_id:string;document_name:string;page_start:number|null;text:string;score:number}[]
};

export default function SearchPage(){
  const [q,setQ]=useState('');
  const search=useMutation({mutationFn:()=>apiGet<Result>('/api/v1/search?q='+encodeURIComponent(q.trim()))});
  const any=!!search.data&&(search.data.transactions.length+search.data.contracts.length+search.data.documents.length)>0;

  return <>
    <PageHeader title="Búsqueda global" description="Busca simultáneamente en movimientos, contratos y documentos indexados. Solo se muestran los bloques que tengan resultados."/>
    <Card>
      <form className="flex flex-col gap-2 sm:flex-row" onSubmit={(e:FormEvent)=>{e.preventDefault();if(q.trim().length>=2)search.mutate()}}>
        <input className="fin-input min-w-0 flex-1" aria-label="Búsqueda global" value={q} onChange={e=>setQ(e.target.value)} placeholder="Proveedor, comercio, cláusula, concepto…"/>
        <button className="fin-button sm:min-w-28" disabled={q.trim().length<2||search.isPending}>{search.isPending?'Buscando…':'Buscar'}</button>
      </form>
      {search.error&&<div className="mt-3"><ErrorState error={search.error}/></div>}
    </Card>

    {search.isPending&&<div className="mt-4"><Loading/></div>}

    {search.data&&any&&<div className="mt-4 space-y-4">
      {search.data.transactions.length>0&&<Card>
        <div className="flex items-center justify-between gap-3"><h2 className="font-bold">Movimientos</h2><span className="text-xs text-[var(--muted)]">{search.data.transactions.length} resultado(s)</span></div>
        <div className="mt-3 divide-y divide-[var(--border)]">{search.data.transactions.map(r=><div key={r.id} className="flex min-w-0 items-center justify-between gap-4 py-3 text-sm first:pt-0 last:pb-0"><div className="min-w-0"><div className="truncate font-medium">{r.description}</div><div className="text-xs text-[var(--muted)]">{r.date}</div></div><strong className="shrink-0"><Money value={r.amount}/></strong></div>)}</div>
      </Card>}

      {search.data.contracts.length>0&&<Card>
        <div className="flex items-center justify-between gap-3"><h2 className="font-bold">Contratos</h2><span className="text-xs text-[var(--muted)]">{search.data.contracts.length} resultado(s)</span></div>
        <div className="mt-3 divide-y divide-[var(--border)]">{search.data.contracts.map(r=><div key={r.id} className="py-3 text-sm first:pt-0 last:pb-0"><strong>{r.provider}</strong><div className="text-xs text-[var(--muted)]">{r.type}</div></div>)}</div>
      </Card>}

      {search.data.documents.length>0&&<Card>
        <div className="flex items-center justify-between gap-3"><h2 className="font-bold">Documentos</h2><span className="text-xs text-[var(--muted)]">{search.data.documents.length} resultado(s)</span></div>
        <div className="mt-3 divide-y divide-[var(--border)]">{search.data.documents.map(r=><div key={r.chunk_id} className="py-3 text-sm first:pt-0 last:pb-0"><a className="font-semibold underline" href={'/api/v1/documents/'+r.document_id+'/file'+(r.page_start?'#page='+r.page_start:'')} target="_blank" rel="noreferrer">{r.document_name}{r.page_start?' · pág. '+r.page_start:''}</a><div className="mt-1 line-clamp-4 text-xs leading-5 text-[var(--muted)]">{r.text}</div></div>)}</div>
      </Card>}
    </div>}

    {search.data&&!any&&<div className="mt-4"><EmptyState>No se ha encontrado ninguna coincidencia.</EmptyState></div>}
  </>;
}
