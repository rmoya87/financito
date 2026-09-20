'use client';

import Link from 'next/link';
import {FormEvent,useEffect,useMemo,useState} from 'react';
import {useMutation,useQuery,useQueryClient} from '@tanstack/react-query';
import {apiGet,apiMutate} from '@/lib/api';
import {PageHeader} from '@/components/page-header';
import {Card} from '@/components/ui/card';
import {Money} from '@/components/ui/money';
import {EmptyState,ErrorState,Loading} from '@/components/ui/states';

type WealthSummary={
  accounts:string;manual_assets:string;investments:string;liabilities:string;mortgages:string;
  gross_assets:string;total_debt:string;net_worth:string
};
type Account={id:string;name:string;institution_name:string;currency:string;balance:string};
type Asset={id:string;type:string;name:string;value:string;currency:string;valuation_date:string;valuation_source:string;ownership_percentage:string};
type Liability={id:string;type:string;name:string;amount:string;currency:string;annual_rate:string|null;ownership_percentage:string};
type Mortgage={id:string;lender:string;remaining_principal:string;currency:string;interest_type:string;nominal_rate:string;monthly_payment:string;remaining_months:number;early_repayment_fee?:string|null};
type Investment={security_id:string;name:string;identifier:string|null;asset_class:string;currency:string;quantity:string;cost_basis:string;current_value:string|null;current_price:string|null;price_provider:string|null};
type Policy={id:string;insurance_type:string;annual_premium:string;currency:string;deductible:string|null;provider:string|null;contract_id:string|null};
type WealthDetails={summary:WealthSummary;accounts:Account[];assets:Asset[];liabilities:Liability[];mortgages:Mortgage[];investments:Investment[];insurance:{annual_premium_total:string;policies:Policy[]}};

type MortgageExtra={
  original_principal:string|null;original_term_months:number|null;start_date:string|null;maturity_date:string|null;
  apr_rate:string|null;reference_index:string|null;differential_rate:string|null;rate_review_months:number|null;next_review_date:string|null;
  opening_fee_percent:string|null;early_repayment_fee_percent:string|null;subrogation_fee_percent:string|null;cancellation_fee_percent:string|null;notes:string|null;
};
type HomeData={
  property:null|{id:string;name:string;value:string;currency:string;valuation_date:string;valuation_source:string;ownership_percentage:string};
  mortgage:Mortgage|null;extra:MortgageExtra;document_facts:Record<string,{value:string;document_id?:string;page?:number}>;
  source_documents:{id:string;name:string}[];insurance:{id:string;insurance_type:string;annual_premium:string;provider:string|null;renewal_date:string|null}[];
  equity:string|null;ltv:string|null;missing:{key:string;label:string;reason:string}[];
};
type MarketLead={
  source_id:string;provider:string;kind:string;status:string;public_tin_min:number|null;benchmark_difference_pp:number|null;
  claims:string[];url:string;retrieved_at:string;requires_personalized_quote:boolean;
  scenario:null|{estimated_payment:string;monthly_payment_difference:string;remaining_interest_difference:string|null;known_exit_penalty:string|null;break_even_months_known_penalty_only:string|null;comparison_scope:string};
};
type MarketScan={
  generated_at:string;current_mortgage_rate_percent:string|null;current_monthly_payment:string|null;
  official_sources:{id:string;provider:string;kind:string;url:string;description:string}[];leads:MarketLead[];disclaimer:string;
};

function sumAssets(rows:Asset[],types:string[]){
  return rows.filter(x=>types.includes(x.type.toLowerCase())).reduce((sum,x)=>sum+Number(x.value||0)*Number(x.ownership_percentage||100)/100,0);
}

function Metric({label,value,detail}:{label:string;value:string|number;detail:string}){
  return <Card><div className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">{label}</div><div className="mt-2 text-2xl font-bold"><Money value={value}/></div><div className="mt-1 text-xs text-[var(--muted)]">{detail}</div></Card>;
}

export default function WealthPage(){
  const qc=useQueryClient();
  const details=useQuery({queryKey:['wealth-details'],queryFn:()=>apiGet<WealthDetails>('/api/v1/wealth/details')});
  const home=useQuery({queryKey:['wealth-home'],queryFn:()=>apiGet<HomeData>('/api/v1/wealth/home')});
  const [asset,setAsset]=useState({name:'',asset_type:'property',current_value:'',valuation_date:new Date().toISOString().slice(0,10)});
  const [debt,setDebt]=useState({name:'',liability_type:'loan',outstanding_amount:''});
  const [mortgageForm,setMortgageForm]=useState({lender:'',remaining_principal:'',interest_type:'fixed',nominal_rate_pct:'',monthly_payment:'',remaining_months:'',early_repayment_fee:''});
  const [extraForm,setExtraForm]=useState({
    original_principal:'',original_term_months:'',start_date:'',maturity_date:'',apr_rate_pct:'',reference_index:'',differential_rate_pct:'',
    rate_review_months:'',next_review_date:'',opening_fee_percent:'',early_repayment_fee_percent:'',subrogation_fee_percent:'',cancellation_fee_percent:'',notes:'',
  });
  const [homeValue,setHomeValue]=useState('');

  useEffect(()=>{
    const h=home.data;
    if(!h)return;
    if(h.property)setHomeValue(h.property.value);
    const m=h.mortgage;
    if(m)setMortgageForm({
      lender:m.lender,remaining_principal:m.remaining_principal,interest_type:m.interest_type,
      nominal_rate_pct:String(Number(m.nominal_rate)*100),monthly_payment:m.monthly_payment,
      remaining_months:String(m.remaining_months),early_repayment_fee:m.early_repayment_fee||'',
    });
    const x=h.extra;
    setExtraForm({
      original_principal:x.original_principal||'',original_term_months:x.original_term_months===null?'':String(x.original_term_months),
      start_date:x.start_date||'',maturity_date:x.maturity_date||'',apr_rate_pct:x.apr_rate===null?'':String(Number(x.apr_rate)*100),
      reference_index:x.reference_index||'',differential_rate_pct:x.differential_rate===null?'':String(Number(x.differential_rate)*100),
      rate_review_months:x.rate_review_months===null?'':String(x.rate_review_months),next_review_date:x.next_review_date||'',
      opening_fee_percent:x.opening_fee_percent||'',early_repayment_fee_percent:x.early_repayment_fee_percent||'',
      subrogation_fee_percent:x.subrogation_fee_percent||'',cancellation_fee_percent:x.cancellation_fee_percent||'',notes:x.notes||'',
    });
  },[home.data]);

  const refresh=()=>{
    qc.invalidateQueries({queryKey:['wealth-details']});qc.invalidateQueries({queryKey:['wealth']});qc.invalidateQueries({queryKey:['wealth-home']});
  };
  const addAsset=useMutation({
    mutationFn:()=>apiMutate('/api/v1/assets','POST',{...asset,currency:'EUR',valuation_source:'manual',ownership_percentage:'100'}),
    onSuccess:()=>{setAsset({...asset,name:'',current_value:''});refresh()},
  });
  const addDebt=useMutation({
    mutationFn:()=>apiMutate('/api/v1/liabilities','POST',{...debt,currency:'EUR',ownership_percentage:'100'}),
    onSuccess:()=>{setDebt({...debt,name:'',outstanding_amount:''});refresh()},
  });

  const d=details.data;
  const properties=useMemo(()=>d?sumAssets(d.assets,['property','home','house','real_estate']):0,[d]);
  const vehicles=useMemo(()=>d?sumAssets(d.assets,['vehicle','car','motorcycle']):0,[d]);
  const otherAssets=useMemo(()=>d?Math.max(0,Number(d.summary.manual_assets)-properties-vehicles):0,[d,properties,vehicles]);

  return <>
    <PageHeader title="Patrimonio" description="Foto completa de lo que tienes y lo que debes. Los seguros se muestran como protección y coste, pero no se suman como activo."/>

    {details.isLoading?<Loading/>:details.error?<ErrorState error={details.error}/>:d&&<>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Metric label="Patrimonio neto" value={d.summary.net_worth} detail="Activos menos hipoteca y otras deudas"/>
        <Metric label="Activos brutos" value={d.summary.gross_assets} detail="Liquidez + bienes + inversiones"/>
        <Metric label="Deuda total" value={d.summary.total_debt} detail="Hipoteca + otros pasivos"/>
        <Metric label="Seguros al año" value={d.insurance.annual_premium_total} detail="Coste de protección; no altera el patrimonio"/>
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        <Card>
          <h2 className="font-bold">Composición de tus activos</h2>
          <p className="mt-1 text-sm text-[var(--muted)]">Cada bloque muestra el valor que actualmente usa Financito para calcular tu patrimonio.</p>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {[
              ['Cuentas y liquidez',d.summary.accounts,'Saldos de tus cuentas'],
              ['Vivienda e inmuebles',properties,'Últimas valoraciones guardadas'],
              ['Vehículos',vehicles,'Coche y otros vehículos registrados'],
              ['Inversiones',d.summary.investments,'Posiciones reales; precio de mercado si está disponible'],
              ['Otros activos',otherAssets,'Bienes manuales no incluidos arriba'],
            ].map(([label,value,detail])=><div key={String(label)} className="rounded-xl bg-[var(--surface-2)] p-4"><div className="text-xs text-[var(--muted)]">{label}</div><div className="mt-1 text-lg font-bold"><Money value={value as string|number}/></div><div className="mt-1 text-[11px] text-[var(--muted)]">{detail}</div></div>)}
          </div>
        </Card>

        <Card>
          <h2 className="font-bold">Deudas</h2>
          <p className="mt-1 text-sm text-[var(--muted)]">Capital pendiente que resta valor a tus activos.</p>
          <div className="mt-4 space-y-2">
            {d.mortgages.map(m=><div key={m.id} className="rounded-xl bg-[var(--surface-2)] p-3 text-sm"><div className="flex justify-between gap-3"><div><strong>Hipoteca · {m.lender}</strong><div className="text-xs text-[var(--muted)]">Cuota <Money value={m.monthly_payment} currency={m.currency}/> · {m.remaining_months} meses · TIN {(Number(m.nominal_rate)*100).toLocaleString('es-ES',{maximumFractionDigits:3})}%</div></div><strong><Money value={m.remaining_principal} currency={m.currency}/></strong></div></div>)}
            {d.liabilities.map(x=><div key={x.id} className="rounded-xl bg-[var(--surface-2)] p-3 text-sm"><div className="flex justify-between gap-3"><div><strong>{x.name}</strong><div className="text-xs text-[var(--muted)]">{x.type}</div></div><strong><Money value={x.amount} currency={x.currency}/></strong></div></div>)}
            {!d.mortgages.length&&!d.liabilities.length&&<EmptyState>No hay deudas registradas.</EmptyState>}
          </div>
        </Card>
      </div>

      <Card className="mt-4">
        <div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="font-bold">Vivienda, coche y otros bienes</h2><p className="mt-1 text-sm text-[var(--muted)]">El valor de mercado que ves es la última valoración guardada. Actualízala cuando tengas una estimación más reciente.</p></div><Link className="text-xs underline" href="/history/">Ver histórico</Link></div>
        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {d.assets.length?d.assets.map(x=><div key={x.id} className="rounded-xl border border-[var(--border)] p-4 text-sm"><div className="flex justify-between gap-3"><div><strong>{x.name}</strong><div className="text-xs text-[var(--muted)]">{x.type} · valoración {new Date(x.valuation_date).toLocaleDateString('es-ES')}</div></div><strong><Money value={x.value} currency={x.currency}/></strong></div><div className="mt-2 text-[11px] text-[var(--muted)]">Fuente: {x.valuation_source} · propiedad {Number(x.ownership_percentage).toLocaleString('es-ES')}%</div></div>):<EmptyState>Aún no has añadido vivienda, coche u otros bienes.</EmptyState>}
        </div>
        <form className="mt-5 grid gap-2 md:grid-cols-4" onSubmit={(e:FormEvent)=>{e.preventDefault();addAsset.mutate()}}>
          <select className="fin-input" aria-label="Tipo de activo" value={asset.asset_type} onChange={e=>setAsset({...asset,asset_type:e.target.value})}><option value="property">Vivienda / inmueble</option><option value="vehicle">Vehículo</option><option value="other">Otro activo</option></select>
          <input className="fin-input" placeholder="Nombre, ej. Vivienda habitual" value={asset.name} onChange={e=>setAsset({...asset,name:e.target.value})} required/>
          <input className="fin-input" placeholder="Valor de mercado" type="number" min="0" step=".01" value={asset.current_value} onChange={e=>setAsset({...asset,current_value:e.target.value})} required/>
          <input className="fin-input" aria-label="Fecha de valoración" type="date" value={asset.valuation_date} onChange={e=>setAsset({...asset,valuation_date:e.target.value})} required/>
          <button className="fin-button md:col-span-4" disabled={addAsset.isPending}>{addAsset.isPending?'Guardando…':'Añadir activo al patrimonio'}</button>
        </form>
        {addAsset.error&&<div className="mt-3"><ErrorState error={addAsset.error}/></div>}
      </Card>

      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        <Card>
          <div className="flex items-start justify-between gap-3"><div><h2 className="font-bold">Cuentas</h2><p className="mt-1 text-sm text-[var(--muted)]">Liquidez que entra directamente en el patrimonio.</p></div><Link href="/accounts/" className="text-xs underline">Gestionar</Link></div>
          <div className="mt-3 space-y-2">{d.accounts.length?d.accounts.map(x=><div key={x.id} className="flex justify-between rounded-xl bg-[var(--surface-2)] p-3 text-sm"><div><strong>{x.name}</strong><div className="text-xs text-[var(--muted)]">{x.institution_name}</div></div><strong><Money value={x.balance} currency={x.currency}/></strong></div>):<EmptyState>No hay cuentas registradas.</EmptyState>}</div>
        </Card>

        <Card>
          <div className="flex items-start justify-between gap-3"><div><h2 className="font-bold">Inversiones reales</h2><p className="mt-1 text-sm text-[var(--muted)]">Solo posiciones reales; los seguimientos y simulaciones no inflan tu patrimonio.</p></div><Link href="/markets/" className="text-xs underline">Mercado</Link></div>
          <div className="mt-3 space-y-2">{d.investments.length?d.investments.map(x=><div key={x.security_id} className="flex justify-between rounded-xl bg-[var(--surface-2)] p-3 text-sm"><div><strong>{x.name}</strong><div className="text-xs text-[var(--muted)]">{x.identifier||x.asset_class}{x.price_provider?' · '+x.price_provider:''}</div></div><strong><Money value={x.current_value??x.cost_basis} currency={x.currency}/></strong></div>):<EmptyState>No hay posiciones reales.</EmptyState>}</div>
        </Card>

        <Card>
          <div className="flex items-start justify-between gap-3"><div><h2 className="font-bold">Seguros y protección</h2><p className="mt-1 text-sm text-[var(--muted)]">Se muestran para tener la foto financiera completa, pero una póliza no es un activo patrimonial.</p></div><Link href="/insurance/" className="text-xs underline">Revisar coberturas</Link></div>
          <div className="mt-3 space-y-2">{d.insurance.policies.length?d.insurance.policies.map(x=><div key={x.id} className="rounded-xl bg-[var(--surface-2)] p-3 text-sm"><div className="flex justify-between gap-3"><div><strong>{x.insurance_type}</strong><div className="text-xs text-[var(--muted)]">{x.provider||'Proveedor no identificado'}{x.deductible?' · franquicia '+Number(x.deductible).toLocaleString('es-ES')+' €':''}</div></div><div className="text-right"><strong><Money value={x.annual_premium} currency={x.currency}/></strong><div className="text-[11px] text-[var(--muted)]">al año</div></div></div></div>):<EmptyState>No hay pólizas registradas.</EmptyState>}</div>
        </Card>

        <Card>
          <h2 className="font-bold">Otras deudas</h2>
          <p className="mt-1 text-sm text-[var(--muted)]">Préstamos, financiación y otros pasivos que no sean la hipoteca principal.</p>
          <form className="mt-3 grid gap-2 sm:grid-cols-2" onSubmit={(e:FormEvent)=>{e.preventDefault();addDebt.mutate()}}>
            <select className="fin-input" aria-label="Tipo de deuda" value={debt.liability_type} onChange={e=>setDebt({...debt,liability_type:e.target.value})}><option value="loan">Préstamo</option><option value="credit">Crédito / financiación</option><option value="other">Otra deuda</option></select>
            <input className="fin-input" placeholder="Nombre" value={debt.name} onChange={e=>setDebt({...debt,name:e.target.value})} required/>
            <input className="fin-input sm:col-span-2" placeholder="Capital pendiente" type="number" min="0" step=".01" value={debt.outstanding_amount} onChange={e=>setDebt({...debt,outstanding_amount:e.target.value})} required/>
            <button className="fin-button sm:col-span-2" disabled={addDebt.isPending}>{addDebt.isPending?'Guardando…':'Añadir deuda'}</button>
          </form>
          {addDebt.error&&<div className="mt-3"><ErrorState error={addDebt.error}/></div>}
        </Card>
      </div>
    </>}
  </>;
}
