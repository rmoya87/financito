export function Loading({label='Cargando…'}:{label?:string}){return <div className="animate-pulse rounded-xl bg-[var(--surface-2)] p-5 text-sm text-[var(--muted)]">{label}</div>}
export function ErrorState({error}:{error:unknown}){return <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">{error instanceof Error?error.message:'Se produjo un error'}</div>}
export function EmptyState({children}:{children:React.ReactNode}){return <div className="rounded-xl border border-dashed border-[var(--border)] p-6 text-center text-sm text-[var(--muted)]">{children}</div>}
