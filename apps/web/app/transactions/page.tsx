'use client';

import {FormEvent,useDeferredValue,useEffect,useMemo,useState} from 'react';
import {MoreHorizontal} from 'lucide-react';
import {useMutation,useQuery,useQueryClient} from '@tanstack/react-query';
import {apiGet,apiMutate,apiUpload} from '@/lib/api';
import {PageHeader} from '@/components/page-header';
import {useFinancialFilters} from '@/components/financial-filters';
import {Card} from '@/components/ui/card';
import {Money} from '@/components/ui/money';
import {EmptyState,ErrorState,Loading} from '@/components/ui/states';
import {DetailGroup,MetricTile,ModalHero,SectionIntro} from '@/components/finance-ui';

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
  const {start:globalStart,end:globalEnd,accountScope}=useFinancialFilters();
  const [accountId,setAccountId]=useState('');
  const [file,setFile]=useState<File|null>(null);
  const [search,setSearch]=useState('');
  const [categoryFilter,setCategoryFilter]=useState('');
  const [page,setPage]=useState(1);
  const [pageSize,setPageSize]=useState(50);
  const deferredSearch=useDeferredValue(search);
  const [rulesOpen,setRulesOpen]=useState(false);
  const [showImport,setShowImport]=useState(false);
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
    queryKey:['transactions',deferredSearch,categoryFilter,globalStart,globalEnd,accountScope,page,pageSize],
    queryFn:()=>{
      const params=new URLSearchParams({page:String(page),page_size:String(pageSize)});
      if(deferredSearch.trim())params.set('q',deferredSearch.trim());
      if(categoryFilter)params.set('category_id',categoryFilter);
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
  const visibleIn=rows.reduce((sum,row)=>sum+(Number(row.amount)>0?Number(row.amount):0),0);
  const visibleOut=rows.reduce((sum,row)=>sum+(Number(row.amount)<0?Math.abs(Number(row.amount)):0),0);
  const visibleUnclassified=rows.filter(row=>!row.category_id).length;

  useEffect(()=>{
    setPage(1);
  },[deferredSearch,categoryFilter,globalStart,globalEnd,accountScope,pageSize]);

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
      action={<button type="button" className="fin-button" onClick={()=>setShowImport(true)}>Importar extracto</button>}
    />

    <SectionIntro eyebrow="Lectura rápida" title="Qué hay en estos movimientos" description="La parte superior resume el filtro actual; debajo puedes buscar, recategorizar o automatizar sin perder contexto."/>
    <div className="mb-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <MetricTile label="Movimientos" value={total} detail={total?`Mostrando ${rangeStart}–${rangeEnd}`:'Sin resultados'} status="Filtro actual" statusTone="calculated"/>
      <MetricTile label="Entradas visibles" value={<Money value={visibleIn}/>} detail="Suma de la página actual"/>
      <MetricTile label="Salidas visibles" value={<Money value={visibleOut}/>} detail="Suma de la página actual" emphasis/>
      <MetricTile label="Sin categoría" value={visibleUnclassified} detail="Movimientos visibles pendientes de clasificación" status={visibleUnclassified?'Revisar':'Todo clasificado'} statusTone={visibleUnclassified?'pending':'confirmed'}/>
    </div>

    <div className="mb-3 flex flex-wrap gap-2">
      <button type="button" className="fin-button secondary" onClick={()=>openRuleFor()}>Nueva regla</button>
      <button type="button" className="fin-button secondary" onClick={()=>setRulesOpen(true)}>Ver reglas ({(rules.data?.length??0)+(paymentRules.data?.length??0)})</button>
      <button type="button" className="fin-button secondary" onClick={()=>aiCategorize.mutate()} disabled={aiCategorize.isPending}>
        {aiCategorize.isPending?'Analizando con IA local…':'Mejorar categorización con IA local'}
      </button>
    </div>
    {aiCategorize.data&&<div className="mb-3 rounded-xl bg-[var(--surface-2)] p-3 text-sm">
      <strong>Mejora terminada:</strong> {aiCategorize.data.reevaluated} recategorizados · {aiCategorize.data.unresolved} sin evidencia suficiente.
      {aiCategorize.data.warnings.length>0&&<div className="mt-1 text-xs text-[var(--muted)]">{aiCategorize.data.warnings.join(' ')}</div>}
    </div>}
    {aiCategorize.error&&<div className="mb-3"><ErrorState error={aiCategorize.error}/></div>}
    {categoryMutation.data&&<div className="mb-3 rounded-xl bg-[var(--brand-soft)] p-3 text-sm">Categoría aplicada al concepto. {categoryMutation.data.reclassified} movimiento(s) histórico(s) actualizado(s); los futuros con el mismo concepto usarán esta categoría automáticamente.</div>}
    {categoryMutation.error&&<div className="mb-3"><ErrorState error={categoryMutation.error}/></div>}
    {insuranceLink.error&&<div className="mb-3"><ErrorState error={insuranceLink.error}/></div>}
    {mortgageLink.error&&<div className="mb-3"><ErrorState error={mortgageLink.error}/></div>}

    <SectionIntro eyebrow="Detalle" title="Todos los movimientos" description="Filtra por texto o categoría; las acciones de cada fila están agrupadas en Opciones para mantener la tabla limpia."/>
    <Card className="overflow-visible">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">Resultados</div>
          <p className="mt-1 text-sm text-[var(--muted)]">{total?`Mostrando ${rangeStart}–${rangeEnd} de ${total}`:'Sin movimientos para estos filtros'}.</p>
        </div>
        <div className="grid w-full gap-2 lg:w-auto lg:grid-cols-[minmax(240px,1fr)_190px_110px]">
          <input className="fin-input min-w-0" type="search" aria-label="Buscar movimientos" placeholder="Buscar concepto, comercio, categoría o importe…" value={search} onChange={e=>setSearch(e.target.value)}/>
          <select className="fin-input min-w-0" aria-label="Filtrar por categoría" value={categoryFilter} onChange={e=>setCategoryFilter(e.target.value)}>
            <option value="">Todas las categorías</option>
            {cats.data?.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          <label className="text-xs text-[var(--muted)]">Por página<select className="fin-input mt-1" aria-label="Movimientos por página" value={pageSize} onChange={e=>setPageSize(Number(e.target.value))}><option value={25}>25</option><option value={50}>50</option><option value={100}>100</option></select></label>
        </div>
      </div>

      {txs.isLoading?<Loading/>:txs.error?<ErrorState error={txs.error}/>:rows.length?
        <div className="w-full">
          <table className="w-full table-fixed text-sm">
            <colgroup><col className="w-[92px]"/><col/><col className="w-[190px]"/><col className="hidden w-[180px] xl:table-column"/><col className="w-[118px]"/><col className="w-[54px]"/></colgroup>
            <thead className="text-left text-xs uppercase text-[var(--muted)]">
              <tr><th className="pb-3">Fecha</th><th>Concepto</th><th>Categoría</th><th className="hidden xl:table-cell">Tratamiento</th><th className="text-right">Importe</th><th className="text-right">Opc.</th></tr>
            </thead>
            <tbody>{rows.map(t=>{
              const category=categoryById.get(t.category_id||'');
              const semantic=category?specialHelp[category.system_key]:undefined;
              const linkedPolicy=insurance.data?.find(p=>p.id===t.linked_insurance_policy_id);
              const linkedMortgage=mortgages.data?.find(m=>m.id===t.linked_mortgage_id);
              return <tr key={t.id} className="border-t border-[var(--border)] align-top">
                <td className="py-3 pr-2 text-xs whitespace-nowrap">{t.booking_date}</td>
                <td className="min-w-0 py-3 pr-3">
                  <div className="truncate font-medium" title={t.description_raw}>{t.description_raw}</div>
                  <div className="mt-0.5 flex min-w-0 flex-wrap gap-x-2 text-[11px] text-[var(--muted)]">
                    {t.merchant_raw&&<span className="max-w-full truncate">{t.merchant_raw}</span>}
                    {linkedPolicy&&<span className="font-medium text-[var(--brand)]">Seguro · {linkedPolicy.provider_name||insuranceLabel[linkedPolicy.insurance_type]||'póliza'}</span>}
                    {linkedMortgage&&<span className="font-medium text-[var(--brand)]">Hipoteca · {linkedMortgage.lender}</span>}
                  </div>
                </td>
                <td className="py-3 pr-3">
                  <select className="w-full min-w-0 rounded-lg border border-[var(--border)] bg-white px-2 py-1 text-xs" aria-label={'Categoría para '+t.description_raw} value={t.category_id||''} onChange={e=>categoryMutation.mutate({id:t.id,category_id:e.target.value})}>
                    <option value="" disabled>Sin categoría</option>
                    {cats.data?.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}
                  </select>
                </td>
                <td className="hidden py-3 pr-3 text-xs text-[var(--muted)] xl:table-cell">
                  <div className="line-clamp-2">{semantic||(t.user_verified?'Clasificación confirmada por ti':t.categorization_method+' · '+Math.round(Number(t.categorization_confidence)*100)+'%')}</div>
                </td>
                <td className={'py-3 text-right font-semibold whitespace-nowrap '+(Number(t.amount)<0?'':'text-[var(--brand)]')}><Money value={t.amount} currency={t.currency}/></td>
                <td className="relative py-3 text-right">
                  <details className="group relative inline-block text-left">
                    <summary className="inline-flex size-8 cursor-pointer list-none items-center justify-center rounded-lg border border-[var(--border)] bg-white hover:bg-[var(--surface-2)] [&::-webkit-details-marker]:hidden" aria-label={'Opciones de '+t.description_raw}><MoreHorizontal size={17}/></summary>
                    <div className="absolute right-0 z-30 mt-2 w-72 rounded-xl border border-[var(--border)] bg-white p-3 text-left shadow-xl">
                      {Number(t.amount)<0&&!t.is_internal_transfer&&<>
                        <label className="block text-[11px] font-medium text-[var(--muted)]">Seguro
                          <select className="fin-input mt-1 w-full text-xs" aria-label={'Seguro para '+t.description_raw} value={t.linked_insurance_policy_id||''} disabled={insuranceLink.isPending} onChange={e=>insuranceLink.mutate({transactionId:t.id,policyId:e.target.value})}>
                            <option value="">Sin vincular</option>
                            {insurance.data?.map(p=><option key={p.id} value={p.id}>{p.provider_name||insuranceLabel[p.insurance_type]||'Seguro'} · {insuranceLabel[p.insurance_type]||p.insurance_type}{p.policy_number_masked?' · '+p.policy_number_masked:''}</option>)}
                          </select>
                        </label>
                        <label className="mt-3 block text-[11px] font-medium text-[var(--muted)]">Hipoteca
                          <select className="fin-input mt-1 w-full text-xs" aria-label={'Hipoteca para '+t.description_raw} value={t.linked_mortgage_id||''} disabled={mortgageLink.isPending} onChange={e=>mortgageLink.mutate({transactionId:t.id,mortgageId:e.target.value})}>
                            <option value="">Sin vincular</option>
                            {mortgages.data?.map(m=><option key={m.id} value={m.id}>{m.lender} · {Number(m.remaining_principal).toLocaleString('es-ES')} {m.currency}</option>)}
                          </select>
                        </label>
                        <div className="my-3 border-t border-[var(--border)]"/>
                      </>}
                      <button className="block w-full rounded-lg px-2 py-2 text-left text-xs hover:bg-[var(--surface-2)]" type="button" onClick={e=>{(e.currentTarget.closest('details') as HTMLDetailsElement|null)?.removeAttribute('open');openRuleFor(t)}}>Crear regla con este movimiento</button>
                      <button className="block w-full rounded-lg px-2 py-2 text-left text-xs hover:bg-[var(--surface-2)]" type="button" onClick={e=>{(e.currentTarget.closest('details') as HTMLDetailsElement|null)?.removeAttribute('open');setSplitTx(t);setSplits([{amount:'',category_id:t.category_id||'',note:''},{amount:'',category_id:'',note:''}])}}>Dividir movimiento</button>
                    </div>
                  </details>
                </td>
              </tr>
            })}</tbody>
          </table>
        </div>:<EmptyState>No hay movimientos que coincidan con los filtros.</EmptyState>}
      {!txs.isLoading&&!txs.error&&total>0&&<div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-[var(--border)] pt-4 text-sm">
        <div className="text-[var(--muted)]">Página {currentPage} de {pages} · {rangeStart}–{rangeEnd} de {total}</div>
        <div className="flex flex-wrap gap-2">
          <button className="fin-button secondary py-1.5" disabled={currentPage<=1||txs.isFetching} onClick={()=>setPage(1)}>Primera</button>
          <button className="fin-button secondary py-1.5" disabled={currentPage<=1||txs.isFetching} onClick={()=>setPage(p=>Math.max(1,p-1))}>Anterior</button>
          <button className="fin-button secondary py-1.5" disabled={currentPage>=pages||txs.isFetching} onClick={()=>setPage(p=>Math.min(pages,p+1))}>Siguiente</button>
          <button className="fin-button secondary py-1.5" disabled={currentPage>=pages||txs.isFetching} onClick={()=>setPage(pages)}>Última</button>
        </div>
      </div>}
    </Card>

    {showImport&&<div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4" role="dialog" aria-modal="true" aria-label="Importar extracto">
      <Card className="w-full max-w-2xl">
        <ModalHero
          eyebrow="Movimientos"
          title="Importar extracto"
          description="Añade un archivo bancario a la cuenta correcta. Financito detectará duplicados, transferencias propias, reembolsos y reglas."
          status="Procesamiento automático"
          statusTone="calculated"
          actions={<button type="button" className="fin-button secondary py-2 text-xs" onClick={()=>setShowImport(false)}>Cerrar</button>}
        />
        <form onSubmit={submit} className="mt-5 grid gap-3 md:grid-cols-[1fr_1fr_auto]">
          <select className="fin-input" aria-label="Cuenta destino" value={accountId} onChange={e=>setAccountId(e.target.value)} required>
            <option value="">Cuenta destino…</option>
            {accounts.data?.map(a=><option key={a.id} value={a.id}>{a.name}</option>)}
          </select>
          <input className="fin-input" aria-label="Archivo de extracto" type="file" accept=".csv,.xlsx,.xlsm,.qif,.ofx,.xml,.camt,.053,.mt940,.sta" onChange={e=>setFile(e.target.files?.[0]||null)} required/>
          <button className="fin-button" disabled={upload.isPending}>{upload.isPending?'Importando…':'Importar'}</button>
        </form>
        {upload.data&&<div className="mt-4 rounded-xl bg-[var(--surface-2)] p-3 text-sm">
          <div><strong>Importación terminada:</strong> {upload.data.inserted} nuevos · {upload.data.duplicates} duplicados · {upload.data.rejected} rechazados.</div>
          <div className="mt-1 text-xs text-[var(--muted)]">Detección automática: {upload.data.transfer_pairs??0} pareja(s) entre cuentas · {upload.data.refunds??0} reembolso(s) enlazados.</div>
        </div>}
        {upload.error&&<div className="mt-4"><ErrorState error={upload.error}/></div>}
      </Card>
    </div>}

    {rulesOpen&&<div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4" role="dialog" aria-modal="true" aria-label="Reglas automáticas">
      <div className="max-h-[88vh] w-full max-w-3xl overflow-y-auto rounded-2xl bg-white p-5 shadow-xl">
        <ModalHero
          eyebrow="Automatización"
          title="Reglas automáticas"
          description="Revisa categorización y vinculaciones de pagos. Lo que confirmas aquí se reutiliza en movimientos futuros."
          status={(rules.data?.length??0)+(paymentRules.data?.length??0)+' reglas'}
          statusTone="confirmed"
          actions={<button className="fin-button secondary py-2 text-xs" onClick={()=>setRulesOpen(false)}>Cerrar</button>}
          metrics={[
            {label:'Categorización',value:rules.data?.length??0,detail:'reglas activas o pausadas'},
            {label:'Pagos vinculados',value:paymentRules.data?.length??0,detail:'seguros e hipotecas'},
          ]}
        />

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

        <DetailGroup title="Reglas de categorización" description="Cambian la categoría y pueden aplicarse también al histórico." className="mt-6">
          <div className="mt-3 space-y-2">{rules.data?.length?rules.data.map(r=>{
            const category=categoryById.get(r.category_id);
            return <div key={r.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-[var(--surface-2)] p-3 text-sm">
              <div><strong>{r.matcher_value}</strong><div className="text-xs text-[var(--muted)]">{r.matcher_type} → {category?.name||'Categoría'}</div></div>
              <div className="flex gap-3"><button className="text-xs underline" onClick={()=>toggleRule.mutate(r)}>{r.enabled?'Pausar':'Activar'}</button><button className="text-xs underline" onClick={()=>delRule.mutate(r.id)}>Eliminar</button></div>
            </div>
          }):<EmptyState>No hay reglas automáticas.</EmptyState>}</div>
        </DetailGroup>

        <DetailGroup title="Vinculaciones automáticas de pagos" description="Se crean al vincular un movimiento a un seguro o una hipoteca. Pausar una regla detiene las vinculaciones futuras sin borrar las ya realizadas." className="mt-4">
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
        </DetailGroup>
      </div>
    </div>}

    {splitTx&&<div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4" role="dialog" aria-modal="true" aria-label="Dividir movimiento">
      <Card className="w-full max-w-2xl">
        <ModalHero
          eyebrow="Movimiento"
          title="Dividir movimiento"
          description={splitTx.description_raw}
          metrics={[{label:'Total',value:<Money value={Math.abs(Number(splitTx.amount))}/>}]}
          actions={<button className="fin-button secondary py-2 text-xs" onClick={()=>setSplitTx(null)}>Cerrar</button>}
        />
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
