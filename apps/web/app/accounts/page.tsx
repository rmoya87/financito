'use client';

import Link from 'next/link';
import {FormEvent,useMemo,useState} from 'react';
import {useMutation,useQuery,useQueryClient} from '@tanstack/react-query';
import {apiGet,apiMutate} from '@/lib/api';
import {PageHeader} from '@/components/page-header';
import {Card} from '@/components/ui/card';
import {Money} from '@/components/ui/money';
import {EmptyState,ErrorState,Loading} from '@/components/ui/states';

type Account={
  id:string;name:string;institution_name:string;account_type:string;currency:string;
  current_balance:string;available_balance:string|null;source:string;sync_status:string
};
type InsightItem={title:string;detail:string;pages:number[];impact?:string};
type DocInsight={document_id:string;file_name:string;analysis:{summary:string;optimization_opportunities:InsightItem[];negotiation_points:InsightItem[];comparison_requirements:InsightItem[];risks:InsightItem[]}};
type SyncAll={connections:number;synced:number;failed:number;inserted:number;skipped:number;errors:{bank_name:string;error:string}[]};

const accountTypeLabel=(value:string)=>({
  checking:'Cuenta corriente',savings:'Ahorro',cash:'Efectivo',card:'Tarjeta',CACC:'Cuenta corriente',
}[value]||value);

export default function AccountsPage(){
  const qc=useQueryClient();
  const query=useQuery({queryKey:['accounts'],queryFn:()=>apiGet<Account[]>('/api/v1/accounts')});
  const insights=useQuery({queryKey:['document-insights','bank_statement'],queryFn:()=>apiGet<DocInsight[]>('/api/v1/document-insights?document_type=bank_statement')});
  const [name,setName]=useState('');
  const [institution,setInstitution]=useState('');
  const [accountType,setAccountType]=useState('savings');
  const [balance,setBalance]=useState('');
  const [editing,setEditing]=useState<Account|null>(null);
  const [deleting,setDeleting]=useState<Account|null>(null);
  const [editName,setEditName]=useState('');
  const [editInstitution,setEditInstitution]=useState('');
  const [editType,setEditType]=useState('savings');
  const [editBalance,setEditBalance]=useState('');

  const invalidate=()=>{
    ['accounts','dashboard','analytics-overview','month-end-forecast','calendar'].forEach(k=>qc.invalidateQueries({queryKey:[k]}));
  };

  const create=useMutation({
    mutationFn:()=>apiMutate<Account>('/api/v1/accounts','POST',{
      name,institution_name:institution||'Manual',account_type:accountType,current_balance:balance,currency:'EUR',
    }),
    onSuccess:()=>{setName('');setInstitution('');setAccountType('savings');setBalance('');invalidate()},
  });
  const update=useMutation({
    mutationFn:()=> {
      if(!editing)throw new Error('No hay cuenta seleccionada');
      return apiMutate<Account>('/api/v1/accounts/'+editing.id,'PATCH',{
        name:editName,institution_name:editInstitution||'Manual',account_type:editType,current_balance:editBalance,
      });
    },
    onSuccess:()=>{setEditing(null);invalidate()},
  });
  const remove=useMutation({
    mutationFn:()=>{
      if(!deleting)throw new Error('No hay cuenta seleccionada');
      return apiMutate<{deleted:string;transactions_deleted:number}>('/api/v1/accounts/'+deleting.id,'DELETE');
    },
    onSuccess:()=>{setDeleting(null);invalidate();qc.invalidateQueries({queryKey:['transactions']});qc.invalidateQueries({queryKey:['banking-connections']})},
  });
  const syncAll=useMutation({
    mutationFn:()=>apiMutate<SyncAll>('/api/v1/banking/sync-all','POST'),
    onSuccess:()=>{invalidate();qc.invalidateQueries({queryKey:['transactions']});qc.invalidateQueries({queryKey:['banking-connections']})},
  });

  const total=useMemo(
    ()=> (query.data||[]).filter(a=>a.sync_status!=='pending_sync').reduce((sum,a)=>sum+Number(a.current_balance||0),0),
    [query.data],
  );

  function submit(e:FormEvent){e.preventDefault();create.mutate()}
  function startEdit(account:Account){
    setEditing(account);setEditName(account.name);setEditInstitution(account.institution_name);
    setEditType(account.account_type||'savings');setEditBalance(account.current_balance);
  }

  return <>
    <PageHeader title="Cuentas" description="Saldos reales de tus bancos y saldos manuales auditables, guardados únicamente en tu Financito local."/>

    <div className="mb-4 grid gap-4 lg:grid-cols-[1fr_auto]">
      <Card>
        <div className="text-xs uppercase text-[var(--muted)]">Liquidez registrada</div>
        <div className="mt-2 text-3xl font-bold"><Money value={total}/></div>
        <p className="mt-2 text-sm text-[var(--muted)]">
          Las cuentas bancarias toman el saldo de PSD2. Las cuentas manuales sirven para ahorro, efectivo o entidades que no quieras/puedas conectar.
        </p>
      </Card>
      <Card className="flex min-w-[280px] flex-col justify-center gap-2">
        <button className="fin-button" onClick={()=>syncAll.mutate()} disabled={syncAll.isPending}>
          {syncAll.isPending?'Sincronizando…':'Sincronizar bancos ahora'}
        </button>
        <Link href="/banking/" className="fin-button secondary text-center">Conectar banco</Link>
        <div className="text-xs text-[var(--muted)]">Financito intenta refrescar las conexiones autorizadas automáticamente cada 15 minutos mientras está abierto.</div>
      </Card>
    </div>

    {syncAll.data&&<div className="mb-4 rounded-xl bg-[var(--brand-soft)] p-3 text-sm">
      {syncAll.data.synced} conexión(es) actualizadas · {syncAll.data.inserted} movimiento(s) nuevo(s)
      {syncAll.data.failed>0&&<div className="mt-1 text-xs">No se pudieron actualizar {syncAll.data.failed}: {syncAll.data.errors.map(x=>x.bank_name).join(', ')}.</div>}
    </div>}
    {syncAll.error&&<div className="mb-4"><ErrorState error={syncAll.error}/></div>}

    <div className="grid gap-4 xl:grid-cols-[1fr_380px]">
      <Card>
        <h2 className="font-bold">Tus cuentas</h2>
        <div className="mt-4 space-y-3">
          {query.isLoading?<Loading/>:query.error?<ErrorState error={query.error}/>:query.data?.length?query.data.map(a=>{
            const connected=a.source!=='manual';
            return <div key={a.id} className="rounded-xl bg-[var(--surface-2)] p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="font-semibold">{a.name}</div>
                  <div className="text-xs text-[var(--muted)]">
                    {a.institution_name} · {accountTypeLabel(a.account_type)} · {connected
                      ? a.sync_status==='synced'?'Saldo bancario sincronizado':a.sync_status==='pending_sync'?'Pendiente de primera sincronización':a.sync_status==='disconnected'?'Banco desconectado':'Cuenta bancaria'
                      :'Saldo manual'}
                  </div>
                </div>
                <div className="text-right">
                  <div className="font-bold">{a.sync_status==='pending_sync'?<span className="text-sm text-[var(--muted)]">Saldo pendiente</span>:<Money value={a.current_balance} currency={a.currency}/>}</div>
                  <div className="mt-1 flex flex-wrap justify-end gap-3">
                    {connected
                      ? <Link className="text-xs underline" href="/banking/">Gestionar conexión</Link>
                      : <button className="text-xs underline" onClick={()=>startEdit(a)}>Editar saldo y datos</button>}
                    <button className="text-xs underline" onClick={()=>setDeleting(a)}>Eliminar cuenta</button>
                  </div>
                </div>
              </div>
            </div>;
          }):<EmptyState>Aún no hay cuentas. Conecta tu banco o registra una cuenta manual.</EmptyState>}
        </div>
      </Card>

      <Card>
        <h2 className="font-bold">Añadir saldo o cuenta manual</h2>
        <p className="mt-1 text-sm text-[var(--muted)]">Por ejemplo, una cuenta de ahorro con 40.000 € aunque todavía no esté conectada por PSD2.</p>
        <form onSubmit={submit} className="mt-4 space-y-3">
          <label className="block text-sm">Nombre<input className="fin-input mt-1" value={name} onChange={e=>setName(e.target.value)} placeholder="Ahorros" required/></label>
          <label className="block text-sm">Entidad<input className="fin-input mt-1" value={institution} onChange={e=>setInstitution(e.target.value)} placeholder="Ej. Bankinter"/></label>
          <label className="block text-sm">Tipo
            <select className="fin-input mt-1" value={accountType} onChange={e=>setAccountType(e.target.value)}>
              <option value="savings">Ahorro</option><option value="checking">Cuenta corriente</option><option value="cash">Efectivo</option>
            </select>
          </label>
          <label className="block text-sm">Saldo actual<input className="fin-input mt-1" type="number" step="0.01" value={balance} onChange={e=>setBalance(e.target.value)} placeholder="40000,00" required/></label>
          <button className="fin-button w-full" disabled={create.isPending}>Guardar cuenta</button>
          {create.error&&<ErrorState error={create.error}/>}
        </form>
      </Card>
    </div>

    {deleting&&<div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4" role="dialog" aria-modal="true" aria-label="Eliminar cuenta">
      <Card className="w-full max-w-lg">
        <h2 className="font-bold">Eliminar cuenta</h2>
        <p className="mt-2 text-sm">Vas a eliminar <strong>{deleting.name}</strong> y todos sus movimientos almacenados en Financito.</p>
        <p className="mt-2 text-sm text-[var(--muted)]">{deleting.source==='manual'
          ?'La eliminación solo afecta a los datos locales de esta cuenta.'
          :'La autorización bancaria general no se cierra automáticamente. Esta cuenta dejará de sincronizarse y, si quieres recuperarla, tendrás que volver a vincularla desde Banca.'}</p>
        <div className="mt-5 flex flex-wrap justify-end gap-2">
          <button className="fin-button secondary" onClick={()=>setDeleting(null)} disabled={remove.isPending}>Cancelar</button>
          <button className="fin-button" onClick={()=>remove.mutate()} disabled={remove.isPending}>{remove.isPending?'Eliminando…':'Eliminar definitivamente'}</button>
        </div>
        {remove.error&&<div className="mt-3"><ErrorState error={remove.error}/></div>}
      </Card>
    </div>}

    {editing&&<div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4" role="dialog" aria-modal="true" aria-label="Editar cuenta manual">
      <Card className="w-full max-w-lg">
        <div className="flex items-start justify-between gap-3"><div><h2 className="font-bold">Editar cuenta manual</h2><p className="mt-1 text-sm text-[var(--muted)]">El nuevo saldo queda registrado como ajuste manual en el histórico.</p></div><button className="text-sm underline" onClick={()=>setEditing(null)}>Cerrar</button></div>
        <form className="mt-4 space-y-3" onSubmit={e=>{e.preventDefault();update.mutate()}}>
          <label className="block text-sm">Nombre<input className="fin-input mt-1" value={editName} onChange={e=>setEditName(e.target.value)} required/></label>
          <label className="block text-sm">Entidad<input className="fin-input mt-1" value={editInstitution} onChange={e=>setEditInstitution(e.target.value)}/></label>
          <label className="block text-sm">Tipo<select className="fin-input mt-1" value={editType} onChange={e=>setEditType(e.target.value)}><option value="savings">Ahorro</option><option value="checking">Cuenta corriente</option><option value="cash">Efectivo</option></select></label>
          <label className="block text-sm">Saldo actual<input className="fin-input mt-1" type="number" step="0.01" value={editBalance} onChange={e=>setEditBalance(e.target.value)} required/></label>
          <button className="fin-button w-full" disabled={update.isPending}>Guardar cambios</button>
          {update.error&&<ErrorState error={update.error}/>}
        </form>
      </Card>
    </div>}

    <Card className="mt-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div><h2 className="font-bold">Costes y condiciones detectadas en extractos</h2><p className="mt-1 text-sm text-[var(--muted)]">La IA local puede señalar comisiones y condiciones visibles en documentos bancarios para ayudarte a comparar cuentas.</p></div>
        <Link className="text-xs underline" href="/documents/">Añadir documentos</Link>
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-2">{insights.data?.length?insights.data.map(x=><div key={x.document_id} className="rounded-xl bg-[var(--surface-2)] p-3 text-sm">
        <div className="flex items-start justify-between gap-3"><strong>{x.file_name}</strong><Link className="text-xs underline" href={'/documents/?document='+encodeURIComponent(x.document_id)}>Evidencia</Link></div>
        <p className="mt-2 text-xs">{x.analysis.summary}</p>
        {x.analysis.optimization_opportunities?.length>0&&<div className="mt-2 rounded-lg bg-[var(--brand-soft)] p-2 text-xs"><strong>Oportunidad:</strong> {x.analysis.optimization_opportunities.slice(0,2).map(i=>i.title||i.detail).join(' · ')}</div>}
        {x.analysis.negotiation_points?.length>0&&<div className="mt-2 text-xs"><strong>Para negociar:</strong> {x.analysis.negotiation_points.slice(0,2).map(i=>i.title||i.detail).join(' · ')}</div>}
      </div>):<EmptyState>Añade extractos o contratos bancarios si quieres revisar costes y condiciones.</EmptyState>}</div>
    </Card>
  </>;
}
