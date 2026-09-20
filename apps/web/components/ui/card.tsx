import type {HTMLAttributes,ReactNode} from 'react';

type CardProps=HTMLAttributes<HTMLElement>&{children:ReactNode};

export function Card({children,className='',...props}:CardProps){
  return <section {...props} className={`fin-card p-5 ${className}`}>{children}</section>;
}
