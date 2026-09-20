'use client';

import {FormEvent,useMemo,useState} from 'react';
import {useMutation} from '@tanstack/react-query';
import {apiMutate} from '@/lib/api';
import {PageHeader} from '@/components/page-header';
import {Card} from '@/components/ui/card';
import {Money} from '@/components/ui/money';
import {ErrorState} from '@/components/ui/states';

type Mortgage={monthly_payment:string;total_payments:string;total_interest:string};
type Prepay={original_monthly_payment:string;original_total_interest:string;reduced_payment:string;reduced_payment_total_interest:string;reduced_term_months:number;reduced_term_total_interest:string;prepayment_fee:string;interest_saved_reduce_payment:string;interest_saved_reduce_term:string};
type RatePath={total_payments:string;total_interest:string;min_monthly_payment:string;max_monthly_payment:string;final_balance:string;notice:string;segments:{start_month:number;annual_rate:string;monthly_payment:string;end_balance:string}[]};
type IndexedPath={status:string;missing_revision_months:number[];applied_rate_steps:{month:number;annual_rate:string}[];notice:string;total_payments?:string;total_interest?:string;min_monthly_payment?:string;max_monthly_payment?:string;final_balance?:string;segments?:{start_month:number;annual_rate:string;monthly_payment:string;end_balance:string}[]};
type Opt={status:string;net_annual_benefit:string|null;break_even_months:string|null};

function parseIndexCurve(raw:string){
  if(!raw.trim())return [];
  return raw.split(',').map((piece)=>{
    const [month,rate]=piece.trim().split(':');
    const m=Number(month);const r=Number((rate||'').replace(',','.'));
    if(!Number.isFinite(m)||!Number.isInteger(m)||m<1||!Number.isFinite(r))throw new Error('Usa mes:índice_decimal, por ejemplo 13:0.02,25:0.025');
    return {month:m,index_rate:String(r)};
  });
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
  const [principal,setPrincipal]=useState('200000');
  const [rate,setRate]=useState('0.025');
  const [months,setMonths]=useState('300');
  const [extra,setExtra]=useState('10000');
  const [fee,setFee]=useState('0');
  const [pathSpec,setPathSpec]=useState('13:0.035,25:0.04');
  const [pathError,setPathError]=useState('');
  const [indexedType,setIndexedType]=useState<'variable'|'mixed'>('mixed');
  const [indexedMonths,setIndexedMonths]=useState('36');
  const [revisionMonths,setRevisionMonths]=useState('12');
  const [spread,setSpread]=useState('0.01');
  const [fixedPeriod,setFixedPeriod]=useState('12');
  const [fixedRate,setFixedRate]=useState('0.018');
  const [floorRate,setFloorRate]=useState('');
  const [capRate,setCapRate]=useState('');
  const [indexSpec,setIndexSpec]=useState('13:0.02,25:0.025');
  const [indexError,setIndexError]=useState('');
  const mortgage=useMutation({mutationFn:()=>apiMutate<Mortgage>('/api/v1/mortgage/scenario','POST',{principal,annual_rate:rate,months:Number(months)})});
  const prepay=useMutation({mutationFn:()=>apiMutate<Prepay>('/api/v1/mortgage/prepayment','POST',{principal,annual_rate:rate,months:Number(months),extra_payment:extra,prepayment_fee:fee})});
  const ratePath=useMutation({mutationFn:()=>{
    const rate_steps=parseRatePath(pathSpec);
    return apiMutate<RatePath>('/api/v1/mortgage/rate-path','POST',{principal,months:Number(months),initial_annual_rate:rate,rate_steps});
  }});
  const indexedPath=useMutation({mutationFn:()=>apiMutate<IndexedPath>('/api/v1/mortgage/indexed-path','POST',{
    principal,months:Number(indexedMonths),interest_type:indexedType,revision_frequency_months:Number(revisionMonths),
    index_curve:parseIndexCurve(indexSpec),spread,fixed_period_months:indexedType==='mixed'?Number(fixedPeriod):0,
    fixed_annual_rate:indexedType==='mixed'?fixedRate:null,floor_rate:floorRate===''?null:floorRate,cap_rate:capRate===''?null:capRate,
  })});
  const [gross,setGross]=useState('600');
  const [switching,setSwitching]=useState('100');
  const [penalty,setPenalty]=useState('');
  const opt=useMutation({mutationFn:()=>apiMutate<Opt>('/api/v1/optimization/calculate','POST',{gross_annual_saving:gross,switching_costs:switching,penalties:penalty===''?null:penalty,lost_benefits:'0',additional_recurring_costs:'0',tax_impact:'0'})});
  return <>
    <PageHeader title="Laboratorio de decisiones" description="Motores deterministas con supuestos explícitos. Un dato contractual desconocido no se convierte en cero y una senda de tipos no se presenta como predicción."/>
    <div className="grid gap-4 xl:grid-cols-2">
      <Card>
        <h2 className="font-bold">Escenario hipotecario</h2>
        <form className="mt-4 grid gap-3" onSubmit={(e:FormEvent)=>{e.preventDefault();mortgage.mutate()}}>
          <label className="text-sm">Capital pendiente<input className="fin-input mt-1" value={principal} onChange={e=>setPrincipal(e.target.value)}/></label>
          <label className="text-sm">TIN anual decimal<input className="fin-input mt-1" value={rate} onChange={e=>setRate(e.target.value)} placeholder="0.025 = 2,5%"/></label>
          <label className="text-sm">Meses restantes<input className="fin-input mt-1" value={months} onChange={e=>setMonths(e.target.value)}/></label>
          <button className="fin-button">Calcular</button>
        </form>
        {mortgage.error&&<div className="mt-3"><ErrorState error={mortgage.error}/></div>}
        {mortgage.data&&<dl className="mt-5 grid gap-3 sm:grid-cols-3 text-sm"><div><dt className="text-[var(--muted)]">Cuota</dt><dd className="font-bold"><Money value={mortgage.data.monthly_payment}/></dd></div><div><dt className="text-[var(--muted)]">Intereses</dt><dd className="font-bold"><Money value={mortgage.data.total_interest}/></dd></div><div><dt className="text-[var(--muted)]">Total</dt><dd className="font-bold"><Money value={mortgage.data.total_payments}/></dd></div></dl>}
      </Card>
      <Card>
        <h2 className="font-bold">Amortización extraordinaria</h2>
        <p className="mt-1 text-sm text-[var(--muted)]">Compara mantener plazo reduciendo cuota frente a mantener cuota reduciendo plazo.</p>
        <form className="mt-4 grid gap-3" onSubmit={(e:FormEvent)=>{e.preventDefault();prepay.mutate()}}>
          <label className="text-sm">Importe a amortizar<input className="fin-input mt-1" value={extra} onChange={e=>setExtra(e.target.value)}/></label>
          <label className="text-sm">Comisión total conocida<input className="fin-input mt-1" value={fee} onChange={e=>setFee(e.target.value)}/></label>
          <button className="fin-button">Comparar</button>
        </form>
        {prepay.error&&<div className="mt-3"><ErrorState error={prepay.error}/></div>}
        {prepay.data&&<div className="mt-4 grid gap-3 sm:grid-cols-2 text-sm"><div className="rounded-xl bg-[var(--surface-2)] p-4"><strong>Reducir cuota</strong><div className="mt-2">Nueva cuota <Money value={prepay.data.reduced_payment}/></div><div>Ahorro neto de intereses <Money value={prepay.data.interest_saved_reduce_payment}/></div></div><div className="rounded-xl bg-[var(--surface-2)] p-4"><strong>Reducir plazo</strong><div className="mt-2">Nuevo plazo {prepay.data.reduced_term_months} meses</div><div>Ahorro neto de intereses <Money value={prepay.data.interest_saved_reduce_term}/></div></div></div>}
      </Card>
      <Card className="xl:col-span-2">
        <h2 className="font-bold">Senda hipotética de tipos</h2>
        <p className="mt-1 text-sm text-[var(--muted)]">Usa el capital/plazo/TIN de arriba. Introduce cambios en formato <code>mes:tipo_decimal</code>, separados por comas.</p>
        <form className="mt-4 grid gap-3 md:grid-cols-[1fr_auto]" onSubmit={(e:FormEvent)=>{e.preventDefault();try{parseRatePath(pathSpec);setPathError('');ratePath.mutate()}catch(err){setPathError(err instanceof Error?err.message:String(err))}}}>
          <label className="text-sm">Cambios de tipo<input className="fin-input mt-1" value={pathSpec} onChange={e=>setPathSpec(e.target.value)} placeholder="13:0.035,25:0.04"/></label>
          <button className="fin-button self-end">Simular</button>
        </form>
        {pathError&&<div className="mt-3 text-sm">{pathError}</div>}
        {ratePath.error&&<div className="mt-3"><ErrorState error={ratePath.error}/></div>}
        {ratePath.data&&<div className="mt-4"><div className="grid gap-3 sm:grid-cols-4 text-sm"><div><span className="text-[var(--muted)]">Intereses</span><div className="font-bold"><Money value={ratePath.data.total_interest}/></div></div><div><span className="text-[var(--muted)]">Cuota mínima</span><div className="font-bold"><Money value={ratePath.data.min_monthly_payment}/></div></div><div><span className="text-[var(--muted)]">Cuota máxima</span><div className="font-bold"><Money value={ratePath.data.max_monthly_payment}/></div></div><div><span className="text-[var(--muted)]">Saldo final</span><div className="font-bold"><Money value={ratePath.data.final_balance}/></div></div></div><div className="mt-4 overflow-auto"><table className="w-full min-w-[560px] text-sm"><thead><tr className="text-left text-xs uppercase text-[var(--muted)]"><th className="p-2">Desde mes</th><th className="p-2">TIN</th><th className="p-2">Cuota</th><th className="p-2">Saldo al cambio</th></tr></thead><tbody>{ratePath.data.segments.map((s,i)=><tr key={i} className="border-t border-[var(--border)]"><td className="p-2">{s.start_month}</td><td className="p-2">{(Number(s.annual_rate)*100).toFixed(3)}%</td><td className="p-2"><Money value={s.monthly_payment}/></td><td className="p-2"><Money value={s.end_balance}/></td></tr>)}</tbody></table></div><p className="mt-3 text-xs text-[var(--muted)]">{ratePath.data.notice}</p></div>}
      </Card>
      <Card className="xl:col-span-2">
        <h2 className="font-bold">Hipoteca variable o mixta por índice</h2>
        <p className="mt-1 text-sm text-[var(--muted)]">Introduce el índice en cada mes contractual de revisión. No se interpolan ni predicen valores ausentes.</p>
        <form className="mt-4 grid gap-3 md:grid-cols-3" onSubmit={(e:FormEvent)=>{e.preventDefault();try{parseIndexCurve(indexSpec);setIndexError('');indexedPath.mutate()}catch(err){setIndexError(err instanceof Error?err.message:String(err))}}}>
          <label className="text-sm">Tipo<select className="fin-input mt-1" value={indexedType} onChange={e=>setIndexedType(e.target.value as 'variable'|'mixed')}><option value="variable">Variable</option><option value="mixed">Mixta</option></select></label>
          <label className="text-sm">Meses restantes<input className="fin-input mt-1" value={indexedMonths} onChange={e=>setIndexedMonths(e.target.value)}/></label>
          <label className="text-sm">Revisión cada N meses<input className="fin-input mt-1" value={revisionMonths} onChange={e=>setRevisionMonths(e.target.value)}/></label>
          <label className="text-sm">Diferencial decimal<input className="fin-input mt-1" value={spread} onChange={e=>setSpread(e.target.value)}/></label>
          {indexedType==='mixed'&&<><label className="text-sm">Tramo fijo (meses)<input className="fin-input mt-1" value={fixedPeriod} onChange={e=>setFixedPeriod(e.target.value)}/></label><label className="text-sm">TIN tramo fijo<input className="fin-input mt-1" value={fixedRate} onChange={e=>setFixedRate(e.target.value)}/></label></>}
          <label className="text-sm">Suelo (opcional)<input className="fin-input mt-1" value={floorRate} onChange={e=>setFloorRate(e.target.value)}/></label>
          <label className="text-sm">Techo (opcional)<input className="fin-input mt-1" value={capRate} onChange={e=>setCapRate(e.target.value)}/></label>
          <label className="text-sm md:col-span-3">Curva de índice<input className="fin-input mt-1" value={indexSpec} onChange={e=>setIndexSpec(e.target.value)} placeholder="13:0.02,25:0.025"/></label>
          <button className="fin-button md:col-span-3">Calcular revisiones</button>
        </form>
        {indexError&&<div className="mt-3 text-sm">{indexError}</div>}
        {indexedPath.error&&<div className="mt-3"><ErrorState error={indexedPath.error}/></div>}
        {indexedPath.data?.status==='needs_more_data'&&<div className="mt-4 rounded-xl bg-[var(--surface-2)] p-4 text-sm">Faltan índices para los meses de revisión: {indexedPath.data.missing_revision_months.join(', ')}.</div>}
        {indexedPath.data?.status==='ready'&&<div className="mt-4 grid gap-3 sm:grid-cols-4 text-sm"><div><span className="text-[var(--muted)]">Intereses</span><div className="font-bold"><Money value={indexedPath.data.total_interest||'0'}/></div></div><div><span className="text-[var(--muted)]">Cuota mínima</span><div className="font-bold"><Money value={indexedPath.data.min_monthly_payment||'0'}/></div></div><div><span className="text-[var(--muted)]">Cuota máxima</span><div className="font-bold"><Money value={indexedPath.data.max_monthly_payment||'0'}/></div></div><div><span className="text-[var(--muted)]">Saldo final</span><div className="font-bold"><Money value={indexedPath.data.final_balance||'0'}/></div></div></div>}
        {indexedPath.data&&<p className="mt-3 text-xs text-[var(--muted)]">{indexedPath.data.notice}</p>}
      </Card>
      <Card className="xl:col-span-2">
        <h2 className="font-bold">Cambio de producto</h2>
        <form className="mt-4 grid gap-3 md:grid-cols-4" onSubmit={(e:FormEvent)=>{e.preventDefault();opt.mutate()}}>
          <label className="text-sm">Ahorro bruto anual<input className="fin-input mt-1" value={gross} onChange={e=>setGross(e.target.value)}/></label>
          <label className="text-sm">Costes de cambio<input className="fin-input mt-1" value={switching} onChange={e=>setSwitching(e.target.value)}/></label>
          <label className="text-sm">Penalización<input className="fin-input mt-1" value={penalty} onChange={e=>setPenalty(e.target.value)} placeholder="Vacío si no consta"/></label>
          <button className="fin-button self-end">Evaluar</button>
        </form>
        {opt.data&&<div className="mt-5 rounded-xl bg-[var(--surface-2)] p-4"><div className="text-xs uppercase text-[var(--muted)]">Estado: {opt.data.status}</div>{opt.data.net_annual_benefit!==null?<><div className="mt-2 text-2xl font-bold"><Money value={opt.data.net_annual_benefit}/>/año</div>{opt.data.break_even_months&&<div className="text-sm text-[var(--muted)]">Break-even: {opt.data.break_even_months} meses</div>}</>:<div className="mt-2 text-sm">Falta evidencia de la penalización. Financito no asume que sea 0.</div>}</div>}
      </Card>
    </div>
  </>
}
