'use client';

import {FormEvent,useDeferredValue,useEffect,useMemo,useState} from 'react';
import {useMutation,useQuery,useQueryClient} from '@tanstack/react-query';
import {apiGet,apiMutate,apiUpload} from '@/lib/api';
import {PageHeader} from '@/components/page-header';
import {DateRangeSelector,DateRangeKey,resolveDateRange} from '@/components/date-range-selector';
import {Card} from '@/components/ui/card';
import {Money} from '@/components/ui/money';
import {EmptyState,ErrorState,Loading} from '@/components/ui/states';

type AIResult={
  considered:number;reevaluated:number;learned_merchant:number;embedding:number;llm:number;
  unresolved:number;warnings:string[];ai:{available:boolean;chat_model:string|null;chat_ready:boolean;embedding_model:string|null;embedding_ready:boolean}
};
type Account={id:string;name:string};
type Category={id:string;name:string;system_key:string};
type InsuranceRef={id:string;insurance_type:string;provider_name:string|null;policy_number_masked?:string|null;annual_premium:string};
type MortgageRef={id:string;lender:string;remaining_principal:string;currency:string};
type Tx={
  id:string;booking_date:string;amount:string;currency:string;description_raw:string;merchant_raw:string|null;
  category_id:string|null;categorization_method:string;categorization_confidence:string;user_verified:boolean;is_internal_transfer:boolean;
  linked_insurance_policy_id:string|null;linked_mortgage_id:string|null
};
type TxPage={items:Tx[];total:number;page:number;page_size:number;pages:number};
type Rule={id:string;matcher_type:string;matcher_value:string;category_id:string;priority:number;enabled:boolean};
type PaymentRule={id:string;matcher_type:string;matcher_value:string;target_type:'insurance_policy'|'mortgage';target_id:string;enabled:boolean;source_transaction_id:string|null};
type Split={amount:string;category_id:string;note:string};
type ImportResult={
  inserted:number;duplicates:number;rejected:number;ignored?:number;duplicates_reference?:number;duplicates_exact?:number;
  duplicates_similar?:number;detected_inflows?:number;detected_outflows?:number;detected_inflow_amount?:string;
  detected_outflow_amount?:string;transfer_pairs?:number;refunds?:number
};

const insuranceLabel:Record<string,string>={home:'Hogar',car:'Coche',life:'Vida',health:'Salud',pet:'Mascota',travel:'Viaje',other:'Otro',unknown:'Seguro'};

const specialHelp:Record<string,string>={
  internal_transfer:'No cuenta como ingreso ni como gasto: solo mueve dinero entre tus propias cuentas.',
  refunds:'Un importe positivo clasificado aquí reduce gasto; no se suma como ingreso.',
  salary:'Los importes positivos cuentan como ingreso de nómina.',
  income:'Los importes positivos cuentan como entrada de dinero.',
};

export default function TransactionsPage(){
  const qc=useQueryClient();
  const [accountId,setAccountId]=useState('');
  const [file,setFile]=useState<File|null>(null);
  const [search,setSearch]=useState('');
  const [categoryFilter,setCategoryFilter]=useState('');
  const defaults=resolveDateRange('month');
  const [range,setRange]=useState<DateRangeKey>('month');
  const [customStart,setCustomStart]=useState(defaults.start);
  const [customEnd,setCustomEnd]=useState(defaults.end);
  const dates=resolveDateRange(range,customStart,customEnd);
  const [page,setPage]=useState(1);
  const [pageSize,setPageSize]=useState(50);
  const deferredSearch=useDeferredValue(search);
  const [rulesOpen,setRulesOpen]=useState(false);
  useEffect(()=>{
    const q=new URLSearchParams(window.location.search).get('q');
    if(q)setSearch(q);
  },[]);
  const [rule,setRule]=useState({matcher_type:'contains',matcher_value:'',category_id:'',priority:100});
  const [splitTx,setSplitTx]=useState<Tx|null>(null);
  const [splits,setSplits]=useState<Split[]>([{amount:'',category_id:'',note:''},{amount:'',category_id:'',note:''}]);

  const accounts=useQuery({queryKey:['accounts'],queryFn:()=>apiGet<Account[]>('/api/v1/accounts')});
  const cats=useQuery({queryKey:['categories'],queryFn:()=>apiGet<Category[]>('/api/v1/categories')});
  const insurance=useQuery({queryKey:['insurance'],queryFn:()=>apiGet<InsuranceRef[]>('/api/v1/insurance')});
  const mortgages=useQuery({queryKey:['mortgages'],queryFn:()=>apiGet<MortgageRef[]>('/api/v1/mortgages')});
  const txs=useQuery({
    queryKey:['transactions',deferredSearch,categoryFilter,dates.start,dates.end,page,pageSize],
    queryFn:()=>{
      const params=new URLSearchParams({page:String(page),page_size:String(pageSize)});
      if(deferredSearch.trim())params.set('q',deferredSearch.trim());
      if(categoryFilter)params.set('category_id',categoryFilter);
      if(dates.start)params.set('start',dates.start);
      if(dates.end)params.set('end',dates.end);
      return apiGet<TxPage>('/api/v1/transactions/page?'+params.toString());
    },
  });
  const rules=useQuery({queryKey:['transaction-rules'],queryFn:()=>apiGet<Rule[]>('/api/v1/transaction-rules')});
  const paymentRules=useQuery({queryKey:['payment-association-rules'],queryFn:()=>apiGet<PaymentRule[]>('/api/v1/payment-association-rules')});

  const invalidateTransactions=()=>{
    ['transactions','dashboard','analytics-overview','month-end-forecast','cost-centers'].forEach(k=>qc.invalidateQueries({queryKey:[k]}));
  };
  const invalidateProductPayments=()=>{
    invalidateTransactions();
    qc.invalidateQueries({queryKey:['insurance-verdict']});
    qc.invalidateQueries({queryKey:['wealth-details']});
    qc.invalidateQueries({queryKey:['wealth-home']});
    qc.invalidateQueries({queryKey:['mortgages']});
    qc.invalidateQueries({queryKey:['payment-association-rules']});
  };

  const upload=useMutation({
    mutationFn:async()=>{
      if(!file||!accountId)throw new Error('Selecciona cuenta y archivo');
      const form=new FormData();form.append('file',file);
      return apiUpload<ImportResult>('/api/v1/imports/statement?account_id='+encodeURIComponent(accountId),form);
    },
    onSuccess:invalidateProductPayments,
  });
  const categoryMutation=useMutation({
    mutationFn:({id,category_id}:{id:string;category_id:string})=>apiMutate<{id:string;reclassified:number}>('/api/v1/transactions/'+id+'/review','POST',{category_id,create_rule:true,apply_to_existing:true}),
    onSuccess:()=>{invalidateTransactions();qc.invalidateQueries({queryKey:['transaction-rules']})},
  });
  const insuranceLink=useMutation({
    mutationFn:({transactionId,policyId}:{transactionId:string;policyId:string})=>policyId
      ?apiMutate('/api/v1/transactions/'+transactionId+'/insurance/'+policyId,'PUT')
      :apiMutate('/api/v1/transactions/'+transactionId+'/insurance','DELETE'),
    onSuccess:invalidateProductPayments,
  });
  const mortgageLink=useMutation({
    mutationFn:({transactionId,mortgageId}:{transactionId:string;mortgageId:string})=>mortgageId
      ?apiMutate('/api/v1/transactions/'+transactionId+'/mortgage/'+mortgageId,'PUT')
      :apiMutate('/api/v1/transactions/'+transactionId+'/mortgage','DELETE'),
    onSuccess:invalidateProductPayments,
  });
  const addRule=useMutation({
    mutationFn:()=>apiMutate<{id:string;reclassified:number}>('/api/v1/transaction-rules','POST',{...rule,enabled:true}),
    onSuccess:data=>{
      setRule({...rule,matcher_value:''});
      qc.invalidateQueries({queryKey:['transaction-rules']});
      invalidateTransactions();
    },
  });
  const delRule=useMutation({
    mutationFn:(id:string)=>apiMutate('/api/v1/transaction-rules/'+id,'DELETE'),
    onSuccess:()=>qc.invalidateQueries({queryKey:['transaction-rules']}),
  });
  const toggleRule=useMutation({
    mutationFn:(r:Rule)=>apiMutate('/api/v1/transaction-rules/'+r.id,'PATCH',{matcher_type:r.matcher_type,matcher_value:r.matcher_value,category_id:r.category_id,priority:r.priority,enabled:!r.enabled}),
    onSuccess:()=>{qc.invalidateQueries({queryKey:['transaction-rules']});invalidateTransactions()},
  });
  const delPaymentRule=useMutation({
    mutationFn:(id:string)=>apiMutate('/api/v1/payment-association-rules/'+id,'DELETE'),
    onSuccess:()=>qc.invalidateQueries({queryKey:['payment-association-rules']}),
  });
  const togglePaymentRule=useMutation({
    mutationFn:(r:PaymentRule)=>apiMutate('/api/v1/payment-association-rules/'+r.id,'PATCH',{enabled:!r.enabled}),
    onSuccess:()=>qc.invalidateQueries({queryKey:['payment-association-rules']}),
  });
  const aiCategorize=useMutation({
    mutationFn:()=>apiMutate<AIResult>('/api/v1/transactions/ai-categorize','POST',{limit:3000,llm_limit:80}),
    onSuccess:invalidateTransactions,
  });
  const saveSplits=useMutation({
    mutationFn:()=>{
      if(!splitTx)throw new Error('Sin movimiento');
      return apiMutate('/api/v1/transactions/'+splitTx.id+'/splits','PUT',{splits:splits.filter(x=>x.amount&&x.category_id)});
    },
    onSuccess:()=>setSplitTx(null),
  });

  const categoryById=useMemo(()=>new Map((cats.data||[]).map(c=>[c.id,c])),[cats.data]);
  const rows=txs.data?.items||[];
  const total=txs.data?.total||0;
  const pages=txs.data?.pages||1;
  const currentPage=txs.data?.page||page;
  const rangeStart=total===0?0:(currentPage-1)*pageSize+1;
  const rangeEnd=Math.min(total,currentPage*pageSize);

  useEffect(()=>{
    setPage(1);
  },[deferredSearch,categoryFilter,dates.start,dates.end,pageSize]);

  useEffect(()=>{
    if(txs.data&&page!==txs.data.page)setPage(txs.data.page);
  },[txs.data,page]);

  function submit(e:FormEvent){e.preventDefault();upload.mutate()}
  function openRuleFor(tx?:Tx){
    if(tx){
      setRule({
        matcher_type:tx.merchant_raw?'merchant_exact':'contains',
        matcher_value:tx.merchant_raw||tx.description_raw,
        category_id:tx.category_id||'',
        priority:50,
      });
    }else{
      setRule({matcher_type:'contains',matcher_value:'',category_id:'',priority:100});
    }
    setRulesOpen(true);
  }

  const selectedRuleCategory=categoryById.get(rule.category_id);

  return <>
    <PageHeader
      title="Movimientos"
      description="Todos tus movimientos en un único sitio. Si cambias una categoría, Financito aplica esa corrección a todo el histórico con el mismo concepto y crea una regla para los futuros movimientos iguales."
      action={<DateRangeSelector
        range={range}
        customStart={customStart}
        customEnd={customEnd}
        onRangeChange={setRange}
        onCustomStartChange={setCustomStart}
        onCustomEndChange={setCustomEnd}
        ariaLabel="Periodo de Movimientos"
      />}
    />

    <Card>
      <form onSubmit={submit} className="grid gap-3 md:grid-cols-[1fr_1fr_auto]">
        <select className="fin-input" aria-label="Cuenta destino" value={accountId} onChange={e=>setAccountId(e.target.value)} required>
          <option value="">Cuenta destino…</option>
          {accounts.data?.map(a=><option key={a.id} value={a.id}>{a.name}</option>)}
        </select>
        <input className="fin-input" aria-label="Archivo de extracto" type="file" accept=".csv,.xlsx,.xlsm,.qif,.ofx,.xml,.camt,.053,.mt940,.sta" onChange={e=>setFile(e.target.files?.[0]||null)} required/>
        <button className="fin-button" disabled={upload.isPending}>{upload.isPending?'Importando…':'Importar extracto'}</button>
      </form>
      <div className="mt-2 text-xs text-[var(--muted)]">
        Al importar, Financito intenta identificar automáticamente movimientos entre tus cuentas y reembolsos. Una corrección de categoría en la tabla se aplica al mismo concepto tanto en movimientos pasados como futuros.
      </div>
      {upload.data&&<div className="mt-3 rounded-xl bg-[var(--surface-2)] p-3 text-sm">
        <div><strong>Importación terminada:</strong> {upload.data.inserted} nuevos · {upload.data.duplicates} duplicados · {upload.data.rejected} rechazados.</div>
        <div className="mt-1 text-xs text-[var(--muted)]">
          Detección automática: {upload.data.transfer_pairs??0} pareja(s) entre cuentas · {upload.data.refunds??0} reembolso(s) enlazados.
        </div>
      </div>}
      {upload.error&&<div className="mt-3"><ErrorState error={upload.error}/></div>}

      <div className="mt-4 flex flex-wrap gap-2">
        <button className="fin-button secondary" onClick={()=>openRuleFor()}>Nueva regla</button>
        <button className="fin-button secondary" onClick={()=>setRulesOpen(true)}>Ver reglas ({(rules.data?.length??0)+(paymentRules.data?.length??0)})</button>
        <button className="fin-button secondary" onClick={()=>aiCategorize.mutate()} disabled={aiCategorize.isPending}>
          {aiCategorize.isPending?'Analizando con IA local…':'Mejorar categorización con IA local'}
        </button>
      </div>
      {aiCategorize.data&&<div className="mt-3 rounded-xl bg-[var(--surface-2)] p-3 text-sm">
        <strong>Mejora terminada:</strong> {aiCategorize.data.reevaluated} recategorizados · {aiCategorize.data.unresolved} sin evidencia suficiente.
        {aiCategorize.data.warnings.length>0&&<div className="mt-1 text-xs text-[var(--muted)]">{aiCategorize.data.warnings.join(' ')}</div>}
      </div>}
      {aiCategorize.error&&<div className="mt-3"><ErrorState error={aiCategorize.error}/></div>}
      {categoryMutation.data&&<div className="mt-3 rounded-xl bg-[var(--brand-soft)] p-3 text-sm">Categoría aplicada al concepto. {categoryMutation.data.reclassified} movimiento(s) histórico(s) actualizado(s); los futuros con el mismo concepto usarán esta categoría automáticamente.</div>}
      {categoryMutation.error&&<div className="mt-3"><ErrorState error={categoryMutation.error}/></div>}
      {insuranceLink.error&&<div className="mt-3"><ErrorState error={insuranceLink.error}/></div>}
      {mortgageLink.error&&<div className="mt-3"><ErrorState error={mortgageLink.error}/></div>}
    </Card>

    <Card className="mt-4 overflow-x-auto">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="font-bold">Todos los movimientos</h2>
          <p className="mt-1 text-sm text-[var(--muted)]">{total?`Mostrando ${rangeStart}–${rangeEnd} de ${total}`:'Sin movimientos para estos filtros'}.</p>
        </div>
        <div className="grid w-full gap-2 xl:w-auto xl:grid-cols-[minmax(260px,1fr)_210px_130px]">
          <input className="fin-input" type="search" aria-label="Buscar movimientos" placeholder="Buscar concepto, comercio, categoría o importe…" value={search} onChange={e=>setSearch(e.target.value)}/>
          <select className="fin-input" aria-label="Filtrar por categoría" value={categoryFilter} onChange={e=>setCategoryFilter(e.target.value)}>
            <option value="">Todas las categorías</option>
            {cats.data?.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          <label className="text-xs text-[var(--muted)]">Por página<select className="fin-input mt-1" aria-label="Movimientos por página" value={pageSize} onChange={e=>setPageSize(Number(e.target.value))}><option value={25}>25</option><option value={50}>50</option><option value={100}>100</option></select></label>
        </div>
      </div>

      {txs.isLoading?<Loading/>:txs.error?<ErrorState error={txs.error}/>:rows.length?
        <table className="w-full min-w-[1050px] text-sm">
          <thead className="text-left text-xs uppercase text-[var(--muted)]">
            <tr><th className="pb-3">Fecha</th><th>Concepto</th><th>Categoría</th><th>Seguro</th><th>Hipoteca</th><th>Tratamiento</th><th>Acciones</th><th className="text-right">Importe</th></tr>
          </thead>
          <tbody>{rows.map(t=>{
            const category=categoryById.get(t.category_id||'');
            const semantic=category?specialHelp[category.system_key]:undefined;
            return <tr key={t.id} className="border-t border-[var(--border)] align-top">
              <td className="py-3">{t.booking_date}</td>
              <td className="max-w-[340px] py-3">
                <div className="truncate font-medium">{t.description_raw}</div>
                {t.merchant_raw&&<div className="text-xs text-[var(--muted)]">{t.merchant_raw}</div>}
              </td>
              <td className="py-3">
                <select className="rounded-lg border border-[var(--border)] bg-white px-2 py-1" aria-label={'Categoría para '+t.description_raw} value={t.category_id||''} onChange={e=>categoryMutation.mutate({id:t.id,category_id:e.target.value})}>
                  <option value="" disabled>Sin categoría</option>
                  {cats.data?.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}
                </select>
              </td>
              <td className="min-w-[220px] py-3">
                {Number(t.amount)<0&&!t.is_internal_transfer?<div>
                  <select
                    className="max-w-[240px] rounded-lg border border-[var(--border)] bg-white px-2 py-1 text-xs"
                    aria-label={'Seguro para '+t.description_raw}
                    value={t.linked_insurance_policy_id||''}
                    disabled={insuranceLink.isPending}
                    onChange={e=>insuranceLink.mutate({transactionId:t.id,policyId:e.target.value})}
                  >
                    <option value="">Sin vincular a seguro</option>
                    {insurance.data?.map(p=><option key={p.id} value={p.id}>{p.provider_name||insuranceLabel[p.insurance_type]||'Seguro'} · {insuranceLabel[p.insurance_type]||p.insurance_type}{p.policy_number_masked?' · '+p.policy_number_masked:''}</option>)}
                  </select>
                  {t.linked_insurance_policy_id&&<div className="mt-1 text-[11px] font-medium text-[var(--brand)]">Pago vinculado · mismo concepto automático</div>}
                </div>:<span className="text-xs text-[var(--muted)]">—</span>}
              </td>
              <td className="min-w-[220px] py-3">
                {Number(t.amount)<0&&!t.is_internal_transfer?<div>
                  <select
                    className="max-w-[240px] rounded-lg border border-[var(--border)] bg-white px-2 py-1 text-xs"
                    aria-label={'Hipoteca para '+t.description_raw}
                    value={t.linked_mortgage_id||''}
                    disabled={mortgageLink.isPending}
                    onChange={e=>mortgageLink.mutate({transactionId:t.id,mortgageId:e.target.value})}
                  >
                    <option value="">Sin vincular a hipoteca</option>
                    {mortgages.data?.map(m=><option key={m.id} value={m.id}>{m.lender} · {Number(m.remaining_principal).toLocaleString('es-ES')} {m.currency}</option>)}
                  </select>
                  {t.linked_mortgage_id&&<div className="mt-1 text-[11px] font-medium text-[var(--brand)]">Cuota vinculada · mismo concepto automático</div>}
                </div>:<span className="text-xs text-[var(--muted)]">—</span>}
              </td>
              <td className="max-w-[260px] py-3 text-xs text-[var(--muted)]">
                {semantic||(
                  t.user_verified?'Clasificación confirmada por ti':
                  t.categorization_method+' · '+Math.round(Number(t.categorization_confidence)*100)+'%'
                )}
              </td>
              <td className="py-3">
                <div className="flex flex-wrap gap-2">
                  <button className="text-xs underline" onClick={()=>openRuleFor(t)}>Crear regla</button>
                  <button className="text-xs underline" onClick={()=>{setSplitTx(t);setSplits([{amount:'',category_id:t.category_id||'',note:''},{amount:'',category_id:'',note:''}])}}>Dividir</button>
                </div>
              </td>
              <td className={'py-3 text-right font-semibold '+(Number(t.amount)<0?'':'text-[var(--brand)]')}><Money value={t.amount} currency={t.currency}/></td>
            </tr>
          })}</tbody>
        </table>:<EmptyState>No hay movimientos que coincidan con los filtros.</EmptyState>}
      {!txs.isLoading&&!txs.error&&total>0&&<div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-[var(--border)] pt-4 text-sm">
        <div className="text-[var(--muted)]">Página {currentPage} de {pages} · {rangeStart}–{rangeEnd} de {total}</div>
        <div className="flex gap-2">
          <button className="fin-button secondary py-1.5" disabled={currentPage<=1||txs.isFetching} onClick={()=>setPage(1)}>Primera</button>
          <button className="fin-button secondary py-1.5" disabled={currentPage<=1||txs.isFetching} onClick={()=>setPage(p=>Math.max(1,p-1))}>Anterior</button>
          <button className="fin-button secondary py-1.5" disabled={currentPage>=pages||txs.isFetching} onClick={()=>setPage(p=>Math.min(pages,p+1))}>Siguiente</button>
          <button className="fin-button secondary py-1.5" disabled={currentPage>=pages||txs.isFetching} onClick={()=>setPage(pages)}>Última</button>
        </div>
      </div>}
    </Card>

    {rulesOpen&&<div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4" role="dialog" aria-modal="true" aria-label="Reglas automáticas">
      <div className="max-h-[88vh] w-full max-w-3xl overflow-y-auto rounded-2xl bg-white p-5 shadow-xl">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-bold">Reglas automáticas</h2>
            <p className="mt-1 text-sm text-[var(--muted)]">Aquí puedes revisar tanto las reglas de categorización como las vinculaciones automáticas de pagos. Al asociar un concepto a un seguro o hipoteca, Financito aprende ese concepto para los movimientos futuros.</p>
          </div>
          <button className="text-sm underline" onClick={()=>setRulesOpen(false)}>Cerrar</button>
        </div>

        <form className="mt-5 grid gap-2 md:grid-cols-2" onSubmit={(e:FormEvent)=>{e.preventDefault();addRule.mutate()}}>
          <select className="fin-input" aria-label="Tipo de regla" value={rule.matcher_type} onChange={e=>setRule({...rule,matcher_type:e.target.value})}>
            <option value="contains">Concepto contiene texto</option>
            <option value="merchant_exact">Comercio exacto</option>
            <option value="description_exact">Concepto exacto</option>
            <option value="regex">Expresión regular</option>
          </select>
          <input className="fin-input" aria-label="Texto de la regla" placeholder="Texto, comercio o patrón" value={rule.matcher_value} onChange={e=>setRule({...rule,matcher_value:e.target.value})} required/>
          <select className="fin-input" aria-label="Categoría de la regla" value={rule.category_id} onChange={e=>setRule({...rule,category_id:e.target.value})} required>
            <option value="">Categoría…</option>
            {cats.data?.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          <button className="fin-button" disabled={addRule.isPending}>{addRule.isPending?'Aplicando…':'Crear y aplicar regla'}</button>
        </form>
        {selectedRuleCategory&&specialHelp[selectedRuleCategory.system_key]&&<div className="mt-2 rounded-xl bg-[var(--brand-soft)] p-3 text-xs">{specialHelp[selectedRuleCategory.system_key]}</div>}
        {addRule.data&&<div className="mt-2 text-xs text-[var(--muted)]">Regla guardada. {addRule.data.reclassified} movimiento(s) histórico(s) sin confirmar actualizados.</div>}
        {addRule.error&&<div className="mt-3"><ErrorState error={addRule.error}/></div>}

        <div className="mt-6 border-t border-[var(--border)] pt-4">
          <h3 className="font-semibold">Reglas de categorización</h3>
          <div className="mt-3 space-y-2">{rules.data?.length?rules.data.map(r=>{
            const category=categoryById.get(r.category_id);
            return <div key={r.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-[var(--surface-2)] p-3 text-sm">
              <div><strong>{r.matcher_value}</strong><div className="text-xs text-[var(--muted)]">{r.matcher_type} → {category?.name||'Categoría'}</div></div>
              <div className="flex gap-3"><button className="text-xs underline" onClick={()=>toggleRule.mutate(r)}>{r.enabled?'Pausar':'Activar'}</button><button className="text-xs underline" onClick={()=>delRule.mutate(r.id)}>Eliminar</button></div>
            </div>
          }):<EmptyState>No hay reglas automáticas.</EmptyState>}</div>
        </div>

        <div className="mt-6 border-t border-[var(--border)] pt-4">
          <h3 className="font-semibold">Vinculaciones automáticas de pagos</h3>
          <p className="mt-1 text-xs text-[var(--muted)]">Se crean al vincular un movimiento a un seguro o una hipoteca. Pausar una regla detiene las vinculaciones futuras sin borrar las ya realizadas.</p>
          <div className="mt-3 space-y-2">{paymentRules.data?.length?paymentRules.data.map(r=>{
            const policy=insurance.data?.find(p=>p.id===r.target_id);
            const mortgage=mortgages.data?.find(m=>m.id===r.target_id);
            const target=r.target_type==='insurance_policy'
              ?(policy?(policy.provider_name||insuranceLabel[policy.insurance_type]||'Seguro')+' · '+(insuranceLabel[policy.insurance_type]||policy.insurance_type):'Seguro eliminado')
              :(mortgage?mortgage.lender:'Hipoteca eliminada');
            return <div key={r.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-[var(--surface-2)] p-3 text-sm">
              <div><strong>{r.matcher_value}</strong><div className="text-xs text-[var(--muted)]">Concepto exacto → {target}</div></div>
              <div className="flex gap-3"><button className="text-xs underline" onClick={()=>togglePaymentRule.mutate(r)}>{r.enabled?'Pausar':'Activar'}</button><button className="text-xs underline" onClick={()=>delPaymentRule.mutate(r.id)}>Eliminar regla</button></div>
            </div>;
          }):<EmptyState>No hay vinculaciones automáticas de pagos.</EmptyState>}</div>
          {(delPaymentRule.error||togglePaymentRule.error)&&<div className="mt-3"><ErrorState error={(delPaymentRule.error||togglePaymentRule.error)!}/></div>}
        </div>
      </div>
    </div>}

    {splitTx&&<div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4" role="dialog" aria-modal="true" aria-label="Dividir movimiento">
      <Card className="w-full max-w-2xl">
        <div className="flex justify-between gap-3"><div><h2 className="font-bold">Dividir movimiento</h2><div className="text-sm text-[var(--muted)]">{splitTx.description_raw} · total {Math.abs(Number(splitTx.amount)).toLocaleString('es-ES',{minimumFractionDigits:2,maximumFractionDigits:2})} €</div></div><button className="text-sm underline" onClick={()=>setSplitTx(null)}>Cerrar</button></div>
        <div className="mt-3 space-y-2">{splits.map((s,i)=><div key={i} className="grid gap-2 md:grid-cols-3">
          <input className="fin-input" aria-label={'Importe de división '+(i+1)} type="number" step=".01" placeholder="Importe" value={s.amount} onChange={e=>setSplits(splits.map((x,j)=>j===i?{...x,amount:e.target.value}:x))}/>
          <select className="fin-input" aria-label={'Categoría de división '+(i+1)} value={s.category_id} onChange={e=>setSplits(splits.map((x,j)=>j===i?{...x,category_id:e.target.value}:x))}><option value="">Categoría…</option>{cats.data?.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</select>
          <input className="fin-input" aria-label={'Nota de división '+(i+1)} placeholder="Nota opcional" value={s.note} onChange={e=>setSplits(splits.map((x,j)=>j===i?{...x,note:e.target.value}:x))}/>
        </div>)}</div>
        <div className="mt-3 flex gap-2"><button className="fin-button secondary" onClick={()=>setSplits([...splits,{amount:'',category_id:'',note:''}])}>Añadir línea</button><button className="fin-button" onClick={()=>saveSplits.mutate()}>Guardar división</button></div>
        {saveSplits.error&&<div className="mt-3"><ErrorState error={saveSplits.error}/></div>}
      </Card>
    </div>}
  </>;
}
