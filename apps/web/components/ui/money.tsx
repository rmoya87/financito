export function formatNumber(value:string|number|null|undefined,minimumFractionDigits=0,maximumFractionDigits=2,fallback='—'){
  if(value===null||value===undefined||value==='')return fallback;
  const n=typeof value==='number'?value:Number(value);
  if(!Number.isFinite(n))return fallback;
  return new Intl.NumberFormat('de-DE',{
    useGrouping:true,
    minimumFractionDigits,
    maximumFractionDigits,
  }).format(n);
}

export function formatMoney(value:string|number|null|undefined,currency='EUR',fallback='—'){
  if(value===null||value===undefined||value==='')return fallback;
  const n=typeof value==='number'?value:Number(value);
  if(!Number.isFinite(n))return fallback;
  return new Intl.NumberFormat('de-DE',{
    style:'currency',
    currency,
    useGrouping:true,
    minimumFractionDigits:2,
    maximumFractionDigits:2,
  }).format(n);
}

export function Money({value,currency='EUR',fallback='—'}:{value:string|number|null|undefined;currency?:string;fallback?:string}){
  return <>{formatMoney(value,currency,fallback)}</>;
}
