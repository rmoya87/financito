export type GlobalDateRange='month'|'30d'|'90d'|'year'|'12m'|'all'|'custom';

export type FinancialFilters={
  range:GlobalDateRange;
  customStart:string;
  customEnd:string;
  accountScope:string;
};

const STORAGE_KEY='financito.financialFilters.v1';

export function isoFinancialDate(value:Date){
  const y=value.getFullYear();
  const m=String(value.getMonth()+1).padStart(2,'0');
  const d=String(value.getDate()).padStart(2,'0');
  return `${y}-${m}-${d}`;
}

export function resolveGlobalDateRange(range:GlobalDateRange,customStart='',customEnd='',reference?:Date){
  if(range==='custom')return {start:customStart,end:customEnd};
  const end=reference?new Date(reference):new Date();
  const start=new Date(end);
  if(range==='month')start.setDate(1);
  if(range==='30d')start.setDate(start.getDate()-29);
  if(range==='90d')start.setDate(start.getDate()-89);
  if(range==='year'){start.setMonth(0);start.setDate(1)}
  if(range==='12m')start.setFullYear(start.getFullYear()-1);
  if(range==='all')return {start:'1900-01-01',end:isoFinancialDate(end)};
  return {start:isoFinancialDate(start),end:isoFinancialDate(end)};
}

export function defaultFinancialFilters():FinancialFilters{
  const dates=resolveGlobalDateRange('month');
  return {range:'month',customStart:dates.start,customEnd:dates.end,accountScope:'all'};
}

export function readFinancialFilters():FinancialFilters{
  const fallback=defaultFinancialFilters();
  if(typeof window==='undefined')return fallback;
  try{
    const parsed=JSON.parse(window.localStorage.getItem(STORAGE_KEY)||'{}') as Partial<FinancialFilters>;
    const allowed:GlobalDateRange[]=['month','30d','90d','year','12m','all','custom'];
    return {
      range:allowed.includes(parsed.range as GlobalDateRange)?parsed.range as GlobalDateRange:fallback.range,
      customStart:typeof parsed.customStart==='string'?parsed.customStart:fallback.customStart,
      customEnd:typeof parsed.customEnd==='string'?parsed.customEnd:fallback.customEnd,
      accountScope:typeof parsed.accountScope==='string'&&parsed.accountScope?parsed.accountScope:'all',
    };
  }catch{return fallback}
}

export function writeFinancialFilters(value:FinancialFilters){
  if(typeof window!=='undefined')window.localStorage.setItem(STORAGE_KEY,JSON.stringify(value));
}

export function filteredApiPath(path:string):string{
  if(typeof window==='undefined'||!path.startsWith('/api/v1/'))return path;
  const filters=readFinancialFilters();
  const dates=resolveGlobalDateRange(filters.range,filters.customStart,filters.customEnd);
  const url=new URL(path,window.location.origin);
  if(dates.start&&!url.searchParams.has('start'))url.searchParams.set('start',dates.start);
  if(dates.end&&!url.searchParams.has('end'))url.searchParams.set('end',dates.end);
  if(filters.accountScope.startsWith('account:')&&!url.searchParams.has('account_id')){
    url.searchParams.set('account_id',filters.accountScope.slice('account:'.length));
  }else if(filters.accountScope.startsWith('type:')&&!url.searchParams.has('account_type')){
    url.searchParams.set('account_type',filters.accountScope.slice('type:'.length));
  }
  return url.pathname+(url.search?'?'+url.searchParams.toString():'');
}
