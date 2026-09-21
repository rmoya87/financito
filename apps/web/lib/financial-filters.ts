export type GlobalDateRange='month'|'previous_month'|'30d'|'90d'|'180d'|'year'|'12m'|'all'|'custom';

export type FinancialFilters={
  range:GlobalDateRange;
  customStart:string;
  customEnd:string;
  accountScope:string;
};

const STORAGE_KEY='financito.financialFilters.v1';

export const globalDateRangeLabels:Record<GlobalDateRange,string>={
  month:'Este mes',
  previous_month:'Mes anterior',
  '30d':'Últimos 30 días',
  '90d':'Últimos 3 meses',
  '180d':'Últimos 6 meses',
  year:'Este año',
  '12m':'Último año',
  all:'Todo el histórico',
  custom:'Personalizado',
};

export function isoFinancialDate(value:Date){
  const y=value.getFullYear();
  const m=String(value.getMonth()+1).padStart(2,'0');
  const d=String(value.getDate()).padStart(2,'0');
  return `${y}-${m}-${d}`;
}

function localDate(value:string){
  const [year,month,day]=value.split('-').map(Number);
  if(!year||!month||!day)return null;
  return new Date(year,month-1,day);
}

export function financialRangeLabel(range:GlobalDateRange,start='',end=''){
  if(range!=='custom')return globalDateRangeLabels[range];
  const startDate=localDate(start);
  const endDate=localDate(end);
  if(!startDate||!endDate)return globalDateRangeLabels.custom;
  const short=new Intl.DateTimeFormat('es-ES',{day:'numeric',month:'short'});
  const full=new Intl.DateTimeFormat('es-ES',{day:'numeric',month:'short',year:'numeric'});
  if(startDate.getFullYear()===endDate.getFullYear()){
    return `${short.format(startDate)} – ${full.format(endDate)}`;
  }
  return `${full.format(startDate)} – ${full.format(endDate)}`;
}

export function resolveGlobalDateRange(range:GlobalDateRange,customStart='',customEnd='',reference?:Date){
  if(range==='custom')return {start:customStart,end:customEnd};
  const end=reference?new Date(reference):new Date();

  if(range==='previous_month'){
    const previousEnd=new Date(end.getFullYear(),end.getMonth(),0);
    const previousStart=new Date(previousEnd.getFullYear(),previousEnd.getMonth(),1);
    return {start:isoFinancialDate(previousStart),end:isoFinancialDate(previousEnd)};
  }

  const start=new Date(end);
  if(range==='month')start.setDate(1);
  if(range==='30d')start.setDate(start.getDate()-29);
  if(range==='90d')start.setDate(start.getDate()-89);
  if(range==='180d')start.setDate(start.getDate()-179);
  if(range==='year'){start.setMonth(0);start.setDate(1)}
  if(range==='12m'){start.setFullYear(start.getFullYear()-1);start.setDate(start.getDate()+1)}
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
    const allowed:GlobalDateRange[]=['month','previous_month','30d','90d','180d','year','12m','all','custom'];
    const stored=allowed.includes(parsed.range as GlobalDateRange)?parsed.range as GlobalDateRange:fallback.range;
    const range:GlobalDateRange=stored==='year'?'12m':stored;
    return {
      range,
      customStart:typeof parsed.customStart==='string'?parsed.customStart:fallback.customStart,
      customEnd:typeof parsed.customEnd==='string'?parsed.customEnd:fallback.customEnd,
      accountScope:typeof parsed.accountScope==='string'&&parsed.accountScope?parsed.accountScope:'all',
    };
  }catch{return fallback}
}

export function writeFinancialFilters(value:FinancialFilters){
  if(typeof window!=='undefined')window.localStorage.setItem(STORAGE_KEY,JSON.stringify(value));
}

function isOneOf(pathname:string,targets:string[]){
  return targets.some(target=>pathname===target||pathname.startsWith(target+'/'));
}

export function filteredApiPath(path:string):string{
  if(typeof window==='undefined'||!path.startsWith('/api/v1/'))return path;

  const url=new URL(path,window.location.origin);
  const pathname=url.pathname;
  const dateScoped=isOneOf(pathname,[
    '/api/v1/dashboard',
    '/api/v1/transactions/page',
    '/api/v1/analytics/overview',
    '/api/v1/anomalies',
    '/api/v1/insurance/verdict',
    '/api/v1/chat',
    '/api/v1/search',
    '/api/v1/stress',
  ]);
  const accountScoped=isOneOf(pathname,[
    '/api/v1/dashboard',
    '/api/v1/transactions/page',
    '/api/v1/analytics/overview',
    '/api/v1/anomalies',
    '/api/v1/wealth',
    '/api/v1/mortgages',
    '/api/v1/insurance',
    '/api/v1/goals',
    '/api/v1/portfolios',
    '/api/v1/commitments',
    '/api/v1/forecast',
    '/api/v1/chat',
    '/api/v1/search',
    '/api/v1/stress',
  ]);

  if(!dateScoped&&!accountScoped)return path;

  const filters=readFinancialFilters();
  if(dateScoped){
    const dates=resolveGlobalDateRange(filters.range,filters.customStart,filters.customEnd);
    if(dates.start&&!url.searchParams.has('start'))url.searchParams.set('start',dates.start);
    if(dates.end&&!url.searchParams.has('end'))url.searchParams.set('end',dates.end);
  }
  if(accountScoped){
    if(filters.accountScope.startsWith('account:')&&!url.searchParams.has('account_id')){
      url.searchParams.set('account_id',filters.accountScope.slice('account:'.length));
    }else if(filters.accountScope.startsWith('type:')&&!url.searchParams.has('account_type')){
      url.searchParams.set('account_type',filters.accountScope.slice('type:'.length));
    }
  }
  return url.pathname+(url.search?'?'+url.searchParams.toString():'');
}
