'use client';

export type DateRangeKey='month'|'30d'|'90d'|'year'|'12m'|'all'|'custom';

export function isoDate(value:Date){
  const y=value.getFullYear();
  const m=String(value.getMonth()+1).padStart(2,'0');
  const d=String(value.getDate()).padStart(2,'0');
  return `${y}-${m}-${d}`;
}

export function resolveDateRange(range:DateRangeKey,customStart='',customEnd='',reference?:Date){
  if(range==='custom')return {start:customStart,end:customEnd};
  const end=reference?new Date(reference):new Date();
  const start=new Date(end);
  if(range==='month')start.setDate(1);
  if(range==='30d')start.setDate(start.getDate()-29);
  if(range==='90d')start.setDate(start.getDate()-89);
  if(range==='year'){start.setMonth(0);start.setDate(1)}
  if(range==='12m')start.setFullYear(start.getFullYear()-1);
  if(range==='all')return {start:'1900-01-01',end:isoDate(end)};
  return {start:isoDate(start),end:isoDate(end)};
}

export function DateRangeSelector({
  range,customStart,customEnd,onRangeChange,onCustomStartChange,onCustomEndChange,ariaLabel='Periodo',
}:{
  range:DateRangeKey;
  customStart:string;
  customEnd:string;
  onRangeChange:(value:DateRangeKey)=>void;
  onCustomStartChange:(value:string)=>void;
  onCustomEndChange:(value:string)=>void;
  ariaLabel?:string;
}){
  return <div className="flex flex-wrap items-end justify-end gap-2">
    <label className="block text-xs font-medium text-[var(--muted)]">Periodo
      <select className="fin-input mt-1 min-w-[180px]" aria-label={ariaLabel} value={range} onChange={e=>onRangeChange(e.target.value as DateRangeKey)}>
        <option value="month">Este mes</option>
        <option value="30d">Últimos 30 días</option>
        <option value="90d">Últimos 90 días</option>
        <option value="year">Este año</option>
        <option value="12m">Últimos 12 meses</option>
        <option value="all">Todo el histórico</option>
        <option value="custom">Personalizado</option>
      </select>
    </label>
    {range==='custom'&&<>
      <label className="block text-xs font-medium text-[var(--muted)]">Desde
        <input className="fin-input mt-1 w-auto" type="date" value={customStart} max={customEnd||undefined} onChange={e=>onCustomStartChange(e.target.value)}/>
      </label>
      <label className="block text-xs font-medium text-[var(--muted)]">Hasta
        <input className="fin-input mt-1 w-auto" type="date" value={customEnd} min={customStart||undefined} onChange={e=>onCustomEndChange(e.target.value)}/>
      </label>
    </>}
  </div>;
}
