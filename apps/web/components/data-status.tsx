export function DataStatus({label,detail,tone='neutral'}:{label:string;detail?:string;tone?:'neutral'|'confirmed'|'pending'|'calculated'}){
  const cls=tone==='confirmed'
    ?'bg-emerald-50 text-emerald-800 border-emerald-200'
    :tone==='pending'
      ?'bg-amber-50 text-amber-800 border-amber-200'
      :tone==='calculated'
        ?'bg-[var(--brand-soft)] text-[var(--brand)] border-[var(--border)]'
        :'bg-[var(--surface-2)] text-[var(--muted)] border-[var(--border)]';
  return <span className={'inline-flex max-w-full items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium '+cls} title={detail||label}>
    <span>{label}</span>{detail&&<span className="hidden text-[10px] opacity-80 sm:inline">· {detail}</span>}
  </span>;
}
