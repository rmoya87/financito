'use client';

import type {ReactNode} from 'react';
import {Card} from '@/components/ui/card';
import {DataStatus} from '@/components/data-status';

export function SectionIntro({
  eyebrow,title,description,aside,className='',
}:{
  eyebrow?:string;title:string;description?:string;aside?:ReactNode;className?:string;
}){
  return <div className={'mb-3 flex flex-wrap items-end justify-between gap-3 '+className}>
    <div className="min-w-0">
      {eyebrow&&<div className="text-[11px] font-semibold uppercase tracking-[.12em] text-[var(--muted)]">{eyebrow}</div>}
      <h2 className="mt-1 text-lg font-bold">{title}</h2>
      {description&&<p className="mt-1 max-w-3xl text-sm text-[var(--muted)]">{description}</p>}
    </div>
    {aside&&<div className="shrink-0">{aside}</div>}
  </div>;
}

export function MetricTile({
  label,value,detail,status,statusTone='neutral',emphasis=false,children,
}:{
  label:string;value?:ReactNode;detail?:ReactNode;status?:string;statusTone?:'neutral'|'confirmed'|'pending'|'calculated';emphasis?:boolean;children?:ReactNode;
}){
  return <Card className={emphasis?'border-[var(--brand)] bg-[var(--brand-soft)]':''}>
    <div className="flex items-start justify-between gap-3">
      <div className="text-[11px] font-semibold uppercase tracking-[.1em] text-[var(--muted)]">{label}</div>
      {status&&<DataStatus label={status} tone={statusTone}/>}
    </div>
    {value!==undefined&&<div className="mt-2 text-2xl font-bold">{value}</div>}
    {detail&&<div className="mt-1 text-xs leading-5 text-[var(--muted)]">{detail}</div>}
    {children&&<div className="mt-3">{children}</div>}
  </Card>;
}

export function VisualPanel({
  title,description,eyebrow,status,statusTone='neutral',action,children,className='',
}:{
  title:string;description?:string;eyebrow?:string;status?:string;statusTone?:'neutral'|'confirmed'|'pending'|'calculated';action?:ReactNode;children:ReactNode;className?:string;
}){
  return <Card className={className}>
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div>
        {eyebrow&&<div className="text-[11px] font-semibold uppercase tracking-[.1em] text-[var(--muted)]">{eyebrow}</div>}
        <h2 className="mt-1 font-bold">{title}</h2>
        {description&&<p className="mt-1 text-sm text-[var(--muted)]">{description}</p>}
      </div>
      <div className="flex items-center gap-2">{status&&<DataStatus label={status} tone={statusTone}/>} {action}</div>
    </div>
    <div className="mt-4">{children}</div>
  </Card>;
}

export function DetailGroup({
  title,description,children,tone='default',className='',
}:{
  title:string;description?:string;children:ReactNode;tone?:'default'|'soft'|'brand'|'warning';className?:string;
}){
  const toneClass=tone==='brand'
    ?'border-[var(--brand)] bg-[var(--brand-soft)]'
    :tone==='warning'
      ?'border-amber-200 bg-amber-50'
      :tone==='soft'
        ?'border-[var(--border)] bg-[var(--surface-2)]'
        :'border-[var(--border)] bg-white';
  return <section className={'rounded-2xl border p-4 '+toneClass+' '+className}>
    <h3 className="font-semibold">{title}</h3>
    {description&&<p className="mt-1 text-xs leading-5 text-[var(--muted)]">{description}</p>}
    <div className="mt-3">{children}</div>
  </section>;
}

export function ModalHero({
  eyebrow,title,description,status,statusTone='neutral',actions,metrics,
}:{
  eyebrow?:string;title:string;description?:ReactNode;status?:string;statusTone?:'neutral'|'confirmed'|'pending'|'calculated';actions?:ReactNode;
  metrics?:{label:string;value:ReactNode;detail?:ReactNode}[];
}){
  return <div className="rounded-2xl bg-[var(--surface-2)] p-4 md:p-5">
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div className="min-w-0">
        {eyebrow&&<div className="text-[11px] font-semibold uppercase tracking-[.12em] text-[var(--muted)]">{eyebrow}</div>}
        <div className="mt-1 flex flex-wrap items-center gap-2">
          <h2 className="text-xl font-bold">{title}</h2>
          {status&&<DataStatus label={status} tone={statusTone}/>}
        </div>
        {description&&<div className="mt-1 text-sm text-[var(--muted)]">{description}</div>}
      </div>
      {actions&&<div className="flex shrink-0 flex-wrap gap-2">{actions}</div>}
    </div>
    {!!metrics?.length&&<div className="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
      {metrics.map(metric=><div key={metric.label} className="rounded-xl border border-[var(--border)] bg-white p-3">
        <div className="text-[11px] font-semibold uppercase tracking-[.08em] text-[var(--muted)]">{metric.label}</div>
        <div className="mt-1 text-lg font-bold">{metric.value}</div>
        {metric.detail&&<div className="mt-1 text-[11px] text-[var(--muted)]">{metric.detail}</div>}
      </div>)}
    </div>}
  </div>;
}
