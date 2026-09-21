'use client';

import Link from 'next/link';
import {FormEvent,useEffect,useState} from 'react';
import {useMutation,useQuery,useQueryClient} from '@tanstack/react-query';
import {apiGet,apiMutate} from '@/lib/api';
import {PageHeader} from '@/components/page-header';
import {Card} from '@/components/ui/card';
import {Money} from '@/components/ui/money';
import {EmptyState,ErrorState,Loading} from '@/components/ui/states';
import {EntityDocumentsModal} from '@/components/entity-documents-modal';
import {DataStatus} from '@/components/data-status';
import {DetailGroup,MetricTile,ModalHero,SectionIntro,VisualPanel} from '@/components/finance-ui';

type CoverageRequirement={id:string;insurance_type:string|null;coverage_type:string;minimum_limit:string|null;currency:string;notes:string|null;enabled:boolean};
type Account={id:string;name:string;institution_name:string;account_type:string;current_balance:string;available_balance:string|null};
type InsuranceProfile={id:string;account_id:string|null;account_name?:string|null;account_institution?:string|null;insurance_type:string;annual_premium:string;deductible:string|null;currency:string;policy_number_masked?:string|null;contract_id:string|null;provider_name?:string|null;renewal_date?:string|null;cancellation_notice_days?:number|null;early_exit_penalty?:string|null;document_count?:number;source_document_ids?:string[];linked_mortgage_ids?:string[]};
type MortgageRef={id:string;lender:string;remaining_principal:string;currency:string};
type InsurancePayment={transaction_id:string;booking_date:string;description:string;merchant:string|null;amount:string;currency:string;account_id:string;account_name:string|null;institution_name:string|null};
type Policy={
  id:string;insurance_type:string;annual_premium:string;monthly_equivalent:string;deductible:string|null;
  policy_number_masked?:string|null;insured_object?:any;
  source_document_id:string|null;source_document_name:string|null;
  source_document_ids?:string[];source_documents?:{id:string;file_name:string}[];linked_mortgage_ids?:string[];
  linked_payments:InsurancePayment[];linked_payment_count:number;linked_payments_last_365_total:string;
  contract:null|{
    provider_name:string;start_date?:string|null;renewal_date:string|null;cancellation_notice_days:number|null;
    permanence_end_date?:string|null;early_exit_penalty:string|null;annual_cost?:string|null;currency?:string;evidence_status:string
  };
  coverages:{id:string;coverage_type:string;limit_amount:string|null;deductible:string|null;confidence:string;user_verified:boolean;
    effective_from?:string|null;effective_to?:string|null;conditions?:any;exclusions?:any;source_document_id?:string|null;source_page:number|null}[];
};
type Missing={field:string;label:string;policy_id:string|null;document_id:string|null;why:string};
type PendingEvidence=Missing&{value:any;unit?:string|null;page?:number|null;source?:string|null;status?:string};
type Issue={code:string;severity:string;title:string;detail:string};
type Verdict={
  status:'insufficient_data'|'review_required'|'partial'|'consistent';summary:string;source_of_truth:string;
  policies:Policy[];
  coverage:{verified:number;requirements:number;gaps:{requirement_id:string;coverage_type:string;insurance_type:string|null;reason:string;minimum_limit:string|null;best_verified_limit?:string}[];covered:any[];overlaps:{id:string;coverage_type:string;left_id:string;right_id:string;overlap_type:string;confidence:string}[]};
  finances:{income_last_365_days:string;expenses_last_365_days:string;savings_last_365_days:string;documented_annual_premiums:string;premium_share_of_income:string|null;spend_reconciliation:{
    period_start:string;period_end:string;data_coverage_days:number;observed_insurance_spend:string;documented_annual_premiums:string;difference:string|null;comparison_reliable:boolean;
    linked_payment_count:number;unlinked_candidate_count:number;needs_attention:boolean;by_merchant:{merchant:string;amount:string}[];
    unlinked_transactions:{transaction_id:string;booking_date:string;description:string;merchant:string|null;amount:string;currency:string}[];
    policy_differences:{policy_id:string;insurance_type:string;provider:string|null;documented_annual_premium:string;linked_payments_total:string;difference:string;linked_payment_count:number}[]
  }};
  linked_products:{document_id:string;document_name:string|null;key:string;value:any;page:number|null}[];
  pending_review:PendingEvidence[];missing_information:Missing[];issues:Issue[];
  ai:null|{plain_summary?:string;priorities?:string[];questions?:string[];model?:string;error?:string};
};
type InsightItem={title:string;detail:string;pages:number[];impact?:string};
type InsightAnalysis={summary:string;confidence:string;advantages:InsightItem[];penalties:InsightItem[];obligations:InsightItem[];risks:InsightItem[];exclusions_or_limits:InsightItem[];linked_products:InsightItem[];optimization_opportunities:InsightItem[];negotiation_points:InsightItem[];comparison_requirements:InsightItem[];cross_area_impacts:InsightItem[];missing_information:InsightItem[]};
type DocInsight={document_id:string;file_name:string;document_type:string;analysis:InsightAnalysis};
type InsuranceMarketLead={
  source_id:string;provider:string;kind:string;insurance_type:string;status:string;url:string;retrieved_at:string;
  claims:string[];comparison_status:string;can_decide:boolean;missing_candidate_data:string[];
  current_policies:{policy_id:string;insurance_type:string;provider:string|null;annual_premium:string;deductible:string|null;renewal_date:string|null;cancellation_notice_days:number|null;exit_penalty:string|null;evidence_status:string|null;verified_coverage_count:number;linked_mortgage_ids:string[]}[];
  rule:string;
};
type InsuranceMarketScan={generated_at:string;insurance_leads:InsuranceMarketLead[];insurance_market_summary:{references:number;decision_ready:number;message:string}};
type InsightKey='advantages'|'penalties'|'obligations'|'risks'|'exclusions_or_limits'|'linked_products'|'optimization_opportunities'|'negotiation_points'|'comparison_requirements'|'cross_area_impacts'|'missing_information';

const statusText:Record<Verdict['status'],{title:string;detail:string}>={
  consistent:{title:'Datos consistentes',detail:'No hay huecos ni duplicidades materiales pendientes respecto a tus requisitos confirmados.'},
  review_required:{title:'Revisión necesaria',detail:'Hay diferencias, duplicidades o huecos que conviene resolver antes de tomar una decisión.'},
  partial:{title:'Análisis parcial',detail:'Los datos disponibles son útiles, pero faltan campos o criterios para cerrar la comparación.'},
  insufficient_data:{title:'Falta información',detail:'Aún no hay evidencia documental suficiente para analizar tus seguros.'},
};
const insuranceLabel:Record<string,string>={home:'Hogar',car:'Coche',life:'Vida',health:'Salud',pet:'Mascota',travel:'Viaje',other:'Otro',unknown:'Seguro'};

function readableDetail(value:any):string{
  if(value===null||value===undefined||value==='')return '—';
  if(Array.isArray(value))return value.length?value.map(readableDetail).join(' · '):'—';
  if(typeof value==='object'){
    const entries=Object.entries(value);
    return entries.length?entries.map(([key,item])=>key.replaceAll('_',' ')+': '+readableDetail(item)).join(' · '):'—';
  }
  if(typeof value==='boolean')return value?'Sí':'No';
  return String(value);
}

function PolicyInsightGroup({title,rows,field}:{title:string;rows:DocInsight[];field:InsightKey}){
  const items=rows.flatMap(row=>(row.analysis[field]||[]).map(item=>({item,documentId:row.document_id}))).slice(0,10);
  const tone: 'default'|'soft'|'brand'|'warning' =
    ['risks','penalties','exclusions_or_limits','missing_information'].includes(field)?'warning':
    ['advantages','optimization_opportunities','negotiation_points'].includes(field)?'brand':'soft';
  return <DetailGroup title={title} tone={tone}>
    <div className="space-y-2">{items.length?items.map(({item,documentId},i)=><div key={field+i} className="rounded-lg bg-white/70 p-2.5 text-xs">
      <div><strong>{item.title||item.detail}</strong>{item.title&&item.detail?<span> · {item.detail}</span>:null}</div>
      {item.impact&&<div className="mt-1 text-[var(--muted)]">{item.impact}</div>}
      {!!item.pages?.length&&<a className="mt-1 inline-block underline" target="_blank" rel="noreferrer" href={'/api/v1/documents/'+documentId+'/file#page='+item.pages[0]}>Ver evidencia · pág. {item.pages[0]}</a>}
    </div>):<span className="text-xs text-[var(--muted)]">Sin información específica extraída.</span>}</div>
  </DetailGroup>;
}


export default function InsurancePage(){
  const qc=useQueryClient();
  const profiles=useQuery({queryKey:['insurance'],queryFn:()=>apiGet<InsuranceProfile[]>('/api/v1/insurance')});
  const accounts=useQuery({queryKey:['accounts','insurance-link'],queryFn:()=>apiGet<Account[]>('/api/v1/accounts')});
  const mortgages=useQuery({queryKey:['mortgages'],queryFn:()=>apiGet<MortgageRef[]>('/api/v1/mortgages')});
  const verdict=useQuery({queryKey:['insurance-verdict'],queryFn:()=>apiGet<Verdict>('/api/v1/insurance/verdict')});
  const requirements=useQuery({queryKey:['coverage-requirements'],queryFn:()=>apiGet<CoverageRequirement[]>('/api/v1/coverage-requirements')});
  const insights=useQuery({queryKey:['document-insights','all'],queryFn:()=>apiGet<DocInsight[]>('/api/v1/document-insights')});
  const market=useQuery({queryKey:['insurance-market-references'],queryFn:()=>apiGet<InsuranceMarketScan>('/api/v1/decision-lab/market-scan'),enabled:false,retry:false});
  const analyze=useMutation({
    mutationFn:()=>apiMutate<Verdict>('/api/v1/insurance/verdict/analyze','POST'),
    onSuccess:()=>qc.invalidateQueries({queryKey:['insurance-verdict']}),
  });

  const emptyPolicy={account_id:'',provider_name:'',insurance_type:'home',annual_premium:'',deductible:'',policy_number_masked:'',renewal_date:'',cancellation_notice_days:'',early_exit_penalty:''};
  const [policyForm,setPolicyForm]=useState(emptyPolicy);
  const [editingPolicyId,setEditingPolicyId]=useState<string|null>(null);
  const [showPolicyForm,setShowPolicyForm]=useState(false);
  const [selectedPolicyId,setSelectedPolicyId]=useState<string|null>(null);
  const [documentPolicyId,setDocumentPolicyId]=useState<string|null>(null);
  const [detailSection,setDetailSection]=useState<'general'|'transactions'|'details'>('general');
  const [manualMissing,setManualMissing]=useState<Record<string,string>>({});

  useEffect(()=>{
    const requested=new URLSearchParams(window.location.search).get('policy');
    if(requested)setSelectedPolicyId(requested);
  },[]);
  useEffect(()=>{if(selectedPolicyId)setDetailSection('general')},[selectedPolicyId]);
  const [req,setReq]=useState({insurance_type:'',coverage_type:'',minimum_limit:'',notes:''});
  const refreshInsurance=()=>{
    qc.invalidateQueries({queryKey:['insurance']});
    qc.invalidateQueries({queryKey:['insurance-verdict']});
    qc.invalidateQueries({queryKey:['wealth-details']});
    qc.invalidateQueries({queryKey:['wealth-home']});
    qc.invalidateQueries({queryKey:['evidence-groups']});
  };
  const savePolicy=useMutation({
    mutationFn:()=>apiMutate<InsuranceProfile>(editingPolicyId?'/api/v1/insurance/'+editingPolicyId:'/api/v1/insurance',editingPolicyId?'PATCH':'POST',{
      account_id:policyForm.account_id||null,
      provider_name:policyForm.provider_name.trim()||null,
      insurance_type:policyForm.insurance_type,
      annual_premium:policyForm.annual_premium,
      deductible:policyForm.deductible||null,
      currency:'EUR',
      policy_number_masked:policyForm.policy_number_masked.trim()||null,
      renewal_date:policyForm.renewal_date||null,
      cancellation_notice_days:policyForm.cancellation_notice_days?Number(policyForm.cancellation_notice_days):null,
      early_exit_penalty:policyForm.early_exit_penalty||null,
      contract_id:null,
    }),
    onSuccess:()=>{setPolicyForm(emptyPolicy);setEditingPolicyId(null);setShowPolicyForm(false);refreshInsurance()},
  });
  const deletePolicy=useMutation({
    mutationFn:(id:string)=>apiMutate('/api/v1/insurance/'+id,'DELETE'),
    onSuccess:(_,id)=>{setEditingPolicyId(null);setShowPolicyForm(false);if(selectedPolicyId===id)setSelectedPolicyId(null);refreshInsurance()},
  });
  const analyzePolicyDocs=useMutation({
    mutationFn:(id:string)=>apiMutate('/api/v1/evidence-groups/insurance_policy/'+id+'/analyze','POST'),
    onSuccess:refreshInsurance,
  });
  const setMortgageLink=useMutation({
    mutationFn:({policyId,mortgageId,linked}:{policyId:string;mortgageId:string;linked:boolean})=>
      apiMutate('/api/v1/mortgages/'+mortgageId+'/insurance/'+policyId,linked?'PUT':'DELETE'),
    onSuccess:()=>{refreshInsurance();qc.invalidateQueries({queryKey:['mortgages']})},
  });
  const unlinkPayment=useMutation({
    mutationFn:(transactionId:string)=>apiMutate('/api/v1/transactions/'+transactionId+'/insurance','DELETE'),
    onSuccess:()=>{refreshInsurance();qc.invalidateQueries({queryKey:['transactions']})},
  });
  const linkPendingPayment=useMutation({
    mutationFn:({transactionId,policyId}:{transactionId:string;policyId:string})=>
      apiMutate('/api/v1/transactions/'+transactionId+'/insurance/'+policyId,'PUT'),
    onSuccess:()=>{refreshInsurance();qc.invalidateQueries({queryKey:['transactions']})},
  });
  const saveMissingPolicy=useMutation({
    mutationFn:({missing,value}:{missing:Missing;value:string})=>{
      if(!missing.policy_id)throw new Error('Este dato aún no está asociado a una póliza. Asocia primero el documento al seguro correcto.');
      const policy=data?.policies.find(p=>p.id===missing.policy_id);
      const profile=profiles.data?.find(p=>p.id===missing.policy_id);
      if(!policy)throw new Error('No se ha encontrado la póliza');
      const body:any={
        account_id:profile?.account_id||null,
        provider_name:policy.contract?.provider_name||profile?.provider_name||null,
        insurance_type:policy.insurance_type,
        annual_premium:policy.annual_premium,
        deductible:policy.deductible,
        currency:'EUR',
        policy_number_masked:profile?.policy_number_masked||null,
        renewal_date:policy.contract?.renewal_date||profile?.renewal_date||null,
        cancellation_notice_days:policy.contract?.cancellation_notice_days??profile?.cancellation_notice_days??null,
        early_exit_penalty:policy.contract?.early_exit_penalty||profile?.early_exit_penalty||null,
        contract_id:profile?.contract_id||null,
      };
      if(missing.field==='deductible')body.deductible=value||null;
      else if(missing.field==='renewal_date')body.renewal_date=value||null;
      else if(missing.field==='cancellation_notice_days')body.cancellation_notice_days=value?Number(value):null;
      else if(missing.field==='early_exit_penalty')body.early_exit_penalty=value||null;
      else if(missing.field==='annual_cost')body.annual_premium=value;
      else if(missing.field==='provider_name')body.provider_name=value;
      else throw new Error('Este dato se completa desde la documentación asociada o editando la póliza.');
      return apiMutate('/api/v1/insurance/'+missing.policy_id,'PATCH',body);
    },
    onSuccess:(_,vars)=>{setManualMissing(prev=>({...prev,[vars.missing.policy_id+':'+vars.missing.field]:''}));refreshInsurance()},
  });
  const editPolicy=(p:Policy)=>{
    const profile=profiles.data?.find(x=>x.id===p.id);
    setEditingPolicyId(p.id);setShowPolicyForm(true);
    setPolicyForm({
      account_id:profile?.account_id||'',
      provider_name:p.contract?.provider_name||profile?.provider_name||'',
      insurance_type:p.insurance_type,
      annual_premium:p.annual_premium,
      deductible:p.deductible||'',
      policy_number_masked:profile?.policy_number_masked||'',
      renewal_date:p.contract?.renewal_date||'',
      cancellation_notice_days:p.contract?.cancellation_notice_days===null||p.contract?.cancellation_notice_days===undefined?'':String(p.contract.cancellation_notice_days),
      early_exit_penalty:p.contract?.early_exit_penalty||'',
    });
  };

  const addReq=useMutation({
    mutationFn:()=>apiMutate('/api/v1/coverage-requirements','POST',{insurance_type:req.insurance_type||null,coverage_type:req.coverage_type,minimum_limit:req.minimum_limit||null,currency:'EUR',notes:req.notes||null,enabled:true}),
    onSuccess:()=>{setReq({insurance_type:'',coverage_type:'',minimum_limit:'',notes:''});qc.invalidateQueries({queryKey:['coverage-requirements']});qc.invalidateQueries({queryKey:['insurance-verdict']})},
  });
  const delReq=useMutation({
    mutationFn:(id:string)=>apiMutate('/api/v1/coverage-requirements/'+id,'DELETE'),
    onSuccess:()=>{qc.invalidateQueries({queryKey:['coverage-requirements']});qc.invalidateQueries({queryKey:['insurance-verdict']})},
  });

  const data=verdict.data;
  const status=data?statusText[data.status]:null;
  const selectedPolicy=data?.policies.find(p=>p.id===selectedPolicyId)||null;
  const selectedProfile=profiles.data?.find(p=>p.id===selectedPolicyId)||null;
  const selectedPending=selectedPolicy?data?.pending_review.filter(item=>item.policy_id===selectedPolicy.id)||[]:[];
  const selectedMissing=selectedPolicy?data?.missing_information.filter(item=>item.policy_id===selectedPolicy.id)||[]:[];
  const selectedPolicyDocuments=new Set(selectedPolicy?.source_document_ids||[]);
  const selectedInsightRows=selectedPolicy?(insights.data||[]).filter(item=>selectedPolicyDocuments.has(item.document_id)):[];

  return <>
    <PageHeader title="Seguros y coberturas" description="La fuente de verdad son tus documentos confirmados. Financito los cruza con movimientos, ingresos, coste, coberturas, duplicidades y productos vinculados antes de darte una conclusión."/>
    {data&&<div className="mb-4 flex flex-wrap gap-2">
      <DataStatus label="Evidencia contractual" detail={data.policies.length+' póliza(s) consolidadas'} tone={data.policies.length?'confirmed':'neutral'}/>
      <DataStatus label={data.pending_review.length?'Pendiente de confirmar':'Sin pendientes materiales'} detail={data.pending_review.length?data.pending_review.length+' dato(s) encontrado(s) por validar':'evidencia material revisada'} tone={data.pending_review.length?'pending':'confirmed'}/>
      <DataStatus label="Cruce calculado" detail="primas, movimientos, coberturas y vinculaciones" tone="calculated"/>
    </div>}

    {verdict.isLoading?<Loading/>:verdict.error?<ErrorState error={verdict.error}/>:data&&<>
      <SectionIntro eyebrow="Lectura rápida" title="Coste, cobertura y calidad de la evidencia" description="Primero la foto global; después cada póliza, pagos pendientes y documentación que falta."/>
      <VisualPanel title={status?.title||'Situación de tus seguros'} description={data.summary} eyebrow="Veredicto basado en evidencia" status={data.pending_review.length?'Hay datos pendientes':'Evidencia revisada'} statusTone={data.pending_review.length?'pending':'confirmed'} action={<div className="flex gap-2"><button className="fin-button secondary" type="button" onClick={()=>{setEditingPolicyId(null);setPolicyForm(emptyPolicy);setShowPolicyForm(v=>!v)}}>{showPolicyForm&&!editingPolicyId?'Cerrar alta':'Nuevo seguro'}</button><button className="fin-button" onClick={()=>analyze.mutate()} disabled={analyze.isPending}>{analyze.isPending?'Analizando con IA…':'Explicar con IA local'}</button></div>}>
        <p className="text-xs text-[var(--muted)]">{status?.detail} La IA, cuando se usa, solo explica el resultado; no sustituye los hechos confirmados.</p>
        {analyze.error&&<div className="mt-3"><ErrorState error={analyze.error}/></div>}
        {data.ai?.plain_summary&&<div className="mt-4 rounded-xl bg-[var(--brand-soft)] p-4 text-sm"><strong>Lectura de la IA local</strong><p className="mt-1">{data.ai.plain_summary}</p>{data.ai.priorities?.length?<div className="mt-2 text-xs"><strong>Prioridades:</strong> {data.ai.priorities.join(' · ')}</div>:null}{data.ai.questions?.length?<div className="mt-2 text-xs"><strong>Preguntas pendientes:</strong> {data.ai.questions.join(' · ')}</div>:null}<div className="mt-2 text-[11px] text-[var(--muted)]">Modelo: {data.ai.model}</div></div>}
        {data.ai?.error&&<div className="mt-3 text-xs text-[var(--muted)]">La IA local no pudo ampliar el análisis: {data.ai.error}. El veredicto determinista sigue disponible.</div>}
        {showPolicyForm&&<form className="mt-4 grid gap-2 rounded-xl border border-[var(--border)] p-4 sm:grid-cols-2" onSubmit={e=>{e.preventDefault();savePolicy.mutate()}}>
          <div className="sm:col-span-2 font-semibold">{editingPolicyId?'Editar seguro':'Crear seguro'}</div>
          <select className="fin-input" aria-label="Cuenta bancaria del seguro" value={policyForm.account_id} onChange={e=>setPolicyForm({...policyForm,account_id:e.target.value})} required><option value="">Cuenta bancaria del seguro…</option>{accounts.data?.map(account=><option key={account.id} value={account.id}>{account.institution_name} · {account.name}</option>)}</select>
          <input className="fin-input" placeholder="Aseguradora" value={policyForm.provider_name} onChange={e=>setPolicyForm({...policyForm,provider_name:e.target.value})}/>
          <select className="fin-input" value={policyForm.insurance_type} onChange={e=>setPolicyForm({...policyForm,insurance_type:e.target.value})}><option value="home">Hogar</option><option value="car">Coche</option><option value="life">Vida</option><option value="health">Salud</option><option value="pet">Mascota</option><option value="travel">Viaje</option><option value="other">Otro</option></select>
          <input className="fin-input" type="number" min="0" step=".01" placeholder="Prima anual (€)" value={policyForm.annual_premium} onChange={e=>setPolicyForm({...policyForm,annual_premium:e.target.value})} required/>
          <input className="fin-input" type="number" min="0" step=".01" placeholder="Franquicia (€)" value={policyForm.deductible} onChange={e=>setPolicyForm({...policyForm,deductible:e.target.value})}/>
          <input className="fin-input" placeholder="Nº póliza (opcional)" value={policyForm.policy_number_masked} onChange={e=>setPolicyForm({...policyForm,policy_number_masked:e.target.value})}/>
          <input className="fin-input" type="date" aria-label="Fecha renovación" value={policyForm.renewal_date} onChange={e=>setPolicyForm({...policyForm,renewal_date:e.target.value})}/>
          <input className="fin-input" type="number" min="0" step="1" placeholder="Preaviso cancelación (días)" value={policyForm.cancellation_notice_days} onChange={e=>setPolicyForm({...policyForm,cancellation_notice_days:e.target.value})}/>
          <input className="fin-input" type="number" min="0" step=".01" placeholder="Penalización salida (€)" value={policyForm.early_exit_penalty} onChange={e=>setPolicyForm({...policyForm,early_exit_penalty:e.target.value})}/>
          <div className="sm:col-span-2 flex gap-2"><button className="fin-button" disabled={savePolicy.isPending}>{savePolicy.isPending?'Guardando…':editingPolicyId?'Guardar cambios':'Crear seguro'}</button>{editingPolicyId&&<button className="fin-button secondary" type="button" onClick={()=>{setEditingPolicyId(null);setPolicyForm(emptyPolicy);setShowPolicyForm(false)}}>Cancelar</button>}</div>
          {savePolicy.error&&<div className="sm:col-span-2"><ErrorState error={savePolicy.error}/></div>}
        </form>}
      </VisualPanel>

      <div className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricTile label="Primas documentadas" value={<><Money value={data.finances.documented_annual_premiums}/><span className="text-base">/año</span></>} detail={data.policies.length+' póliza(s) registradas'} status="Documentado" statusTone="confirmed"/>
        <MetricTile label="Pagos observados" value={<Money value={data.finances.spend_reconciliation.observed_insurance_spend}/>} detail={data.finances.spend_reconciliation.period_start+' → '+data.finances.spend_reconciliation.period_end} status="Movimientos" statusTone="calculated"/>
        <MetricTile label="Peso sobre ingresos" value={data.finances.premium_share_of_income===null?'—':(Number(data.finances.premium_share_of_income)*100).toLocaleString('es-ES',{maximumFractionDigits:1})+'%'} detail="Primas equivalentes / ingresos del periodo"/>
        <MetricTile label="Coberturas verificadas" value={data.coverage.verified} detail={data.coverage.gaps.length+' hueco(s) · '+data.coverage.overlaps.length+' posible(s) duplicidad(es)'} status={data.coverage.gaps.length?'Revisar':'Verificadas'} statusTone={data.coverage.gaps.length?'pending':'confirmed'} emphasis={data.coverage.gaps.length>0}/>
      </div>

      <div className="mt-6"><SectionIntro eyebrow="Detalle" title="Pólizas consolidadas" description="Una póliza puede tener varios PDFs, anexos o condiciones. Financito los reúne en una sola ficha."/></div>
      <VisualPanel title="Tus pólizas" description="Abre una ficha para ver coste, pagos, coberturas, riesgos, obligaciones, oportunidades y evidencia en una sola vista.">
        <div className="mt-4 grid gap-3 md:grid-cols-2 lg:grid-cols-3">{data.policies.length?data.policies.map(p=><div key={p.id} onClick={()=>setSelectedPolicyId(p.id)} className="cursor-pointer rounded-xl bg-[var(--surface-2)] p-4 hover:ring-1 hover:ring-[var(--brand)]">
          <div className="flex items-start justify-between gap-3"><div><strong>{insuranceLabel[p.insurance_type]||p.insurance_type}</strong><div className="text-xs text-[var(--muted)]">{p.contract?.provider_name||p.source_document_name||'Proveedor pendiente'}</div></div><strong className="shrink-0"><Money value={p.annual_premium}/>/año</strong></div>
          <div className="mt-3 grid gap-1 text-xs">
            <div>Mensual equivalente: <strong><Money value={p.monthly_equivalent}/></strong></div>
            <div>Franquicia: <strong><Money value={p.deductible}/></strong></div>
            <div>Renovación: <strong>{p.contract?.renewal_date?new Date(p.contract.renewal_date).toLocaleDateString('es-ES'):'—'}</strong></div>
            <div>Pagos vinculados: <strong>{p.linked_payment_count}</strong></div>
          </div>
          {!!p.linked_mortgage_ids?.length&&<div className="mt-2 text-xs font-medium text-[var(--brand)]">Vinculado a {p.linked_mortgage_ids.length} hipoteca(s)</div>}
          <div className="mt-3 flex flex-wrap gap-2">
            <button className="fin-button secondary py-1.5 text-xs" type="button" onClick={e=>{e.stopPropagation();setSelectedPolicyId(p.id)}}>Ver detalle</button>
            <button className="text-xs underline" type="button" onClick={e=>{e.stopPropagation();editPolicy(p);setSelectedPolicyId(p.id)}}>Editar</button>
            <button className="text-xs underline" type="button" onClick={e=>{e.stopPropagation();if(window.confirm('¿Eliminar este seguro? Los documentos no se borrarán del Vault.'))deletePolicy.mutate(p.id)}}>Eliminar</button>
          </div>
        </div>):<EmptyState>Crea tu primer seguro y después asocia su documentación desde la propia póliza.</EmptyState>}</div>
      </VisualPanel>

      <VisualPanel className="mt-4" title="Comparar seguros con el mercado" description="Las referencias públicas solo sirven para descubrir alternativas. La decisión exige precio y cobertura personalizados." action={<button className="fin-button" type="button" onClick={()=>market.refetch()} disabled={market.isFetching}>{market.isFetching?'Consultando…':'Buscar alternativas públicas'}</button>}>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="text-xs text-[var(--muted)]">Una web genérica nunca se considera mejor que tu póliza sin precio personalizado, franquicia, coberturas, límites, exclusiones y cancelación equivalentes.</div>
        </div>
        {market.error&&<div className="mt-3"><ErrorState error={market.error}/></div>}
        {market.data&&<>
          <div className="mt-4 rounded-xl bg-[var(--brand-soft)] p-3 text-sm"><strong>{market.data.insurance_market_summary.references} referencia(s) oficial(es) localizada(s)</strong><div className="mt-1 text-xs">{market.data.insurance_market_summary.message}</div></div>
          <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-3">{market.data.insurance_leads.length?market.data.insurance_leads.map(lead=><div key={lead.source_id} className="rounded-xl border border-[var(--border)] p-4 text-sm">
            <div className="flex items-start justify-between gap-3"><div><strong>{lead.provider}</strong><div className="text-xs text-[var(--muted)]">{insuranceLabel[lead.insurance_type]||lead.insurance_type} · referencia pública</div></div><span className="rounded-full bg-[var(--surface-2)] px-2 py-1 text-[10px] font-semibold uppercase text-[var(--muted)]">Falta oferta</span></div>
            {lead.current_policies.length>0&&<div className="mt-3 rounded-lg bg-[var(--surface-2)] p-3 text-xs"><strong>Tu punto de partida</strong>{lead.current_policies.map(policy=><div key={policy.policy_id} className="mt-1">{policy.provider||insuranceLabel[policy.insurance_type]||'Seguro'} · <Money value={policy.annual_premium}/>/año · {policy.verified_coverage_count} cobertura(s) verificada(s){policy.linked_mortgage_ids.length?' · vinculada a hipoteca':''}</div>)}</div>}
            <div className="mt-3 text-xs"><strong>Para poder decidir:</strong> prima y franquicia personalizadas, coberturas/límites equivalentes, exclusiones, cancelación y costes de entrada. Si tu póliza bonifica una hipoteca, también se suma la pérdida de esa bonificación.</div>
            <a className="mt-3 inline-block text-xs underline" href={lead.url} target="_blank" rel="noreferrer">Abrir fuente oficial</a>
          </div>):<EmptyState>No se han podido recuperar referencias públicas de seguros en esta consulta.</EmptyState>}</div>
          <div className="mt-3 text-[11px] text-[var(--muted)]">Consulta realizada bajo demanda. No se envían tus pólizas ni tus datos privados a estas páginas.</div>
        </>}
      </VisualPanel>

      {data.finances.spend_reconciliation.needs_attention&&<Card className="mt-4">
        <h2 className="font-bold">Pagos de seguros por revisar</h2>
        <p className="mt-1 text-sm text-[var(--muted)]">Este bloque solo aparece cuando queda algo accionable: un cargo clasificado como seguro sin póliza asociada o una diferencia relevante entre la prima documentada y los pagos que has vinculado.</p>
        {data.finances.spend_reconciliation.unlinked_transactions.length>0&&<div className="mt-4">
          <h3 className="text-sm font-semibold">Movimientos sin vincular</h3>
          <div className="mt-2 space-y-2">{data.finances.spend_reconciliation.unlinked_transactions.map(tx=><div key={tx.transaction_id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-[var(--surface-2)] p-3 text-sm">
            <div><strong>{tx.merchant||tx.description}</strong><div className="text-xs text-[var(--muted)]">{new Date(tx.booking_date).toLocaleDateString('es-ES')} · {tx.description}</div></div>
            <div className="flex flex-wrap items-center gap-3">
              <strong><Money value={tx.amount} currency={tx.currency}/></strong>
              <select className="fin-input min-w-56 py-1.5 text-xs" aria-label={'Vincular '+tx.description+' a seguro'} defaultValue="" disabled={linkPendingPayment.isPending} onChange={e=>{if(e.target.value)linkPendingPayment.mutate({transactionId:tx.transaction_id,policyId:e.target.value})}}>
                <option value="">Vincular a póliza…</option>
                {data.policies.map(policy=><option key={policy.id} value={policy.id}>{policy.contract?.provider_name||insuranceLabel[policy.insurance_type]||'Seguro'} · {insuranceLabel[policy.insurance_type]||policy.insurance_type}</option>)}
              </select>
            </div>
          </div>)}</div>
        </div>}
        {linkPendingPayment.error&&<div className="mt-3"><ErrorState error={linkPendingPayment.error}/></div>}
        {data.finances.spend_reconciliation.policy_differences.length>0&&<div className="mt-4">
          <h3 className="text-sm font-semibold">Pólizas con diferencia</h3>
          <div className="mt-2 grid gap-2 md:grid-cols-2">{data.finances.spend_reconciliation.policy_differences.map(item=><button key={item.policy_id} type="button" onClick={()=>setSelectedPolicyId(item.policy_id)} className="rounded-xl bg-[var(--surface-2)] p-3 text-left text-sm">
            <strong>{item.provider||insuranceLabel[item.insurance_type]||item.insurance_type}</strong>
            <div className="mt-1 text-xs">Prima: <Money value={item.documented_annual_premium}/> · pagos vinculados: <Money value={item.linked_payments_total}/></div>
            <div className="mt-1 text-xs text-[var(--muted)]">Diferencia: <Money value={item.difference}/> · {item.linked_payment_count} pago(s)</div>
          </button>)}</div>
        </div>}
      </Card>}

      {data.pending_review?.length>0&&<Card className="mt-4">
        <div><h2 className="font-bold">Datos encontrados pendientes de validar</h2><p className="mt-1 text-sm text-[var(--muted)]">La IA local o el extractor ya han localizado estos datos. No hace falta volver a introducirlos: entra en la documentación de la póliza indicada y confirma la evidencia.</p></div>
        <div className="mt-4 grid gap-3 md:grid-cols-2">{data.pending_review.map((m,i)=><div key={(m.document_id||m.policy_id||'x')+m.field+i} className="rounded-xl bg-[var(--brand-soft)] p-3 text-sm"><strong>{m.label}</strong><div className="mt-1 text-xs">{String(m.value??'Dato localizado')}{m.unit?' '+m.unit:''}</div><div className="mt-1 text-xs text-[var(--muted)]">{m.why}</div>{m.policy_id?<Link className="mt-2 inline-block text-xs underline" href={'/documents/?entity_type=insurance_policy&entity_id='+encodeURIComponent(m.policy_id)+'&label='+encodeURIComponent('Seguro')+(m.document_id?'&document='+encodeURIComponent(m.document_id):'')}>Revisar documentación{m.page?' · pág. '+m.page:''}</Link>:m.document_id&&<Link className="mt-2 inline-block text-xs underline" href={'/documents/?document='+encodeURIComponent(m.document_id)}>Revisar evidencia{m.page?' · pág. '+m.page:''}</Link>}</div>)}</div>
      </Card>}

      <Card className="mt-4">
        <div><h2 className="font-bold">Información que falta</h2><p className="mt-1 text-sm text-[var(--muted)]">Para cada póliza Financito intenta primero localizar el dato con la IA local en su documentación. Si no aparece, puedes introducirlo aquí manualmente y después editarlo desde las opciones del seguro.</p></div>
        <div className="mt-4 grid gap-3 md:grid-cols-2">{data.missing_information.length?data.missing_information.map((m,i)=>{
          const key=(m.policy_id||m.document_id||'x')+':'+m.field;
          const supportsManual=!!m.policy_id&&['deductible','renewal_date','cancellation_notice_days','early_exit_penalty','annual_cost','provider_name'].includes(m.field);
          return <div key={key+i} className="rounded-xl bg-[var(--surface-2)] p-3 text-sm">
            <strong>{m.label}</strong><div className="mt-1 text-xs text-[var(--muted)]">{m.why}</div>
            {m.policy_id&&<div className="mt-2 flex flex-wrap gap-2"><button className="fin-button secondary py-1.5 text-xs" type="button" onClick={()=>analyzePolicyDocs.mutate(m.policy_id!)} disabled={analyzePolicyDocs.isPending}>Intentar completar con IA</button><Link className="fin-button secondary py-1.5 text-xs" href={'/documents/?entity_type=insurance_policy&entity_id='+encodeURIComponent(m.policy_id)+'&label='+encodeURIComponent('Seguro')}>Documentación</Link></div>}
            {supportsManual&&<div className="mt-3 flex gap-2">
              <input className="fin-input flex-1" type={m.field==='renewal_date'?'date':m.field==='provider_name'?'text':'number'} step={m.field==='cancellation_notice_days'?'1':'.01'} placeholder={'Completar '+m.label.toLowerCase()} value={manualMissing[key]||''} onChange={e=>setManualMissing({...manualMissing,[key]:e.target.value})}/>
              <button className="fin-button" type="button" disabled={!manualMissing[key]||saveMissingPolicy.isPending} onClick={()=>saveMissingPolicy.mutate({missing:m,value:manualMissing[key]||''})}>Guardar</button>
            </div>}
            {!m.policy_id&&m.document_id&&<Link className="mt-2 inline-block text-xs underline" href={'/documents/?document='+encodeURIComponent(m.document_id)}>Asociar este documento a un seguro</Link>}
          </div>;
        }):<EmptyState>No faltan campos documentales básicos para las pólizas proyectadas.</EmptyState>}</div>
        {(analyzePolicyDocs.error||saveMissingPolicy.error)&&<div className="mt-3"><ErrorState error={(analyzePolicyDocs.error||saveMissingPolicy.error)!}/></div>}
      </Card>
    </>}

      {selectedPolicy&&<div className="fixed inset-0 z-50 overflow-y-auto bg-black/45 p-4 md:p-8" role="dialog" aria-modal="true" aria-label="Detalle del seguro">
        <div className="mx-auto max-w-5xl">
          <Card>
            <ModalHero
              eyebrow="Seguro"
              title={insuranceLabel[selectedPolicy.insurance_type]||selectedPolicy.insurance_type}
              description={(selectedPolicy.contract?.provider_name||selectedProfile?.provider_name||'Proveedor pendiente')+(selectedPolicy.policy_number_masked?' · póliza '+selectedPolicy.policy_number_masked:'')}
              status={selectedPolicy.contract?.evidence_status==='confirmed'?'Evidencia confirmada':'Revisar evidencia'}
              statusTone={selectedPolicy.contract?.evidence_status==='confirmed'?'confirmed':'pending'}
              actions={<button className="fin-button secondary py-2 text-xs" type="button" onClick={()=>setSelectedPolicyId(null)}>Cerrar</button>}
              metrics={[
                {label:'Prima anual',value:<Money value={selectedPolicy.annual_premium}/>},
                {label:'Mensual',value:<Money value={selectedPolicy.monthly_equivalent}/>},
                {label:'Franquicia',value:<Money value={selectedPolicy.deductible}/>},
                {label:'Renovación',value:selectedPolicy.contract?.renewal_date||'—',detail:selectedPolicy.linked_payment_count+' pago(s) vinculados'},
              ]}
            />

            <div className="mt-5 flex flex-wrap gap-2 border-b border-[var(--border)] pb-3" role="tablist" aria-label="Secciones del seguro">
              {([
                ['general','General'],
                ['transactions','Transacciones'],
                ['details','Detalles'],
              ] as const).map(([key,label])=><button key={key} role="tab" aria-selected={detailSection===key} type="button" className={detailSection===key?'fin-button py-2 text-xs':'fin-button secondary py-2 text-xs'} onClick={()=>setDetailSection(key)}>{label}</button>)}
            </div>

            {detailSection==='general'&&<>
              <div className="mt-4 grid gap-3 md:grid-cols-2">
                <DetailGroup title="Identificación" description="Datos de la póliza y su vinculación bancaria."><div className="space-y-2 text-sm"><div>Aseguradora: <strong>{selectedPolicy.contract?.provider_name||selectedProfile?.provider_name||'—'}</strong></div><div>Cuenta bancaria: <strong>{selectedProfile?.account_id?(selectedProfile.account_institution||'Banco')+' · '+(selectedProfile.account_name||'Cuenta'):'Sin vincular'}</strong></div><div>Nº póliza: <strong>{selectedPolicy.policy_number_masked||selectedProfile?.policy_number_masked||'—'}</strong></div><div>Tipo: <strong>{insuranceLabel[selectedPolicy.insurance_type]||selectedPolicy.insurance_type}</strong></div><div>Documentos: <strong>{selectedPolicy.source_documents?.length||0}</strong></div></div></DetailGroup>
                <DetailGroup title="Situación" description="Renovación, evidencia y relaciones con otros productos."><div className="space-y-2 text-sm"><div>Renovación: <strong>{selectedPolicy.contract?.renewal_date||'—'}</strong></div><div>Evidencia: <strong>{selectedPolicy.contract?.evidence_status||'Sin contrato consolidado'}</strong></div><div>Hipotecas vinculadas: <strong>{selectedPolicy.linked_mortgage_ids?.length||0}</strong></div><div>Objeto asegurado: <strong>{readableDetail(selectedPolicy.insured_object)}</strong></div></div></DetailGroup>
              </div>

              {editingPolicyId===selectedPolicy.id&&showPolicyForm&&<form className="mt-5 grid gap-2 rounded-xl border border-[var(--border)] p-4 sm:grid-cols-2" onSubmit={e=>{e.preventDefault();savePolicy.mutate()}}>
                <div className="sm:col-span-2"><h3 className="font-semibold">Editar seguro</h3><p className="mt-1 text-xs text-[var(--muted)]">Actualiza solo los datos que conoces. La documentación sigue siendo la fuente de verdad de las condiciones extraídas.</p></div>
                <select className="fin-input" aria-label="Cuenta bancaria del seguro" value={policyForm.account_id} onChange={e=>setPolicyForm({...policyForm,account_id:e.target.value})} required><option value="">Cuenta bancaria del seguro…</option>{accounts.data?.map(account=><option key={account.id} value={account.id}>{account.institution_name} · {account.name}</option>)}</select>
          <input className="fin-input" placeholder="Aseguradora" value={policyForm.provider_name} onChange={e=>setPolicyForm({...policyForm,provider_name:e.target.value})}/>
                <select className="fin-input" value={policyForm.insurance_type} onChange={e=>setPolicyForm({...policyForm,insurance_type:e.target.value})}><option value="home">Hogar</option><option value="car">Coche</option><option value="life">Vida</option><option value="health">Salud</option><option value="pet">Mascota</option><option value="travel">Viaje</option><option value="other">Otro</option></select>
                <input className="fin-input" type="number" min="0" step=".01" placeholder="Prima anual (€)" value={policyForm.annual_premium} onChange={e=>setPolicyForm({...policyForm,annual_premium:e.target.value})} required/>
                <input className="fin-input" type="number" min="0" step=".01" placeholder="Franquicia (€)" value={policyForm.deductible} onChange={e=>setPolicyForm({...policyForm,deductible:e.target.value})}/>
                <input className="fin-input" placeholder="Nº póliza" value={policyForm.policy_number_masked} onChange={e=>setPolicyForm({...policyForm,policy_number_masked:e.target.value})}/>
                <input className="fin-input" type="date" aria-label="Fecha renovación en detalle" value={policyForm.renewal_date} onChange={e=>setPolicyForm({...policyForm,renewal_date:e.target.value})}/>
                <input className="fin-input" type="number" min="0" step="1" placeholder="Preaviso cancelación (días)" value={policyForm.cancellation_notice_days} onChange={e=>setPolicyForm({...policyForm,cancellation_notice_days:e.target.value})}/>
                <input className="fin-input" type="number" min="0" step=".01" placeholder="Penalización salida (€)" value={policyForm.early_exit_penalty} onChange={e=>setPolicyForm({...policyForm,early_exit_penalty:e.target.value})}/>
                <div className="sm:col-span-2 flex gap-2"><button className="fin-button" disabled={savePolicy.isPending}>{savePolicy.isPending?'Guardando…':'Guardar cambios'}</button><button className="fin-button secondary" type="button" onClick={()=>{setEditingPolicyId(null);setShowPolicyForm(false)}}>Cancelar</button></div>
                {savePolicy.error&&<div className="sm:col-span-2"><ErrorState error={savePolicy.error}/></div>}
              </form>}
            </>}

            {detailSection==='transactions'&&<DetailGroup title="Transacciones del seguro" description="Pagos bancarios vinculados explícitamente a esta póliza. No crean un segundo gasto." className="mt-4">
              <div className="flex justify-end"><Link className="text-xs underline" href="/transactions/">Ir a Movimientos</Link></div>
              <div className="mt-3 space-y-2">{selectedPolicy.linked_payments.length?selectedPolicy.linked_payments.map(payment=><div key={payment.transaction_id} className="flex flex-wrap items-center justify-between gap-3 rounded-lg bg-[var(--surface-2)] p-3 text-sm">
                <div><strong>{payment.merchant||payment.description}</strong><div className="mt-0.5 text-xs text-[var(--muted)]">{new Date(payment.booking_date).toLocaleDateString('es-ES')} · {payment.description}{payment.account_name?' · '+payment.account_name:''}{payment.institution_name?' · '+payment.institution_name:''}</div></div>
                <div className="text-right"><strong><Money value={payment.amount} currency={payment.currency}/></strong><div><button className="mt-1 text-xs underline" type="button" disabled={unlinkPayment.isPending} onClick={()=>unlinkPayment.mutate(payment.transaction_id)}>Desvincular</button></div></div>
              </div>):<EmptyState>No hay pagos vinculados todavía. Puedes vincularlos desde Movimientos o desde los pagos pendientes de esta misma pantalla.</EmptyState>}</div>
              {unlinkPayment.error&&<div className="mt-3"><ErrorState error={unlinkPayment.error}/></div>}
            </DetailGroup>}

            {detailSection==='details'&&<>
              <div className="mt-4 rounded-xl border border-[var(--border)] p-4">
                <h3 className="font-semibold">Vinculación con hipoteca</h3>
                <p className="mt-1 text-xs text-[var(--muted)]">Marca qué pólizas forman parte de las condiciones de cada hipoteca. El vínculo no inventa una subida del TIN: solo se usa un impacto cuando está confirmado documentalmente.</p>
                <div className="mt-3 grid gap-2 sm:grid-cols-2">{mortgages.data?.length?mortgages.data.map(m=>{
                  const checked=!!selectedPolicy.linked_mortgage_ids?.includes(m.id);
                  return <label key={m.id} className="flex cursor-pointer items-center gap-3 rounded-lg bg-[var(--surface-2)] p-3 text-sm">
                    <input type="checkbox" checked={checked} disabled={setMortgageLink.isPending} onChange={e=>setMortgageLink.mutate({policyId:selectedPolicy.id,mortgageId:m.id,linked:e.target.checked})}/>
                    <span><strong>{m.lender}</strong><span className="block text-xs text-[var(--muted)]"><Money value={m.remaining_principal}/> pendientes</span></span>
                  </label>;
                }):<EmptyState>No hay hipotecas creadas. Crea primero la hipoteca en Casa.</EmptyState>}</div>
                {setMortgageLink.error&&<div className="mt-3"><ErrorState error={setMortgageLink.error}/></div>}
              </div>

              <div className="mt-4 grid gap-4 lg:grid-cols-2">
                <div className="rounded-xl border border-[var(--border)] p-4">
                  <h3 className="font-semibold">Condiciones contractuales</h3>
                  <div className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
                    <div>Inicio: <strong>{selectedPolicy.contract?.start_date||'—'}</strong></div>
                    <div>Renovación: <strong>{selectedPolicy.contract?.renewal_date||'—'}</strong></div>
                    <div>Preaviso: <strong>{selectedPolicy.contract?.cancellation_notice_days==null?'—':selectedPolicy.contract.cancellation_notice_days+' días'}</strong></div>
                    <div>Fin permanencia: <strong>{selectedPolicy.contract?.permanence_end_date||'—'}</strong></div>
                    <div>Penalización salida: <strong><Money value={selectedPolicy.contract?.early_exit_penalty}/></strong></div>
                    <div>Coste contractual anual: <strong><Money value={selectedPolicy.contract?.annual_cost||selectedPolicy.annual_premium}/></strong></div>
                  </div>
                </div>
                <div className="rounded-xl border border-[var(--border)] p-4">
                  <h3 className="font-semibold">Documentación</h3>
                  <p className="mt-1 text-xs text-[var(--muted)]">La lectura de los documentos se concentra aquí, dentro de la póliza.</p>
                  <div className="mt-3 space-y-2">{selectedPolicy.source_documents?.length?selectedPolicy.source_documents.map(doc=><button key={doc.id} type="button" onClick={()=>setDocumentPolicyId(selectedPolicy.id)} className="block w-full rounded-xl bg-[var(--surface-2)] p-3 text-left text-sm underline">{doc.file_name}</button>):<EmptyState>Esta póliza no tiene documentos asociados todavía.</EmptyState>}</div>
                  <button className="fin-button secondary mt-3 py-1.5 text-xs" type="button" onClick={()=>setDocumentPolicyId(selectedPolicy.id)}>Gestionar documentación</button>
                </div>
              </div>

              <div className="mt-5">
                <h3 className="font-semibold">Coberturas, límites y exclusiones</h3>
                <div className="mt-3 space-y-3">{selectedPolicy.coverages.length?selectedPolicy.coverages.map(coverage=><div key={coverage.id} className="rounded-xl bg-[var(--surface-2)] p-4 text-sm">
                  <div className="flex flex-wrap items-start justify-between gap-3"><strong>{coverage.coverage_type}</strong><span className="text-xs text-[var(--muted)]">{coverage.user_verified?'Verificada':'Pendiente de validar'} · confianza {Math.round(Number(coverage.confidence||0)*100)}%</span></div>
                  <div className="mt-2 grid gap-2 sm:grid-cols-2"><div>Límite: <strong><Money value={coverage.limit_amount}/></strong></div><div>Franquicia: <strong><Money value={coverage.deductible}/></strong></div><div>Vigencia desde: <strong>{coverage.effective_from||'—'}</strong></div><div>Vigencia hasta: <strong>{coverage.effective_to||'—'}</strong></div></div>
                  <div className="mt-3 text-xs"><strong>Condiciones:</strong> {readableDetail(coverage.conditions)}</div>
                  <div className="mt-2 text-xs"><strong>Exclusiones:</strong> {readableDetail(coverage.exclusions)}</div>
                  {coverage.source_document_id&&<a className="mt-2 inline-block text-xs underline" target="_blank" rel="noreferrer" href={'/api/v1/documents/'+coverage.source_document_id+'/file'+(coverage.source_page?'#page='+coverage.source_page:'')}>Ver en el documento{coverage.source_page?' · pág. '+coverage.source_page:''}</a>}
                </div>):<EmptyState>No hay coberturas verificadas o extraídas para esta póliza.</EmptyState>}</div>
              </div>

              <div className="mt-5">
                <h3 className="font-semibold">Lectura de la documentación</h3>
                <p className="mt-1 text-xs text-[var(--muted)]">Toda la interpretación extraída de los documentos asociados a esta póliza.</p>
                <div className="mt-3 grid gap-3 md:grid-cols-2">
                  <PolicyInsightGroup title="Ventajas y coberturas útiles" rows={selectedInsightRows} field="advantages"/>
                  <PolicyInsightGroup title="Penalizaciones y costes de salida" rows={selectedInsightRows} field="penalties"/>
                  <PolicyInsightGroup title="Obligaciones" rows={selectedInsightRows} field="obligations"/>
                  <PolicyInsightGroup title="Riesgos" rows={selectedInsightRows} field="risks"/>
                  <PolicyInsightGroup title="Exclusiones o límites" rows={selectedInsightRows} field="exclusions_or_limits"/>
                  <PolicyInsightGroup title="Productos vinculados" rows={selectedInsightRows} field="linked_products"/>
                  <PolicyInsightGroup title="Oportunidades de optimizar" rows={selectedInsightRows} field="optimization_opportunities"/>
                  <PolicyInsightGroup title="Puntos para negociar" rows={selectedInsightRows} field="negotiation_points"/>
                  <PolicyInsightGroup title="Qué exigir para comparar ofertas" rows={selectedInsightRows} field="comparison_requirements"/>
                  <PolicyInsightGroup title="Impactos en otras áreas" rows={selectedInsightRows} field="cross_area_impacts"/>
                  <PolicyInsightGroup title="Información que falta" rows={selectedInsightRows} field="missing_information"/>
                </div>
              </div>

              {(selectedPending.length>0||selectedMissing.length>0)&&<div className="mt-5 grid gap-4 lg:grid-cols-2">
                <div><h3 className="font-semibold">Datos encontrados pendientes</h3><div className="mt-2 space-y-2">{selectedPending.length?selectedPending.map((item,i)=><div key={item.field+i} className="rounded-xl bg-[var(--brand-soft)] p-3 text-xs"><strong>{item.label}</strong><div className="mt-1">{readableDetail(item.value)}{item.unit?' '+item.unit:''}</div></div>):<EmptyState>Sin datos pendientes.</EmptyState>}</div></div>
                <div><h3 className="font-semibold">Información que todavía falta</h3><div className="mt-2 space-y-2">{selectedMissing.length?selectedMissing.map((item,i)=><div key={item.field+i} className="rounded-xl bg-[var(--surface-2)] p-3 text-xs"><strong>{item.label}</strong><div className="mt-1 text-[var(--muted)]">{item.why}</div></div>):<EmptyState>No faltan campos básicos.</EmptyState>}</div></div>
              </div>}
            </>}

            <div className="mt-5 flex flex-wrap gap-2 border-t border-[var(--border)] pt-4">
              <button className="fin-button" type="button" onClick={()=>{editPolicy(selectedPolicy);setDetailSection('general')}}>Editar seguro</button>
              <button className="fin-button secondary" type="button" onClick={()=>analyzePolicyDocs.mutate(selectedPolicy.id)} disabled={analyzePolicyDocs.isPending}>Buscar datos con IA</button>
              <button className="fin-button secondary" type="button" disabled={deletePolicy.isPending} onClick={()=>{if(window.confirm('¿Eliminar este seguro? La ficha, coberturas y vínculos se borrarán. Los archivos permanecerán en Documentación sin recrear automáticamente la póliza.'))deletePolicy.mutate(selectedPolicy.id)}}>{deletePolicy.isPending?'Eliminando…':'Eliminar seguro'}</button>
            </div>
          </Card>
        </div>
      </div>}

    <Card className="mt-4">
      <h2 className="font-bold">Qué cobertura consideras necesaria</h2>
      <p className="mt-1 text-sm text-[var(--muted)]">Estos requisitos son criterios tuyos, no una segunda fuente de hechos sobre la póliza. Sirven para que Financito pueda decir si la documentación acredita lo que necesitas.</p>
      <form className="mt-3 grid gap-2 md:grid-cols-4" onSubmit={(e:FormEvent)=>{e.preventDefault();addReq.mutate()}}>
        <select className="fin-input" aria-label="Tipo de seguro requerido" value={req.insurance_type} onChange={e=>setReq({...req,insurance_type:e.target.value})}><option value="">Cualquier póliza</option><option value="home">Hogar</option><option value="car">Coche</option><option value="life">Vida</option><option value="health">Salud</option><option value="pet">Mascota</option></select>
        <input className="fin-input" placeholder="Cobertura requerida" value={req.coverage_type} onChange={e=>setReq({...req,coverage_type:e.target.value})} required/>
        <input className="fin-input" placeholder="Límite mínimo opcional" value={req.minimum_limit} onChange={e=>setReq({...req,minimum_limit:e.target.value})}/>
        <input className="fin-input" placeholder="Notas" value={req.notes} onChange={e=>setReq({...req,notes:e.target.value})}/>
        <button className="fin-button md:col-span-4">Añadir criterio</button>
      </form>
      <div className="mt-4 grid gap-2 md:grid-cols-2">{requirements.data?.length?requirements.data.map(r=><div key={r.id} className="flex justify-between rounded-xl bg-[var(--surface-2)] p-3 text-sm"><div><strong>{r.coverage_type}</strong><div className="text-xs text-[var(--muted)]">{r.insurance_type?insuranceLabel[r.insurance_type]||r.insurance_type:'cualquier póliza'}{r.minimum_limit?' · mínimo '+new Intl.NumberFormat('es-ES',{style:'currency',currency:r.currency}).format(Number(r.minimum_limit)):''}</div></div><button className="text-xs underline" onClick={()=>delReq.mutate(r.id)}>Eliminar</button></div>):<EmptyState>Sin criterios definidos. Mientras estén vacíos, Financito puede detectar incoherencias y duplicidades, pero no afirmar que tu cobertura sea suficiente.</EmptyState>}</div>
    </Card>

    {documentPolicyId&&<EntityDocumentsModal open={!!documentPolicyId} onClose={()=>setDocumentPolicyId(null)} entityType="insurance_policy" entityId={documentPolicyId} documentType="insurance" title={'Documentos del seguro · '+(data?.policies.find(p=>p.id===documentPolicyId)?.contract?.provider_name||insuranceLabel[data?.policies.find(p=>p.id===documentPolicyId)?.insurance_type||'unknown']||'Seguro')}/>}
  </>;
}
