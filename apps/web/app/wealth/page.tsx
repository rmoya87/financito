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
import {DataStatus} from '@/components/data-status';
import {DetailGroup,MetricTile,ModalHero,SectionIntro} from '@/components/finance-ui';

type WealthSummary={
  accounts:string;manual_assets:string;investments:string;liabilities:string;mortgages:string;
  gross_assets:string;total_debt:string;net_worth:string
};
type Account={id:string;name:string;institution_name:string;account_type?:string;currency:string;balance:string;available_balance?:string|null};
type BankAccount={id:string;name:string;institution_name:string;account_type:string;currency:string;current_balance:string;available_balance:string|null};
type Asset={id:string;type:string;name:string;value:string;currency:string;valuation_date:string;valuation_source:string;ownership_type:string;ownership_percentage:string;previous_value?:string|null;previous_valuation_date?:string|null;change_amount?:string|null;change_pct?:string|null};
type Liability={id:string;type:string;name:string;amount:string;currency:string;annual_rate:string|null;ownership_percentage:string};
type Mortgage={id:string;account_id:string|null;lender:string;remaining_principal:string;currency:string;interest_type:string;nominal_rate:string;monthly_payment:string;remaining_months:number;early_repayment_fee?:string|null;source_document_id?:string|null;source_document_ids?:string[];document_count?:number};
type MortgagePayment={id:string;transaction_id:string;booking_date:string;description:string;merchant:string|null;payment_amount:string;principal_amount:string;interest_amount:string;currency:string;balance_before:string;balance_after:string;applied_to_balance:boolean;calculation_method:string;account_id:string;account_name:string|null;institution_name:string|null};
type Investment={security_id:string;name:string;identifier:string|null;asset_class:string;currency:string;quantity:string;cost_basis:string;current_value:string|null;current_price:string|null;price_provider:string|null};
type Policy={id:string;insurance_type:string;annual_premium:string;currency:string;deductible:string|null;provider:string|null;contract_id:string|null};
type WealthDetails={summary:WealthSummary;accounts:Account[];assets:Asset[];liabilities:Liability[];mortgages:Mortgage[];investments:Investment[];insurance:{annual_premium_total:string;policies:Policy[]}};

type PrepaymentRestriction={
  status:string;calculation_ready:boolean;permission_confirmed:boolean;partial_prepayment_allowed:boolean|null;
  missing:string[];pending_review:{key:string;value:any;unit:string|null;document_id:string|null;page:number|null;source?:string|null;status?:string}[];
  blockers:{code:string;message:string;limit?:string}[];effective_min_amount:string|null;effective_max_amount:string|null;
  notice_days:number|null;frequency_limit_per_year:number|null;window:string|null;condition:string|null;
  allowed_reduction_options:string[];operational_checks:{code:string;message:string;confirmed?:boolean}[];
  requires_manual_execution_check:boolean;
};
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
  mortgage_payments:MortgagePayment[];
  current_apr_estimate:null|{rate:string|null;status:string;monthly_payment:string;known_linked_annual_cost:string;known_linked_monthly_cost:string;basis:string};
  rate_review_automation:{status:string;automatic:boolean;missing:string[];reference_index?:string|null;differential_rate?:string|null;rate_review_months?:number|null;next_review_date?:string|null;reference_index_lag_months?:number|null;rule?:string;message?:string|null;estimate?:null|{review_date:string;reference_month:string;reference_index_value_percent:string;reference_source:string;reference_series:string;reference_period:string;estimated_nominal_rate:string;estimated_monthly_payment:string;estimated_remaining_interest:string;estimated_current_apr:string|null;known_linked_annual_cost:string;confirmation_required:boolean;notice:string}};
  prepayment_restrictions:PrepaymentRestriction|null;
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

const editableMortgageMissingKeys=new Set([
  'apr_rate','reference_index','differential_rate','rate_review_months','next_review_date',
  'early_repayment_fee_percent','subrogation_fee_percent',
]);

function prepaymentOptionLabel(value:string){
  if(value==='payment')return 'reducir cuota';
  if(value==='term')return 'reducir plazo';
  if(value==='lender_choice')return 'lo decide la entidad';
  return value;
}

function sumAssets(rows:Asset[],types:string[]){
  return rows.filter(x=>types.includes(x.type.toLowerCase())).reduce((sum,x)=>sum+Number(x.value||0)*Number(x.ownership_percentage||100)/100,0);
}

function Metric({label,value,detail}:{label:string;value:string|number;detail:string}){
  return <Card><div className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">{label}</div><div className="mt-2 text-2xl font-bold"><Money value={value}/></div><div className="mt-1 text-xs text-[var(--muted)]">{detail}</div></Card>;
}

export function WealthPage({mode='home'}:{mode?:'home'|'mortgage'}={}){
  const qc=useQueryClient();
  const details=useQuery({queryKey:['wealth-details'],queryFn:()=>apiGet<WealthDetails>('/api/v1/wealth/details')});
  const allAccounts=useQuery({queryKey:['accounts','mortgage-link'],queryFn:()=>apiGet<BankAccount[]>('/api/v1/accounts')});
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
  const [mortgageForm,setMortgageForm]=useState({account_id:'',remaining_principal:'',interest_type:'fixed',nominal_rate_pct:'',monthly_payment:'',remaining_months:'',early_repayment_fee:''});
  const [extraForm,setExtraForm]=useState({
    original_principal:'',original_term_months:'',start_date:'',maturity_date:'',apr_rate_pct:'',reference_index:'',differential_rate_pct:'',
    rate_review_months:'',next_review_date:'',opening_fee_percent:'',early_repayment_fee_percent:'',subrogation_fee_percent:'',cancellation_fee_percent:'',notes:'',
  });
  const [homeValue,setHomeValue]=useState('');
  const [showMortgageDocuments,setShowMortgageDocuments]=useState(false);
  const [showMortgageEdit,setShowMortgageEdit]=useState(false);
  const [mortgageSection,setMortgageSection]=useState<'general'|'transactions'|'details'>('general');

  useEffect(()=>{
    if(creatingMortgage||!mortgages.data)return;
    if(selectedMortgageId&&!mortgages.data.some(m=>m.id===selectedMortgageId)){
      setSelectedMortgageId(mortgages.data[0]?.id||'');
      return;
    }
    if(!selectedMortgageId&&mortgages.data.length)setSelectedMortgageId(mortgages.data[0].id);
  },[mortgages.data,selectedMortgageId,creatingMortgage]);

  useEffect(()=>{if(showMortgageEdit)setMortgageSection('general')},[showMortgageEdit,selectedMortgageId]);

  useEffect(()=>{
    const h=home.data;
    if(!h||creatingMortgage)return;
    if(h.property)setHomeValue(h.property.value);
    const m=h.mortgage;
    if(m)setMortgageForm({
      account_id:m.account_id||'',remaining_principal:m.remaining_principal,interest_type:m.interest_type,
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
    setMortgageForm({account_id:'',remaining_principal:'',interest_type:'fixed',nominal_rate_pct:'',monthly_payment:'',remaining_months:'',early_repayment_fee:''});
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
      const account=allAccounts.data?.find(a=>a.id===mortgageForm.account_id);
      if(!account)throw new Error('Selecciona la cuenta bancaria vinculada a la hipoteca');
      const payload={
        account_id:account.id,
        lender:account.institution_name,
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
  const unlinkMortgagePayment=useMutation({
    mutationFn:(transactionId:string)=>apiMutate('/api/v1/transactions/'+transactionId+'/mortgage','DELETE'),
    onSuccess:()=>{refresh();qc.invalidateQueries({queryKey:['transactions']})},
  });
  const deleteInsurance=useMutation({
    mutationFn:(id:string)=>apiMutate('/api/v1/insurance/'+id,'DELETE'),
    onSuccess:()=>{refresh();qc.invalidateQueries({queryKey:['insurance']});qc.invalidateQueries({queryKey:['insurance-verdict']});qc.invalidateQueries({queryKey:['switching-readiness']})},
  });

  const d=details.data;
  const properties=useMemo(()=>d?sumAssets(d.assets,['property','home','house','real_estate']):0,[d]);
  const vehicles=useMemo(()=>d?sumAssets(d.assets,['vehicle','car','motorcycle']):0,[d]);
  const otherAssets=useMemo(()=>d?Math.max(0,Number(d.summary.manual_assets)-properties-vehicles):0,[d,properties,vehicles]);

  if(mode==='home'){
    return <>
      <PageHeader title="Casa" description="Resumen de tu vivienda, hipoteca y seguros. Entra en cada apartado solo cuando necesites ver o modificar el detalle."/>
      {home.data&&<div className="mb-4"><DataStatus label="Resumen calculado" detail="vivienda, hipoteca y seguros guardados" tone="calculated"/></div>}
      {details.isLoading||home.isLoading?<Loading/>:details.error?<ErrorState error={details.error}/>:home.error?<ErrorState error={home.error}/>:d&&home.data&&<>
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <Metric label="Valor vivienda" value={home.data.property?.value||'0'} detail={home.data.property?'Última valoración guardada':'Sin valoración guardada'}/>
          <Metric label="Capital hipotecario" value={home.data.mortgage?.remaining_principal||'0'} detail={home.data.mortgage?home.data.mortgage.lender:'Sin hipoteca registrada'}/>
          <Metric label="Equity estimado" value={home.data.equity||'0'} detail="Valor de vivienda menos capital pendiente"/>
          <Metric label="Seguros al año" value={d.insurance.annual_premium_total} detail={d.insurance.policies.length+' póliza(s) registrada(s)'}/>
        </div>

        <div className="mt-4 grid gap-4 xl:grid-cols-2">
          <Card>
            <div className="flex items-start justify-between gap-3">
              <div><div className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">Hipoteca</div><h2 className="mt-1 text-lg font-bold">{home.data.mortgage?home.data.mortgage.lender:'Sin hipoteca'}</h2></div>
              <Link className="fin-button secondary py-1.5 text-xs" href="/mortgage/">Ver hipoteca</Link>
            </div>
            {home.data.mortgage?<div className="mt-4 grid gap-3 sm:grid-cols-2">
              <div className="rounded-xl bg-[var(--surface-2)] p-3"><div className="text-xs text-[var(--muted)]">Cuota mensual</div><strong><Money value={home.data.mortgage.monthly_payment}/></strong></div>
              <div className="rounded-xl bg-[var(--surface-2)] p-3"><div className="text-xs text-[var(--muted)]">TIN actual</div><strong>{(Number(home.data.mortgage.nominal_rate)*100).toLocaleString('es-ES',{maximumFractionDigits:3})}%</strong></div>
              <div className="rounded-xl bg-[var(--surface-2)] p-3"><div className="text-xs text-[var(--muted)]">Plazo restante</div><strong>{home.data.mortgage.remaining_months} meses</strong></div>
              <div className="rounded-xl bg-[var(--surface-2)] p-3"><div className="text-xs text-[var(--muted)]">LTV actual</div><strong>{home.data.ltv===null?'—':Number(home.data.ltv).toLocaleString('es-ES',{maximumFractionDigits:1})+'%'}</strong></div>
            </div>:<div className="mt-4"><EmptyState>No hay una hipoteca registrada. Créala desde Hipoteca.</EmptyState></div>}
          </Card>

          <Card>
            <div className="flex items-start justify-between gap-3">
              <div><div className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">Seguros</div><h2 className="mt-1 text-lg font-bold">Protección y coste</h2></div>
              <Link className="fin-button secondary py-1.5 text-xs" href="/insurance/">Ver seguros</Link>
            </div>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <div className="rounded-xl bg-[var(--surface-2)] p-3"><div className="text-xs text-[var(--muted)]">Coste anual</div><strong><Money value={d.insurance.annual_premium_total}/></strong></div>
              <div className="rounded-xl bg-[var(--surface-2)] p-3"><div className="text-xs text-[var(--muted)]">Pólizas</div><strong>{d.insurance.policies.length}</strong></div>
            </div>
            <div className="mt-3 space-y-2">{d.insurance.policies.slice(0,4).map(policy=><div key={policy.id} className="flex items-center justify-between gap-3 rounded-xl bg-[var(--surface-2)] p-3 text-sm">
              <div><strong>{policy.provider||'Aseguradora pendiente'}</strong><div className="text-xs text-[var(--muted)]">{policy.insurance_type}</div></div>
              <strong><Money value={policy.annual_premium} currency={policy.currency}/>/año</strong>
            </div>)}</div>
            {!d.insurance.policies.length&&<div className="mt-4"><EmptyState>No hay seguros registrados.</EmptyState></div>}
          </Card>
        </div>
      </>}
    </>;
  }

  return <>
    <PageHeader title="Hipoteca" description="Deuda, cuota, condiciones, documentación, seguros vinculados y comparación de mercado de tu hipoteca."/>
    {home.data&&<div className="mb-4 flex flex-wrap gap-2">
      <DataStatus label="Datos guardados" detail={home.data.mortgage?'hipoteca vinculada a movimientos y cuenta':'sin hipoteca registrada'} tone={home.data.mortgage?'confirmed':'neutral'}/>
      <DataStatus label={home.data.pending_review?.length?'Pendiente de confirmar':'Evidencia contractual'} detail={home.data.pending_review?.length?home.data.pending_review.length+' dato(s) localizado(s) sin validar':home.data.source_documents.length?home.data.source_documents.length+' documento(s) vinculados':'sin documentación vinculada'} tone={home.data.pending_review?.length?'pending':home.data.source_documents.length?'confirmed':'neutral'}/>
      <DataStatus label="Cálculos actuales" detail="cuota, capital y estimaciones con datos vigentes" tone="calculated"/>
    </div>}

    {details.isLoading?<Loading/>:details.error?<ErrorState error={details.error}/>:d&&<>
      <SectionIntro eyebrow="Lectura rápida" title="Tu hipoteca hoy" description="Deuda, cuota, coste y relación con el valor de la vivienda antes de entrar en condiciones o documentación."/>
      {home.data&&<div className="mb-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <MetricTile label="Capital pendiente" value={home.data.mortgage?<Money value={home.data.mortgage.remaining_principal}/>:<>—</>} detail={home.data.mortgage?.lender||'Sin hipoteca seleccionada'} status="Saldo actual" statusTone="confirmed"/>
        <MetricTile label="Cuota mensual" value={home.data.mortgage?<Money value={home.data.mortgage.monthly_payment}/>:<>—</>} detail={home.data.mortgage?home.data.mortgage.remaining_months+' meses pendientes':'Sin datos'} status="Guardado" statusTone="confirmed"/>
        <MetricTile label="TIN actual" value={home.data.mortgage?(Number(home.data.mortgage.nominal_rate)*100).toLocaleString('es-ES',{maximumFractionDigits:3})+'%':'—'} detail={home.data.mortgage?(home.data.mortgage.interest_type==='fixed'?'Tipo fijo':home.data.mortgage.interest_type==='variable'?'Tipo variable':'Tipo mixto'):'Sin datos'} status={home.data.source_documents.length?'Evidencia':'Dato guardado'} statusTone={home.data.source_documents.length?'confirmed':'neutral'}/>
        <MetricTile label="LTV actual" value={home.data.ltv===null?'—':Number(home.data.ltv).toLocaleString('es-ES',{maximumFractionDigits:1})+'%'} detail="Capital pendiente / valor atribuible de la vivienda" emphasis/>
      </div>}
      <SectionIntro eyebrow="Detalle" title="Condiciones, coste y vínculos" description="Aquí quedan los datos que explican el coste real de la hipoteca y lo que puede cambiar una decisión."/>
      <Card>
        <div>
          <div className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">Hipoteca</div>
          <h2 className="mt-1 text-xl font-bold">Tu hipoteca</h2>
          <p className="mt-1 max-w-3xl text-sm text-[var(--muted)]">Centraliza valor de la vivienda, deuda, condiciones, seguros vinculados y evidencia documental. Estos datos alimentan las simulaciones de amortización, novación y subrogación.</p>
        </div>
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
          <select className="fin-input w-full py-2 text-xs sm:w-auto sm:min-w-[220px] sm:max-w-[330px]" aria-label="Hipoteca seleccionada" value={creatingMortgage?'':selectedMortgageId} onChange={e=>{setCreatingMortgage(false);setSelectedMortgageId(e.target.value)}}>
            <option value="">{mortgages.data?.length?'Selecciona una hipoteca…':'Sin hipotecas'}</option>
            {mortgages.data?.map(m=><option key={m.id} value={m.id}>{m.lender} · {Number(m.remaining_principal).toLocaleString('es-ES')} {m.currency}</option>)}
          </select>
          <div className="flex flex-wrap items-center justify-end gap-2">
            <button className="fin-button py-2 text-xs" type="button" onClick={()=>{setCreatingMortgage(true);setSelectedMortgageId('');clearMortgageForms();setShowMortgageEdit(true)}}>Nueva hipoteca</button>
            {selectedMortgageId&&<button className="fin-button secondary py-2 text-xs" type="button" onClick={()=>setShowMortgageEdit(true)}>Detalle de la hipoteca</button>}
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
                <div className="mt-1 text-[11px] text-[var(--muted)]">Capital inicial <Money value={home.data.principal_progress.original_principal}/></div>
              </div>:<div className="mt-1 text-[11px] text-[var(--muted)]">{home.data.mortgage?'Añade el capital inicial en Datos de la hipoteca para ver el porcentaje amortizado.':'Sin hipoteca'}</div>}
            </div>
            <div className="rounded-xl bg-[var(--surface-2)] p-4"><div className="text-xs text-[var(--muted)]">Cuota mensual</div><div className="mt-1 text-xl font-bold">{home.data.mortgage?<Money value={home.data.mortgage.monthly_payment}/>:<span>—</span>}</div><div className="mt-1 text-[11px] text-[var(--muted)]">{home.data.mortgage?home.data.mortgage.remaining_months+' meses pendientes':'—'}</div></div>
            <div className="rounded-xl bg-[var(--surface-2)] p-4">
              <div className="text-xs text-[var(--muted)]">Tipo / TIN</div>
              <div className="mt-1 text-xl font-bold">{home.data.mortgage?(home.data.mortgage.interest_type==='fixed'?'Fija':home.data.mortgage.interest_type==='variable'?'Variable':'Mixta'):'—'}</div>
              <div className="mt-1 text-[11px] font-medium">
                {home.data.mortgage&&home.data.mortgage.interest_type!=='fixed'
                  ?((home.data.extra.reference_index||home.data.rate_review_automation.reference_index||'Índice pendiente')+(home.data.extra.differential_rate!==null?' + '+(Number(home.data.extra.differential_rate)*100).toLocaleString('es-ES',{maximumFractionDigits:3})+'%':' + diferencial pendiente'))
                  :home.data.mortgage?'Tipo fijo contractual':'—'}
              </div>
              <div className="mt-1 text-[11px] text-[var(--muted)]">{home.data.mortgage?'TIN actual '+(Number(home.data.mortgage.nominal_rate)*100).toLocaleString('es-ES',{maximumFractionDigits:3})+'%':'—'}</div>
            </div>
            <div className="rounded-xl bg-[var(--surface-2)] p-4"><div className="text-xs text-[var(--muted)]">TAE contractual</div><div className="mt-1 text-xl font-bold">{home.data.extra.apr_rate===null?'—':(Number(home.data.extra.apr_rate)*100).toLocaleString('es-ES',{maximumFractionDigits:3})+'%'}</div><div className="mt-1 text-[11px] text-[var(--muted)]">Dato original/contractual; no se sobrescribe en revisiones.</div></div>
            <div className="rounded-xl bg-[var(--surface-2)] p-4"><div className="text-xs text-[var(--muted)]">TAE estimada actual</div><div className="mt-1 text-xl font-bold">{home.data.current_apr_estimate?.rate?(Number(home.data.current_apr_estimate.rate)*100).toLocaleString('es-ES',{maximumFractionDigits:3})+'%':'—'}</div><div className="mt-1 text-[11px] text-[var(--muted)]">{home.data.current_apr_estimate?.rate?'TIN vigente + costes futuros vinculados conocidos':'Sin datos suficientes'}</div></div>
            <div className="rounded-xl bg-[var(--surface-2)] p-4"><div className="text-xs text-[var(--muted)]">Vencimiento</div><div className="mt-1 text-xl font-bold">{home.data.extra.maturity_date?new Date(home.data.extra.maturity_date).toLocaleDateString('es-ES'):'—'}</div><div className="mt-1 text-[11px] text-[var(--muted)]">{home.data.extra.next_review_date?'Próxima revisión '+new Date(home.data.extra.next_review_date).toLocaleDateString('es-ES'):'Sin próxima revisión informada'}</div></div>
            <div className="rounded-xl bg-[var(--surface-2)] p-4"><div className="text-xs text-[var(--muted)]">Equity estimado</div><div className="mt-1 text-xl font-bold">{home.data.equity!==null?<Money value={home.data.equity}/>:<span>—</span>}</div><div className="mt-1 text-[11px] text-[var(--muted)]">Vivienda menos capital pendiente</div></div>
            <div className="rounded-xl bg-[var(--surface-2)] p-4"><div className="text-xs text-[var(--muted)]">LTV actual</div><div className="mt-1 text-xl font-bold">{home.data.ltv===null?'—':Number(home.data.ltv).toLocaleString('es-ES',{maximumFractionDigits:1})+'%'}</div><div className="mt-1 text-[11px] text-[var(--muted)]">Capital pendiente / valor atribuible</div></div>
          </div>

          {home.data.pending_review?.filter(x=>x.key!=='reference_index_lag_months').length>0&&<div className="mt-4 rounded-xl border border-[var(--brand)] bg-[var(--brand-soft)] p-4">
            <h3 className="font-semibold">Datos ya encontrados pendientes de validar</h3>
            <p className="mt-1 text-xs text-[var(--muted)]">No están ausentes: el extractor o la IA local los ha localizado. Confírmalos en el documento para que se proyecten automáticamente a la hipoteca y entren en cálculos.</p>
            <div className="mt-2 grid gap-2 md:grid-cols-2">{home.data.pending_review.filter(x=>x.key!=='reference_index_lag_months').map(x=><div key={x.key} className="rounded-lg bg-white p-3 text-xs"><strong>{x.label}</strong><div className="mt-1">{String(x.value??'Dato localizado')}{x.unit?' '+x.unit:''}</div><div className="mt-1 text-[var(--muted)]">{x.reason}</div>{x.document_id&&selectedMortgageId&&<Link className="mt-2 inline-block underline" href={'/documents/?entity_type=mortgage&entity_id='+encodeURIComponent(selectedMortgageId)+'&label='+encodeURIComponent('Hipoteca · '+(home.data?.mortgage?.lender||'seleccionada'))+'&document='+encodeURIComponent(x.document_id)}>Revisar documentación{x.page?' · pág. '+x.page:''}</Link>}</div>)}</div>
          </div>}

          {home.data.missing.filter(x=>x.key!=='reference_index_lag_months').length>0&&selectedMortgageId&&!creatingMortgage&&<div className="mt-4 rounded-xl bg-[var(--surface-2)] p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div><h3 className="font-semibold">Información que falta</h3><p className="mt-1 text-xs text-[var(--muted)]">Primero intenta localizarla en los documentos de esta hipoteca. Los datos numéricos sencillos pueden completarse manualmente; las condiciones contractuales como permiso, límites o forma de amortizar deben confirmarse desde la documentación.</p></div>
              <button className="fin-button secondary py-1.5 text-xs" type="button" onClick={()=>analyzeMortgageDocs.mutate()} disabled={analyzeMortgageDocs.isPending}>{analyzeMortgageDocs.isPending?'Buscando…':'Intentar completar con IA'}</button>
            </div>
            <div className="mt-3 grid gap-3 md:grid-cols-2">{home.data.missing.filter(x=>x.key!=='reference_index_lag_months').map(x=><div key={x.key} className="rounded-lg bg-white p-3 text-xs">
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
              {home.data.missing.filter(x=>x.key!=='reference_index_lag_months').some(x=>editableMortgageMissingKeys.has(x.key))&&<button className="fin-button" type="button" onClick={()=>saveExtra.mutate()} disabled={saveExtra.isPending}>Guardar datos de hipoteca</button>}
            </div>
            {analyzeMortgageDocs.error&&<div className="mt-3"><ErrorState error={analyzeMortgageDocs.error}/></div>}
          </div>}

          <div className="mt-4 grid gap-4 xl:grid-cols-2">
            <div className="rounded-xl border border-[var(--border)] p-4">
              <div className="flex items-start justify-between gap-3"><div><h3 className="font-semibold">Seguros relacionados con la vivienda</h3><p className="mt-1 text-xs text-[var(--muted)]">Hogar y vida aparecen aquí porque pueden afectar al coste efectivo de la hipoteca o a sus bonificaciones.</p></div><Link className="text-xs underline" href="/insurance/">Seguros</Link></div>
              <div className="mt-3 space-y-2">{home.data.insurance.length?home.data.insurance.map(x=><div key={x.id} className="flex items-center justify-between gap-3 rounded-lg bg-[var(--surface-2)] p-3 text-sm">
                <Link href={'/insurance/?policy='+encodeURIComponent(x.id)} className="min-w-0 flex-1 hover:underline">
                  <div className="flex flex-wrap items-center gap-2"><strong>{x.insurance_type}</strong>{x.linked_to_mortgage&&<span className="rounded-full bg-[var(--brand-soft)] px-2 py-0.5 text-[10px] font-semibold">Vinculado a esta hipoteca</span>}</div>
                  <div className="text-xs text-[var(--muted)]">{x.provider||'Proveedor pendiente'}{x.renewal_date?' · renueva '+new Date(x.renewal_date).toLocaleDateString('es-ES'):''}</div>
                  <div className="mt-1 text-[11px] underline">Ver ficha completa</div>
                </Link>
                <div className="shrink-0 text-right"><strong><Money value={x.annual_premium}/>/año</strong><div><button className="mt-1 text-xs underline" type="button" disabled={deleteInsurance.isPending} onClick={()=>{if(window.confirm('¿Eliminar este seguro? La ficha, coberturas y vínculos con la hipoteca se borrarán. Sus archivos permanecerán en Documentación como evidencia anulada/sin clasificar.'))deleteInsurance.mutate(x.id)}}>{deleteInsurance.isPending?'Eliminando…':'Eliminar seguro'}</button></div></div>
              </div>):<EmptyState>No hay seguros de hogar o seguros vinculados a esta hipoteca estructurados todavía.</EmptyState>}</div>
              {deleteInsurance.error&&<div className="mt-3"><ErrorState error={deleteInsurance.error}/></div>}
              {home.data.source_documents.length>0&&<div className="mt-3 text-xs text-[var(--muted)]"><strong>Documentación hipotecaria vinculada:</strong> {home.data.source_documents.map(x=>x.name).join(' · ')}</div>}
            </div>

            <div className="rounded-xl border border-[var(--border)] p-4">
              <div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="font-semibold">Comparar con el mercado</h3><p className="mt-1 text-xs text-[var(--muted)]">Busca referencias públicas para detectar si merece la pena pedir una novación o una oferta de subrogación.</p></div><button className="fin-button py-1.5 text-xs" onClick={()=>marketScan.mutate()} disabled={marketScan.isPending||!selectedMortgageId}>{marketScan.isPending?'Consultando…':'Actualizar mercado'}</button></div>
              {!home.data.mortgage&&<div className="mt-3 text-xs text-[var(--muted)]">Completa primero la hipoteca para poder comparar la misma deuda y plazo.</div>}
              {marketScan.error&&<div className="mt-3"><ErrorState error={marketScan.error}/></div>}
              {marketScan.data&&<>
                <div className="mt-3 rounded-xl bg-[var(--brand-soft)] p-3 text-sm"><strong>{marketScan.data.conclusion.headline}</strong><div className="mt-1">{marketScan.data.conclusion.action}</div>{marketScan.data.conclusion.estimated_monthly_saving&&<div className="mt-2 text-xs">Posible ahorro mensual si la oferta final mantiene estas condiciones: <strong><Money value={marketScan.data.conclusion.estimated_monthly_saving}/></strong>{marketScan.data.conclusion.break_even_months?' · punto de equilibrio estimado '+marketScan.data.conclusion.break_even_months+' meses':''}</div>}{marketScan.data.conclusion.missing?.length>0&&<div className="mt-2 text-xs text-[var(--muted)]">Pendiente: {marketScan.data.conclusion.missing.join(' · ')}</div>}</div>
                <div className="mt-3 grid gap-2 text-xs sm:grid-cols-3">
                  <div className="rounded-lg bg-[var(--surface-2)] p-3"><span className="text-[var(--muted)]">Tu cuota actual</span><div className="font-semibold"><Money value={marketScan.data.current_monthly_payment}/></div></div>
                  <div className="rounded-lg bg-[var(--surface-2)] p-3"><span className="text-[var(--muted)]">Penalización de salida confirmada</span><div className="font-semibold">{marketScan.data.current_conditions.known_exit_penalty===null?'Pendiente':<Money value={marketScan.data.current_conditions.known_exit_penalty}/>}</div></div>
                  <div className="rounded-lg bg-[var(--surface-2)] p-3"><span className="text-[var(--muted)]">Seguros vinculados actuales</span><div className="font-semibold"><Money value={marketScan.data.current_conditions.linked_insurance_annual_cost}/> / año</div></div>
                </div>
                <div className="mt-3 rounded-lg bg-[var(--surface-2)] p-3 text-xs">{marketScan.data.disclaimer}</div>
                <div className="mt-3 space-y-2">{marketScan.data.better_offers.length?marketScan.data.better_offers.map(x=><div key={x.source_id} className="rounded-lg border border-[var(--border)] p-3 text-sm">
                  <div className="flex flex-wrap items-start justify-between gap-3"><div><strong>{x.provider}</strong><div className="text-xs text-[var(--muted)]">{x.kind==='mortgage_subrogation'?'Referencia de subrogación / cambio de banco':'Referencia pública para pedir una oferta'}</div></div><a className="text-xs underline" href={x.url} target="_blank" rel="noreferrer">Fuente</a></div>
                  <div className="mt-2 grid gap-2 sm:grid-cols-4 text-xs">
                    <div><span className="text-[var(--muted)]">TIN público desde</span><div className="font-semibold">{x.public_tin_min?.toLocaleString('es-ES',{maximumFractionDigits:3})}%</div></div>
                    <div><span className="text-[var(--muted)]">Cuota comparable</span><div className="font-semibold">{x.scenario?<Money value={x.scenario.estimated_payment}/>:<span>—</span>}</div></div>
                    <div><span className="text-[var(--muted)]">Ahorro mensual estimado</span><div className="font-semibold">{x.scenario?<Money value={x.scenario.actual_monthly_saving}/>:<span>—</span>}</div></div>
                    <div><span className="text-[var(--muted)]">Empieza a compensar</span><div className="font-semibold">{x.scenario?.break_even_months?x.scenario.break_even_months+' meses':'—'}</div></div>
                  </div>
                  {x.scenario&&<div className="mt-2 text-xs">Penalización actual aplicada: <strong><Money value={x.scenario.known_exit_penalty}/></strong> · diferencia estimada de intereses con costes conocidos: <strong><Money value={x.scenario.estimated_net_interest_saving_known_costs}/></strong>. Falta confirmar la oferta personalizada.</div>}
                </div>):<EmptyState>No hay una oferta pública que se pueda demostrar mejor que tu hipoteca con tus condiciones actuales.</EmptyState>}</div>
                {marketScan.data.lower_rate_but_not_better.length>0&&<div className="mt-3 text-xs text-[var(--muted)]">{marketScan.data.lower_rate_but_not_better.length} referencia(s) tienen un TIN menor pero no se muestran como mejores porque no compensan dentro del plazo o faltan costes de vinculaciones para demostrarlo.</div>}
                <div className="mt-3"><div className="text-xs font-semibold">Referencias oficiales</div><div className="mt-1 space-y-1">{marketScan.data.official_sources.map(x=><div key={x.id} className="text-xs"><a className="underline" href={x.url} target="_blank" rel="noreferrer">{x.provider}</a> · <span className="text-[var(--muted)]">{x.description}</span></div>)}</div></div>
              </>}
            </div>
          </div>

        </>}
      </Card>

    {showMortgageEdit&&<div className="fixed inset-0 z-50 overflow-y-auto bg-black/45 p-4 md:p-8" role="dialog" aria-modal="true" aria-label={creatingMortgage?'Nueva hipoteca':'Datos de la hipoteca'}>
      <div className="mx-auto max-w-5xl"><Card>
        <ModalHero
          eyebrow="Hipoteca"
          title={creatingMortgage?'Nueva hipoteca':home.data?.mortgage?.lender||'Hipoteca'}
          description={creatingMortgage?'Introduce los datos principales para crearla.':'Datos globales, transacciones vinculadas, condiciones y documentación en una única ficha.'}
          status={creatingMortgage?'Nueva':home.data?.pending_review?.length?'Pendiente de confirmar':home.data?.source_documents?.length?'Evidencia vinculada':'Datos guardados'}
          statusTone={creatingMortgage?'neutral':home.data?.pending_review?.length?'pending':home.data?.source_documents?.length?'confirmed':'neutral'}
          actions={<button className="fin-button secondary py-2 text-xs" type="button" onClick={()=>setShowMortgageEdit(false)}>Cerrar</button>}
          metrics={!creatingMortgage&&home.data?.mortgage?[
            {label:'Capital pendiente',value:<Money value={home.data.mortgage.remaining_principal}/>},
            {label:'Cuota',value:<Money value={home.data.mortgage.monthly_payment}/>},
            {label:'TIN',value:(Number(home.data.mortgage.nominal_rate)*100).toLocaleString('es-ES',{maximumFractionDigits:3})+'%'},
            {label:'LTV',value:home.data.ltv===null?'—':Number(home.data.ltv).toLocaleString('es-ES',{maximumFractionDigits:1})+'%'},
          ]:undefined}
        />
        {!creatingMortgage&&selectedMortgageId&&<div className="mt-5 flex flex-wrap gap-2 border-b border-[var(--border)] pb-3" role="tablist" aria-label="Secciones de la hipoteca">
          {([
            ['general','General'],
            ['transactions','Transacciones'],
            ['details','Detalles'],
          ] as const).map(([key,label])=><button key={key} role="tab" aria-selected={mortgageSection===key} type="button" className={mortgageSection===key?'fin-button py-2 text-xs':'fin-button secondary py-2 text-xs'} onClick={()=>setMortgageSection(key)}>{label}</button>)}
        </div>}
        {(creatingMortgage||mortgageSection==='general')&&<>
        <form className="mt-4 grid gap-2 sm:grid-cols-2" onSubmit={(e:FormEvent)=>{e.preventDefault();saveMortgage.mutate()}}>
          <select className="fin-input sm:col-span-2" aria-label="Cuenta bancaria de la hipoteca" value={mortgageForm.account_id} onChange={e=>setMortgageForm({...mortgageForm,account_id:e.target.value})} required>
            <option value="">Cuenta bancaria de la hipoteca…</option>
            {allAccounts.data?.map(account=><option key={account.id} value={account.id}>{account.institution_name} · {account.name}</option>)}
          </select>
          <input className="fin-input" type="number" min="0.01" step=".01" placeholder="Capital pendiente (€)" value={mortgageForm.remaining_principal} onChange={e=>setMortgageForm({...mortgageForm,remaining_principal:e.target.value})} required/>
          <input className="fin-input" type="number" min="0.01" step=".01" placeholder="Cuota mensual (€)" value={mortgageForm.monthly_payment} onChange={e=>setMortgageForm({...mortgageForm,monthly_payment:e.target.value})} required/>
          <select className="fin-input" aria-label="Tipo de hipoteca" value={mortgageForm.interest_type} onChange={e=>setMortgageForm({...mortgageForm,interest_type:e.target.value})}><option value="fixed">Fija</option><option value="variable">Variable</option><option value="mixed">Mixta</option></select>
          <input className="fin-input" type="number" min="0" step=".001" placeholder="TIN actual (%)" value={mortgageForm.nominal_rate_pct} onChange={e=>setMortgageForm({...mortgageForm,nominal_rate_pct:e.target.value})} required/>
          <input className="fin-input" type="number" min="1" step="1" placeholder="Meses pendientes" value={mortgageForm.remaining_months} onChange={e=>setMortgageForm({...mortgageForm,remaining_months:e.target.value})} required/>
          <input className="fin-input" type="number" min="0" step=".01" placeholder="Comisión amortización en €" value={mortgageForm.early_repayment_fee} onChange={e=>setMortgageForm({...mortgageForm,early_repayment_fee:e.target.value})}/>
          <button className="fin-button sm:col-span-2" disabled={saveMortgage.isPending}>{saveMortgage.isPending?'Guardando…':creatingMortgage?'Crear hipoteca':'Guardar datos principales'}</button>
        </form>
        {!creatingMortgage&&<DetailGroup title="Valor de la vivienda" description="Se usa para patrimonio, equity y LTV." className="mt-4">
          <form className="grid gap-2 sm:grid-cols-[1fr_auto]" onSubmit={(e:FormEvent)=>{e.preventDefault();saveHomeValue.mutate()}}>
            <input className="fin-input" type="number" min="0" step=".01" placeholder="Valor actual vivienda (€)" value={homeValue} onChange={e=>setHomeValue(e.target.value)} required/>
            <button className="fin-button secondary" disabled={saveHomeValue.isPending}>{saveHomeValue.isPending?'Guardando…':'Guardar valoración'}</button>
          </form>
        </DetailGroup>}
        </>}
        {!creatingMortgage&&selectedMortgageId&&mortgageSection==='transactions'&&<DetailGroup title="Transacciones de la hipoteca" description="La cuota se separa en interés estimado y capital amortizado usando el TIN vigente. Solo el capital reduce el saldo." className="mt-4">
          <div className="flex justify-end"><Link className="text-xs underline" href="/transactions/">Ir a Movimientos</Link></div>
          <div className="mt-3 space-y-2">{home.data?.mortgage_payments?.length?home.data.mortgage_payments.map(payment=><div key={payment.id} className="rounded-xl bg-[var(--surface-2)] p-4 text-sm">
            <div className="flex flex-wrap items-start justify-between gap-3"><div><strong>{payment.merchant||payment.description}</strong><div className="mt-1 text-xs text-[var(--muted)]">{new Date(payment.booking_date).toLocaleDateString('es-ES')} · {payment.description}{payment.account_name?' · '+payment.account_name:''}{payment.institution_name?' · '+payment.institution_name:''}</div></div><strong><Money value={payment.payment_amount} currency={payment.currency}/></strong></div>
            <div className="mt-3 grid gap-2 text-xs sm:grid-cols-3"><div>Capital: <strong><Money value={payment.principal_amount} currency={payment.currency}/></strong></div><div>Interés estimado: <strong><Money value={payment.interest_amount} currency={payment.currency}/></strong></div><div>Saldo después: <strong><Money value={payment.balance_after} currency={payment.currency}/></strong></div></div>
            <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-[11px] text-[var(--muted)]"><span>{payment.applied_to_balance?'Aplicada al capital pendiente':'Histórica · saldo reconciliado manualmente'}</span><button className="text-xs underline" type="button" disabled={unlinkMortgagePayment.isPending} onClick={()=>unlinkMortgagePayment.mutate(payment.transaction_id)}>Desvincular</button></div>
          </div>):<EmptyState>No hay cuotas vinculadas. En Movimientos selecciona esta hipoteca en el cargo de la cuota.</EmptyState>}</div>
          {unlinkMortgagePayment.error&&<div className="mt-3"><ErrorState error={unlinkMortgagePayment.error}/></div>}
        </DetailGroup>}
        {!creatingMortgage&&selectedMortgageId&&mortgageSection==='details'&&<>
          <div className="mt-4 grid gap-4 lg:grid-cols-2">
            <form className="grid gap-2 rounded-xl border border-[var(--border)] p-4 sm:grid-cols-2" onSubmit={(e:FormEvent)=>{e.preventDefault();saveExtra.mutate()}}>
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
              <input className="fin-input" type="number" min="0" step=".001" placeholder="Comisión por amortización anticipada (%)" value={extraForm.early_repayment_fee_percent} onChange={e=>setExtraForm({...extraForm,early_repayment_fee_percent:e.target.value})}/>
              <input className="fin-input" type="number" min="0" step=".001" placeholder="Subrogación (%)" value={extraForm.subrogation_fee_percent} onChange={e=>setExtraForm({...extraForm,subrogation_fee_percent:e.target.value})}/>
              <input className="fin-input" type="number" min="0" step=".001" placeholder="Cancelación/salida (%)" value={extraForm.cancellation_fee_percent} onChange={e=>setExtraForm({...extraForm,cancellation_fee_percent:e.target.value})}/>
              <textarea className="fin-input sm:col-span-2" placeholder="Notas relevantes" value={extraForm.notes} onChange={e=>setExtraForm({...extraForm,notes:e.target.value})}/>
              <button className="fin-button sm:col-span-2" disabled={saveExtra.isPending}>{saveExtra.isPending?'Guardando…':'Guardar condiciones'}</button>
            </form>
            <div className="rounded-xl border border-[var(--border)] p-4">
              <h3 className="font-semibold">Documentación</h3>
              <p className="mt-1 text-xs text-[var(--muted)]">Documentos y evidencia que sustentan las condiciones de esta hipoteca.</p>
              <div className="mt-3 space-y-2">{home.data?.source_documents?.length?home.data.source_documents.map(doc=><div key={doc.id} className="rounded-lg bg-[var(--surface-2)] p-3 text-sm">{doc.name}</div>):<EmptyState>No hay documentación vinculada.</EmptyState>}</div>
              <button className="fin-button secondary mt-3 py-1.5 text-xs" type="button" onClick={()=>setShowMortgageDocuments(true)}>Gestionar documentación</button>
              <div className="mt-5 grid gap-2 text-sm">
                <div>TAE contractual: <strong>{home.data?.extra.apr_rate===null?'—':(Number(home.data?.extra.apr_rate||0)*100).toLocaleString('es-ES',{maximumFractionDigits:3})+'%'}</strong></div>
                <div>TAE estimada actual: <strong>{home.data?.current_apr_estimate?.rate?(Number(home.data.current_apr_estimate.rate)*100).toLocaleString('es-ES',{maximumFractionDigits:3})+'%':'—'}</strong></div>
                <div>Vencimiento: <strong>{home.data?.extra.maturity_date?new Date(home.data.extra.maturity_date).toLocaleDateString('es-ES'):'—'}</strong></div>
                <div>Próxima revisión: <strong>{home.data?.extra.next_review_date?new Date(home.data.extra.next_review_date).toLocaleDateString('es-ES'):'—'}</strong></div>
              </div>
            </div>
          </div>
          {!!home.data?.pending_review?.length&&<DetailGroup title="Datos encontrados pendientes" description="Ya están localizados en la documentación, pero todavía necesitan validación antes de entrar en los cálculos." tone="warning" className="mt-4"><div className="grid gap-2 md:grid-cols-2">{home.data.pending_review.map(item=><div key={item.key} className="rounded-lg bg-[var(--brand-soft)] p-3 text-xs"><strong>{item.label}</strong><div className="mt-1">{String(item.value??'Dato localizado')}{item.unit?' '+item.unit:''}</div><div className="mt-1 text-[var(--muted)]">{item.reason}</div></div>)}</div></DetailGroup>}
          {!!home.data?.missing?.length&&<DetailGroup title="Información que falta" description="Campos que aún no están en la ficha ni se han confirmado en documentación." tone="soft" className="mt-4"><div className="grid gap-2 md:grid-cols-2">{home.data.missing.map(item=><div key={item.key} className="rounded-lg bg-[var(--surface-2)] p-3 text-xs"><strong>{item.label}</strong><div className="mt-1 text-[var(--muted)]">{item.reason}</div></div>)}</div></DetailGroup>}
          <div className="mt-4 flex justify-end"><button type="button" className="text-xs underline" onClick={()=>{if(window.confirm('¿Eliminar esta hipoteca? La documentación permanecerá en la biblioteca.')){deleteMortgage.mutate(selectedMortgageId);setShowMortgageEdit(false)}}}>Eliminar hipoteca</button></div>
        </>}
        {(saveMortgage.error||saveExtra.error||saveHomeValue.error)&&<div className="mt-3"><ErrorState error={(saveMortgage.error||saveExtra.error||saveHomeValue.error)!}/></div>}
      </Card></div>
    </div>}
    {selectedMortgageId&&<EntityDocumentsModal open={showMortgageDocuments} onClose={()=>setShowMortgageDocuments(false)} entityType="mortgage" entityId={selectedMortgageId} documentType="mortgage" title={'Documentos de la hipoteca · '+(home.data?.mortgage?.lender||'seleccionada')}/>}
    </>}
  </>;
}

export default function WealthPageRoute(){
  return <WealthPage mode="home"/>;
}
