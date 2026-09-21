'use client';

import Link from 'next/link';
import {FormEvent,useState} from 'react';
import {useMutation} from '@tanstack/react-query';
import {apiMutate} from '@/lib/api';
import {PageHeader} from '@/components/page-header';
import {Card} from '@/components/ui/card';
import {ErrorState,Loading} from '@/components/ui/states';

type Answer={
  result:string;
  sources:{document_id:string;document_name:string;chunk_id:string;page_start:number|null;excerpt:string}[];
  calculations:any;
  ai:{available:boolean;ready:boolean;model:string|null;used:boolean;error:string|null};
};

export default function ChatPage(){
  const [q,setQ]=useState('');
  const ask=useMutation({mutationFn:()=>apiMutate<Answer>('/api/v1/chat','POST',{question:q.trim()})});

  return <>
    <PageHeader title="Preguntar" description="Pregunta sobre tus finanzas. Financito usa primero datos y cálculos verificables y, cuando el modelo local está disponible, usa IA para explicarlos."/>
    <Card>
      <form className="flex flex-col gap-2 sm:flex-row" onSubmit={(e:FormEvent)=>{e.preventDefault();if(q.trim().length>=2)ask.mutate()}}>
        <input className="fin-input min-w-0 flex-1" aria-label="Pregunta financiera" value={q} onChange={e=>setQ(e.target.value)} placeholder="¿Cuánto gasté? ¿Qué contratos renuevan? ¿Qué dice mi póliza?"/>
        <button className="fin-button sm:min-w-28" disabled={q.trim().length<2||ask.isPending}>{ask.isPending?'Pensando…':'Preguntar'}</button>
      </form>
      <div className="mt-2 text-xs text-[var(--muted)]">La cuenta y el periodo seleccionados arriba se aplican también a esta consulta financiera.</div>
    </Card>

    {ask.isPending&&<div className="mt-4"><Loading/></div>}
    {ask.error&&<div className="mt-4"><ErrorState error={ask.error}/></div>}

    {ask.data&&<Card className="mt-4">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2 border-b border-[var(--border)] pb-3">
        <div className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
          {ask.data.ai.used?'Respuesta con IA local':'Respuesta determinista'}
        </div>
        <div className="text-xs text-[var(--muted)]">
          {ask.data.ai.used
            ?'Modelo '+(ask.data.ai.model||'local')
            :ask.data.ai.ready
              ?'IA disponible pero no usada'
              :'IA local no disponible'}
        </div>
      </div>

      <div className="whitespace-pre-wrap leading-7">{ask.data.result}</div>

      {!ask.data.ai.used&&<div className="mt-4 rounded-xl bg-[var(--surface-2)] p-3 text-sm">
        <strong>La IA generativa no se ha usado en esta respuesta.</strong>
        <div className="mt-1 text-xs text-[var(--muted)]">
          {ask.data.ai.error||(
            ask.data.ai.model
              ?'El modelo configurado no está listo en Ollama.'
              :'No hay un modelo de chat configurado.'
          )}
        </div>
        <Link href="/settings/" className="mt-2 inline-block text-xs font-semibold underline">Revisar y probar IA local</Link>
      </div>}

      {ask.data.sources.length>0&&<div className="mt-6">
        <h2 className="font-bold">Evidencia utilizada</h2>
        <div className="mt-2 space-y-2">{ask.data.sources.map((s,i)=><div key={s.chunk_id} className="rounded-xl bg-[var(--surface-2)] p-3 text-sm">
          <a className="font-semibold underline" href={'/api/v1/documents/'+s.document_id+'/file'+(s.page_start?'#page='+s.page_start:'')} target="_blank" rel="noreferrer">[{i+1}] {s.document_name}{s.page_start&&' · pág. '+s.page_start}</a>
          <div className="mt-1 text-[var(--muted)]">{s.excerpt}</div>
        </div>)}</div>
      </div>}
    </Card>}
  </>;
}
