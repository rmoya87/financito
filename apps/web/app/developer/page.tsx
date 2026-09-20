'use client';
import {useQuery} from '@tanstack/react-query';
import {apiGet} from '@/lib/api';
import {PageHeader} from '@/components/page-header';
import {Card} from '@/components/ui/card';
import {ErrorState,Loading} from '@/components/ui/states';

type Fresh={value:string|null;age_hours:number|null;status:'fresh'|'stale'|'observed'|'unknown'};
type Snapshot={
  schema_version:number;
  runtime:{local_only:boolean;database_encrypted:boolean;db_bytes:number;vault:{files:number;bytes:number}};
  counts:Record<string,number>;
  freshness:Record<string,Fresh>;
  ai:{available:boolean;configured_model:string|null;embedding_model:string|null;models:string[]};
  providers:Record<string,unknown>;
  provenance:Record<string,string>;
};
function bytes(v:number){if(v<1024)return v+' B';if(v<1024**2)return (v/1024).toFixed(1)+' KB';if(v<1024**3)return (v/1024**2).toFixed(1)+' MB';return (v/1024**3).toFixed(1)+' GB'}
function badge(status:string){return status==='fresh'?'Actual':status==='stale'?'Desactualizado':status==='observed'?'Observado':'Sin datos'}
export default function DeveloperPage(){const q=useQuery({queryKey:['developer-snapshot'],queryFn:()=>apiGet<Snapshot>('/api/v1/developer/snapshot'),refetchInterval:30000});return <><PageHeader title="Developer Mode" description="Diagnóstico, frescura y procedencia del runtime local. Nunca muestra valores de secretos." />{q.isLoading?<Loading/>:q.error?<ErrorState error={q.error}/>:q.data&&<div className="space-y-4"><div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"><Card><div className="text-xs uppercase text-[var(--muted)]">Schema</div><div className="mt-2 text-2xl font-bold">v{q.data.schema_version}</div></Card><Card><div className="text-xs uppercase text-[var(--muted)]">Base</div><div className="mt-2 text-lg font-bold">{q.data.runtime.database_encrypted?'SQLCipher':'SQLite dev'}</div><div className="text-xs text-[var(--muted)]">{bytes(q.data.runtime.db_bytes)}</div></Card><Card><div className="text-xs uppercase text-[var(--muted)]">Vault</div><div className="mt-2 text-lg font-bold">{q.data.runtime.vault.files} archivos</div><div className="text-xs text-[var(--muted)]">{bytes(q.data.runtime.vault.bytes)}</div></Card><Card><div className="text-xs uppercase text-[var(--muted)]">IA local</div><div className="mt-2 text-lg font-bold">{q.data.ai.available?'Disponible':'No disponible'}</div><div className="text-xs text-[var(--muted)]">{q.data.ai.configured_model||'sin modelo'}</div></Card></div><Card><h2 className="font-bold">Frescura</h2><div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-5">{Object.entries(q.data.freshness).map(([name,f])=><div key={name} className="rounded-xl bg-[var(--surface-2)] p-3"><div className="text-xs uppercase text-[var(--muted)]">{name}</div><div className="mt-1 font-semibold">{badge(f.status)}</div><div className="mt-1 text-xs text-[var(--muted)]">{f.value?String(f.value):'sin observación'}{f.age_hours!==null?' · '+f.age_hours+' h':''}</div></div>)}</div></Card><div className="grid gap-4 xl:grid-cols-2"><Card><h2 className="font-bold">Contadores</h2><div className="mt-3 grid grid-cols-2 gap-2">{Object.entries(q.data.counts).map(([k,v])=><div key={k} className="flex justify-between rounded-lg bg-[var(--surface-2)] p-2 text-sm"><span>{k.replaceAll('_',' ')}</span><strong>{v}</strong></div>)}</div></Card><Card><h2 className="font-bold">Provenance</h2><div className="mt-3 space-y-2">{Object.entries(q.data.provenance).map(([k,v])=><div key={k} className="rounded-lg bg-[var(--surface-2)] p-3 text-sm"><strong>{k}</strong><div className="mt-1 text-xs text-[var(--muted)]">{v}</div></div>)}</div></Card></div><Card><h2 className="font-bold">Providers</h2><p className="mt-1 text-sm text-[var(--muted)]">Solo estado/configuración; nunca se devuelven claves ni tokens.</p><pre className="mt-3 overflow-auto rounded-xl bg-[var(--surface-2)] p-3 text-xs">{JSON.stringify(q.data.providers,null,2)}</pre></Card></div>}</>}
