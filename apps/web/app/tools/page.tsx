'use client';

import {FormEvent,useEffect,useMemo,useState} from 'react';
import {useMutation,useQuery,useQueryClient} from '@tanstack/react-query';
import {apiGet,apiMutate} from '@/lib/api';
import {PageHeader} from '@/components/page-header';
import {Card} from '@/components/ui/card';
import {Money} from '@/components/ui/money';
import {EmptyState,ErrorState,Loading} from '@/components/ui/states';

type MortgageProfile={
  id:string;lender:string;remaining_principal:string;currency:string;interest_type:string;
  nominal_rate:string;monthly_payment:string;remaining_months:number;early_repayment_fee:string|null;updated_at:string|null
};
type MortgageScenario={mortgage:MortgageProfile;calculated_monthly_payment:string;saved_monthly_payment:string;monthly_payment_difference:string;total_payments:string;total_interest:string;source:string};
type Prepay={mortgage:MortgageProfile;original_monthly_payment:string;original_total_interest:string;reduced_payment:string;reduced_payment_total_interest:string;reduced_term_months:number;reduced_term_total_interest:string;prepayment_fee:string;interest_saved_reduce_payment:string;interest_saved_reduce_term:string;source:string;assumption:{extra_payment:string}};
type RatePath={mortgage:MortgageProfile;total_payments:string;total_interest:string;min_monthly_payment:string;max_monthly_payment:string;final_balance:string;notice:string;segments:{start_month:number;annual_rate:string;monthly_payment:string;end_balance:string}[]};
type Contract={id:string;provider_name:string;contract_type:string;annual_cost:string|null;early_exit_penalty:string|null;evidence_status:string;renewal_date:string|null};
type Opt={status:string;net_annual_benefit:string|null;break_even_months:string|null};
type Context={generated_at:string;real_data_only:boolean;liquidity:string;cash_flow_current_month:{start:string;end:string;income:string;expenses:string;savings:string;savings_rate:string|null};cash_flow_last_90_days:{start:string;end:string;income:string;expenses:string;savings:string;savings_rate:string|null;average_monthly_income:string;average_monthly_expenses:string;average_monthly_savings:string};tracked_assets:any[];rules:string[]};
type SwitchingReadiness={ready:boolean;missing:string[];mortgage:null|{id:string;lender:string;remaining_principal:string;nominal_rate:string;monthly_payment:string;remaining_months:number;subrogation_penalty:{status:string;amount:string|null;formula:string|null;source:any};linked_product_signals:string[];linked_product_rate_impacts:{product:string;fact_key:string;rate_penalty_pp:string;monthly_payment_at_current_rate:string;monthly_payment_without_product:string;monthly_payment_increase:string;remaining_interest_increase:string;source:any;assumption:string}[]};insurance:{policy_id:string;insurance_type:string;annual_premium:string;provider:string|null;renewal_date:string|null;cancellation_notice_days:number|null;exit_penalty:string|null;evidence_status:string|null;source_document_id:string|null}[];hypotheses:{key:string;label:string}[];rule:string};
type MarketScan={generated_at:string;current_mortgage_rate_percent:string|null;leads:{source_id:string;provider:string;kind:string;status:string;public_tin_min:number|null;benchmark_difference_pp:number|null;promo_percent:string|null;claims:string[];url:string;retrieved_at:string;requires_personalized_quote:boolean}[];disclaimer:string};

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

const EMPTY_MORTGAGE={lender:'',remaining_principal:'',currency:'EUR',interest_type:'fixed',nominal_rate:'',monthly_payment:'',remaining_months:'',early_repayment_fee:''};

export default function ToolsPage(){
  const qc=useQueryClient();
  const [selectedMortgage,setSelectedMortgage]=useState('');
  const [mortgageForm,setMortgageForm]=useState(EMPTY_MORTGAGE);
  const mortgages=useQuery({queryKey:['mortgages'],queryFn:()=>apiGet<MortgageProfile[]>('/api/v1/mortgages')});
  const contracts=useQuery({queryKey:['contracts'],queryFn:()=>apiGet<Contract[]>('/api/v1/contracts')});
  const context=useQuery({queryKey:['decision-lab-context'],queryFn:()=>apiGet<Context>('/api/v1/decision-lab/context')});
  const readiness=useQuery({queryKey:['switching-readiness',selectedMortgage],queryFn:()=>apiGet<SwitchingReadiness>('/api/v1/decision-lab/switching-readiness'+(selectedMortgage?'?mortgage_id='+encodeURIComponent(selectedMortgage):''))});
  const marketScan=useMutation({mutationFn:()=>apiGet<MarketScan>('/api/v1/decision-lab/market-scan')});

  useEffect(()=>{
    if(!selectedMortgage&&mortgages.data?.length)setSelectedMortgage(mortgages.data[0].id);
  },[mortgages.data,selectedMortgage]);

  useEffect(()=>{
    const m=mortgages.data?.find(x=>x.id===selectedMortgage);
    if(m)setMortgageForm({
      lender:m.lender,remaining_principal:m.remaining_principal,currency:m.currency,interest_type:m.interest_type,
      nominal_rate:m.nominal_rate,monthly_payment:m.monthly_payment,remaining_months:String(m.remaining_months),
      early_repayment_fee:m.early_repayment_fee??''
    });
    else if(!selectedMortgage)setMortgageForm(EMPTY_MORTGAGE);
  },[selectedMortgage,mortgages.data]);

  const saveMortgage=useMutation({
    mutationFn:()=>apiMutate<MortgageProfile>(
      selectedMortgage?'/api/v1/mortgages/'+selectedMortgage:'/api/v1/mortgages',
      selectedMortgage?'PATCH':'POST',
      {
        lender:mortgageForm.lender,
        remaining_principal:mortgageForm.remaining_principal,
        currency:mortgageForm.currency,
        interest_type:mortgageForm.interest_type,
        nominal_rate:mortgageForm.nominal_rate,
        monthly_payment:mortgageForm.monthly_payment,
        remaining_months:Number(mortgageForm.remaining_months),
        early_repayment_fee:mortgageForm.early_repayment_fee===''?null:mortgageForm.early_repayment_fee,
      }
    ),
    onSuccess:(m)=>{setSelectedMortgage(m.id);qc.invalidateQueries({queryKey:['mortgages']});qc.invalidateQueries({queryKey:['decision-lab-context']})}
  });

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
        <div className="rounded-xl bg-[var(--surface-2)] p-3"><div className="text-xs text-[var(--muted)]">Ingresos mes actual</div><div className="mt-1 font-bold"><Money value={context.data.cash_flow_current_month.income}/></div></div>
        <div className="rounded-xl bg-[var(--surface-2)] p-3"><div className="text-xs text-[var(--muted)]">Gastos mes actual</div><div className="mt-1 font-bold"><Money value={context.data.cash_flow_current_month.expenses}/></div></div>
        <div className="rounded-xl bg-[var(--surface-2)] p-3"><div className="text-xs text-[var(--muted)]">Ahorro mes actual</div><div className="mt-1 font-bold"><Money value={context.data.cash_flow_current_month.savings}/></div></div>
        <div className="rounded-xl bg-[var(--surface-2)] p-3"><div className="text-xs text-[var(--muted)]">Ingreso medio mensual 90 días</div><div className="mt-1 font-bold"><Money value={context.data.cash_flow_last_90_days.average_monthly_income}/></div></div>
      </div>:null}
    </Card>

    <div className="mt-4 grid gap-4 xl:grid-cols-2">
      <Card>
        <h2 className="font-bold">Costes contractuales antes de cambiar</h2>
        <p className="mt-1 text-sm text-[var(--muted)]">Financito resuelve penalizaciones y preavisos desde los PDF confirmados. Si falta un dato material, la comparación queda bloqueada en vez de asumir 0 €.</p>
        {readiness.isLoading?<div className="mt-3"><Loading/></div>:readiness.error?<div className="mt-3"><ErrorState error={readiness.error}/></div>:readiness.data?<div className="mt-4 space-y-3 text-sm">
          {readiness.data.mortgage?<div className="rounded-xl bg-[var(--surface-2)] p-3"><strong>{readiness.data.mortgage.lender}</strong><div className="mt-1 text-xs text-[var(--muted)]">Capital {readiness.data.mortgage.remaining_principal} € · TIN {(Number(readiness.data.mortgage.nominal_rate)*100).toFixed(3)}% · penalización subrogación {readiness.data.mortgage.subrogation_penalty.amount===null?'pendiente de confirmar':readiness.data.mortgage.subrogation_penalty.amount+' €'}</div>{readiness.data.mortgage.subrogation_penalty.formula&&<div className="mt-1 text-xs text-[var(--muted)]">{readiness.data.mortgage.subrogation_penalty.formula}</div>}{readiness.data.mortgage.linked_product_rate_impacts.map(x=><div key={x.fact_key} className="mt-2 border-t border-[var(--border)] pt-2 text-xs"><strong>Quitar {x.product.replace('_',' ')}</strong>: +{x.rate_penalty_pp} pp · cuota estimada +{x.monthly_payment_increase} €/mes · intereses restantes +{x.remaining_interest_increase} €.<div className="text-[var(--muted)]">{x.assumption==='fixed_rate_contract'?'Cálculo sobre tu tipo fijo actual.':'Escenario comparativo manteniendo constante el tipo actual; para variable/mixta se sustituye por la senda de tipos.'}</div></div>)}</div>:<EmptyState>No hay hipoteca guardada.</EmptyState>}
          {readiness.data.insurance.map(p=><div key={p.policy_id} className="rounded-xl bg-[var(--surface-2)] p-3"><strong>Seguro {p.insurance_type}</strong><div className="mt-1 text-xs text-[var(--muted)]">{p.provider||'Proveedor sin identificar'} · {p.annual_premium} €/año · preaviso {p.cancellation_notice_days===null?'desconocido':p.cancellation_notice_days+' días'} · penalización {p.exit_penalty===null?'desconocida':p.exit_penalty+' €'}</div>{p.source_document_id&&<a className="mt-1 inline-block text-xs underline" href={'/documents/?document='+encodeURIComponent(p.source_document_id)}>Ver evidencia</a>}</div>)}
          <div className={readiness.data.ready?'text-xs':'text-xs font-medium'}>{readiness.data.ready?'Datos contractuales suficientes para comparar escenarios.':'Faltan datos: '+readiness.data.missing.join(' · ')}</div>
        </div>:null}
      </Card>

      <Card>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div><h2 className="font-bold">Mercado actual</h2><p className="mt-1 text-sm text-[var(--muted)]">Consulta bajo demanda páginas oficiales de bancos y aseguradoras. Las ofertas públicas se tratan como referencia; una FEIN o presupuesto personalizado es lo que permite calcular ahorro real.</p></div>
          <button className="fin-button secondary" onClick={()=>marketScan.mutate()} disabled={marketScan.isPending}>{marketScan.isPending?'Consultando…':'Buscar mercado ahora'}</button>
        </div>
        {marketScan.error&&<div className="mt-3"><ErrorState error={marketScan.error}/></div>}
        {marketScan.data&&<div className="mt-4 space-y-2">{marketScan.data.leads.map(x=><div key={x.source_id} className="rounded-xl bg-[var(--surface-2)] p-3 text-sm"><div className="flex items-start justify-between gap-3"><div><strong>{x.provider}</strong><div className="text-xs text-[var(--muted)]">{x.kind} · {x.status}</div></div><a className="text-xs underline" href={x.url} target="_blank" rel="noreferrer">Fuente oficial</a></div><div className="mt-2 text-xs">{x.public_tin_min===null?'Sin TIN público fiable extraíble':('TIN público detectado desde '+x.public_tin_min.toFixed(2)+'%')}{x.benchmark_difference_pp!==null?' · diferencia frente a tu TIN: '+x.benchmark_difference_pp.toFixed(2)+' pp':''}{x.promo_percent?' · promoción pública '+x.promo_percent+'%':''}</div><div className="mt-1 text-[11px] text-[var(--muted)]">{x.requires_personalized_quote?'Requiere oferta personalizada para calcular ahorro neto.':''}</div></div>)}
          <p className="text-xs text-[var(--muted)]">{marketScan.data.disclaimer}</p>
        </div>}
      </Card>

      <Card className="xl:col-span-2">
        <h2 className="font-bold">Hipótesis que Financito debe comparar</h2>
        <p className="mt-1 text-sm text-[var(--muted)]">No se limita a “cambiar de banco”. Se evalúan por separado hipoteca, seguros y uso de liquidez.</p>
        <div className="mt-3 grid gap-2 md:grid-cols-2">{readiness.data?.hypotheses.map(h=><div key={h.key} className="rounded-xl bg-[var(--surface-2)] p-3 text-sm">{h.label}</div>)}</div>
      </Card>

      <Card className="xl:col-span-2">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="font-bold">Tu hipoteca actual</h2>
            <p className="mt-1 text-sm text-[var(--muted)]">Mantén aquí el capital, TIN, cuota y plazo que realmente tienes ahora. Cada actualización queda registrada como snapshot.</p>
          </div>
          <select className="fin-input max-w-72" aria-label="Hipoteca guardada" value={selectedMortgage} onChange={e=>setSelectedMortgage(e.target.value)}>
            <option value="">Nueva hipoteca</option>
            {mortgages.data?.map(m=><option key={m.id} value={m.id}>{m.lender} · {m.remaining_principal} €</option>)}
          </select>
        </div>
        <form className="mt-4 grid gap-3 md:grid-cols-4" onSubmit={(e:FormEvent)=>{e.preventDefault();saveMortgage.mutate()}}>
          <label className="text-sm">Entidad<input className="fin-input mt-1" value={mortgageForm.lender} onChange={e=>setMortgageForm({...mortgageForm,lender:e.target.value})} required/></label>
          <label className="text-sm">Capital pendiente<input className="fin-input mt-1" type="number" step=".01" value={mortgageForm.remaining_principal} onChange={e=>setMortgageForm({...mortgageForm,remaining_principal:e.target.value})} required/></label>
          <label className="text-sm">Tipo<select className="fin-input mt-1" value={mortgageForm.interest_type} onChange={e=>setMortgageForm({...mortgageForm,interest_type:e.target.value})}><option value="fixed">Fija</option><option value="variable">Variable</option><option value="mixed">Mixta</option></select></label>
          <label className="text-sm">TIN actual decimal<input className="fin-input mt-1" value={mortgageForm.nominal_rate} onChange={e=>setMortgageForm({...mortgageForm,nominal_rate:e.target.value})} placeholder="0.025 = 2,5%" required/></label>
          <label className="text-sm">Cuota real actual<input className="fin-input mt-1" type="number" step=".01" value={mortgageForm.monthly_payment} onChange={e=>setMortgageForm({...mortgageForm,monthly_payment:e.target.value})} required/></label>
          <label className="text-sm">Meses restantes<input className="fin-input mt-1" type="number" value={mortgageForm.remaining_months} onChange={e=>setMortgageForm({...mortgageForm,remaining_months:e.target.value})} required/></label>
          <label className="text-sm">Comisión total de amortización<input className="fin-input mt-1" type="number" step=".01" value={mortgageForm.early_repayment_fee} onChange={e=>setMortgageForm({...mortgageForm,early_repayment_fee:e.target.value})} placeholder="Vacío si no consta"/></label>
          <button className="fin-button self-end" disabled={saveMortgage.isPending}>{selectedMortgage?'Actualizar datos reales':'Guardar hipoteca'}</button>
        </form>
        {saveMortgage.error&&<div className="mt-3"><ErrorState error={saveMortgage.error}/></div>}
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
        <p className="mt-1 text-sm text-[var(--muted)]">El único supuesto es cuánto quieres amortizar. Capital, TIN, plazo y comisión salen de tu hipoteca guardada.</p>
        <form className="mt-4 grid gap-3" onSubmit={(e:FormEvent)=>{e.preventDefault();prepay.mutate()}}>
          <label className="text-sm">Importe hipotético a amortizar<input className="fin-input mt-1" type="number" step=".01" value={extra} onChange={e=>setExtra(e.target.value)} required/></label>
          <button className="fin-button" disabled={!activeMortgage||prepay.isPending}>Comparar con mis datos</button>
        </form>
        {activeMortgage?.early_repayment_fee===null&&<div className="mt-2 text-xs text-[var(--muted)]">La comisión no consta. Añádela arriba; Financito no asumirá 0.</div>}
        {prepay.error&&<div className="mt-3"><ErrorState error={prepay.error}/></div>}
        {prepay.data&&<div className="mt-4 grid gap-3 sm:grid-cols-2 text-sm">
          <div className="rounded-xl bg-[var(--surface-2)] p-4"><strong>Reducir cuota</strong><div className="mt-2">Nueva cuota <Money value={prepay.data.reduced_payment}/></div><div>Ahorro neto de intereses <Money value={prepay.data.interest_saved_reduce_payment}/></div></div>
          <div className="rounded-xl bg-[var(--surface-2)] p-4"><strong>Reducir plazo</strong><div className="mt-2">Nuevo plazo {prepay.data.reduced_term_months} meses</div><div>Ahorro neto de intereses <Money value={prepay.data.interest_saved_reduce_term}/></div></div>
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
          <div className="mt-4 overflow-auto"><table className="w-full min-w-[560px] text-sm"><thead><tr className="text-left text-xs uppercase text-[var(--muted)]"><th className="p-2">Desde mes</th><th className="p-2">TIN</th><th className="p-2">Cuota</th><th className="p-2">Saldo al cambio</th></tr></thead><tbody>{ratePath.data.segments.map((s,i)=><tr key={i} className="border-t border-[var(--border)]"><td className="p-2">{s.start_month}</td><td className="p-2">{(Number(s.annual_rate)*100).toFixed(3)}%</td><td className="p-2"><Money value={s.monthly_payment}/></td><td className="p-2"><Money value={s.end_balance}/></td></tr>)}</tbody></table></div>
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
