'use client';
import {FormEvent,useState} from 'react';
import {useMutation} from '@tanstack/react-query';
import {apiMutate} from '@/lib/api';
import {PageHeader} from '@/components/page-header';
import {Card} from '@/components/ui/card';
import {Money} from '@/components/ui/money';
type Estimate={jurisdiction:string;tax_year:number;realized_pnl:string;estimated_tax:string|null;assumed_rate:string|null;status:string;notice:string;rule_version?:string;sources?:string[];verified_on?:string;missing_inputs?:string[];taxable_savings_base_from_available_data?:string;carryforward_capital_gains?:string};

export default function TaxPage(){
  const [year,setYear]=useState(String(new Date().getFullYear()));
  const [rate,setRate]=useState('');
  const q=useMutation({mutationFn:()=>apiMutate<Estimate>('/api/v1/tax/estimate','POST',{jurisdiction:'ES',tax_year:Number(year),assumed_rate:rate===''?null:rate})});
  return <><PageHeader title="Tax Center" description="Aplica normativa versionada cuando existe un módulo verificado; si no, solo permite una simulación con tasa explícita. Nunca presenta la estimación como declaración oficial."/>
    <Card>
      <form className="grid gap-2 sm:grid-cols-3" onSubmit={(e:FormEvent)=>{e.preventDefault();q.mutate()}}>
        <label className="text-sm">Ejercicio<input className="fin-input mt-1" type="number" value={year} onChange={e=>setYear(e.target.value)}/></label>
        <label className="text-sm">Tasa asumida (solo simulación)<input className="fin-input mt-1" placeholder="Vacío = normativa disponible" value={rate} onChange={e=>setRate(e.target.value)}/></label>
        <button className="fin-button self-end">Calcular</button>
      </form>
      {q.data&&<div className="mt-5 space-y-3">
        <div><div className="text-sm text-[var(--muted)]">P&L realizado detectado</div><div className="text-2xl font-bold"><Money value={q.data.realized_pnl}/></div></div>
        {q.data.taxable_savings_base_from_available_data&&<div className="text-sm">Base del ahorro calculable con los datos disponibles: <strong><Money value={q.data.taxable_savings_base_from_available_data}/></strong></div>}
        <div className="text-sm">{q.data.estimated_tax===null?'No hay cálculo normativo disponible para ese ejercicio y falta una tasa de simulación.':'Impuesto estimado con el alcance indicado: '+q.data.estimated_tax+' €'}</div>
        {q.data.rule_version&&<div className="rounded-xl bg-[var(--surface-2)] p-4 text-sm"><strong>Regla:</strong> {q.data.rule_version}{q.data.verified_on&&<> · verificada {q.data.verified_on}</>}<br/>{q.data.sources?.map((source)=><a key={source} className="block underline" href={source} target="_blank" rel="noreferrer">Fuente oficial</a>)}</div>}
        {q.data.missing_inputs?.length?<div className="text-sm"><strong>Para una liquidación completa aún faltan:</strong> {q.data.missing_inputs.join('; ')}.</div>:null}
        <div className="text-xs text-[var(--muted)]">{q.data.notice}</div>
      </div>}
    </Card>
  </>;
}
