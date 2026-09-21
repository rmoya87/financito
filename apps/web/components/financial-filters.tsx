'use client';

import {createContext,useContext,useEffect,useMemo,useState} from 'react';
import {useQuery,useQueryClient} from '@tanstack/react-query';
import {apiGet} from '@/lib/api';
import {FinancialFilters,GlobalDateRange,defaultFinancialFilters,readFinancialFilters,resolveGlobalDateRange,writeFinancialFilters} from '@/lib/financial-filters';

type Account={
  id:string;name:string;institution_name:string;account_type:string;currency:string;
  current_balance:string;available_balance:string|null
};

type ContextValue=FinancialFilters&{
  start:string;
  end:string;
  setRange:(value:GlobalDateRange)=>void;
  setCustomStart:(value:string)=>void;
  setCustomEnd:(value:string)=>void;
  setAccountScope:(value:string)=>void;
};

const Context=createContext<ContextValue|null>(null);

const typeLabels:Record<string,string>={
  checking:'Cuenta corriente',savings:'Ahorro',brokerage:'Inversión / broker',
  investment:'Inversión',credit:'Crédito',cash:'Efectivo',card:'Tarjeta',CACC:'Cuenta corriente',other:'Otra',
};

export function FinancialFiltersProvider({children}:{children:React.ReactNode}){
  const qc=useQueryClient();
  const [filters,setFilters]=useState<FinancialFilters>(()=>defaultFinancialFilters());
  const [hydrated,setHydrated]=useState(false);
  const dates=useMemo(
    ()=>resolveGlobalDateRange(filters.range,filters.customStart,filters.customEnd),
    [filters.range,filters.customStart,filters.customEnd],
  );

  useEffect(()=>{
    setFilters(readFinancialFilters());
    setHydrated(true);
  },[]);

  useEffect(()=>{
    if(!hydrated)return;
    writeFinancialFilters(filters);
    qc.invalidateQueries();
  },[filters,hydrated,qc]);

  const value:ContextValue={
    ...filters,start:dates.start,end:dates.end,
    setRange:range=>setFilters(current=>({...current,range})),
    setCustomStart:customStart=>setFilters(current=>({...current,customStart})),
    setCustomEnd:customEnd=>setFilters(current=>({...current,customEnd})),
    setAccountScope:accountScope=>setFilters(current=>({...current,accountScope})),
  };
  return <Context.Provider value={value}>{children}</Context.Provider>;
}

export function useFinancialFilters(){
  const value=useContext(Context);
  if(!value)throw new Error('useFinancialFilters must be used inside FinancialFiltersProvider');
  return value;
}

export function GlobalFinancialFilters(){
  const filters=useFinancialFilters();
  const accounts=useQuery({queryKey:['accounts','global-filter'],queryFn:()=>apiGet<Account[]>('/api/v1/accounts')});
  const accountTypes=Array.from(new Set((accounts.data||[]).map(a=>a.account_type).filter(Boolean))).sort();

  return <div className="mb-5 flex flex-wrap items-end justify-between gap-3 rounded-2xl border border-[var(--border)] bg-white p-3" aria-label="Filtros financieros globales">
    <label className="block min-w-0 flex-1 text-xs font-medium text-[var(--muted)] sm:max-w-sm">Cuenta
      <select className="fin-input mt-1 w-full" aria-label="Cuenta o tipo de cuenta global" value={filters.accountScope} onChange={e=>filters.setAccountScope(e.target.value)}>
        <option value="all">Todas las cuentas</option>
        {accountTypes.length>0&&<optgroup label="Por tipo de cuenta">
          {accountTypes.map(type=><option key={type} value={'type:'+type}>{typeLabels[type]||type}</option>)}
        </optgroup>}
        {(accounts.data?.length||0)>0&&<optgroup label="Cuenta concreta">
          {accounts.data?.map(account=><option key={account.id} value={'account:'+account.id}>{account.institution_name} · {account.name}</option>)}
        </optgroup>}
      </select>
    </label>

    <div className="flex flex-wrap items-end justify-end gap-2">
      <label className="block text-xs font-medium text-[var(--muted)]">Periodo
        <select className="fin-input mt-1 min-w-[170px]" aria-label="Periodo global" value={filters.range} onChange={e=>filters.setRange(e.target.value as GlobalDateRange)}>
          <option value="month">Este mes</option>
          <option value="30d">Últimos 30 días</option>
          <option value="90d">Últimos 90 días</option>
          <option value="year">Este año</option>
          <option value="12m">Últimos 12 meses</option>
          <option value="all">Todo el histórico</option>
          <option value="custom">Personalizado</option>
        </select>
      </label>
      {filters.range==='custom'&&<>
        <label className="block text-xs font-medium text-[var(--muted)]">Desde
          <input className="fin-input mt-1 w-auto" type="date" value={filters.customStart} max={filters.customEnd||undefined} onChange={e=>filters.setCustomStart(e.target.value)}/>
        </label>
        <label className="block text-xs font-medium text-[var(--muted)]">Hasta
          <input className="fin-input mt-1 w-auto" type="date" value={filters.customEnd} min={filters.customStart||undefined} onChange={e=>filters.setCustomEnd(e.target.value)}/>
        </label>
      </>}
    </div>
  </div>;
}
