'use client';

import Link from 'next/link';
import {FormEvent,useEffect,useMemo,useState} from 'react';
import {useMutation,useQuery} from '@tanstack/react-query';
import {apiGet,apiMutate} from '@/lib/api';
import {PageHeader} from '@/components/page-header';
import {Card} from '@/components/ui/card';
import {Money} from '@/components/ui/money';
import {EmptyState,ErrorState,Loading} from '@/components/ui/states';

type MortgageProfile={
  id:string;lender:string;remaining_principal:string;currency:string;interest_type:string;
  nominal_rate:string;monthly_payment:string;remaining_months:number;early_repayment_fee:string|null;updated_at:string|null;source_document_id?:string|null
};
type MortgageScenario={mortgage:MortgageProfile;calculated_monthly_payment:string;saved_monthly_payment:string;monthly_payment_difference:string;total_payments:string;total_interest:string;source:string};
type PrepaymentRestriction={
  status:string;calculation_ready:boolean;permission_confirmed:boolean;partial_prepayment_allowed:boolean|null;
  missing:string[];pending_review:{key:string;value:any;document_id:string;page:number|null}[];
  blockers:{code:string;message:string;limit?:string}[];effective_min_amount:string|null;effective_max_amount:string|null;
  notice_days:number|null;frequency_limit_per_year:number|null;window:string|null;condition:string|null;
  allowed_reduction_options:string[];operational_checks:{code:string;message:string;confirmed?:boolean}[];
  requires_manual_execution_check:boolean;
};
type Prepay={mortgage:MortgageProfile;original_monthly_payment:string;original_total_interest:string;reduced_payment:string|null;reduced_payment_total_interest:string|null;reduced_term_months:number|null;reduced_term_total_interest:string|null;prepayment_fee:string;interest_saved_reduce_payment:string|null;interest_saved_reduce_term:string|null;source:string;assumption:{extra_payment:string};prepayment_restrictions:PrepaymentRestriction};
type RatePath={mortgage:MortgageProfile;total_payments:string;total_interest:string;min_monthly_payment:string;max_monthly_payment:string;final_balance:string;notice:string;segments:{start_month:number;annual_rate:string;monthly_payment:string;end_balance:string}[]};
type Contract={id:string;provider_name:string;contract_type:string;annual_cost:string|null;early_exit_penalty:string|null;evidence_status:string;renewal_date:string|null};
type Opt={status:string;net_annual_benefit:string|null;break_even_months:string|null};
type GlobalScenario={monthly_income_after_shock:string;monthly_net:string;ending_liquidity:string;cash_runway_months:string|null;portfolio_after_shock:string};
type Context={generated_at:string;real_data_only:boolean;liquidity:string;cash_flow_current_month:{start:string;end:string;income:string;expenses:string;savings:string;savings_rate:string|null};cash_flow_last_90_days:{start:string;end:string;income:string;expenses:string;savings:string;savings_rate:string|null;average_monthly_income:string;average_monthly_expenses:string;average_monthly_savings:string};tracked_assets:any[];rules:string[]};
type SwitchingReadiness={ready:boolean;missing:string[];mortgage:null|{id:string;lender:string;remaining_principal:string;nominal_rate:string;monthly_payment:string;remaining_months:number;subrogation_penalty:{status:string;amount:string|null;formula:string|null;source:any};linked_product_signals:string[];linked_product_rate_impacts:{product:string;fact_key:string;rate_penalty_pp:string;monthly_payment_at_current_rate:string;monthly_payment_without_product:string;monthly_payment_increase:string;remaining_interest_increase:string;source:any;assumption:string}[];prepayment_restrictions:PrepaymentRestriction};insurance:{policy_id:string;insurance_type:string;annual_premium:string;provider:string|null;renewal_date:string|null;cancellation_notice_days:number|null;exit_penalty:string|null;evidence_status:string|null;source_document_id:string|null}[];hypotheses:{key:string;label:string}[];rule:string};
type MarketConclusion={status:string;headline:string;action:string;provider:string|null;source_id:string|null;missing:string[];assumptions:string[];estimated_monthly_saving?:string;estimated_remaining_interest_saving?:string;known_exit_penalty?:string;estimated_net_interest_saving_known_costs?:string;break_even_months_known_penalty_only?:string};
type MarketScan={generated_at:string;current_mortgage_rate_percent:string|null;leads:{source_id:string;provider:string;kind:string;status:string;public_tin_min:number|null;benchmark_difference_pp:number|null;promo_percent:string|null;claims:string[];url:string;retrieved_at:string;requires_personalized_quote:boolean;scenario:null|{estimated_payment:string;monthly_payment_difference:string;remaining_interest_difference:string|null;known_exit_penalty:string|null;break_even_months_known_penalty_only:string|null}}[];conclusion:MarketConclusion;disclaimer:string};
type InsightItem={title:string;detail:string;pages:number[];impact?:string};
type DocInsight={document_id:string;file_name:string;document_type:string;analysis:{summary:string;confidence:string;advantages:InsightItem[];penalties:InsightItem[];risks:InsightItem[];linked_products:InsightItem[];optimization_opportunities:InsightItem[];negotiation_points:InsightItem[];comparison_requirements:InsightItem[];cross_area_impacts:InsightItem[];missing_information:InsightItem[]}};

function friendlyMissing(value:string){
  const labels:Record<string,string>={
    mortgage_exit_or_subrogation_penalty:'coste de salida o subrogación de la hipoteca',
    partial_prepayment_allowed:'si tu contrato permite amortización parcial',
    prepayment_reduction_options:'si la amortización reduce cuota, plazo o ambas',
    prepayment_penalty:'comisión de amortización anticipada',
  };
  if(labels[value])return labels[value];
  if(value.startsWith('insurance_evidence:'))return 'confirmar la póliza vinculada';
  if(value.startsWith('insurance_notice:'))return 'preaviso del seguro vinculado';
  if(value.startsWith('insurance_exit_penalty:'))return 'coste de salida del seguro vinculado';
  if(value.startsWith('linked_insurance_mapping:'))return 'relación entre hipoteca y seguro vinculado';
  return value.replaceAll('_',' ');
}

function reductionLabel(value:string){
  return value==='payment'?'reducir cuota':value==='term'?'reducir plazo':value==='lender_choice'?'lo decide la entidad':value;
}

function parseRatePath(raw:string){
  if(!raw.trim())return [];
  return raw.split(',').map((piece)=>{
    const [month,rate]=piece.trim().split(':');
    const m=Number(month);
    const r=Number((rate||'').replace(',','.'));
    if(!Number.isFinite(m)||!Number.isInteger(m)||m<1||!Number.isFinite(r)||r<0)throw new Error('Usa formato mes:tipo_decimal, por ejemplo 13:0.035,25:0.04');
    return {month:m,annual_rate:String(r)};
  });
}


export default function ToolsPage(){
  const [selectedMortgage,setSelectedMortgage]=useState('');
  const mortgages=useQuery({queryKey:['mortgages'],queryFn:()=>apiGet<MortgageProfile[]>('/api/v1/mortgages')});
  const contracts=useQuery({queryKey:['contracts'],queryFn:()=>apiGet<Contract[]>('/api/v1/contracts')});
  const context=useQuery({queryKey:['decision-lab-context'],queryFn:()=>apiGet<Context>('/api/v1/decision-lab/context')});
  const readiness=useQuery({queryKey:['switching-readiness',selectedMortgage],queryFn:()=>apiGet<SwitchingReadiness>('/api/v1/decision-lab/switching-readiness'+(selectedMortgage?'?mortgage_id='+encodeURIComponent(selectedMortgage):''))});
  const marketScan=useMutation({mutationFn:()=>apiGet<MarketScan>('/api/v1/decision-lab/market-scan'+(selectedMortgage?'?mortgage_id='+encodeURIComponent(selectedMortgage):''))});
  const [globalShock,setGlobalShock]=useState({income_reduction_pct:'20',extraordinary_expense:'0',portfolio_drop_pct:'20',months:6});
  const globalScenario=useMutation({mutationFn:()=>apiMutate<GlobalScenario>('/api/v1/stress','POST',globalShock)});
  const mortgageInsights=useQuery({queryKey:['document-insights','mortgage'],queryFn:()=>apiGet<DocInsight[]>('/api/v1/document-insights?document_type=mortgage')});

  useEffect(()=>{
    if(!selectedMortgage&&mortgages.data?.length)setSelectedMortgage(mortgages.data[0].id);
  },[mortgages.data,selectedMortgage]);

  const current=useMutation({mutationFn:()=>apiMutate<MortgageScenario>('/api/v1/decision-lab/mortgage/current','POST',{mortgage_id:selectedMortgage})});
  const [extra,setExtra]=useState('');
  const prepay=useMutation({mutationFn:()=>apiMutate<Prepay>('/api/v1/decision-lab/mortgage/prepayment','POST',{mortgage_id:selectedMortgage,extra_payment:extra})});
  const [pathSpec,setPathSpec]=useState('');
  const [pathError,setPathError]=useState('');
  const ratePath=useMutation({mutationFn:()=>apiMutate<RatePath>('/api/v1/decision-lab/mortgage/rate-path','POST',{mortgage_id:selectedMortgage,rate_steps:parseRatePath(pathSpec)})});

  const [contractId,setContractId]=useState('');
  const [newAnnualCost,setNewAnnualCost]=useState('');
  const [switching,setSwitching]=useState('');
  const [lostBenefits,setLostBenefits]=useState('');
  const [extraRecurring,setExtraRecurring]=useState('');
  const [taxImpact,setTaxImpact]=useState('');
  const selectedContract=useMemo(()=>contracts.data?.find(c=>c.id===contractId),[contracts.data,contractId]);
  const opt=useMutation({mutationFn:()=>{
    if(!selectedContract||selectedContract.annual_cost===null)throw new Error('El contrato actual no tiene coste anual confirmado.');
    if(newAnnualCost==='')throw new Error('Introduce el coste anual de la alternativa.');
    const gross=Math.max(0,Number(selectedContract.annual_cost)-Number(newAnnualCost));
    return apiMutate<Opt>('/api/v1/optimization/calculate','POST',{
      gross_annual_saving:String(gross),
      switching_costs:switching||'0',
      penalties:selectedContract.early_exit_penalty,
      lost_benefits:lostBenefits||'0',
      additional_recurring_costs:extraRecurring||'0',
      tax_impact:taxImpact||'0'
    });
  }});

  const activeMortgage=mortgages.data?.find(x=>x.id===selectedMortgage);
  const prepaymentRules=readiness.data?.mortgage?.prepayment_restrictions;

  return <>
    <PageHeader title="Laboratorio de decisiones" description="Los cálculos parten de tus datos guardados en Financito. Las variables futuras —como una senda de tipos o una nueva oferta— se muestran como supuestos explícitos, nunca como datos reales."/>

    <Card>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-bold">Datos reales utilizados</h2>
          <p className="mt-1 text-sm text-[var(--muted)]">Hipoteca, ingresos, gastos, ahorro, contratos, liquidez, patrimonio e inversiones se leen de tu base local. No se cargan ejemplos por defecto.</p>
        </div>
        {context.data&&<div className="text-right text-xs text-[var(--muted)]">Contexto actualizado<br/>{new Date(context.data.generated_at).toLocaleString()}</div>}
      </div>
      {context.isLoading?<div className="mt-3"><Loading/></div>:context.error?<div className="mt-3"><ErrorState error={context.error}/></div>:context.data?<div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-5 text-sm">
        <div className="rounded-xl bg-[var(--surface-2)] p-3"><div className="text-xs text-[var(--muted)]">Liquidez acumulada</div><div className="mt-1 font-bold"><Money value={context.data.liquidity}/></div><div className="mt-1 text-[11px] text-[var(--muted)]">Saldo real de cuentas; no se presupone que todo sea amortizable.</div></div>
        <div className="rounded-xl bg-[var(--surface-2)] p-3"><div className="text-xs text-[var(--muted)]">Ingresos mes actual</div><div className="mt-1 font-bold"><Money value={context.data.cash_flow_current_month?.income||'0'}/></div></div>
        <div className="rounded-xl bg-[var(--surface-2)] p-3"><div className="text-xs text-[var(--muted)]">Gastos mes actual</div><div className="mt-1 font-bold"><Money value={context.data.cash_flow_current_month?.expenses||'0'}/></div></div>
        <div className="rounded-xl bg-[var(--surface-2)] p-3"><div className="text-xs text-[var(--muted)]">Ahorro mes actual</div><div className="mt-1 font-bold"><Money value={context.data.cash_flow_current_month?.savings||'0'}/></div></div>
        <div className="rounded-xl bg-[var(--surface-2)] p-3"><div className="text-xs text-[var(--muted)]">Ingreso medio mensual 90 días</div><div className="mt-1 font-bold"><Money value={context.data.cash_flow_last_90_days?.average_monthly_income||'0'}/></div></div>
      </div>:null}
    </Card>

    <Card className="mt-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div><h2 className="font-bold">Escenario global</h2><p className="mt-1 text-sm text-[var(--muted)]">Combina liquidez, ingresos/gastos observados y cartera real para probar una caída de ingresos, un gasto extraordinario y una caída hipotética de inversiones en un mismo escenario.</p></div>
        <div className="flex gap-2"><Link className="text-xs underline" href="/goals/">Ver objetivos</Link><Link className="text-xs underline" href="/markets/">Simular inversiones</Link></div>
      </div>
      <form className="mt-4 grid gap-3 md:grid-cols-4" onSubmit={(e:FormEvent)=>{e.preventDefault();globalScenario.mutate()}}>
        <label className="text-sm">Caída de ingresos (%)<input className="fin-input mt-1" type="number" min="0" max="100" step=".1" value={globalShock.income_reduction_pct} onChange={e=>setGlobalShock({...globalShock,income_reduction_pct:e.target.value})}/></label>
        <label className="text-sm">Gasto extraordinario<input className="fin-input mt-1" type="number" min="0" step=".01" value={globalShock.extraordinary_expense} onChange={e=>setGlobalShock({...globalShock,extraordinary_expense:e.target.value})}/></label>
        <label className="text-sm">Caída de cartera (%)<input className="fin-input mt-1" type="number" min="0" max="100" step=".1" value={globalShock.portfolio_drop_pct} onChange={e=>setGlobalShock({...globalShock,portfolio_drop_pct:e.target.value})}/></label>
        <label className="text-sm">Horizonte (meses)<input className="fin-input mt-1" type="number" min="1" max="60" value={globalShock.months} onChange={e=>setGlobalShock({...globalShock,months:Number(e.target.value)})}/></label>
        <button className="fin-button md:col-span-4" disabled={globalScenario.isPending}>{globalScenario.isPending?'Calculando…':'Simular escenario completo'}</button>
      </form>
      {globalScenario.error&&<div className="mt-3"><ErrorState error={globalScenario.error}/></div>}
      {globalScenario.data&&<div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4 text-sm">
        <div className="rounded-xl bg-[var(--surface-2)] p-3"><div className="text-xs text-[var(--muted)]">Ingreso mensual tras shock</div><strong><Money value={globalScenario.data.monthly_income_after_shock}/></strong></div>
        <div className="rounded-xl bg-[var(--surface-2)] p-3"><div className="text-xs text-[var(--muted)]">Flujo mensual resultante</div><strong><Money value={globalScenario.data.monthly_net}/></strong></div>
        <div className="rounded-xl bg-[var(--surface-2)] p-3"><div className="text-xs text-[var(--muted)]">Liquidez al final</div><strong><Money value={globalScenario.data.ending_liquidity}/></strong></div>
        <div className="rounded-xl bg-[var(--surface-2)] p-3"><div className="text-xs text-[var(--muted)]">Cartera tras shock</div><strong><Money value={globalScenario.data.portfolio_after_shock}/></strong><div className="text-[11px] text-[var(--muted)]">Runway {globalScenario.data.cash_runway_months===null?'sin consumo neto':globalScenario.data.cash_runway_months+' meses'}</div></div>
      </div>}
    </Card>

    <div className="mt-4 grid gap-4 xl:grid-cols-2">
      <Card className="xl:col-span-2">
        <div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="font-bold">Conclusiones de tu documentación hipotecaria</h2><p className="mt-1 text-sm text-[var(--muted)]">La IA local interpreta cláusulas y relaciones entre hipoteca, seguros y vinculaciones. Los cálculos siguen usando únicamente hechos confirmados y datos reales.</p></div><a className="text-xs underline" href="/documents/">Añadir o revisar documentos</a></div>
        <div className="mt-4 rounded-xl bg-[var(--brand-soft)] p-4 text-sm">
          <strong>Qué hacer ahora</strong>
          {!readiness.data?.mortgage?<p className="mt-1">1. Abre Documentos. 2. Selecciona tu escritura/FEIN vigente. 3. Usa “Crear hipoteca y vincular este documento” o vincúlalo a una hipoteca existente. Después vuelve aquí: escenario base, amortización y mercado usarán esa misma hipoteca.</p>:!readiness.data.ready?<p className="mt-1">Antes de decidir un cambio, confirma en Documentos: {(readiness.data.missing||[]).map(friendlyMissing).join(' · ')}. Hasta entonces Financito no supondrá que una penalización, seguro o condición desconocida cuesta 0 €.</p>:<p className="mt-1">La documentación ya permite comparar. Pulsa “Buscar mercado ahora”. Financito te indicará qué referencia concreta merece pedir como oferta personalizada y calculará el ahorro frente a tu hipoteca incluyendo la penalización confirmada.</p>}
        </div>
        <div className="mt-4 grid gap-3 md:grid-cols-2">{Array.isArray(mortgageInsights.data)&&mortgageInsights.data.length?mortgageInsights.data.map(x=><div key={x.document_id} className="rounded-xl border border-[var(--border)] p-4"><div className="flex items-start justify-between gap-3"><div><strong>{x.file_name}</strong><div className="mt-1 text-xs text-[var(--muted)]">Confianza interpretativa {Math.round(Number(x.analysis.confidence)*100)}%</div></div><a className="text-xs underline" href={'/documents/?document='+encodeURIComponent(x.document_id)}>Evidencia</a></div><p className="mt-3 text-sm">{x.analysis.summary}</p>{x.analysis.penalties?.length>0&&<div className="mt-3"><div className="text-xs font-semibold uppercase">Penalizaciones / cambio</div><div className="mt-1 space-y-1">{x.analysis.penalties.slice(0,4).map((i,n)=><div key={'p'+n} className="text-xs">{i.title||i.detail}</div>)}</div></div>}{x.analysis.linked_products?.length>0&&<div className="mt-3"><div className="text-xs font-semibold uppercase">Vinculaciones</div><div className="mt-1 space-y-1">{x.analysis.linked_products.slice(0,4).map((i,n)=><div key={'l'+n} className="text-xs">{i.title||i.detail}</div>)}</div></div>}{x.analysis.optimization_opportunities?.length>0&&<div className="mt-3 rounded-xl bg-[var(--brand-soft)] p-3"><div className="text-xs font-semibold">Oportunidades a contrastar</div><div className="mt-1 space-y-1">{x.analysis.optimization_opportunities.slice(0,4).map((i,n)=><div key={'o'+n} className="text-xs">{i.title||i.detail}</div>)}</div></div>}{x.analysis.negotiation_points?.length>0&&<div className="mt-3"><div className="text-xs font-semibold uppercase">Para negociar</div><div className="mt-1 space-y-1">{x.analysis.negotiation_points.slice(0,4).map((i,n)=><div key={'n'+n} className="text-xs">{i.title||i.detail}</div>)}</div></div>}{x.analysis.comparison_requirements?.length>0&&<div className="mt-3"><div className="text-xs font-semibold uppercase">Qué debe igualar una oferta</div><div className="mt-1 space-y-1">{x.analysis.comparison_requirements.slice(0,4).map((i,n)=><div key={'c'+n} className="text-xs">{i.title||i.detail}</div>)}</div></div>}{x.analysis.cross_area_impacts?.length>0&&<div className="mt-3 text-xs text-[var(--muted)]"><strong>Impacto cruzado:</strong> {x.analysis.cross_area_impacts.slice(0,3).map(i=>i.title||i.detail).join(' · ')}</div>}</div>):<EmptyState>Añade la FEIN, escritura o condiciones de tu hipoteca en Documentos para obtener conclusiones locales.</EmptyState>}</div>
      </Card>

      <Card>
        <h2 className="font-bold">Costes contractuales antes de cambiar</h2>
        <p className="mt-1 text-sm text-[var(--muted)]">Financito resuelve penalizaciones y preavisos desde los PDF confirmados. Si falta un dato material, la comparación queda bloqueada en vez de asumir 0 €.</p>
        {readiness.isLoading?<div className="mt-3"><Loading/></div>:readiness.error?<div className="mt-3"><ErrorState error={readiness.error}/></div>:readiness.data?<div className="mt-4 space-y-3 text-sm">
          {readiness.data.mortgage?<div className="rounded-xl bg-[var(--surface-2)] p-3"><strong>{readiness.data.mortgage.lender}</strong><div className="mt-1 text-xs text-[var(--muted)]">Capital {readiness.data.mortgage.remaining_principal} € · TIN {(Number(readiness.data.mortgage.nominal_rate)*100).toFixed(3)}% · penalización subrogación {readiness.data.mortgage.subrogation_penalty?.amount==null?'pendiente de confirmar':readiness.data.mortgage.subrogation_penalty?.amount+' €'}</div>{readiness.data.mortgage.subrogation_penalty?.formula&&<div className="mt-1 text-xs text-[var(--muted)]">{readiness.data.mortgage.subrogation_penalty?.formula}</div>}{readiness.data.mortgage.linked_product_rate_impacts?.map(x=><div key={x.fact_key} className="mt-2 border-t border-[var(--border)] pt-2 text-xs"><strong>Quitar {x.product.replace('_',' ')}</strong>: +{x.rate_penalty_pp} pp · cuota estimada +{x.monthly_payment_increase} €/mes · intereses restantes +{x.remaining_interest_increase} €.<div className="text-[var(--muted)]">{x.assumption==='fixed_rate_contract'?'Cálculo sobre tu tipo fijo actual.':'Escenario comparativo manteniendo constante el tipo actual; para variable/mixta se sustituye por la senda de tipos.'}</div></div>)}
            <div className="mt-3 border-t border-[var(--border)] pt-3 text-xs">
              <strong>Amortización anticipada</strong>
              <div className="mt-1">{readiness.data.mortgage.prepayment_restrictions.partial_prepayment_allowed===true?'Permiso parcial confirmado':readiness.data.mortgage.prepayment_restrictions.partial_prepayment_allowed===false?'El contrato la prohíbe':'Permiso pendiente de confirmar'}</div>
              <div className="mt-1 text-[var(--muted)]">
                {readiness.data.mortgage.prepayment_restrictions.effective_min_amount?'Mínimo '+readiness.data.mortgage.prepayment_restrictions.effective_min_amount+' € · ':''}
                Máximo {readiness.data.mortgage.prepayment_restrictions.effective_max_amount||'pendiente'} €
                {readiness.data.mortgage.prepayment_restrictions.notice_days!==null?' · preaviso '+readiness.data.mortgage.prepayment_restrictions.notice_days+' días':' · preaviso sin confirmar'}
              </div>
              {readiness.data.mortgage.prepayment_restrictions.allowed_reduction_options.length>0&&<div className="mt-1 text-[var(--muted)]">Aplicación: {readiness.data.mortgage.prepayment_restrictions.allowed_reduction_options.map(reductionLabel).join(' / ')}</div>}
              {readiness.data.mortgage.prepayment_restrictions.pending_review.length>0&&<div className="mt-2 font-medium">Hay {readiness.data.mortgage.prepayment_restrictions.pending_review.length} condición(es) encontrada(s) en documentos pendientes de validar.</div>}
            </div>
          </div>:<EmptyState>No hay hipoteca guardada.</EmptyState>}
          {readiness.data.insurance?.map(p=><div key={p.policy_id} className="rounded-xl bg-[var(--surface-2)] p-3"><strong>Seguro {p.insurance_type}</strong><div className="mt-1 text-xs text-[var(--muted)]">{p.provider||'Proveedor sin identificar'} · {p.annual_premium} €/año · preaviso {p.cancellation_notice_days===null?'desconocido':p.cancellation_notice_days+' días'} · penalización {p.exit_penalty===null?'desconocida':p.exit_penalty+' €'}</div>{p.source_document_id&&<a className="mt-1 inline-block text-xs underline" href={'/documents/?document='+encodeURIComponent(p.source_document_id)}>Ver evidencia</a>}</div>)}
          <div className={readiness.data.ready?'text-xs':'text-xs font-medium'}>{readiness.data.ready?'Datos contractuales suficientes para comparar escenarios de cambio.':'Falta confirmar: '+(readiness.data.missing||[]).map(friendlyMissing).join(' · ')}</div>
        </div>:null}
      </Card>

      <Card>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div><h2 className="font-bold">Mercado actual</h2><p className="mt-1 text-sm text-[var(--muted)]">Consulta bajo demanda páginas oficiales de bancos y aseguradoras. Las ofertas públicas se tratan como referencia; una FEIN o presupuesto personalizado es lo que permite calcular ahorro real.</p></div>
          <button className="fin-button secondary" onClick={()=>marketScan.mutate()} disabled={marketScan.isPending||!selectedMortgage}>{marketScan.isPending?'Consultando…':'Buscar mercado ahora'}</button>
        </div>
        {marketScan.error&&<div className="mt-3"><ErrorState error={marketScan.error}/></div>}
        {marketScan.data&&<div className="mt-4 space-y-3">
          <div className="rounded-xl bg-[var(--brand-soft)] p-4 text-sm">
            <div className="text-xs font-semibold uppercase">Conclusión con la hipoteca seleccionada</div>
            <div className="mt-1 text-base font-bold">{marketScan.data.conclusion.headline}</div>
            <p className="mt-1">{marketScan.data.conclusion.action}</p>
            {marketScan.data.conclusion.estimated_monthly_saving&&<div className="mt-3 grid gap-2 sm:grid-cols-2">
              <div><span className="text-xs text-[var(--muted)]">Ahorro mensual comparable</span><div className="font-bold"><Money value={marketScan.data.conclusion.estimated_monthly_saving}/></div></div>
              <div><span className="text-xs text-[var(--muted)]">Ahorro de intereses menos penalización conocida</span><div className="font-bold"><Money value={marketScan.data.conclusion.estimated_net_interest_saving_known_costs||null}/></div></div>
              <div><span className="text-xs text-[var(--muted)]">Penalización de salida usada</span><div className="font-bold"><Money value={marketScan.data.conclusion.known_exit_penalty||null}/></div></div>
              <div><span className="text-xs text-[var(--muted)]">Break-even</span><div className="font-bold">{marketScan.data.conclusion.break_even_months_known_penalty_only||'—'} meses</div></div>
            </div>}
            {marketScan.data.conclusion.missing?.length>0&&<div className="mt-2 text-xs text-[var(--muted)]">No se puede elegir todavía porque falta: {marketScan.data.conclusion.missing.join(' · ')}</div>}
          </div>
          {(marketScan.data.leads||[]).map(x=><div key={x.source_id} className="rounded-xl bg-[var(--surface-2)] p-3 text-sm"><div className="flex items-start justify-between gap-3"><div><strong>{x.provider}</strong><div className="text-xs text-[var(--muted)]">{x.kind} · {x.status}</div></div><a className="text-xs underline" href={x.url} target="_blank" rel="noreferrer">Fuente oficial</a></div><div className="mt-2 text-xs">{x.public_tin_min===null?'Sin TIN público fiable extraíble':('TIN público detectado desde '+x.public_tin_min.toFixed(2)+'%')}{x.benchmark_difference_pp!==null?' · diferencia frente a tu TIN: '+x.benchmark_difference_pp.toFixed(2)+' pp':''}{x.promo_percent?' · promoción pública '+x.promo_percent+'%':''}</div>{x.scenario&&<div className="mt-1 text-xs">Cuota comparable <strong><Money value={x.scenario.estimated_payment}/></strong> · ahorro mensual <strong><Money value={x.scenario.monthly_payment_difference}/></strong>{x.scenario.break_even_months_known_penalty_only?' · break-even '+x.scenario.break_even_months_known_penalty_only+' meses':''}</div>}<div className="mt-1 text-[11px] text-[var(--muted)]">{x.requires_personalized_quote?'La referencia pública debe validarse con una FEIN/oferta personalizada.':''}</div></div>)}
          <p className="text-xs text-[var(--muted)]">{marketScan.data.disclaimer}</p>
        </div>}
      </Card>

      <Card className="xl:col-span-2">
        <h2 className="font-bold">Hipótesis que Financito debe comparar</h2>
        <p className="mt-1 text-sm text-[var(--muted)]">No se limita a “cambiar de banco”. Se evalúan por separado hipoteca, seguros y uso de liquidez.</p>
        <div className="mt-3 grid gap-2 md:grid-cols-2">{readiness.data?.hypotheses?.map(h=><div key={h.key} className="rounded-xl bg-[var(--surface-2)] p-3 text-sm">{h.label}</div>)}</div>
      </Card>

      <Card className="xl:col-span-2">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="font-bold">Hipoteca utilizada en las simulaciones</h2>
            <p className="mt-1 text-sm text-[var(--muted)]">Los datos contractuales proceden de la documentación confirmada. Si falta o cambia un dato, corrígelo en el documento origen para que se actualice en toda la aplicación.</p>
          </div>
          <select className="fin-input max-w-72" aria-label="Hipoteca guardada" value={selectedMortgage} onChange={e=>setSelectedMortgage(e.target.value)}>
            <option value="">Selecciona una hipoteca…</option>
            {mortgages.data?.map(m=><option key={m.id} value={m.id}>{m.lender} · {new Intl.NumberFormat('es-ES',{style:'currency',currency:m.currency}).format(Number(m.remaining_principal))}</option>)}
          </select>
        </div>
        {activeMortgage?<div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4 text-sm">
          <div className="rounded-xl bg-[var(--surface-2)] p-3"><div className="text-xs text-[var(--muted)]">Capital pendiente</div><strong><Money value={activeMortgage.remaining_principal} currency={activeMortgage.currency}/></strong></div>
          <div className="rounded-xl bg-[var(--surface-2)] p-3"><div className="text-xs text-[var(--muted)]">TIN</div><strong>{(Number(activeMortgage.nominal_rate)*100).toLocaleString('es-ES',{maximumFractionDigits:3})}%</strong></div>
          <div className="rounded-xl bg-[var(--surface-2)] p-3"><div className="text-xs text-[var(--muted)]">Cuota</div><strong><Money value={activeMortgage.monthly_payment} currency={activeMortgage.currency}/></strong></div>
          <div className="rounded-xl bg-[var(--surface-2)] p-3"><div className="text-xs text-[var(--muted)]">Plazo restante</div><strong>{activeMortgage.remaining_months.toLocaleString('es-ES')} meses</strong></div>
        </div>:<EmptyState>Añade y confirma la FEIN, escritura o condiciones hipotecarias en Documentos para poder simular con una fuente única y trazable.</EmptyState>}
        <div className="mt-3 flex flex-wrap gap-2">
          {activeMortgage?.source_document_id?<Link className="fin-button secondary py-2 text-xs" href={'/documents/?document='+encodeURIComponent(activeMortgage.source_document_id)}>Ver o completar documento origen</Link>:activeMortgage?<Link className="fin-button secondary py-2 text-xs" href="/documents/">Vincular la hipoteca a documentación</Link>:<Link className="fin-button py-2 text-xs" href="/documents/">Añadir documentación hipotecaria</Link>}
          {activeMortgage&&!activeMortgage.source_document_id&&<span className="self-center text-xs text-[var(--muted)]">Este registro procede de una versión anterior/manual y todavía no tiene documento canónico asociado.</span>}
        </div>
      </Card>

      <Card>
        <h2 className="font-bold">Escenario base de tu hipoteca</h2>
        <p className="mt-1 text-sm text-[var(--muted)]">Usa exclusivamente capital, TIN y plazo de la hipoteca seleccionada y contrasta la cuota calculada con la cuota que has guardado.</p>
        <button className="fin-button mt-4" disabled={!activeMortgage||current.isPending} onClick={()=>current.mutate()}>Calcular con mis datos</button>
        {current.error&&<div className="mt-3"><ErrorState error={current.error}/></div>}
        {current.data&&<dl className="mt-5 grid gap-3 sm:grid-cols-2 text-sm">
          <div><dt className="text-[var(--muted)]">Cuota guardada</dt><dd className="font-bold"><Money value={current.data.saved_monthly_payment}/></dd></div>
          <div><dt className="text-[var(--muted)]">Cuota matemática</dt><dd className="font-bold"><Money value={current.data.calculated_monthly_payment}/></dd></div>
          <div><dt className="text-[var(--muted)]">Intereses restantes</dt><dd className="font-bold"><Money value={current.data.total_interest}/></dd></div>
          <div><dt className="text-[var(--muted)]">Total restante</dt><dd className="font-bold"><Money value={current.data.total_payments}/></dd></div>
        </dl>}
      </Card>

      <Card>
        <h2 className="font-bold">Amortización extraordinaria</h2>
        <p className="mt-1 text-sm text-[var(--muted)]">Tú solo eliges el importe. Financito usa capital, TIN, plazo, comisión y límites confirmados de tu contrato; si falta una condición esencial, no calcula como si no existiera.</p>
        {prepaymentRules&&<div className={prepaymentRules.calculation_ready?'mt-3 rounded-xl bg-[var(--brand-soft)] p-3 text-sm':'mt-3 rounded-xl bg-[var(--surface-2)] p-3 text-sm'}>
          <strong>{prepaymentRules.calculation_ready?'Contrato preparado para calcular':'Antes de calcular falta confirmar el contrato'}</strong>
          <div className="mt-1 text-xs">
            {prepaymentRules.partial_prepayment_allowed===true?'Amortización parcial permitida.':prepaymentRules.partial_prepayment_allowed===false?'La evidencia confirmada indica que no está permitida.':'No está confirmado si la amortización parcial está permitida.'}
            {prepaymentRules.effective_min_amount?' Mínimo '+prepaymentRules.effective_min_amount+' €.':''}
            {prepaymentRules.effective_max_amount?' Máximo '+prepaymentRules.effective_max_amount+' €.':''}
          </div>
          {prepaymentRules.allowed_reduction_options.length>0&&<div className="mt-1 text-xs">El contrato permite: {prepaymentRules.allowed_reduction_options.map(reductionLabel).join(' / ')}.</div>}
          {prepaymentRules.missing.length>0&&<div className="mt-2 text-xs"><strong>Falta:</strong> {prepaymentRules.missing.map(friendlyMissing).join(' · ')}</div>}
          {prepaymentRules.pending_review.length>0&&<div className="mt-2 text-xs"><strong>Pendiente de validar:</strong> {prepaymentRules.pending_review.map(x=>friendlyMissing(x.key)).join(' · ')}</div>}
          {!prepaymentRules.calculation_ready&&<Link className="mt-2 inline-block text-xs underline" href={activeMortgage?.source_document_id?'/documents/?document='+encodeURIComponent(activeMortgage.source_document_id):'/documents/'}>Revisar documentación</Link>}
        </div>}
        <form className="mt-4 grid gap-3" onSubmit={(e:FormEvent)=>{e.preventDefault();prepay.mutate()}}>
          <label className="text-sm">Importe que quieres simular<input className="fin-input mt-1" type="number" step=".01" min={prepaymentRules?.effective_min_amount||'0.01'} max={prepaymentRules?.effective_max_amount||activeMortgage?.remaining_principal||undefined} value={extra} onChange={e=>setExtra(e.target.value)} required/></label>
          <button className="fin-button" disabled={!activeMortgage||prepay.isPending||!prepaymentRules?.calculation_ready}>{prepay.isPending?'Calculando…':'Calcular con mis condiciones reales'}</button>
        </form>
        {activeMortgage?.early_repayment_fee===null&&<div className="mt-2 text-xs text-[var(--muted)]">La comisión también debe estar confirmada en tu documentación; si falta, el cálculo se bloquea en lugar de asumir 0 €.</div>}
        {prepay.error&&<div className="mt-3"><ErrorState error={prepay.error}/></div>}
        {prepay.data&&<div className="mt-4">
          <div className="grid gap-3 sm:grid-cols-2 text-sm">
            {prepay.data.reduced_payment!==null&&<div className="rounded-xl bg-[var(--surface-2)] p-4"><strong>Si reduces cuota</strong><div className="mt-2">Nueva cuota <Money value={prepay.data.reduced_payment}/></div><div>Ahorro neto de intereses <Money value={prepay.data.interest_saved_reduce_payment}/></div></div>}
            {prepay.data.reduced_term_months!==null&&<div className="rounded-xl bg-[var(--surface-2)] p-4"><strong>Si reduces plazo</strong><div className="mt-2">Nuevo plazo {prepay.data.reduced_term_months} meses</div><div>Ahorro neto de intereses <Money value={prepay.data.interest_saved_reduce_term}/></div></div>}
          </div>
          {prepay.data.prepayment_restrictions.operational_checks.length>0&&<div className="mt-3 rounded-xl bg-[var(--brand-soft)] p-3 text-xs"><strong>Antes de hacerlo</strong><div className="mt-1 space-y-1">{prepay.data.prepayment_restrictions.operational_checks.map((item,i)=><div key={item.code+i}>{item.message}</div>)}</div></div>}
          <div className="mt-3 text-[11px] text-[var(--muted)]">Resultado calculado con datos contractuales confirmados. Si cambia el contrato o el banco comunica otras condiciones, actualiza la evidencia antes de decidir.</div>
        </div>}
      </Card>

      <Card className="xl:col-span-2">
        <h2 className="font-bold">Senda hipotética de tipos</h2>
        <p className="mt-1 text-sm text-[var(--muted)]">El saldo, plazo y TIN inicial son los reales de tu hipoteca. Solo los cambios futuros son hipotéticos. Formato: <code>mes:tipo_decimal</code>.</p>
        <form className="mt-4 grid gap-3 md:grid-cols-[1fr_auto]" onSubmit={(e:FormEvent)=>{e.preventDefault();try{parseRatePath(pathSpec);setPathError('');ratePath.mutate()}catch(err){setPathError(err instanceof Error?err.message:String(err))}}}>
          <label className="text-sm">Cambios hipotéticos<input className="fin-input mt-1" value={pathSpec} onChange={e=>setPathSpec(e.target.value)} placeholder="13:0.035,25:0.04"/></label>
          <button className="fin-button self-end" disabled={!activeMortgage||ratePath.isPending}>Simular desde mi situación actual</button>
        </form>
        {pathError&&<div className="mt-3 text-sm">{pathError}</div>}
        {ratePath.error&&<div className="mt-3"><ErrorState error={ratePath.error}/></div>}
        {ratePath.data&&<div className="mt-4">
          <div className="grid gap-3 sm:grid-cols-4 text-sm">
            <div><span className="text-[var(--muted)]">Intereses</span><div className="font-bold"><Money value={ratePath.data.total_interest}/></div></div>
            <div><span className="text-[var(--muted)]">Cuota mínima</span><div className="font-bold"><Money value={ratePath.data.min_monthly_payment}/></div></div>
            <div><span className="text-[var(--muted)]">Cuota máxima</span><div className="font-bold"><Money value={ratePath.data.max_monthly_payment}/></div></div>
            <div><span className="text-[var(--muted)]">Saldo final</span><div className="font-bold"><Money value={ratePath.data.final_balance}/></div></div>
          </div>
          <div className="mt-4 overflow-auto"><table className="w-full min-w-[560px] text-sm"><thead><tr className="text-left text-xs uppercase text-[var(--muted)]"><th className="p-2">Desde mes</th><th className="p-2">TIN</th><th className="p-2">Cuota</th><th className="p-2">Saldo al cambio</th></tr></thead><tbody>{(ratePath.data.segments||[]).map((s,i)=><tr key={i} className="border-t border-[var(--border)]"><td className="p-2">{s.start_month}</td><td className="p-2">{(Number(s.annual_rate)*100).toFixed(3)}%</td><td className="p-2"><Money value={s.monthly_payment}/></td><td className="p-2"><Money value={s.end_balance}/></td></tr>)}</tbody></table></div>
          <p className="mt-3 text-xs text-[var(--muted)]">{ratePath.data.notice}</p>
        </div>}
      </Card>

      <Card className="xl:col-span-2">
        <h2 className="font-bold">Cambio de contrato</h2>
        <p className="mt-1 text-sm text-[var(--muted)]">El coste y la penalización actuales proceden del contrato guardado y de su evidencia. Tú solo introduces las condiciones de la alternativa que estás valorando.</p>
        <form className="mt-4 grid gap-3 md:grid-cols-3" onSubmit={(e:FormEvent)=>{e.preventDefault();opt.mutate()}}>
          <label className="text-sm">Contrato actual<select className="fin-input mt-1" value={contractId} onChange={e=>setContractId(e.target.value)} required><option value="">Selecciona…</option>{contracts.data?.map(c=><option key={c.id} value={c.id}>{c.provider_name} · {c.contract_type}</option>)}</select></label>
          <label className="text-sm">Coste anual de la alternativa<input className="fin-input mt-1" type="number" step=".01" value={newAnnualCost} onChange={e=>setNewAnnualCost(e.target.value)} required/></label>
          <label className="text-sm">Coste de cambio<input className="fin-input mt-1" type="number" step=".01" value={switching} onChange={e=>setSwitching(e.target.value)} placeholder="0"/></label>
          <label className="text-sm">Beneficios que perderías<input className="fin-input mt-1" type="number" step=".01" value={lostBenefits} onChange={e=>setLostBenefits(e.target.value)} placeholder="0"/></label>
          <label className="text-sm">Costes recurrentes adicionales<input className="fin-input mt-1" type="number" step=".01" value={extraRecurring} onChange={e=>setExtraRecurring(e.target.value)} placeholder="0"/></label>
          <label className="text-sm">Impacto fiscal conocido<input className="fin-input mt-1" type="number" step=".01" value={taxImpact} onChange={e=>setTaxImpact(e.target.value)} placeholder="0"/></label>
          <button className="fin-button md:col-span-3">Evaluar contra mi contrato real</button>
        </form>
        {selectedContract&&<div className="mt-3 text-xs text-[var(--muted)]">Actual: {selectedContract.annual_cost??'coste desconocido'} €/año · penalización {selectedContract.early_exit_penalty??'desconocida'} · evidencia {selectedContract.evidence_status}</div>}
        {opt.error&&<div className="mt-3"><ErrorState error={opt.error}/></div>}
        {opt.data&&<div className="mt-5 rounded-xl bg-[var(--surface-2)] p-4"><div className="text-xs uppercase text-[var(--muted)]">Estado: {opt.data.status}</div>{opt.data.net_annual_benefit!==null?<><div className="mt-2 text-2xl font-bold"><Money value={opt.data.net_annual_benefit}/>/año</div>{opt.data.break_even_months&&<div className="text-sm text-[var(--muted)]">Break-even: {opt.data.break_even_months} meses</div>}</>:<div className="mt-2 text-sm">Falta evidencia material. Financito no la sustituye por cero.</div>}</div>}
      </Card>
    </div>
  </>;
}
