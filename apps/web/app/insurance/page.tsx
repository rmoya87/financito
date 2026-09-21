'use client';

import Link from 'next/link';
import {FormEvent,useState} from 'react';
import {useMutation,useQuery,useQueryClient} from '@tanstack/react-query';
import {apiGet,apiMutate} from '@/lib/api';
import {PageHeader} from '@/components/page-header';
import {Card} from '@/components/ui/card';
import {Money} from '@/components/ui/money';
import {EmptyState,ErrorState,Loading} from '@/components/ui/states';

type CoverageRequirement={id:string;insurance_type:string|null;coverage_type:string;minimum_limit:string|null;currency:string;notes:string|null;enabled:boolean};
type InsuranceProfile={id:string;insurance_type:string;annual_premium:string;deductible:string|null;currency:string;policy_number_masked?:string|null;contract_id:string|null;provider_name?:string|null;renewal_date?:string|null;cancellation_notice_days?:number|null;early_exit_penalty?:string|null;document_count?:number;source_document_ids?:string[]};
type Policy={
  id:string;insurance_type:string;annual_premium:string;monthly_equivalent:string;deductible:string|null;
  source_document_id:string|null;source_document_name:string|null;
  source_document_ids?:string[];source_documents?:{id:string;file_name:string}[];
  contract:null|{provider_name:string;renewal_date:string|null;cancellation_notice_days:number|null;early_exit_penalty:string|null;evidence_status:string};
  coverages:{id:string;coverage_type:string;limit_amount:string|null;deductible:string|null;confidence:string;user_verified:boolean;source_page:number|null}[];
};
type Missing={field:string;label:string;policy_id:string|null;document_id:string|null;why:string};
type PendingEvidence=Missing&{value:any;unit?:string|null;page?:number|null;source?:string|null;status?:string};
type Issue={code:string;severity:string;title:string;detail:string};
type Verdict={
  status:'insufficient_data'|'review_required'|'partial'|'consistent';summary:string;source_of_truth:string;
  policies:Policy[];
  coverage:{verified:number;requirements:number;gaps:{requirement_id:string;coverage_type:string;insurance_type:string|null;reason:string;minimum_limit:string|null;best_verified_limit?:string}[];covered:any[];overlaps:{id:string;coverage_type:string;left_id:string;right_id:string;overlap_type:string;confidence:string}[]};
  finances:{income_last_365_days:string;expenses_last_365_days:string;savings_last_365_days:string;documented_annual_premiums:string;premium_share_of_income:string|null;spend_reconciliation:{period_start:string;period_end:string;data_coverage_days:number;observed_insurance_spend:string;documented_annual_premiums:string;difference:string|null;comparison_reliable:boolean;by_merchant:{merchant:string;amount:string}[]}};
  linked_products:{document_id:string;document_name:string|null;key:string;value:any;page:number|null}[];
  pending_review:PendingEvidence[];missing_information:Missing[];issues:Issue[];
  ai:null|{plain_summary?:string;priorities?:string[];questions?:string[];model?:string;error?:string};
};
type InsightItem={title:string;detail:string;pages:number[];impact?:string};
type DocInsight={document_id:string;file_name:string;document_type:string;analysis:{summary:string;confidence:string;advantages:InsightItem[];penalties:InsightItem[];risks:InsightItem[];exclusions_or_limits:InsightItem[];optimization_opportunities:InsightItem[];negotiation_points:InsightItem[];comparison_requirements:InsightItem[];cross_area_impacts:InsightItem[];missing_information:InsightItem[]}};

const statusText:Record<Verdict['status'],{title:string;detail:string}>={
  consistent:{title:'Datos consistentes',detail:'No hay huecos ni duplicidades materiales pendientes respecto a tus requisitos confirmados.'},
  review_required:{title:'Revisión necesaria',detail:'Hay diferencias, duplicidades o huecos que conviene resolver antes de tomar una decisión.'},
  partial:{title:'Análisis parcial',detail:'Los datos disponibles son útiles, pero faltan campos o criterios para cerrar la comparación.'},
  insufficient_data:{title:'Falta información',detail:'Aún no hay evidencia documental suficiente para analizar tus seguros.'},
};
const insuranceLabel:Record<string,string>={home:'Hogar',car:'Coche',life:'Vida',health:'Salud',pet:'Mascota',travel:'Viaje',other:'Otro',unknown:'Seguro'};

export default function InsurancePage(){
  const qc=useQueryClient();
  const profiles=useQuery({queryKey:['insurance'],queryFn:()=>apiGet<InsuranceProfile[]>('/api/v1/insurance')});
  const verdict=useQuery({queryKey:['insurance-verdict'],queryFn:()=>apiGet<Verdict>('/api/v1/insurance/verdict')});
  const requirements=useQuery({queryKey:['coverage-requirements'],queryFn:()=>apiGet<CoverageRequirement[]>('/api/v1/coverage-requirements')});
  const insights=useQuery({queryKey:['document-insights','insurance'],queryFn:()=>apiGet<DocInsight[]>('/api/v1/document-insights?document_type=insurance')});
  const analyze=useMutation({
    mutationFn:()=>apiMutate<Verdict>('/api/v1/insurance/verdict/analyze','POST'),
    onSuccess:data=>qc.setQueryData(['insurance-verdict'],data),
  });

  const emptyPolicy={provider_name:'',insurance_type:'home',annual_premium:'',deductible:'',policy_number_masked:'',renewal_date:'',cancellation_notice_days:'',early_exit_penalty:''};
  const [policyForm,setPolicyForm]=useState(emptyPolicy);
  const [editingPolicyId,setEditingPolicyId]=useState<string|null>(null);
  const [showPolicyForm,setShowPolicyForm]=useState(false);
  const [manualMissing,setManualMissing]=useState<Record<string,string>>({});
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
    onSuccess:()=>{setEditingPolicyId(null);setShowPolicyForm(false);refreshInsurance()},
  });
  const analyzePolicyDocs=useMutation({
    mutationFn:(id:string)=>apiMutate('/api/v1/evidence-groups/insurance_policy/'+id+'/analyze','POST'),
    onSuccess:refreshInsurance,
  });
  const saveMissingPolicy=useMutation({
    mutationFn:({missing,value}:{missing:Missing;value:string})=>{
      if(!missing.policy_id)throw new Error('Este dato aún no está asociado a una póliza. Asocia primero el documento al seguro correcto.');
      const policy=data?.policies.find(p=>p.id===missing.policy_id);
      const profile=profiles.data?.find(p=>p.id===missing.policy_id);
      if(!policy)throw new Error('No se ha encontrado la póliza');
      const body:any={
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

  return <>
    <PageHeader title="Seguros y coberturas" description="La fuente de verdad son tus documentos confirmados. Financito los cruza con movimientos, ingresos, coste, coberturas, duplicidades y productos vinculados antes de darte una conclusión."/>

    {verdict.isLoading?<Loading/>:verdict.error?<ErrorState error={verdict.error}/>:data&&<>
      <Card>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="max-w-3xl">
            <div className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">Veredicto basado en evidencia</div>
            <h2 className="mt-1 text-xl font-bold">{status?.title}</h2>
            <p className="mt-2 text-sm">{data.summary}</p>
            <p className="mt-2 text-xs text-[var(--muted)]">{status?.detail} La IA, cuando se usa, solo explica el resultado; no sustituye los hechos confirmados.</p>
          </div>
          <div className="flex gap-2">
            <button className="fin-button secondary" type="button" onClick={()=>{setEditingPolicyId(null);setPolicyForm(emptyPolicy);setShowPolicyForm(v=>!v)}}>{showPolicyForm&&!editingPolicyId?'Cerrar alta':'Nuevo seguro'}</button>
            <button className="fin-button" onClick={()=>analyze.mutate()} disabled={analyze.isPending}>{analyze.isPending?'Analizando con IA…':'Explicar con IA local'}</button>
          </div>
        </div>
        {analyze.error&&<div className="mt-3"><ErrorState error={analyze.error}/></div>}
        {data.ai?.plain_summary&&<div className="mt-4 rounded-xl bg-[var(--brand-soft)] p-4 text-sm"><strong>Lectura de la IA local</strong><p className="mt-1">{data.ai.plain_summary}</p>{data.ai.priorities?.length?<div className="mt-2 text-xs"><strong>Prioridades:</strong> {data.ai.priorities.join(' · ')}</div>:null}{data.ai.questions?.length?<div className="mt-2 text-xs"><strong>Preguntas pendientes:</strong> {data.ai.questions.join(' · ')}</div>:null}<div className="mt-2 text-[11px] text-[var(--muted)]">Modelo: {data.ai.model}</div></div>}
        {data.ai?.error&&<div className="mt-3 text-xs text-[var(--muted)]">La IA local no pudo ampliar el análisis: {data.ai.error}. El veredicto determinista sigue disponible.</div>}
        {showPolicyForm&&<form className="mt-4 grid gap-2 rounded-xl border border-[var(--border)] p-4 sm:grid-cols-2" onSubmit={e=>{e.preventDefault();savePolicy.mutate()}}>
          <div className="sm:col-span-2 font-semibold">{editingPolicyId?'Editar seguro':'Crear seguro'}</div>
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
      </Card>

      <div className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Card><div className="text-xs uppercase text-[var(--muted)]">Primas documentadas</div><div className="mt-2 text-2xl font-bold"><Money value={data.finances.documented_annual_premiums}/>/año</div><div className="mt-1 text-xs text-[var(--muted)]">{data.policies.length} póliza(s) registradas</div></Card>
        <Card><div className="text-xs uppercase text-[var(--muted)]">Pagos clasificados como seguros</div><div className="mt-2 text-2xl font-bold"><Money value={data.finances.spend_reconciliation.observed_insurance_spend}/></div><div className="mt-1 text-xs text-[var(--muted)]">Últimos {data.finances.spend_reconciliation.data_coverage_days} días disponibles</div></Card>
        <Card><div className="text-xs uppercase text-[var(--muted)]">Peso sobre ingresos</div><div className="mt-2 text-2xl font-bold">{data.finances.premium_share_of_income===null?'—':(Number(data.finances.premium_share_of_income)*100).toLocaleString('es-ES',{maximumFractionDigits:1})+'%'}</div><div className="mt-1 text-xs text-[var(--muted)]">Primas documentadas / ingresos observados en 365 días</div></Card>
        <Card><div className="text-xs uppercase text-[var(--muted)]">Coberturas verificadas</div><div className="mt-2 text-2xl font-bold">{data.coverage.verified}</div><div className="mt-1 text-xs text-[var(--muted)]">{data.coverage.gaps.length} hueco(s) · {data.coverage.overlaps.length} posible(s) duplicidad(es)</div></Card>
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        <Card>
          <h2 className="font-bold">Pólizas consolidadas</h2>
          <p className="mt-1 text-sm text-[var(--muted)]">Una póliza puede tener varios PDFs, anexos o condiciones. Financito los reúne en una sola ficha y combina su evidencia sin multiplicar seguros.</p>
          <div className="mt-4 space-y-3">{data.policies.length?data.policies.map(p=><div key={p.id} className="rounded-xl bg-[var(--surface-2)] p-4">
            <div className="flex items-start justify-between gap-3"><div><strong>{insuranceLabel[p.insurance_type]||p.insurance_type}</strong><div className="text-xs text-[var(--muted)]">{p.contract?.provider_name||p.source_document_name||'Proveedor pendiente'}</div></div><div className="text-right"><strong><Money value={p.annual_premium}/>/año</strong><div className="text-xs text-[var(--muted)]"><Money value={p.monthly_equivalent}/>/mes equivalente</div><div className="mt-2 flex gap-2"><button className="text-xs underline" type="button" onClick={()=>editPolicy(p)}>Editar</button><button className="text-xs underline" type="button" onClick={()=>{if(window.confirm('¿Eliminar este seguro? Los documentos no se borrarán del Vault.'))deletePolicy.mutate(p.id)}}>Eliminar</button></div></div></div>
            <div className="mt-3 grid gap-2 text-xs sm:grid-cols-2">
              <div>Franquicia: <strong><Money value={p.deductible}/></strong></div>
              <div>Renovación: <strong>{p.contract?.renewal_date?new Date(p.contract.renewal_date).toLocaleDateString('es-ES'):'—'}</strong></div>
              <div>Preaviso: <strong>{p.contract?.cancellation_notice_days===null||p.contract?.cancellation_notice_days===undefined?'—':p.contract.cancellation_notice_days+' días'}</strong></div>
              <div>Penalización: <strong><Money value={p.contract?.early_exit_penalty}/></strong></div>
            </div>
            {p.coverages.length>0&&<div className="mt-3 flex flex-wrap gap-1">{p.coverages.map(c=><span key={c.id} className="rounded-full bg-white px-2 py-1 text-[11px]">{c.coverage_type}{c.limit_amount?' · '+new Intl.NumberFormat('es-ES',{style:'currency',currency:'EUR'}).format(Number(c.limit_amount)):''}</span>)}</div>}
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <Link className="fin-button secondary py-1.5 text-xs" href={'/documents/?entity_type=insurance_policy&entity_id='+encodeURIComponent(p.id)+'&label='+encodeURIComponent('Seguro '+(insuranceLabel[p.insurance_type]||p.insurance_type)+' · '+(p.contract?.provider_name||'sin proveedor'))}>Documentación</Link>
              <button className="fin-button secondary py-1.5 text-xs" type="button" onClick={()=>analyzePolicyDocs.mutate(p.id)} disabled={analyzePolicyDocs.isPending}>Buscar datos con IA</button>
              <span className="text-xs text-[var(--muted)]">{p.source_documents?.length??(p.source_document_id?1:0)} documento(s) asociados</span>
            </div>
          </div>):<EmptyState>Crea tu primer seguro y después asocia su documentación desde la propia póliza.</EmptyState>}</div>
        </Card>

        <Card>
          <h2 className="font-bold">Qué requiere atención</h2>
          <div className="mt-3 space-y-2">{data.issues.length?data.issues.map(i=><div key={i.code} className="rounded-xl bg-[var(--surface-2)] p-3 text-sm"><strong>{i.title}</strong><div className="mt-1 text-xs text-[var(--muted)]">{i.detail}</div></div>):<EmptyState>No hay incidencias materiales detectadas con los datos actuales.</EmptyState>}</div>
          {data.linked_products.length>0&&<div className="mt-4"><h3 className="text-sm font-semibold">Relaciones con hipoteca u otros productos</h3><div className="mt-2 space-y-2">{data.linked_products.map((x,i)=><div key={x.document_id+x.key+i} className="rounded-xl border border-[var(--border)] p-3 text-xs"><strong>{x.key.replaceAll('_',' ')}</strong><div className="mt-1">{typeof x.value==='string'||typeof x.value==='number'?String(x.value):'Dato vinculado confirmado en la documentación'}</div><Link className="mt-1 inline-block underline" href={'/documents/?document='+encodeURIComponent(x.document_id)}>Ver evidencia{x.page?' · pág. '+x.page:''}</Link></div>)}</div></div>}
        </Card>
      </div>

      <Card className="mt-4">
        <h2 className="font-bold">Conciliación con tus movimientos</h2>
        <p className="mt-1 text-sm text-[var(--muted)]">Compara lo que dicen las pólizas con lo que realmente aparece cargado en tus cuentas. Una diferencia no se interpreta automáticamente como error: puede ser una prima fraccionada, un cambio de precio o un movimiento mal categorizado.</p>
        <div className="mt-4 grid gap-3 md:grid-cols-3">
          <div className="rounded-xl bg-[var(--surface-2)] p-3"><div className="text-xs text-[var(--muted)]">Primas documentadas</div><strong><Money value={data.finances.spend_reconciliation.documented_annual_premiums}/></strong></div>
          <div className="rounded-xl bg-[var(--surface-2)] p-3"><div className="text-xs text-[var(--muted)]">Pagos observados</div><strong><Money value={data.finances.spend_reconciliation.observed_insurance_spend}/></strong></div>
          <div className="rounded-xl bg-[var(--surface-2)] p-3"><div className="text-xs text-[var(--muted)]">Diferencia comparable</div><strong><Money value={data.finances.spend_reconciliation.difference}/></strong><div className="text-[11px] text-[var(--muted)]">{data.finances.spend_reconciliation.comparison_reliable?'Histórico suficiente para conciliación anual':'Aún no hay 330 días de movimientos; no se fuerza una comparación anual'}</div></div>
        </div>
        {data.finances.spend_reconciliation.by_merchant.length>0&&<div className="mt-4 grid gap-2 md:grid-cols-2">{data.finances.spend_reconciliation.by_merchant.slice(0,8).map(x=><div key={x.merchant} className="flex justify-between rounded-xl bg-[var(--surface-2)] p-3 text-sm"><span>{x.merchant}</span><strong><Money value={x.amount}/></strong></div>)}</div>}
      </Card>

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

    <Card className="mt-4">
      <div><h2 className="font-bold">Lectura de los documentos de las pólizas</h2><p className="mt-1 text-sm text-[var(--muted)]">Cada archivo conserva su análisis para trazabilidad. Para añadir o asociar documentos usa el botón “Documentación” de la póliza correspondiente.</p></div>
      <div className="mt-4 grid gap-3 md:grid-cols-2">{insights.data?.length?insights.data.map(x=><div key={x.document_id} className="rounded-xl border border-[var(--border)] p-4"><div className="flex items-start justify-between gap-3"><div><strong>{x.file_name}</strong><div className="mt-1 text-xs text-[var(--muted)]">Confianza interpretativa {Math.round(Number(x.analysis.confidence)*100)}%</div></div><Link className="text-xs underline" href={'/documents/?document='+encodeURIComponent(x.document_id)}>Evidencia</Link></div><p className="mt-3 text-sm">{x.analysis.summary}</p>{x.analysis.exclusions_or_limits.length>0&&<div className="mt-3 text-xs"><strong>Límites:</strong> {x.analysis.exclusions_or_limits.slice(0,3).map(i=>i.title||i.detail).join(' · ')}</div>}{x.analysis.optimization_opportunities.length>0&&<div className="mt-3 rounded-xl bg-[var(--brand-soft)] p-3 text-xs"><strong>A revisar:</strong> {x.analysis.optimization_opportunities.slice(0,3).map(i=>i.title||i.detail).join(' · ')}</div>}{x.analysis.cross_area_impacts.length>0&&<div className="mt-3 text-xs text-[var(--muted)]"><strong>Impactos en otras áreas:</strong> {x.analysis.cross_area_impacts.slice(0,3).map(i=>i.title||i.detail).join(' · ')}</div>}</div>):<EmptyState>Crea una póliza y asocia documentación para obtener conclusiones locales.</EmptyState>}</div>
    </Card>
  </>;
}
