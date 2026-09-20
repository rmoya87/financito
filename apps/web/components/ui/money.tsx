export function Money({value,currency='EUR',fallback='—'}:{value:string|number|null|undefined;currency?:string;fallback?:string}){
  if(value===null||value===undefined||value==='')return <>{fallback}</>;
  const n=typeof value==='number'?value:Number(value);
  if(!Number.isFinite(n))return <>{fallback}</>;
  return <>{new Intl.NumberFormat('es-ES',{style:'currency',currency,minimumFractionDigits:2,maximumFractionDigits:2}).format(n)}</>;
}
