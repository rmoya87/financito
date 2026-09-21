'use client';

import Link from 'next/link';
import {FormEvent,useEffect,useMemo,useState} from 'react';
import {useMutation,useQuery,useQueryClient} from '@tanstack/react-query';
import {apiGet,apiMutate} from '@/lib/api';
import {PageHeader} from '@/components/page-header';
import {Card} from '@/components/ui/card';
import {Money,formatNumber} from '@/components/ui/money';
import {EmptyState,ErrorState,Loading} from '@/components/ui/states';
import {EntityDocumentsModal} from '@/components/entity-documents-modal';

type WealthSummary={
  accounts:string;manual_assets:string;investments:string;liabilities:string;mortgages:string;
  gross_assets:string;total_debt:string;net_worth:string
};
type Account={id:string;name:string;institution_name:string;currency:string;balance:string};
type Asset={id:string;type:string;name:string;value:string;currency:string;valuation_date:string;valuation_source:string;ownership_type:string;ownership_percentage:string;previous_value?:string|null;previous_valuation_date?:string|null;change_amount?:string|null;change_pct?:string|null};
type Liability={id:string;type:string;name:string;amount:string;currency:string;annual_rate:string|null;ownership_percentage:string};
type Mortgage={id:string;lender:string;remaining_principal:string;currency:string;interest_type:string;nominal_rate:string;monthly_payment:string;remaining_months:number;early_repayment_fee?:string|null;source_document_id?:string|null;source_document_ids?:string[];document_count?:number};
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
  source_documents:{id:string;name:string}[];insurance:{id:string;insurance_type:string;annual_premium:string;provider:string|null;renewal_date:string|null;linked_to_mortgage?:boolean}[];
  equity:string|null;ltv:string|null;
  principal_progress:null|{original_principal:string;remaining_principal:string;paid_principal:string;remaining_percent:string;paid_percent:string;status:string};
  current_apr_estimate:null|{rate:string|null;status:string;monthly_payment:string;known_linked_annual_cost:string;known_linked_monthly_cost:string;basis:string};
  rate_review_automation:{status:string;automatic:boolean;missing:string[];reference_index?:string|null;differential_rate?:string|null;rate_review_months?:number|null;next_review_date?:string|null;reference_index_lag_months?:number|null;rule?:string;message?:string|null;estimate?:null|{review_date:string;reference_month:string;reference_index_value_percent:string;reference_source:string;reference_series:string;reference_period:string;estimated_nominal_rate:string;estimated_monthly_payment:string;estimated_remaining_interest:string;estimated_current_apr:string|null;known_linked_annual_cost:string;confirmation_required:boolean;notice:string}};
  pending_review:{key:string;label:string;reason:string;value:any;unit:string|null;document_id:string|null;page:number|null;source:string|null;status:string}[];
  missing:{key:string;label:string;reason:string}[];
};
type MarketLead={
  source_id:string;provider:string;kind:string;status:string;public_tin_min:number|null;public_tae_min?:number|null;benchmark_difference_pp:number|null;
  claims:string[];url:string;retrieved_at:string;requires_personalized_quote:boolean;rate_better:boolean;
  scenario:null|{estimated_payment:string;theoretical_monthly_saving:string;actual_monthly_saving:string;remaining_interest_difference:string;known_exit_penalty:string|null;estimated_net_interest_saving_known_costs:string|null;break_even_months:string|null;compensates:boolean;comparison_complete:boolean;rejection_reason:string|null;comparison_scope:string};
};
type MarketConclusion={status:string;headline:string;action:string;provider:string|null;source_id:string|null;missing:string[];estimated_monthly_saving?:string;estimated_net_interest_saving_known_costs?:string;break_even_months?:string;known_exit_penalty?:string;assumptions:string[]};
type MarketScan={
  generated_at:string;current_mortgage_rate_percent:string|null;current_monthly_payment:string|null;
  current_conditions:{remaining_months:number|null;known_exit_penalty:string|null;exit_penalty_status:string|null;linked_insurance_annual_cost:string;linked_policies:{policy_id:string;insurance_type:string;annual_premium:string;provider:string|null;exit_penalty:string|null;conditions:string}[];linked_product_rate_impacts:any[];linked_product_signals:string[]};
  official_sources:{id:string;provider:string;kind:string;url:string;description:string}[];leads:MarketLead[];better_offers:MarketLead[];lower_rate_but_not_better:MarketLead[];conclusion:MarketConclusion;disclaimer:string;
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
  const mortgages=useQuery({queryKey:['mortgages'],queryFn:()=>apiGet<Mortgage[]>('/api/v1/mortgages')});
  const [selectedMortgageId,setSelectedMortgageId]=useState('');
  const [creatingMortgage,setCreatingMortgage]=useState(false);
  const home=useQuery({
    queryKey:['wealth-home',selectedMortgageId],
    queryFn:()=>apiGet<HomeData>('/api/v1/wealth/home'+(selectedMortgageId?'?mortgage_id='+encodeURIComponent(selectedMortgageId):'')),
  });
  const [asset,setAsset]=useState({name:'',asset_type:'property',current_value:'',valuation_date:new Date().toISOString().slice(0,10)});
  const [editingAsset,setEditingAsset]=useState<Asset|null>(null);
  const [debt,setDebt]=useState({name:'',liability_type:'loan',outstanding_amount:''});
  const [mortgageForm,setMortgageForm]=useState({lender:'',remaining_principal:'',interest_type:'fixed',nominal_rate_pct:'',monthly_payment:'',remaining_months:'',early_repayment_fee:''});
  const [extraForm,setExtraForm]=useState({
    original_principal:'',original_term_months:'',start_date:'',maturity_date:'',apr_rate_pct:'',reference_index:'',differential_rate_pct:'',
    rate_review_months:'',next_review_date:'',opening_fee_percent:'',early_repayment_fee_percent:'',subrogation_fee_percent:'',cancellation_fee_percent:'',notes:'',
  });
  const [homeValue,setHomeValue]=useState('');
  const [showMortgageDocuments,setShowMortgageDocuments]=useState(false);
  const [showMortgageEdit,setShowMortgageEdit]=useState(false);

  useEffect(()=>{
    if(!creatingMortgage&&!selectedMortgageId&&mortgages.data?.length)setSelectedMortgageId(mortgages.data[0].id);
  },[mortgages.data,selectedMortgageId,creatingMortgage]);

  useEffect(()=>{
    const h=home.data;
    if(!h||creatingMortgage)return;
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

  const clearMortgageForms=()=>{
    setMortgageForm({lender:'',remaining_principal:'',interest_type:'fixed',nominal_rate_pct:'',monthly_payment:'',remaining_months:'',early_repayment_fee:''});
    setExtraForm({
      original_principal:'',original_term_months:'',start_date:'',maturity_date:'',apr_rate_pct:'',reference_index:'',differential_rate_pct:'',
      rate_review_months:'',next_review_date:'',opening_fee_percent:'',early_repayment_fee_percent:'',subrogation_fee_percent:'',cancellation_fee_percent:'',notes:'',
    });
  };

  const refresh=()=>{
    qc.invalidateQueries({queryKey:['wealth-details']});qc.invalidateQueries({queryKey:['wealth']});qc.invalidateQueries({queryKey:['wealth-home']});qc.invalidateQueries({queryKey:['mortgages']});
  };
  const addAsset=useMutation({
    mutationFn:()=>apiMutate('/api/v1/assets','POST',{...asset,currency:'EUR',valuation_source:'manual',ownership_percentage:'100'}),
    onSuccess:()=>{setAsset({...asset,name:'',current_value:''});refresh()},
  });
  const updateAsset=useMutation({
    mutationFn:()=>{
      if(!editingAsset)throw new Error('Selecciona un activo');
      return apiMutate('/api/v1/assets/'+editingAsset.id,'PATCH',{
        asset_type:editingAsset.type,name:editingAsset.name,current_value:editingAsset.value,currency:editingAsset.currency,
        valuation_date:editingAsset.valuation_date,valuation_source:editingAsset.valuation_source||'manual',
        ownership_type:editingAsset.ownership_type||'personal',ownership_percentage:editingAsset.ownership_percentage,
      });
    },
    onSuccess:()=>{setEditingAsset(null);refresh()},
  });
  const removeAsset=useMutation({
    mutationFn:(id:string)=>apiMutate('/api/v1/assets/'+id,'DELETE'),
    onSuccess:(_,id)=>{if(editingAsset?.id===id)setEditingAsset(null);refresh()},
  });
  const addDebt=useMutation({
    mutationFn:()=>apiMutate('/api/v1/liabilities','POST',{...debt,currency:'EUR',ownership_percentage:'100'}),
    onSuccess:()=>{setDebt({...debt,name:'',outstanding_amount:''});refresh()},
  });
  const removeDebt=useMutation({
    mutationFn:(id:string)=>apiMutate('/api/v1/liabilities/'+id,'DELETE'),
    onSuccess:refresh,
  });

  const saveMortgage=useMutation({
    mutationFn:()=>{
      const payload={
        lender:mortgageForm.lender.trim(),
        remaining_principal:mortgageForm.remaining_principal,
        currency:'EUR',
        interest_type:mortgageForm.interest_type,
        nominal_rate:String(Number(mortgageForm.nominal_rate_pct||0)/100),
        monthly_payment:mortgageForm.monthly_payment,
        remaining_months:Number(mortgageForm.remaining_months),
        early_repayment_fee:mortgageForm.early_repayment_fee||null,
      };
      return creatingMortgage||!selectedMortgageId
        ?apiMutate<Mortgage>('/api/v1/mortgages','POST',payload)
        :apiMutate<Mortgage>('/api/v1/mortgages/'+selectedMortgageId,'PATCH',payload);
    },
    onSuccess:(saved)=>{setCreatingMortgage(false);setSelectedMortgageId(saved.id);refresh()},
  });
  const saveExtra=useMutation({
    mutationFn:()=>{
      const mortgageId=selectedMortgageId;
      if(!mortgageId||creatingMortgage)throw new Error('Guarda primero los datos principales de la hipoteca');
      const nullable=(v:string)=>v.trim()===''?null:v.trim();
      return apiMutate('/api/v1/mortgages/'+mortgageId+'/profile-extra','PATCH',{
        original_principal:nullable(extraForm.original_principal),
        original_term_months:extraForm.original_term_months?Number(extraForm.original_term_months):null,
        start_date:nullable(extraForm.start_date),maturity_date:nullable(extraForm.maturity_date),
        apr_rate:extraForm.apr_rate_pct?String(Number(extraForm.apr_rate_pct)/100):null,
        reference_index:nullable(extraForm.reference_index),
        differential_rate:extraForm.differential_rate_pct?String(Number(extraForm.differential_rate_pct)/100):null,
        rate_review_months:extraForm.rate_review_months?Number(extraForm.rate_review_months):null,
        next_review_date:nullable(extraForm.next_review_date),
        opening_fee_percent:nullable(extraForm.opening_fee_percent),
        early_repayment_fee_percent:nullable(extraForm.early_repayment_fee_percent),
        subrogation_fee_percent:nullable(extraForm.subrogation_fee_percent),
        cancellation_fee_percent:nullable(extraForm.cancellation_fee_percent),
        notes:nullable(extraForm.notes),
      });
    },
    onSuccess:refresh,
  });
  const saveHomeValue=useMutation({
    mutationFn:()=>{
      const h=home.data;
      const payload={
        asset_type:'property',name:h?.property?.name||'Vivienda habitual',current_value:homeValue,
        currency:'EUR',valuation_date:new Date().toISOString().slice(0,10),valuation_source:'manual',
        ownership_type:'personal',ownership_percentage:h?.property?.ownership_percentage||'100',
      };
      return h?.property
        ?apiMutate('/api/v1/assets/'+h.property.id,'PATCH',payload)
        :apiMutate('/api/v1/assets','POST',payload);
    },
    onSuccess:refresh,
  });
  const marketScan=useMutation({
    mutationFn:()=>apiGet<MarketScan>('/api/v1/decision-lab/market-scan'+(selectedMortgageId?'?mortgage_id='+encodeURIComponent(selectedMortgageId):'')),
  });
  const analyzeMortgageDocs=useMutation({
    mutationFn:()=>{
      if(!selectedMortgageId)throw new Error('Selecciona una hipoteca');
      return apiMutate('/api/v1/evidence-groups/mortgage/'+selectedMortgageId+'/analyze','POST');
    },
    onSuccess:()=>{qc.invalidateQueries({queryKey:['wealth-home',selectedMortgageId]});qc.invalidateQueries({queryKey:['document-insights']})},
  });
  const deleteMortgage=useMutation({
    mutationFn:(id:string)=>apiMutate('/api/v1/mortgages/'+id,'DELETE'),
    onSuccess:()=>{setSelectedMortgageId('');setCreatingMortgage(false);clearMortgageForms();refresh()},
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

      <Card className="mt-4" id="casa">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">Casa</div>
            <h2 className="mt-1 text-xl font-bold">Vivienda e hipoteca</h2>
            <p className="mt-1 max-w-3xl text-sm text-[var(--muted)]">Centraliza valor de la vivienda, deuda, condiciones, seguros vinculados y evidencia documental. Estos datos alimentan las simulaciones de amortización, novación y subrogación.</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <select className="fin-input min-w-64 py-2 text-xs" aria-label="Hipoteca seleccionada" value={creatingMortgage?'':selectedMortgageId} onChange={e=>{setCreatingMortgage(false);setSelectedMortgageId(e.target.value)}}>
              <option value="">{mortgages.data?.length?'Selecciona una hipoteca…':'Sin hipotecas'}</option>
              {mortgages.data?.map(m=><option key={m.id} value={m.id}>{m.lender} · {Number(m.remaining_principal).toLocaleString('es-ES')} {m.currency}</option>)}
            </select>
            <button className="fin-button py-2 text-xs" type="button" onClick={()=>{setCreatingMortgage(true);setSelectedMortgageId('');clearMortgageForms();setShowMortgageEdit(true)}}>Nueva hipoteca</button>
            {selectedMortgageId&&<button className="fin-button secondary py-2 text-xs" type="button" onClick={()=>setShowMortgageEdit(true)}>Datos de la hipoteca</button>}
            {selectedMortgageId&&<button className="fin-button secondary py-2 text-xs" type="button" onClick={()=>setShowMortgageDocuments(true)}>Documentación</button>}
            <Link className="fin-button secondary py-2 text-xs" href="/tools/">Simulaciones</Link>
          </div>
        </div>

        {home.isLoading?<div className="mt-4"><Loading/></div>:home.error?<div className="mt-4"><ErrorState error={home.error}/></div>:home.data&&<>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <div className="rounded-xl bg-[var(--surface-2)] p-4"><div className="text-xs text-[var(--muted)]">Valor vivienda</div><div className="mt-1 text-xl font-bold">{home.data.property?<Money value={home.data.property.value}/>:<span>—</span>}</div><div className="mt-1 text-[11px] text-[var(--muted)]">{home.data.property?new Date(home.data.property.valuation_date).toLocaleDateString('es-ES'):'Sin valoración'}</div></div>
            <div className="rounded-xl bg-[var(--surface-2)] p-4">
              <div className="text-xs text-[var(--muted)]">Capital pendiente</div>
              <div className="mt-1 text-xl font-bold">{home.data.mortgage?<Money value={home.data.mortgage.remaining_principal}/>:<span>—</span>}</div>
              <div className="mt-1 text-[11px] text-[var(--muted)]">{home.data.mortgage?.lender||'Sin hipoteca'}</div>
              {home.data.principal_progress?<div className="mt-2">
                <div className="flex items-center justify-between text-[11px]"><strong>{Number(home.data.principal_progress.remaining_percent).toLocaleString('es-ES',{maximumFractionDigits:1})}% pendiente</strong><span className="text-[var(--muted)]">{Number(home.data.principal_progress.paid_percent).toLocaleString('es-ES',{maximumFractionDigits:1})}% pagado</span></div>
                <div className="mt-1 flex h-2 overflow-hidden rounded-full bg-[var(--border)]" aria-label="Progreso del capital hipotecario">
                  <div className="h-full bg-emerald-500" style={{width:home.data.principal_progress.remaining_percent+'%'}} title={home.data.principal_progress.remaining_percent+'% pendiente'}/>
                  <div className="h-full bg-[var(--border)]" style={{width:home.data.principal_progress.paid_percent+'%'}} title={home.data.principal_progress.paid_percent+'% pagado'}/>
                </div>
                <div className="mt-1 text-[11px] text-[var(--muted)]">Verde: pendiente · gris: ya amortizado · inicial <Money value={home.data.principal_progress.original_principal}/></div>
              </div>:<div className="mt-1 text-[11px] text-[var(--muted)]">{home.data.mortgage?'Añade el capital inicial en Datos de la hipoteca para ver el porcentaje amortizado.':'Sin hipoteca'}</div>}
            </div>
            <div className="rounded-xl bg-[var(--surface-2)] p-4"><div className="text-xs text-[var(--muted)]">Cuota mensual</div><div className="mt-1 text-xl font-bold">{home.data.mortgage?<Money value={home.data.mortgage.monthly_payment}/>:<span>—</span>}</div><div className="mt-1 text-[11px] text-[var(--muted)]">{home.data.mortgage?home.data.mortgage.remaining_months+' meses pendientes':'—'}</div></div>
            <div className="rounded-xl bg-[var(--surface-2)] p-4"><div className="text-xs text-[var(--muted)]">Tipo / TIN</div><div className="mt-1 text-xl font-bold">{home.data.mortgage?(home.data.mortgage.interest_type==='fixed'?'Fija':home.data.mortgage.interest_type==='variable'?'Variable':'Mixta'):'—'}</div><div className="mt-1 text-[11px] text-[var(--muted)]">{home.data.mortgage?(Number(home.data.mortgage.nominal_rate)*100).toLocaleString('es-ES',{maximumFractionDigits:3})+'% TIN':'—'}</div></div>
            <div className="rounded-xl bg-[var(--surface-2)] p-4"><div className="text-xs text-[var(--muted)]">TAE contractual</div><div className="mt-1 text-xl font-bold">{home.data.extra.apr_rate===null?'—':(Number(home.data.extra.apr_rate)*100).toLocaleString('es-ES',{maximumFractionDigits:3})+'%'}</div><div className="mt-1 text-[11px] text-[var(--muted)]">Dato original/contractual; no se sobrescribe en revisiones.</div></div>
            <div className="rounded-xl bg-[var(--surface-2)] p-4"><div className="text-xs text-[var(--muted)]">TAE estimada actual</div><div className="mt-1 text-xl font-bold">{home.data.current_apr_estimate?.rate?(Number(home.data.current_apr_estimate.rate)*100).toLocaleString('es-ES',{maximumFractionDigits:3})+'%':'—'}</div><div className="mt-1 text-[11px] text-[var(--muted)]">{home.data.current_apr_estimate?.rate?'TIN vigente + costes futuros vinculados conocidos':'Sin datos suficientes'}</div></div>
            <div className="rounded-xl bg-[var(--surface-2)] p-4"><div className="text-xs text-[var(--muted)]">Vencimiento</div><div className="mt-1 text-xl font-bold">{home.data.extra.maturity_date?new Date(home.data.extra.maturity_date).toLocaleDateString('es-ES'):'—'}</div><div className="mt-1 text-[11px] text-[var(--muted)]">{home.data.extra.next_review_date?'Próxima revisión '+new Date(home.data.extra.next_review_date).toLocaleDateString('es-ES'):'Sin próxima revisión informada'}</div></div>
            <div className="rounded-xl bg-[var(--surface-2)] p-4"><div className="text-xs text-[var(--muted)]">Equity estimado</div><div className="mt-1 text-xl font-bold">{home.data.equity!==null?<Money value={home.data.equity}/>:<span>—</span>}</div><div className="mt-1 text-[11px] text-[var(--muted)]">Vivienda menos capital pendiente</div></div>
            <div className="rounded-xl bg-[var(--surface-2)] p-4"><div className="text-xs text-[var(--muted)]">LTV actual</div><div className="mt-1 text-xl font-bold">{home.data.ltv===null?'—':Number(home.data.ltv).toLocaleString('es-ES',{maximumFractionDigits:1})+'%'}</div><div className="mt-1 text-[11px] text-[var(--muted)]">Capital pendiente / valor atribuible</div></div>
          </div>

          {home.data.mortgage?.interest_type!=='fixed'&&<div className="mt-4 rounded-xl bg-[var(--surface-2)] p-4 text-sm">
            <div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="font-semibold">Revisión automática del tipo</h3><p className="mt-1 text-xs text-[var(--muted)]">{home.data.rate_review_automation.automatic?'La regla contractual necesaria está completa para automatizar el cálculo de la próxima revisión.':'Todavía no se debe actualizar el tipo automáticamente porque falta evidencia contractual.'}</p></div><span className="rounded-full bg-[var(--brand-soft)] px-2 py-1 text-[10px] font-semibold text-[var(--brand)]">{home.data.rate_review_automation.automatic?'Preparada':'Pendiente'}</span></div>
            {!home.data.rate_review_automation.automatic&&home.data.rate_review_automation.missing.length>0&&<div className="mt-2 text-xs"><strong>Falta:</strong> {home.data.rate_review_automation.missing.map(key=>key==='reference_index_lag_months'?'mes/publicación del índice que usa el contrato':key.replaceAll('_',' ')).join(' · ')}</div>}
            {home.data.rate_review_automation.rule&&<div className="mt-2 text-[11px] text-[var(--muted)]">{home.data.rate_review_automation.rule}</div>}
            {home.data.rate_review_automation.estimate&&<div className="mt-3 rounded-xl bg-[var(--brand-soft)] p-3">
              <div className="font-semibold">Cálculo automático de la revisión</div>
              <div className="mt-2 grid gap-2 text-xs sm:grid-cols-2 lg:grid-cols-4">
                <div><span className="text-[var(--muted)]">Índice oficial usado</span><div className="font-semibold">{Number(home.data.rate_review_automation.estimate.reference_index_value_percent).toLocaleString('es-ES',{maximumFractionDigits:4})}% · {home.data.rate_review_automation.estimate.reference_period}</div></div>
                <div><span className="text-[var(--muted)]">TIN estimado</span><div className="font-semibold">{(Number(home.data.rate_review_automation.estimate.estimated_nominal_rate)*100).toLocaleString('es-ES',{maximumFractionDigits:4})}%</div></div>
                <div><span className="text-[var(--muted)]">Nueva cuota estimada</span><div className="font-semibold"><Money value={home.data.rate_review_automation.estimate.estimated_monthly_payment}/></div></div>
                <div><span className="text-[var(--muted)]">TAE estimada tras revisión</span><div className="font-semibold">{home.data.rate_review_automation.estimate.estimated_current_apr?(Number(home.data.rate_review_automation.estimate.estimated_current_apr)*100).toLocaleString('es-ES',{maximumFractionDigits:3})+'%':'—'}</div></div>
              </div>
              <div className="mt-2 text-[11px] text-[var(--muted)]">{home.data.rate_review_automation.estimate.notice} Fuente: {home.data.rate_review_automation.estimate.reference_source} · {home.data.rate_review_automation.estimate.reference_series}.</div>
            </div>}
            {home.data.rate_review_automation.message&&<div className="mt-2 text-xs text-[var(--muted)]">{home.data.rate_review_automation.message}</div>}
            {home.data.current_apr_estimate?.basis&&<div className="mt-2 text-[11px] text-[var(--muted)]">{home.data.current_apr_estimate.basis}</div>}
          </div>}

          {home.data.pending_review?.length>0&&<div className="mt-4 rounded-xl border border-[var(--brand)] bg-[var(--brand-soft)] p-4">
            <h3 className="font-semibold">Datos ya encontrados pendientes de validar</h3>
            <p className="mt-1 text-xs text-[var(--muted)]">No están ausentes: el extractor o la IA local los ha localizado. Confírmalos en el documento para que se proyecten automáticamente a la hipoteca y entren en cálculos.</p>
            <div className="mt-2 grid gap-2 md:grid-cols-2">{home.data.pending_review.map(x=><div key={x.key} className="rounded-lg bg-white p-3 text-xs"><strong>{x.label}</strong><div className="mt-1">{String(x.value??'Dato localizado')}{x.unit?' '+x.unit:''}</div><div className="mt-1 text-[var(--muted)]">{x.reason}</div>{x.document_id&&selectedMortgageId&&<Link className="mt-2 inline-block underline" href={'/documents/?entity_type=mortgage&entity_id='+encodeURIComponent(selectedMortgageId)+'&label='+encodeURIComponent('Hipoteca · '+(home.data?.mortgage?.lender||'seleccionada'))+'&document='+encodeURIComponent(x.document_id)}>Revisar documentación{x.page?' · pág. '+x.page:''}</Link>}</div>)}</div>
          </div>}

          {home.data.missing.length>0&&selectedMortgageId&&!creatingMortgage&&<div className="mt-4 rounded-xl bg-[var(--surface-2)] p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div><h3 className="font-semibold">Información que falta</h3><p className="mt-1 text-xs text-[var(--muted)]">Primero intenta localizarla en los documentos de esta hipoteca. Si la IA local no puede encontrarla, completa el campo aquí y quedará guardado en el perfil de la hipoteca.</p></div>
              <button className="fin-button secondary py-1.5 text-xs" type="button" onClick={()=>analyzeMortgageDocs.mutate()} disabled={analyzeMortgageDocs.isPending}>{analyzeMortgageDocs.isPending?'Buscando…':'Intentar completar con IA'}</button>
            </div>
            <div className="mt-3 grid gap-3 md:grid-cols-2">{home.data.missing.map(x=><div key={x.key} className="rounded-lg bg-white p-3 text-xs">
              <strong>{x.label}</strong><div className="mt-1 text-[var(--muted)]">{x.reason}</div>
              <div className="mt-2">
                {x.key==='property_value'?<input className="fin-input" type="number" step=".01" placeholder="Valor de la vivienda (€)" value={homeValue} onChange={e=>setHomeValue(e.target.value)}/>:
                x.key==='apr_rate'?<input className="fin-input" type="number" step=".001" placeholder="TAE (%)" value={extraForm.apr_rate_pct} onChange={e=>setExtraForm({...extraForm,apr_rate_pct:e.target.value})}/>:
                x.key==='reference_index'?<input className="fin-input" placeholder="Ej. Euríbor 12 meses" value={extraForm.reference_index} onChange={e=>setExtraForm({...extraForm,reference_index:e.target.value})}/>:
                x.key==='differential_rate'?<input className="fin-input" type="number" step=".001" placeholder="Diferencial (%)" value={extraForm.differential_rate_pct} onChange={e=>setExtraForm({...extraForm,differential_rate_pct:e.target.value})}/>:
                x.key==='rate_review_months'?<input className="fin-input" type="number" step="1" placeholder="Meses entre revisiones" value={extraForm.rate_review_months} onChange={e=>setExtraForm({...extraForm,rate_review_months:e.target.value})}/>:
                x.key==='next_review_date'?<input className="fin-input" type="date" value={extraForm.next_review_date} onChange={e=>setExtraForm({...extraForm,next_review_date:e.target.value})}/>:
                x.key==='early_repayment_fee_percent'?<input className="fin-input" type="number" step=".001" placeholder="Comisión amortización (%)" value={extraForm.early_repayment_fee_percent} onChange={e=>setExtraForm({...extraForm,early_repayment_fee_percent:e.target.value})}/>:
                x.key==='subrogation_fee_percent'?<input className="fin-input" type="number" step=".001" placeholder="Comisión subrogación/salida (%)" value={extraForm.subrogation_fee_percent} onChange={e=>setExtraForm({...extraForm,subrogation_fee_percent:e.target.value})}/>:null}
              </div>
            </div>)}</div>
            <div className="mt-3 flex gap-2">
              {home.data.missing.some(x=>x.key==='property_value')&&<button className="fin-button secondary" type="button" onClick={()=>saveHomeValue.mutate()} disabled={!homeValue||saveHomeValue.isPending}>Guardar valor vivienda</button>}
              {home.data.missing.some(x=>x.key!=='property_value')&&<button className="fin-button" type="button" onClick={()=>saveExtra.mutate()} disabled={saveExtra.isPending}>Guardar datos de hipoteca</button>}
            </div>
            {analyzeMortgageDocs.error&&<div className="mt-3"><ErrorState error={analyzeMortgageDocs.error}/></div>}
          </div>}

          <div className="mt-4 grid gap-4 xl:grid-cols-2">
            <div className="rounded-xl border border-[var(--border)] p-4">
              <div className="flex items-start justify-between gap-3"><div><h3 className="font-semibold">Seguros relacionados con la vivienda</h3><p className="mt-1 text-xs text-[var(--muted)]">Hogar y vida aparecen aquí porque pueden afectar al coste efectivo de la hipoteca o a sus bonificaciones.</p></div><Link className="text-xs underline" href="/insurance/">Seguros</Link></div>
              <div className="mt-3 space-y-2">{home.data.insurance.length?home.data.insurance.map(x=><Link href={'/insurance/?policy='+encodeURIComponent(x.id)} key={x.id} className="flex justify-between gap-3 rounded-lg bg-[var(--surface-2)] p-3 text-sm hover:ring-1 hover:ring-[var(--brand)]"><div><div className="flex flex-wrap items-center gap-2"><strong>{x.insurance_type}</strong>{x.linked_to_mortgage&&<span className="rounded-full bg-[var(--brand-soft)] px-2 py-0.5 text-[10px] font-semibold">Vinculado a esta hipoteca</span>}</div><div className="text-xs text-[var(--muted)]">{x.provider||'Proveedor pendiente'}{x.renewal_date?' · renueva '+new Date(x.renewal_date).toLocaleDateString('es-ES'):''}</div><div className="mt-1 text-[11px] underline">Ver ficha completa</div></div><strong><Money value={x.annual_premium}/>/año</strong></Link>):<EmptyState>No hay seguros de hogar o seguros vinculados a esta hipoteca estructurados todavía.</EmptyState>}</div>
              {home.data.source_documents.length>0&&<div className="mt-3 text-xs text-[var(--muted)]"><strong>Documentación hipotecaria vinculada:</strong> {home.data.source_documents.map(x=>x.name).join(' · ')}</div>}
            </div>

            <div className="rounded-xl border border-[var(--border)] p-4">
              <div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="font-semibold">Comparar con el mercado</h3><p className="mt-1 text-xs text-[var(--muted)]">Busca referencias públicas para detectar si merece la pena pedir una novación o una oferta de subrogación.</p></div><button className="fin-button py-1.5 text-xs" onClick={()=>marketScan.mutate()} disabled={marketScan.isPending||!selectedMortgageId}>{marketScan.isPending?'Consultando…':'Actualizar mercado'}</button></div>
              {!home.data.mortgage&&<div className="mt-3 text-xs text-[var(--muted)]">Completa primero la hipoteca para poder comparar la misma deuda y plazo.</div>}
              {marketScan.error&&<div className="mt-3"><ErrorState error={marketScan.error}/></div>}
              {marketScan.data&&<>
                <div className="mt-3 rounded-xl bg-[var(--brand-soft)] p-3 text-sm"><strong>{marketScan.data.conclusion.headline}</strong><div className="mt-1">{marketScan.data.conclusion.action}</div>{marketScan.data.conclusion.estimated_monthly_saving&&<div className="mt-2 text-xs">Ahorro mensual sobre tu cuota actual: <strong><Money value={marketScan.data.conclusion.estimated_monthly_saving}/></strong>{marketScan.data.conclusion.break_even_months?' · empieza a compensar aprox. en '+marketScan.data.conclusion.break_even_months+' meses':''}</div>}{marketScan.data.conclusion.missing?.length>0&&<div className="mt-2 text-xs text-[var(--muted)]">Pendiente: {marketScan.data.conclusion.missing.join(' · ')}</div>}</div>
                <div className="mt-3 grid gap-2 text-xs sm:grid-cols-3">
                  <div className="rounded-lg bg-[var(--surface-2)] p-3"><span className="text-[var(--muted)]">Tu cuota actual</span><div className="font-semibold"><Money value={marketScan.data.current_monthly_payment}/></div></div>
                  <div className="rounded-lg bg-[var(--surface-2)] p-3"><span className="text-[var(--muted)]">Penalización de salida confirmada</span><div className="font-semibold">{marketScan.data.current_conditions.known_exit_penalty===null?'Pendiente':<Money value={marketScan.data.current_conditions.known_exit_penalty}/>}</div></div>
                  <div className="rounded-lg bg-[var(--surface-2)] p-3"><span className="text-[var(--muted)]">Seguros vinculados actuales</span><div className="font-semibold"><Money value={marketScan.data.current_conditions.linked_insurance_annual_cost}/> / año</div></div>
                </div>
                <div className="mt-3 rounded-lg bg-[var(--surface-2)] p-3 text-xs">{marketScan.data.disclaimer}</div>
                <div className="mt-3 space-y-2">{marketScan.data.better_offers.length?marketScan.data.better_offers.map(x=><div key={x.source_id} className="rounded-lg border border-[var(--border)] p-3 text-sm">
                  <div className="flex flex-wrap items-start justify-between gap-3"><div><strong>{x.provider}</strong><div className="text-xs text-[var(--muted)]">{x.kind==='mortgage_subrogation'?'Subrogación / cambio de banco':'Referencia hipotecaria pública que mejora tu escenario'}</div></div><a className="text-xs underline" href={x.url} target="_blank" rel="noreferrer">Fuente</a></div>
                  <div className="mt-2 grid gap-2 sm:grid-cols-4 text-xs">
                    <div><span className="text-[var(--muted)]">TIN público desde</span><div className="font-semibold">{x.public_tin_min?.toLocaleString('es-ES',{maximumFractionDigits:3})}%</div></div>
                    <div><span className="text-[var(--muted)]">Cuota comparable</span><div className="font-semibold">{x.scenario?<Money value={x.scenario.estimated_payment}/>:<span>—</span>}</div></div>
                    <div><span className="text-[var(--muted)]">Ahorro mensual real</span><div className="font-semibold">{x.scenario?<Money value={x.scenario.actual_monthly_saving}/>:<span>—</span>}</div></div>
                    <div><span className="text-[var(--muted)]">Empieza a compensar</span><div className="font-semibold">{x.scenario?.break_even_months?x.scenario.break_even_months+' meses':'—'}</div></div>
                  </div>
                  {x.scenario&&<div className="mt-2 text-xs">Penalización aplicada: <strong><Money value={x.scenario.known_exit_penalty}/></strong> · ahorro neto de intereses conocido: <strong><Money value={x.scenario.estimated_net_interest_saving_known_costs}/></strong>.</div>}
                </div>):<EmptyState>No hay una oferta pública que se pueda demostrar mejor que tu hipoteca con tus condiciones actuales.</EmptyState>}</div>
                {marketScan.data.lower_rate_but_not_better.length>0&&<div className="mt-3 text-xs text-[var(--muted)]">{marketScan.data.lower_rate_but_not_better.length} referencia(s) tienen un TIN menor pero no se muestran como mejores porque no compensan dentro del plazo o faltan costes de vinculaciones para demostrarlo.</div>}
                <div className="mt-3"><div className="text-xs font-semibold">Referencias oficiales</div><div className="mt-1 space-y-1">{marketScan.data.official_sources.map(x=><div key={x.id} className="text-xs"><a className="underline" href={x.url} target="_blank" rel="noreferrer">{x.provider}</a> · <span className="text-[var(--muted)]">{x.description}</span></div>)}</div></div>
              </>}
            </div>
          </div>

        </>}
      </Card>

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
            {d.liabilities.map(x=><div key={x.id} className="rounded-xl bg-[var(--surface-2)] p-3 text-sm"><div className="flex justify-between gap-3"><div><strong>{x.name}</strong><div className="text-xs text-[var(--muted)]">{x.type}</div></div><div className="text-right"><strong><Money value={x.amount} currency={x.currency}/></strong><div><button className="mt-1 text-xs underline" onClick={()=>{if(window.confirm('¿Eliminar la deuda '+x.name+'?'))removeDebt.mutate(x.id)}} disabled={removeDebt.isPending}>Eliminar deuda</button></div></div></div></div>)}
            {!d.mortgages.length&&!d.liabilities.length&&<EmptyState>No hay deudas registradas.</EmptyState>}
          </div>
        </Card>
      </div>

      <Card className="mt-4">
        <div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="font-bold">Bienes y evolución de valor</h2><p className="mt-1 text-sm text-[var(--muted)]">Vivienda, coche y otros bienes sí forman parte de tu patrimonio. Cada nueva valoración queda guardada para medir revalorización o depreciación frente a la valoración anterior; no se inventan precios de mercado automáticamente.</p></div><Link className="text-xs underline" href="/history/">Ver histórico completo</Link></div>
        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {d.assets.length?d.assets.map(x=><div key={x.id} className="rounded-xl border border-[var(--border)] p-4 text-sm">
            {editingAsset?.id===x.id?<form className="grid gap-2" onSubmit={e=>{e.preventDefault();updateAsset.mutate()}}>
              <select className="fin-input" aria-label="Tipo de activo editado" value={editingAsset.type} onChange={e=>setEditingAsset({...editingAsset,type:e.target.value})}><option value="property">Vivienda / inmueble</option><option value="vehicle">Vehículo</option><option value="other">Otro activo</option></select>
              <input className="fin-input" value={editingAsset.name} onChange={e=>setEditingAsset({...editingAsset,name:e.target.value})} required/>
              <input className="fin-input" type="number" min="0" step=".01" value={editingAsset.value} onChange={e=>setEditingAsset({...editingAsset,value:e.target.value})} required/>
              <input className="fin-input" type="date" value={editingAsset.valuation_date} onChange={e=>setEditingAsset({...editingAsset,valuation_date:e.target.value})} required/>
              <div className="flex gap-2"><button className="fin-button py-1.5 text-xs" disabled={updateAsset.isPending}>Guardar cambios</button><button type="button" className="fin-button secondary py-1.5 text-xs" onClick={()=>setEditingAsset(null)}>Cancelar</button></div>
            </form>:<>
              <div className="flex justify-between gap-3"><div><strong>{x.name}</strong><div className="text-xs text-[var(--muted)]">{x.type} · valoración {new Date(x.valuation_date).toLocaleDateString('es-ES')}</div></div><strong><Money value={x.value} currency={x.currency}/></strong></div>
              <div className="mt-2 text-[11px] text-[var(--muted)]">Fuente: {x.valuation_source} · propiedad {formatNumber(x.ownership_percentage,0,2)}%</div>
              {x.change_amount!=null&&<div className="mt-2 rounded-lg bg-[var(--surface-2)] p-2 text-xs"><strong>{Number(x.change_amount)>=0?'Revalorización':'Depreciación'}: <Money value={x.change_amount} currency={x.currency}/>{x.change_pct!=null?' · '+formatNumber(x.change_pct,1,1)+'%':''}</strong><div className="mt-1 text-[11px] text-[var(--muted)]">Desde la valoración anterior{x.previous_valuation_date?' del '+new Date(x.previous_valuation_date).toLocaleDateString('es-ES'):''}{x.previous_value!=null?' ('+formatNumber(x.previous_value,2,2)+' '+x.currency+')':''}.</div></div>}
              {x.change_amount==null&&<div className="mt-2 text-[11px] text-[var(--muted)]">Aún no hay una segunda valoración para medir su evolución.</div>}
              <div className="mt-3 flex gap-3"><button className="text-xs underline" onClick={()=>setEditingAsset(x)}>Editar</button><button className="text-xs underline" onClick={()=>{if(window.confirm('¿Eliminar '+x.name+' del patrimonio?'))removeAsset.mutate(x.id)}} disabled={removeAsset.isPending}>Eliminar</button></div>
            </>}
          </div>):<EmptyState>Aún no has añadido vivienda, coche u otros bienes.</EmptyState>}
        </div>
        <form className="mt-5 grid gap-2 md:grid-cols-4" onSubmit={(e:FormEvent)=>{e.preventDefault();addAsset.mutate()}}>
          <select className="fin-input" aria-label="Tipo de activo" value={asset.asset_type} onChange={e=>setAsset({...asset,asset_type:e.target.value})}><option value="property">Vivienda / inmueble</option><option value="vehicle">Vehículo</option><option value="other">Otro activo</option></select>
          <input className="fin-input" placeholder="Nombre, ej. Vivienda habitual" value={asset.name} onChange={e=>setAsset({...asset,name:e.target.value})} required/>
          <input className="fin-input" placeholder="Valor de mercado" type="number" min="0" step=".01" value={asset.current_value} onChange={e=>setAsset({...asset,current_value:e.target.value})} required/>
          <input className="fin-input" aria-label="Fecha de valoración" type="date" value={asset.valuation_date} onChange={e=>setAsset({...asset,valuation_date:e.target.value})} required/>
          <button className="fin-button md:col-span-4" disabled={addAsset.isPending}>{addAsset.isPending?'Guardando…':'Añadir activo al patrimonio'}</button>
        </form>
        {(addAsset.error||updateAsset.error||removeAsset.error)&&<div className="mt-3"><ErrorState error={(addAsset.error||updateAsset.error||removeAsset.error)!}/></div>}
      </Card>

      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        <Card>
          <div className="flex items-start justify-between gap-3"><div><h2 className="font-bold">Cuentas</h2><p className="mt-1 text-sm text-[var(--muted)]">Liquidez que entra directamente en el patrimonio.</p></div><Link href="/accounts/" className="text-xs underline">Gestionar</Link></div>
          <div className="mt-3 space-y-2">{d.accounts.length?d.accounts.map(x=><div key={x.id} className="flex justify-between rounded-xl bg-[var(--surface-2)] p-3 text-sm"><div><strong>{x.name}</strong><div className="text-xs text-[var(--muted)]">{x.institution_name}</div></div><strong><Money value={x.balance} currency={x.currency}/></strong></div>):<EmptyState>No hay cuentas registradas.</EmptyState>}</div>
        </Card>

        <Card>
          <div className="flex items-start justify-between gap-3"><div><h2 className="font-bold">Inversiones que posees</h2><p className="mt-1 text-sm text-[var(--muted)]">Aquí solo se suman acciones, ETF, fondos, bonos o cripto que hayas marcado como “Lo tengo realmente”. Los valores que solo sigues y las compras simuladas no forman parte de tu patrimonio.</p></div><Link href="/markets/" className="text-xs underline">Gestionar y seguir mercado</Link></div>
          <div className="mt-3 space-y-2">{d.investments.length?d.investments.map(x=><div key={x.security_id} className="flex justify-between rounded-xl bg-[var(--surface-2)] p-3 text-sm"><div><strong>{x.name}</strong><div className="text-xs text-[var(--muted)]">{x.identifier||x.asset_class}{x.price_provider?' · '+x.price_provider:''}</div></div><strong><Money value={x.current_value??x.cost_basis} currency={x.currency}/></strong></div>):<EmptyState>No hay posiciones reales.</EmptyState>}</div>
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
          <div className="mt-4 space-y-2">{d.liabilities.length?d.liabilities.map(x=><div key={x.id} className="flex items-center justify-between gap-3 rounded-xl bg-[var(--surface-2)] p-3 text-sm"><div><strong>{x.name}</strong><div className="text-xs text-[var(--muted)]">{x.type}</div></div><div className="flex items-center gap-3"><strong><Money value={x.amount} currency={x.currency}/></strong><button className="text-xs underline" type="button" onClick={()=>{if(window.confirm('¿Eliminar la deuda '+x.name+'?'))removeDebt.mutate(x.id)}} disabled={removeDebt.isPending}>Eliminar</button></div></div>):<EmptyState>No hay otras deudas.</EmptyState>}</div>
          {(addDebt.error||removeDebt.error)&&<div className="mt-3"><ErrorState error={(addDebt.error||removeDebt.error)!}/></div>}
        </Card>
      </div>

    {showMortgageEdit&&<div className="fixed inset-0 z-50 overflow-y-auto bg-black/45 p-4 md:p-8" role="dialog" aria-modal="true" aria-label={creatingMortgage?'Nueva hipoteca':'Datos de la hipoteca'}>
      <div className="mx-auto max-w-5xl"><Card>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div><div className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">Casa</div><h2 className="mt-1 text-xl font-bold">{creatingMortgage?'Nueva hipoteca':'Actualizar datos de la hipoteca'}</h2><p className="mt-1 text-sm text-[var(--muted)]">Aquí mantienes los datos que usa Financito para patrimonio y simulaciones. La documentación se gestiona aparte y nunca se sustituye por datos inventados.</p></div>
          <button className="fin-button secondary py-2 text-xs" type="button" onClick={()=>setShowMortgageEdit(false)}>Cerrar</button>
        </div>
        <form className="mt-4 grid gap-2 sm:grid-cols-2" onSubmit={(e:FormEvent)=>{e.preventDefault();saveMortgage.mutate()}}>
          <input className="fin-input sm:col-span-2" placeholder="Entidad" value={mortgageForm.lender} onChange={e=>setMortgageForm({...mortgageForm,lender:e.target.value})} required/>
          <input className="fin-input" type="number" min="0.01" step=".01" placeholder="Capital pendiente (€)" value={mortgageForm.remaining_principal} onChange={e=>setMortgageForm({...mortgageForm,remaining_principal:e.target.value})} required/>
          <input className="fin-input" type="number" min="0.01" step=".01" placeholder="Cuota mensual (€)" value={mortgageForm.monthly_payment} onChange={e=>setMortgageForm({...mortgageForm,monthly_payment:e.target.value})} required/>
          <select className="fin-input" aria-label="Tipo de hipoteca" value={mortgageForm.interest_type} onChange={e=>setMortgageForm({...mortgageForm,interest_type:e.target.value})}><option value="fixed">Fija</option><option value="variable">Variable</option><option value="mixed">Mixta</option></select>
          <input className="fin-input" type="number" min="0" step=".001" placeholder="TIN actual (%)" value={mortgageForm.nominal_rate_pct} onChange={e=>setMortgageForm({...mortgageForm,nominal_rate_pct:e.target.value})} required/>
          <input className="fin-input" type="number" min="1" step="1" placeholder="Meses pendientes" value={mortgageForm.remaining_months} onChange={e=>setMortgageForm({...mortgageForm,remaining_months:e.target.value})} required/>
          <input className="fin-input" type="number" min="0" step=".01" placeholder="Comisión amortización en €" value={mortgageForm.early_repayment_fee} onChange={e=>setMortgageForm({...mortgageForm,early_repayment_fee:e.target.value})}/>
          <button className="fin-button sm:col-span-2" disabled={saveMortgage.isPending}>{saveMortgage.isPending?'Guardando…':creatingMortgage?'Crear hipoteca':'Guardar datos principales'}</button>
        </form>
        {!creatingMortgage&&selectedMortgageId&&<>
          <div className="my-5 border-t border-[var(--border)]"/>
          <div className="grid gap-4 lg:grid-cols-2">
            <form className="grid gap-2" onSubmit={(e:FormEvent)=>{e.preventDefault();saveHomeValue.mutate()}}>
              <h3 className="font-semibold">Valor de la vivienda</h3>
              <input className="fin-input" type="number" min="0" step=".01" placeholder="Valor actual vivienda (€)" value={homeValue} onChange={e=>setHomeValue(e.target.value)} required/>
              <button className="fin-button secondary" disabled={saveHomeValue.isPending}>{saveHomeValue.isPending?'Guardando…':'Guardar valoración'}</button>
            </form>
            <form className="grid gap-2 sm:grid-cols-2" onSubmit={(e:FormEvent)=>{e.preventDefault();saveExtra.mutate()}}>
              <h3 className="font-semibold sm:col-span-2">Condiciones y calendario</h3>
              <input className="fin-input" type="number" min="0" step=".01" placeholder="Capital inicial (€)" value={extraForm.original_principal} onChange={e=>setExtraForm({...extraForm,original_principal:e.target.value})}/>
              <input className="fin-input" type="number" min="1" step="1" placeholder="Plazo inicial (meses)" value={extraForm.original_term_months} onChange={e=>setExtraForm({...extraForm,original_term_months:e.target.value})}/>
              <label className="text-xs text-[var(--muted)]">Inicio<input className="fin-input mt-1" type="date" value={extraForm.start_date} onChange={e=>setExtraForm({...extraForm,start_date:e.target.value})}/></label>
              <label className="text-xs text-[var(--muted)]">Vencimiento<input className="fin-input mt-1" type="date" value={extraForm.maturity_date} onChange={e=>setExtraForm({...extraForm,maturity_date:e.target.value})}/></label>
              <input className="fin-input" type="number" min="0" step=".001" placeholder="TAE actual (%)" value={extraForm.apr_rate_pct} onChange={e=>setExtraForm({...extraForm,apr_rate_pct:e.target.value})}/>
              <input className="fin-input" placeholder="Índice, ej. Euríbor 12m" value={extraForm.reference_index} onChange={e=>setExtraForm({...extraForm,reference_index:e.target.value})}/>
              <input className="fin-input" type="number" step=".001" placeholder="Diferencial (%)" value={extraForm.differential_rate_pct} onChange={e=>setExtraForm({...extraForm,differential_rate_pct:e.target.value})}/>
              <input className="fin-input" type="number" min="1" step="1" placeholder="Revisión cada N meses" value={extraForm.rate_review_months} onChange={e=>setExtraForm({...extraForm,rate_review_months:e.target.value})}/>
              <label className="text-xs text-[var(--muted)] sm:col-span-2">Próxima revisión<input className="fin-input mt-1" type="date" value={extraForm.next_review_date} onChange={e=>setExtraForm({...extraForm,next_review_date:e.target.value})}/></label>
              <input className="fin-input" type="number" min="0" step=".001" placeholder="Comisión apertura (%)" value={extraForm.opening_fee_percent} onChange={e=>setExtraForm({...extraForm,opening_fee_percent:e.target.value})}/>
              <input className="fin-input" type="number" min="0" step=".001" placeholder="Amortización anticipada (%)" value={extraForm.early_repayment_fee_percent} onChange={e=>setExtraForm({...extraForm,early_repayment_fee_percent:e.target.value})}/>
              <input className="fin-input" type="number" min="0" step=".001" placeholder="Subrogación (%)" value={extraForm.subrogation_fee_percent} onChange={e=>setExtraForm({...extraForm,subrogation_fee_percent:e.target.value})}/>
              <input className="fin-input" type="number" min="0" step=".001" placeholder="Cancelación/salida (%)" value={extraForm.cancellation_fee_percent} onChange={e=>setExtraForm({...extraForm,cancellation_fee_percent:e.target.value})}/>
              <textarea className="fin-input sm:col-span-2" placeholder="Notas relevantes" value={extraForm.notes} onChange={e=>setExtraForm({...extraForm,notes:e.target.value})}/>
              <button className="fin-button sm:col-span-2" disabled={saveExtra.isPending}>{saveExtra.isPending?'Guardando…':'Guardar condiciones'}</button>
            </form>
          </div>
          <div className="mt-4 flex justify-end"><button type="button" className="text-xs underline" onClick={()=>{if(window.confirm('¿Eliminar esta hipoteca? La documentación permanecerá en la biblioteca.')){deleteMortgage.mutate(selectedMortgageId);setShowMortgageEdit(false)}}}>Eliminar hipoteca</button></div>
        </>}
        {(saveMortgage.error||saveExtra.error||saveHomeValue.error)&&<div className="mt-3"><ErrorState error={(saveMortgage.error||saveExtra.error||saveHomeValue.error)!}/></div>}
      </Card></div>
    </div>}
    {selectedMortgageId&&<EntityDocumentsModal open={showMortgageDocuments} onClose={()=>setShowMortgageDocuments(false)} entityType="mortgage" entityId={selectedMortgageId} documentType="mortgage" title={'Documentos de la hipoteca · '+(home.data?.mortgage?.lender||'seleccionada')}/>}
    </>}
  </>;
}
