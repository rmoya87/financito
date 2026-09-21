'use client';

import {FormEvent,useEffect,useMemo,useState} from 'react';
import {useMutation,useQuery,useQueryClient} from '@tanstack/react-query';
import {apiGet,apiMutate} from '@/lib/api';
import {useFinancialFilters} from '@/components/financial-filters';
import {PageHeader} from '@/components/page-header';
import {Card} from '@/components/ui/card';
import {Money} from '@/components/ui/money';
import {EmptyState,ErrorState} from '@/components/ui/states';

type Account={id:string;name:string;institution_name:string};
type Commitment={id:string;account_id:string|null;account_name?:string|null;account_institution?:string|null;title:string;amount:string;due_date:string;status:string;confidence:string};
type Forecast={horizon_start:string;horizon_end:string;baseline_start:string;baseline_end:string;predicted_income:string;predicted_expenses:string;predicted_savings:string;predicted_min_liquidity:string;lower_bound:string;upper_bound:string;known_commitments:string;historical_baseline:string;model_version:string};
const iso=(d:Date)=>d.toISOString().slice(0,10);

export default function ForecastPage(){
  const today=useMemo(()=>new Date(),[]);
  const future=useMemo(()=>new Date(today.getTime()+90*86400000),[today]);
  const [start,setStart]=useState(iso(today));
  const [end,setEnd]=useState(iso(future));
  const [title,setTitle]=useState('');
  const [amount,setAmount]=useState('');
  const [due,setDue]=useState(iso(future));
  const [accountId,setAccountId]=useState('');
  const filters=useFinancialFilters();
  const qc=useQueryClient();
  const accounts=useQuery({queryKey:['accounts','forecast'],queryFn:()=>apiGet<Account[]>('/api/v1/accounts')});
  const commitments=useQuery({queryKey:['commitments'],queryFn:()=>apiGet<Commitment[]>('/api/v1/commitments')});
  const calc=useMutation({mutationFn:()=>apiMutate<Forecast>('/api/v1/forecast','POST',{start,end})});
  const create=useMutation({
    mutationFn:()=>apiMutate('/api/v1/commitments','POST',{account_id:accountId||null,commitment_type:'manual',title,amount,due_date:due,currency:'EUR',mandatory:true,cancellable:false}),
    onSuccess:()=>{setTitle('');setAmount('');qc.invalidateQueries({queryKey:['commitments']})},
  });

  useEffect(()=>{
    if(filters.accountScope.startsWith('account:'))setAccountId(filters.accountScope.slice('account:'.length));
  },[filters.accountScope]);

  function submit(e:FormEvent){e.preventDefault();calc.mutate()}

  return <>
    <PageHeader title="Previsión" description="Combina mismo periodo del año anterior, tendencia acotada y obligaciones futuras conocidas. La cuenta seleccionada arriba limita los datos cuando procede."/>
    <div className="grid gap-4 xl:grid-cols-[1fr_360px]">
      <div className="space-y-4">
        <Card>
          <form onSubmit={submit} className="grid gap-3 sm:grid-cols-[1fr_1fr_auto]">
            <input className="fin-input" aria-label="Inicio de previsión" type="date" value={start} onChange={e=>setStart(e.target.value)}/>
            <input className="fin-input" aria-label="Fin de previsión" type="date" value={end} onChange={e=>setEnd(e.target.value)}/>
            <button className="fin-button">Calcular</button>
          </form>
        </Card>
        {calc.error&&<ErrorState error={calc.error}/>}
        {calc.data&&<>
          <div className="grid gap-4 sm:grid-cols-2">
            <Card><div className="text-xs uppercase text-[var(--muted)]">Gasto previsto</div><div className="mt-2 text-2xl font-bold"><Money value={calc.data.predicted_expenses}/></div><div className="mt-2 text-xs text-[var(--muted)]">Rango <Money value={calc.data.lower_bound}/> – <Money value={calc.data.upper_bound}/></div></Card>
            <Card><div className="text-xs uppercase text-[var(--muted)]">Ahorro previsto</div><div className="mt-2 text-2xl font-bold"><Money value={calc.data.predicted_savings}/></div><div className="mt-2 text-xs text-[var(--muted)]">Liquidez mínima estimada: <Money value={calc.data.predicted_min_liquidity}/></div></Card>
          </div>
          <Card>
            <h2 className="font-bold">Explicación del cálculo</h2>
            <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
              <div><dt className="text-[var(--muted)]">Baseline año anterior</dt><dd><Money value={calc.data.historical_baseline}/> · {calc.data.baseline_start} — {calc.data.baseline_end}</dd></div>
              <div><dt className="text-[var(--muted)]">Compromisos conocidos</dt><dd><Money value={calc.data.known_commitments}/></dd></div>
              <div><dt className="text-[var(--muted)]">Ingresos previstos</dt><dd><Money value={calc.data.predicted_income}/></dd></div>
              <div><dt className="text-[var(--muted)]">Modelo</dt><dd>{calc.data.model_version}</dd></div>
            </dl>
          </Card>
        </>}
      </div>
      <Card>
        <h2 className="font-bold">Añadir compromiso</h2>
        <form className="mt-4 space-y-3" onSubmit={e=>{e.preventDefault();create.mutate()}}>
          <select className="fin-input" aria-label="Cuenta del compromiso" value={accountId} onChange={e=>setAccountId(e.target.value)} required>
            <option value="">Cuenta bancaria…</option>
            {accounts.data?.map(a=><option key={a.id} value={a.id}>{a.institution_name} · {a.name}</option>)}
          </select>
          <input className="fin-input" placeholder="Seguro, impuesto, reserva…" value={title} onChange={e=>setTitle(e.target.value)} required/>
          <input className="fin-input" type="number" step="0.01" placeholder="Importe" value={amount} onChange={e=>setAmount(e.target.value)} required/>
          <input className="fin-input" aria-label="Fecha del compromiso" type="date" value={due} onChange={e=>setDue(e.target.value)} required/>
          <button className="fin-button w-full">Guardar</button>
        </form>
        {create.error&&<div className="mt-3"><ErrorState error={create.error}/></div>}
        <div className="mt-5 space-y-3">{commitments.data?.length?commitments.data.slice(0,8).map(c=><div key={c.id} className="rounded-xl bg-[var(--surface-2)] p-3 text-sm"><div className="font-medium">{c.title}</div><div className="mt-1 text-xs text-[var(--muted)]">{c.account_id?(c.account_institution||'Banco')+' · '+(c.account_name||'Cuenta'):'Sin cuenta vinculada'}</div><div className="mt-1 flex justify-between text-xs text-[var(--muted)]"><span>{c.due_date}</span><strong><Money value={c.amount}/></strong></div></div>):<EmptyState>No hay compromisos.</EmptyState>}</div>
      </Card>
    </div>
  </>;
}
