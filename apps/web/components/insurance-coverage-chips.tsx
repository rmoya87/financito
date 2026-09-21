'use client';

import {Money} from '@/components/ui/money';

export type InsuranceCoverageChip={
  id?:string;
  coverage_type:string;
  limit_amount?:string|null;
  deductible?:string|null;
  user_verified?:boolean;
};

export function InsuranceCoverageChips({
  coverages,limit=6,emptyText,
}:{
  coverages:InsuranceCoverageChip[];
  limit?:number;
  emptyText?:string;
}){
  const rows=(coverages||[]).slice(0,limit);
  if(!rows.length)return emptyText?<div className="text-xs text-[var(--muted)]">{emptyText}</div>:null;
  return <div className="flex flex-wrap gap-1.5">
    {rows.map((coverage,index)=><span
      key={coverage.id||coverage.coverage_type+index}
      className={coverage.user_verified
        ?'inline-flex items-center gap-1 rounded-full bg-[var(--brand-soft)] px-2.5 py-1 text-[11px] font-medium text-[var(--brand)]'
        :'inline-flex items-center gap-1 rounded-full border border-[var(--border)] bg-white px-2.5 py-1 text-[11px] font-medium text-[var(--text)]'
      }
      title={coverage.user_verified?'Cobertura verificada':'Cobertura pendiente de validar'}
    >
      <span>{coverage.coverage_type}</span>
      {coverage.limit_amount&&<><span aria-hidden="true">·</span><Money value={coverage.limit_amount}/></>}
      {coverage.user_verified===false&&<span className="text-[10px] text-[var(--muted)]">por verificar</span>}
    </span>)}
    {coverages.length>limit&&<span className="inline-flex items-center rounded-full bg-[var(--surface-2)] px-2.5 py-1 text-[11px] text-[var(--muted)]">+{coverages.length-limit}</span>}
  </div>;
}
