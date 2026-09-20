import type {ReactNode} from 'react';

export function PageHeader({title,description,action}:{title:string;description?:string;action?:ReactNode}){
  return <header className="mb-6 flex flex-wrap items-start justify-between gap-3">
    <div>
      <h1 className="text-2xl font-bold tracking-tight md:text-3xl">{title}</h1>
      {description&&<p className="mt-1 max-w-3xl text-sm text-[var(--muted)]">{description}</p>}
    </div>
    {action?<div className="ml-auto">{action}</div>:null}
  </header>;
}
