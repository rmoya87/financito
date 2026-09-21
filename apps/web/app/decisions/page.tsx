'use client';

import Link from 'next/link';
import {FormEvent,useState} from 'react';
import {useMutation,useQuery,useQueryClient} from '@tanstack/react-query';
import {ArrowRight,Calculator,ShieldCheck,Sparkles,TriangleAlert} from 'lucide-react';
import {apiGet,apiMutate} from '@/lib/api';
import {PageHeader} from '@/components/page-header';
import {Card} from '@/components/ui/card';
import {Money} from '@/components/ui/money';
import {EmptyState,ErrorState,Loading} from '@/components/ui/states';
import {DetailGroup,MetricTile,SectionIntro,VisualPanel} from '@/components/finance-ui';

type Decision={id:string;type:string;question:string;status:string;created_at:string};
type Detail={
  id:string;type:string;question:string;status:string;current_state:any;live_current_state:any;assumptions:any;constraints:any;
  alternatives:{id:string;name:string;one_off_cost:string;monthly_cost:string;expected_benefit:string;net_benefit:string;break_even_months:string|null;risk_level:string;uncertainties:any[]}[];
  outcomes:{id:string;selected_alternative_id:string|null;observation_start:string;observation_end:string;expected:any;observed:any;variance:any;explanation:string|null;data_completeness:string}[];
};
type ChoiceCard={id:string;domain:string;title:string;status:string;headline:string;missing:string[];next_action:string;path:string};
type PrepaymentRestriction={
  status:string;calculation_ready:boolean;partial_prepayment_allowed:boolean|null;missing:string[];
  pending_review:{key:string;value:any;document_id:string;page:number|null}[];
  effective_min_amount:string|null;effective_max_amount:string|null;notice_days:number|null;
  frequency_limit_per_year:number|null;window:string|null;condition:string|null;
  allowed_reduction_options:string[];operational_checks:{code:string;message:string}[];
  requires_manual_execution_check:boolean;
};
type Signal={id:string;kind:string;severity:string;title:string;detail:string;action_path:string;source_id:string};
type DecisionOverview={
  summary:{choices:number;requiring_data:number;alerts:number;pending_actions:number};
  financial_context:{
    liquidity:string;
    cash_flow_current_month:{income:string;expenses:string;savings:string;savings_rate:string|null};
    cash_flow_last_90_days:{average_monthly_income:string;average_monthly_expenses:string;average_monthly_savings:string};
    wealth:{net_worth:string};
  };
  prepayment_guardrail:{
    status:string;
    protected_liquidity_reference_months:number;
    protected_liquidity_reference:string|null;
    cash_above_reference:string|null;
    illustrative_extra_payment:string|null;
    scenario:null|{reduced_payment:string|null;reduced_term_months:number|null;interest_saved_reduce_payment:string|null;interest_saved_reduce_term:string|null;allowed_reduction_options:string[]};
    restrictions:PrepaymentRestriction|null;
    missing:string[];
    notice:string;
  };
  signals:Signal[];
  choice_cards:ChoiceCard[];
  rules:string[];
};

const statusLabels:Record<string,string>={
  ready_for_market_check:'Listo para contrastar',
  ready_for_personalized_quote:'Listo para pedir oferta',
  illustrative:'Escenario disponible',
  illustrative_with_manual_check:'Cálculo disponible · revisar paso',
  not_allowed:'No permitido por contrato',
  below_contract_minimum:'No alcanza el mínimo contractual',
  needs_more_data:'Faltan datos',
  needs_mortgage:'Falta hipoteca',
  no_cash_above_reference:'Sin excedente sobre referencia',
};
const priorityLabels:Record<string,string>={high:'Alta',medium:'Media',low:'Baja'};

function readableMissing(value:string):string{
  const map:Record<string,string>={
    mortgage:'hipoteca',
    mortgage_exit_or_subrogation_penalty:'coste de salida/subrogación',
    expense_history:'histórico de gasto',
    confirmed_policy_evidence:'evidencia confirmada de la póliza',
    cancellation_notice_days:'preaviso de cancelación',
    exit_penalty:'coste o penalización de salida',
    verified_coverages:'coberturas verificadas',
    partial_prepayment_allowed:'si el contrato permite amortización parcial',
    prepayment_reduction_options:'si la amortización reduce cuota, plazo o ambas',
    prepayment_penalty:'comisión de amortización anticipada',
  };
  if(map[value])return map[value];
  if(value.startsWith('insurance_evidence:'))return 'evidencia del seguro vinculado';
  if(value.startsWith('insurance_notice:'))return 'preaviso del seguro vinculado';
  if(value.startsWith('insurance_exit_penalty:'))return 'coste de salida del seguro vinculado';
  if(value.startsWith('linked_insurance_mapping:'))return 'vinculación hipotecaria del seguro';
  if(value.startsWith('prepayment_review:'))return 'validar '+readableMissing(value.split(':',2)[1]);
  return value.replaceAll('_',' ');
}

function ChoiceStatus({status}:{status:string}){
  const ready=status.startsWith('ready_')||status==='illustrative';
  return <span className={ready?'rounded-full bg-[var(--brand-soft)] px-2 py-1 text-[10px] font-bold uppercase tracking-wide text-[var(--brand)]':'rounded-full bg-[var(--surface-2)] px-2 py-1 text-[10px] font-bold uppercase tracking-wide text-[var(--muted)]'}>{statusLabels[status]||status.replaceAll('_',' ')}</span>;
}

export default function DecisionsPage(){
  const qc=useQueryClient();
  const overview=useQuery({queryKey:['decision-overview'],queryFn:()=>apiGet<DecisionOverview>('/api/v1/decision-lab/overview')});
  const list=useQuery({queryKey:['decisions'],queryFn:()=>apiGet<Decision[]>('/api/v1/decisions')});
  const [selected,setSelected]=useState('');
  const detail=useQuery({queryKey:['decision',selected],queryFn:()=>apiGet<Detail>('/api/v1/decisions/'+selected),enabled:!!selected});

  const [question,setQuestion]=useState('');
  const [type,setType]=useState('financial_choice');
  const create=useMutation({
    mutationFn:()=>apiMutate<{id:string}>('/api/v1/decisions','POST',{decision_type:type,question,current_state:{},assumptions:{},constraints:{}}),
    onSuccess:d=>{setQuestion('');setSelected(d.id);qc.invalidateQueries({queryKey:['decisions']})},
  });

  const [alt,setAlt]=useState({name:'',one_off_cost:'0',monthly_cost:'0',expected_benefit:'0',risk_level:'unknown',uncertainty:''});
  const addAlt=useMutation({
    mutationFn:()=>apiMutate('/api/v1/decisions/'+selected+'/alternatives','POST',{
      name:alt.name,one_off_cost:alt.one_off_cost,monthly_cost:alt.monthly_cost,expected_benefit:alt.expected_benefit,
      risk_level:alt.risk_level,horizon_results:{},uncertainties:alt.uncertainty?[alt.uncertainty]:[],
    }),
    onSuccess:()=>{setAlt({...alt,name:'',uncertainty:''});qc.invalidateQueries({queryKey:['decision',selected]})},
  });
  const [outcome,setOutcome]=useState({
    selected_alternative_id:'',observation_start:new Date().toISOString().slice(0,10),
    observation_end:new Date().toISOString().slice(0,10),expected:'',observed:'',explanation:'',
  });
  const addOutcome=useMutation({
    mutationFn:()=>apiMutate('/api/v1/decisions/'+selected+'/outcomes','POST',{
      selected_alternative_id:outcome.selected_alternative_id||null,observation_start:outcome.observation_start,
      observation_end:outcome.observation_end,expected_impact:{net:Number(outcome.expected||0)},
      observed_impact:{net:Number(outcome.observed||0)},explanation:outcome.explanation||null,data_completeness:'1',
    }),
    onSuccess:()=>qc.invalidateQueries({queryKey:['decision',selected]}),
  });
  const status=useMutation({
    mutationFn:(s:string)=>apiMutate('/api/v1/decisions/'+selected,'PATCH',{status:s}),
    onSuccess:()=>{qc.invalidateQueries({queryKey:['decision',selected]});qc.invalidateQueries({queryKey:['decisions']})},
  });
  const remove=useMutation({
    mutationFn:(id:string)=>apiMutate('/api/v1/decisions/'+id,'DELETE'),
    onSuccess:(_,id)=>{if(selected===id)setSelected('');qc.invalidateQueries({queryKey:['decisions']})},
  });

  return <>
    <PageHeader title="Mis decisiones" description="Una única lectura de tus datos cruza hipoteca, seguros, movimientos, presupuestos, patrimonio, contratos y evidencia para decir qué se puede comparar ya y qué falta antes de decidir."/>

    {overview.isLoading?<Loading/>:overview.error?<ErrorState error={overview.error}/>:overview.data&&<>
      <SectionIntro eyebrow="Lectura rápida" title="Qué puedes decidir con los datos actuales" description="Separa liquidez, ahorro, alertas y datos pendientes antes de entrar en cada decisión."/>
      <VisualPanel title="Cómo leer los resultados" description="Cada dato indica si está confirmado, calculado o es solo una referencia de mercado." className="mb-4">
        <div className="grid gap-3 md:grid-cols-3 text-sm">
          <div><strong>Confirmado</strong><div className="mt-1 text-xs text-[var(--muted)]">Dato de movimientos o documentos que ya forma parte del cálculo.</div></div>
          <div><strong>Calculado</strong><div className="mt-1 text-xs text-[var(--muted)]">Resultado matemático usando solo datos confirmados y supuestos visibles.</div></div>
          <div><strong>Referencia de mercado</strong><div className="mt-1 text-xs text-[var(--muted)]">Sirve para pedir una oferta; no se trata como condición personal hasta aportar FEIN o presupuesto.</div></div>
        </div>
      </VisualPanel>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <MetricTile label="Liquidez" value={<Money value={overview.data.financial_context.liquidity}/>} detail="Saldo consolidado usado en escenarios" status="Real" statusTone="confirmed"/>
        <MetricTile label="Ahorro este mes" value={<Money value={overview.data.financial_context.cash_flow_current_month.savings}/>} detail="Movimientos reales, reembolsos neteados" status="Calculado" statusTone="calculated"/>
        <MetricTile label="Faltan datos" value={overview.data.summary.requiring_data} detail="Decisiones que todavía no pueden cerrarse" status={overview.data.summary.requiring_data?'Revisar':'Completo'} statusTone={overview.data.summary.requiring_data?'pending':'confirmed'} emphasis={overview.data.summary.requiring_data>0}/>
        <MetricTile label="Alertas" value={overview.data.summary.alerts} detail={overview.data.summary.pending_actions+' acción(es) adicional(es) pendientes'}/>
      </div>

      <VisualPanel className="mt-4" title="Qué puedes decidir ahora" description="Cada tarjeta separa resultado calculable, información pendiente y siguiente paso. No ordena alternativas por un único precio." action={<Sparkles size={20} className="text-[var(--brand)]"/>}>
        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {overview.data.choice_cards.map(choice=><div key={choice.id} className="rounded-xl border border-[var(--border)] p-4">
            <div className="flex items-start justify-between gap-3"><div className="font-semibold">{choice.title}</div><ChoiceStatus status={choice.status}/></div>
            <p className="mt-2 text-sm">{choice.headline}</p>
            {choice.missing.length>0&&<div className="mt-3 rounded-lg bg-[var(--surface-2)] p-3 text-xs"><strong>Antes falta:</strong> {choice.missing.map(readableMissing).join(' · ')}</div>}
            <div className="mt-3 text-xs text-[var(--muted)]"><strong>Siguiente paso:</strong> {choice.next_action}</div>
            <Link href={choice.path} className="mt-3 inline-flex items-center gap-1 text-sm font-semibold text-[var(--brand)]">Abrir <ArrowRight size={14}/></Link>
          </div>)}
        </div>
      </VisualPanel>

      <div className="mt-6"><SectionIntro eyebrow="Profundizar" title="Protecciones y señales antes de actuar" description="Liquidez protegida, condiciones contractuales y alertas se presentan antes de cualquier escenario."/></div>
      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        <Card>
          <div className="flex items-start justify-between gap-3"><div><h2 className="font-bold">Amortización y liquidez</h2><p className="mt-1 text-sm text-[var(--muted)]">La simulación protege primero un colchón de referencia y aplica la comisión contractual real cuando está confirmada.</p></div><Calculator size={20} className="text-[var(--brand)]"/></div>
          <div className="mt-4 grid gap-2 sm:grid-cols-2">
            <div className="rounded-xl bg-[var(--surface-2)] p-3"><div className="text-xs text-[var(--muted)]">Colchón de referencia</div><strong>{overview.data.prepayment_guardrail.protected_liquidity_reference===null?'—':<Money value={overview.data.prepayment_guardrail.protected_liquidity_reference}/>}</strong><div className="text-[11px] text-[var(--muted)]">{overview.data.prepayment_guardrail.protected_liquidity_reference_months} meses del gasto medio reciente</div></div>
            <div className="rounded-xl bg-[var(--surface-2)] p-3"><div className="text-xs text-[var(--muted)]">Efectivo sobre la referencia</div><strong>{overview.data.prepayment_guardrail.cash_above_reference===null?'—':<Money value={overview.data.prepayment_guardrail.cash_above_reference}/>}</strong><div className="text-[11px] text-[var(--muted)]">No se interpreta automáticamente como dinero para amortizar</div></div>
          </div>
          {overview.data.prepayment_guardrail.restrictions&&<div className="mt-3 rounded-xl border border-[var(--border)] p-3 text-xs">
            <strong>Lo que dice tu contrato</strong>
            <div className="mt-1">{overview.data.prepayment_guardrail.restrictions.partial_prepayment_allowed===true?'Permite amortización parcial.':overview.data.prepayment_guardrail.restrictions.partial_prepayment_allowed===false?'No permite amortización parcial.':'Permiso pendiente de confirmar.'}</div>
            <div className="mt-1 text-[var(--muted)]">
              {overview.data.prepayment_guardrail.restrictions.effective_min_amount?'Mínimo '+overview.data.prepayment_guardrail.restrictions.effective_min_amount+' € · ':''}
              {overview.data.prepayment_guardrail.restrictions.effective_max_amount?'Máximo '+overview.data.prepayment_guardrail.restrictions.effective_max_amount+' € · ':''}
              {overview.data.prepayment_guardrail.restrictions.notice_days!==null?'Preaviso '+overview.data.prepayment_guardrail.restrictions.notice_days+' días':'Preaviso sin confirmar'}
            </div>
            {overview.data.prepayment_guardrail.restrictions.pending_review.length>0&&<div className="mt-2 font-medium">Hay condiciones encontradas en tus documentos pendientes de validar.</div>}
          </div>}
          {overview.data.prepayment_guardrail.scenario&&<div className="mt-3 rounded-xl bg-[var(--brand-soft)] p-3 text-sm">
            <strong>Cálculo con <Money value={overview.data.prepayment_guardrail.illustrative_extra_payment||'0'}/></strong>
            <div className="mt-2 grid gap-2 text-xs sm:grid-cols-2">
              {overview.data.prepayment_guardrail.scenario.reduced_payment!==null&&<div>Si reduces cuota: <strong><Money value={overview.data.prepayment_guardrail.scenario.reduced_payment}/></strong><div>Ahorro neto de intereses <Money value={overview.data.prepayment_guardrail.scenario.interest_saved_reduce_payment}/></div></div>}
              {overview.data.prepayment_guardrail.scenario.reduced_term_months!==null&&<div>Si reduces plazo: <strong>{overview.data.prepayment_guardrail.scenario.reduced_term_months} meses</strong><div>Ahorro neto de intereses <Money value={overview.data.prepayment_guardrail.scenario.interest_saved_reduce_term}/></div></div>}
            </div>
          </div>}
          {overview.data.prepayment_guardrail.restrictions?.operational_checks?.length?<div className="mt-3 rounded-xl bg-[var(--surface-2)] p-3 text-xs"><strong>Antes de hacerlo</strong><div className="mt-1 space-y-1">{overview.data.prepayment_guardrail.restrictions.operational_checks.map((item,i)=><div key={item.code+i}>{item.message}</div>)}</div></div>:null}
          <p className="mt-3 text-xs text-[var(--muted)]">{overview.data.prepayment_guardrail.notice}</p>
          <Link href="/tools/" className="mt-3 inline-flex items-center gap-1 text-sm font-semibold text-[var(--brand)]">Abrir simulador <ArrowRight size={14}/></Link>
        </Card>

        <Card>
          <div className="flex items-start justify-between gap-3"><div><h2 className="font-bold">Alertas que pueden cambiar una decisión</h2><p className="mt-1 text-sm text-[var(--muted)]">Presupuestos y movimientos anómalos entran en el mismo contexto que hipoteca y seguros.</p></div><TriangleAlert size={20} className="text-[var(--brand)]"/></div>
          <div className="mt-4 space-y-2">{overview.data.signals.length?overview.data.signals.slice(0,8).map(signal=><Link key={signal.id} href={signal.action_path} className="block rounded-xl bg-[var(--surface-2)] p-3 text-sm hover:ring-1 hover:ring-[var(--brand)]">
            <div className="flex items-center justify-between gap-3"><strong>{signal.title}</strong><span className="text-[10px] font-semibold uppercase text-[var(--muted)]">{priorityLabels[signal.severity]||signal.severity}</span></div>
            <div className="mt-1 text-xs text-[var(--muted)]">{signal.detail}</div>
          </Link>):<EmptyState>No hay presupuestos en alerta ni movimientos anómalos abiertos.</EmptyState>}</div>
          <Link href="/actions/" className="mt-3 inline-flex items-center gap-1 text-sm font-semibold text-[var(--brand)]">Ver todas las acciones <ArrowRight size={14}/></Link>
        </Card>
      </div>

      <Card className="mt-4">
        <div className="flex items-start justify-between gap-3"><div><h2 className="font-bold">Reglas de seguridad de la decisión</h2><p className="mt-1 text-sm text-[var(--muted)]">Son las mismas reglas que recibe la IA local al explicar una decisión.</p></div><ShieldCheck size={20} className="text-[var(--brand)]"/></div>
        <div className="mt-3 grid gap-2 md:grid-cols-2">{overview.data.rules.map(rule=><div key={rule} className="rounded-xl bg-[var(--surface-2)] p-3 text-xs">{rule}</div>)}</div>
      </Card>
    </>}

    <section className="mt-7">
      <SectionIntro eyebrow="Seguimiento" title="Mis decisiones guardadas" description="Guarda una decisión concreta para añadir alternativas, supuestos y después comparar el resultado observado."/>
      <div className="grid gap-4 xl:grid-cols-[360px_1fr]">
        <div className="space-y-4">
          <Card>
            <h3 className="font-bold">Nuevo caso</h3>
            <form className="mt-3 space-y-2" onSubmit={(e:FormEvent)=>{e.preventDefault();create.mutate()}}>
              <select className="fin-input" aria-label="Tipo de decisión" value={type} onChange={e=>setType(e.target.value)}><option value="financial_choice">Decisión financiera</option><option value="mortgage">Hipoteca</option><option value="insurance">Seguro</option><option value="contract_switch">Cambio de contrato</option><option value="investment">Inversión</option></select>
              <textarea className="fin-input min-h-24" placeholder="¿Qué decisión quieres analizar?" value={question} onChange={e=>setQuestion(e.target.value)} required/>
              <button className="fin-button w-full" disabled={create.isPending}>{create.isPending?'Creando…':'Crear caso'}</button>
            </form>
            {create.error&&<div className="mt-3"><ErrorState error={create.error}/></div>}
          </Card>
          <Card>
            <h3 className="font-bold">Historial</h3>
            <div className="mt-3 space-y-2">{list.isLoading?<Loading/>:list.error?<ErrorState error={list.error}/>:list.data?.length?list.data.map(d=><div key={d.id} className={'flex items-start gap-2 rounded-xl p-2 '+(selected===d.id?'bg-[var(--brand-soft)]':'bg-[var(--surface-2)]')}>
              <button className="min-w-0 flex-1 p-1 text-left" onClick={()=>setSelected(d.id)}><div className="font-medium">{d.question}</div><div className="text-xs text-[var(--muted)]">{d.type.replaceAll('_',' ')} · {d.status==='draft'?'Borrador':d.status==='evaluating'?'Evaluando':d.status==='decided'?'Decidida':d.status==='closed'?'Cerrada':'Cancelada'}</div></button>
              <button className="px-2 py-1 text-xs underline" aria-label={'Borrar '+d.question} onClick={()=>remove.mutate(d.id)}>Borrar</button>
            </div>):<EmptyState>Sin decisiones registradas.</EmptyState>}</div>
          </Card>
        </div>

        <div>{!selected?<EmptyState>Selecciona o crea un caso para documentar alternativas y resultado.</EmptyState>:detail.isLoading?<Loading/>:detail.error?<ErrorState error={detail.error}/>:detail.data&&<div className="space-y-4">
          <VisualPanel title={detail.data.question} description={detail.data.type.replaceAll('_',' ')} status={detail.data.status} statusTone={detail.data.status==='closed'||detail.data.status==='decided'?'confirmed':'calculated'} action={<select className="fin-input max-w-44" aria-label="Estado de la decisión" value={detail.data.status} onChange={e=>status.mutate(e.target.value)}><option value="draft">Borrador</option><option value="evaluating">Evaluando</option><option value="decided">Decidida</option><option value="closed">Cerrada</option><option value="cancelled">Cancelada</option></select>}>
            <div className="text-xs text-[var(--muted)]">Puedes cambiar el estado sin perder alternativas ni resultados observados.</div>
          </VisualPanel>

          <VisualPanel title="Qué sabe Financito para este caso" description="La instantánea guardada se contrasta con el contexto vivo actual; ambos proceden de los mismos motores deterministas." status="Contexto vivo" statusTone="calculated">
            <div className="mt-3 grid gap-2 md:grid-cols-4 text-sm">
              <div className="rounded-xl bg-[var(--surface-2)] p-3"><div className="text-xs text-[var(--muted)]">Hipotecas</div><strong>{detail.data.live_current_state?.mortgages?.length??0}</strong></div>
              <div className="rounded-xl bg-[var(--surface-2)] p-3"><div className="text-xs text-[var(--muted)]">Seguros</div><strong>{detail.data.live_current_state?.insurance?.policies?.length??0}</strong></div>
              <div className="rounded-xl bg-[var(--surface-2)] p-3"><div className="text-xs text-[var(--muted)]">Alertas</div><strong>{detail.data.live_current_state?.decision_alerts?.length??0}</strong></div>
              <div className="rounded-xl bg-[var(--surface-2)] p-3"><div className="text-xs text-[var(--muted)]">Liquidez</div><strong><Money value={detail.data.live_current_state?.liquidity??'0'}/></strong></div>
            </div>
          </VisualPanel>

          <DetailGroup title="Alternativas" description="Añade opciones concretas y deja visibles los costes, beneficio esperado, riesgo e incertidumbre.">
            <form className="mt-3 grid gap-2 md:grid-cols-2" onSubmit={(e:FormEvent)=>{e.preventDefault();addAlt.mutate()}}>
              <input className="fin-input" placeholder="Nombre" value={alt.name} onChange={e=>setAlt({...alt,name:e.target.value})} required/>
              <select className="fin-input" aria-label="Nivel de riesgo" value={alt.risk_level} onChange={e=>setAlt({...alt,risk_level:e.target.value})}><option value="unknown">Riesgo desconocido</option><option value="low">Bajo</option><option value="medium">Medio</option><option value="high">Alto</option></select>
              <input className="fin-input" type="number" step=".01" placeholder="Coste inicial" value={alt.one_off_cost} onChange={e=>setAlt({...alt,one_off_cost:e.target.value})}/>
              <input className="fin-input" type="number" step=".01" placeholder="Coste mensual" value={alt.monthly_cost} onChange={e=>setAlt({...alt,monthly_cost:e.target.value})}/>
              <input className="fin-input" type="number" step=".01" placeholder="Beneficio esperado anual" value={alt.expected_benefit} onChange={e=>setAlt({...alt,expected_benefit:e.target.value})}/>
              <input className="fin-input" placeholder="Incertidumbre / dato pendiente" value={alt.uncertainty} onChange={e=>setAlt({...alt,uncertainty:e.target.value})}/>
              <button className="fin-button md:col-span-2" disabled={addAlt.isPending}>Añadir alternativa</button>
            </form>
            {addAlt.error&&<div className="mt-3"><ErrorState error={addAlt.error}/></div>}
            <div className="mt-4 grid gap-3 md:grid-cols-2">{detail.data.alternatives.length?detail.data.alternatives.map(a=><div key={a.id} className="rounded-xl bg-[var(--surface-2)] p-4 text-sm"><strong>{a.name}</strong><div className="mt-2">Beneficio neto anual <Money value={a.net_benefit}/></div><div>Break-even {a.break_even_months??'n/d'} meses · riesgo {a.risk_level}</div>{a.uncertainties.length>0&&<div className="mt-1 text-xs text-[var(--muted)]">Pendiente: {a.uncertainties.join(', ')}</div>}</div>):<EmptyState>Añade alternativas concretas para este caso.</EmptyState>}</div>
          </DetailGroup>

          <DetailGroup title="Resultado observado" description="Cuando ejecutes una decisión, registra qué ocurrió para comparar expectativa y realidad.">
            <form className="mt-3 grid gap-2 md:grid-cols-2" onSubmit={(e:FormEvent)=>{e.preventDefault();addOutcome.mutate()}}>
              <select className="fin-input" aria-label="Alternativa aplicada" value={outcome.selected_alternative_id} onChange={e=>setOutcome({...outcome,selected_alternative_id:e.target.value})}><option value="">Alternativa aplicada…</option>{detail.data.alternatives.map(a=><option key={a.id} value={a.id}>{a.name}</option>)}</select>
              <input className="fin-input" aria-label="Inicio de observación" type="date" value={outcome.observation_start} onChange={e=>setOutcome({...outcome,observation_start:e.target.value})}/>
              <input className="fin-input" aria-label="Fin de observación" type="date" value={outcome.observation_end} onChange={e=>setOutcome({...outcome,observation_end:e.target.value})}/>
              <input className="fin-input" type="number" step=".01" placeholder="Impacto esperado (€)" value={outcome.expected} onChange={e=>setOutcome({...outcome,expected:e.target.value})}/>
              <input className="fin-input" type="number" step=".01" placeholder="Impacto observado (€)" value={outcome.observed} onChange={e=>setOutcome({...outcome,observed:e.target.value})}/>
              <input className="fin-input" placeholder="Explicación" value={outcome.explanation} onChange={e=>setOutcome({...outcome,explanation:e.target.value})}/>
              <button className="fin-button md:col-span-2" disabled={addOutcome.isPending}>Guardar resultado</button>
            </form>
            {addOutcome.error&&<div className="mt-3"><ErrorState error={addOutcome.error}/></div>}
            <div className="mt-4 space-y-2">{detail.data.outcomes.map(o=><div key={o.id} className="rounded-xl bg-[var(--surface-2)] p-3 text-sm"><div>{o.observation_start} → {o.observation_end}</div><div className="text-[var(--muted)]">Variación observada: <Money value={o.variance?.net??0}/> · datos disponibles {Math.round(Number(o.data_completeness)*100)}%</div></div>)}</div>
          </DetailGroup>
        </div>}</div>
      </div>
    </section>
  </>;
}
