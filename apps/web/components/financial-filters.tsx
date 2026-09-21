'use client';

import {createContext,useContext,useEffect,useMemo,useRef,useState} from 'react';
import {useQuery,useQueryClient} from '@tanstack/react-query';
import {CalendarDays,ChevronDown,Landmark} from 'lucide-react';
import {apiGet} from '@/lib/api';
import {
  FinancialFilters,GlobalDateRange,defaultFinancialFilters,financialRangeLabel,
  globalDateRangeLabels,isoFinancialDate,readFinancialFilters,resolveGlobalDateRange,writeFinancialFilters,
} from '@/lib/financial-filters';

type Account={
  id:string;name:string;institution_name:string;account_type:string;currency:string;
  current_balance:string;available_balance:string|null
};

type ContextValue=FinancialFilters&{
  start:string;
  end:string;
  setRange:(value:GlobalDateRange)=>void;
  setCustomRange:(start:string,end:string)=>void;
  setAccountScope:(value:string)=>void;
};

const Context=createContext<ContextValue|null>(null);

const visibleRanges:GlobalDateRange[]=['month','previous_month','30d','90d','180d','12m','all'];

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
    void qc.cancelQueries().then(()=>qc.invalidateQueries());
  },[filters,hydrated,qc]);

  const value:ContextValue={
    ...filters,start:dates.start,end:dates.end,
    setRange:range=>setFilters(current=>({...current,range})),
    setCustomRange:(customStart,customEnd)=>setFilters(current=>({...current,range:'custom',customStart,customEnd})),
    setAccountScope:accountScope=>setFilters(current=>({...current,accountScope})),
  };
  return <Context.Provider value={value}>{children}</Context.Provider>;
}

export function useFinancialFilters(){
  const value=useContext(Context);
  if(!value)throw new Error('useFinancialFilters must be used inside FinancialFiltersProvider');
  return value;
}

function PeriodRangePicker({compact}:{compact:boolean}){
  const filters=useFinancialFilters();
  const root=useRef<HTMLDivElement>(null);
  const startInput=useRef<HTMLInputElement>(null);
  const [open,setOpen]=useState(false);
  const [draftStart,setDraftStart]=useState(filters.start);
  const [draftEnd,setDraftEnd]=useState(filters.end);
  const label=financialRangeLabel(filters.range,filters.start,filters.end);
  const validCustom=!!draftStart&&!!draftEnd&&draftStart<=draftEnd;

  useEffect(()=>{
    if(!open)return;
    setDraftStart(filters.start);
    setDraftEnd(filters.end);
    const close=(event:PointerEvent)=>{
      if(root.current&&!root.current.contains(event.target as Node))setOpen(false);
    };
    const escape=(event:KeyboardEvent)=>{if(event.key==='Escape')setOpen(false)};
    document.addEventListener('pointerdown',close);
    document.addEventListener('keydown',escape);
    return ()=>{
      document.removeEventListener('pointerdown',close);
      document.removeEventListener('keydown',escape);
    };
  },[open,filters.start,filters.end]);

  function chooseRange(value:GlobalDateRange){
    filters.setRange(value);
    setOpen(false);
  }

  function applyCustom(){
    if(!validCustom)return;
    filters.setCustomRange(draftStart,draftEnd);
    setOpen(false);
  }

  function chooseToday(){
    const today=isoFinancialDate(new Date());
    setDraftStart(today);
    setDraftEnd(today);
  }

  return <div className="relative" ref={root}>
    {!compact&&<div className="mb-1 text-xs font-medium text-[var(--muted)]">Periodo</div>}
    <button
      type="button"
      className={compact
        ?"flex min-h-10 min-w-[178px] items-center justify-between gap-2 rounded-xl border border-[var(--border)] bg-white px-3 py-2 text-sm font-semibold shadow-sm hover:bg-[var(--surface-2)]"
        :"flex min-h-11 min-w-[200px] items-center justify-between gap-2 rounded-xl border border-[var(--border)] bg-white px-3 py-2 text-sm font-semibold shadow-sm hover:bg-[var(--surface-2)]"
      }
      aria-label={'Periodo global: '+label}
      aria-haspopup="dialog"
      aria-expanded={open}
      onClick={()=>setOpen(value=>!value)}
    >
      <span className="flex min-w-0 items-center gap-2"><CalendarDays size={17} className="shrink-0 text-[var(--brand)]"/><span className="truncate">{label}</span></span>
      <ChevronDown size={15} className={'shrink-0 transition-transform '+(open?'rotate-180':'')}/>
    </button>

    {open&&<div
      role="dialog"
      aria-label="Seleccionar periodo"
      className="absolute right-0 z-[80] mt-2 w-[min(700px,calc(100vw-2rem))] overflow-hidden rounded-2xl border border-[var(--border)] bg-white shadow-2xl"
    >
      <div className="grid md:grid-cols-[minmax(320px,1fr)_220px]">
        <div className="p-4 md:p-5">
          <div className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">Rango personalizado</div>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <label className="text-xs font-medium text-[var(--muted)]">Inicio
              <input ref={startInput} className="fin-input mt-1 w-full" aria-label="Inicio del periodo" type="date" value={draftStart} max={draftEnd||undefined} onChange={e=>setDraftStart(e.target.value)}/>
            </label>
            <label className="text-xs font-medium text-[var(--muted)]">Fin
              <input className="fin-input mt-1 w-full" aria-label="Fin del periodo" type="date" value={draftEnd} min={draftStart||undefined} onChange={e=>setDraftEnd(e.target.value)}/>
            </label>
          </div>
          <div className="mt-4 rounded-xl bg-[var(--surface-2)] p-3 text-sm">
            <div className="text-xs text-[var(--muted)]">Periodo seleccionado</div>
            <div className="mt-1 font-semibold">{financialRangeLabel('custom',draftStart,draftEnd)}</div>
          </div>
          <div className="mt-4 flex items-center justify-between gap-2 border-t border-[var(--border)] pt-4">
            <button className="text-sm font-medium underline" type="button" onClick={chooseToday}>Hoy</button>
            <div className="flex gap-2">
              <button className="fin-button secondary py-2 text-xs" type="button" onClick={()=>setOpen(false)}>Cancelar</button>
              <button className="fin-button py-2 text-xs" type="button" disabled={!validCustom} onClick={applyCustom}>Aplicar</button>
            </div>
          </div>
        </div>

        <div className="border-t border-[var(--border)] bg-[var(--surface-2)] p-3 md:border-l md:border-t-0">
          <div className="px-2 pb-2 text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">Periodos rápidos</div>
          <div className="space-y-1">
            {visibleRanges.map(value=><button
              key={value}
              type="button"
              className={'block w-full rounded-xl px-3 py-2.5 text-left text-sm font-medium transition-colors '+(filters.range===value?'bg-white text-[var(--text)] shadow-sm':'text-[var(--text)] hover:bg-white/80')}
              onClick={()=>chooseRange(value)}
            >{globalDateRangeLabels[value]}</button>)}
            <div className="my-2 border-t border-[var(--border)]"/>
            <button
              type="button"
              className={'block w-full rounded-xl px-3 py-2.5 text-left text-sm font-medium transition-colors '+(filters.range==='custom'?'bg-white text-[var(--text)] shadow-sm':'hover:bg-white/80')}
              onClick={()=>startInput.current?.focus()}
            >Personalizado</button>
          </div>
        </div>
      </div>
    </div>}
  </div>;
}

export function GlobalFinancialFilters({compact=false}:{compact?:boolean}={}){
  const filters=useFinancialFilters();
  const accounts=useQuery({queryKey:['accounts','global-filter'],queryFn:()=>apiGet<Account[]>('/api/v1/accounts')});
  const accountSelect=<div className={compact
    ?"flex min-h-10 min-w-[190px] items-center rounded-xl border border-[var(--border)] bg-white shadow-sm"
    :"flex min-h-11 w-full items-center rounded-xl border border-[var(--border)] bg-white"
  }>
    <Landmark size={16} className="ml-3 shrink-0 text-[var(--brand)]"/>
    <select
      className="min-h-9 min-w-0 flex-1 appearance-none bg-transparent px-2 pr-8 text-sm font-semibold outline-none"
      aria-label="Cuenta global"
      value={filters.accountScope}
      onChange={e=>filters.setAccountScope(e.target.value)}
    >
      <option value="all">Todas las cuentas</option>
      {accounts.data?.map(account=><option key={account.id} value={'account:'+account.id}>{account.institution_name} · {account.name}</option>)}
    </select>
    <ChevronDown size={14} className="mr-3 shrink-0 text-[var(--muted)]"/>
  </div>;

  if(compact){
    return <div className="flex min-w-0 flex-wrap items-center justify-end gap-2" aria-label="Filtros financieros globales">
      {accountSelect}
      <PeriodRangePicker compact/>
    </div>;
  }

  return <div className="mb-5 flex flex-wrap items-end justify-between gap-3 rounded-2xl border border-[var(--border)] bg-white p-3" aria-label="Filtros financieros globales">
    <label className="block min-w-0 flex-1 text-xs font-medium text-[var(--muted)] sm:max-w-sm">Cuenta
      <div className="mt-1">{accountSelect}</div>
    </label>
    <PeriodRangePicker compact={false}/>
  </div>;
}
