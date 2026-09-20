import type {HTMLAttributes} from 'react';

export function Card({children,className='',...props}:HTMLAttributes<HTMLElement>){return <section {...props} className={`fin-card p-5 ${className}`}>{children}</section>}
