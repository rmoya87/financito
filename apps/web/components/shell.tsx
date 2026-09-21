'use client';

import Link from 'next/link';
import {useEffect,useState} from 'react';
import {usePathname} from 'next/navigation';
import {
  ArrowLeftRight,
  Bot,
  Gauge,
  LayoutDashboard,
  Search,
  Settings,
  Sparkles,
  WalletCards,
} from 'lucide-react';

type NavItem={href:string;label:string};
type Area={href:string;label:string;Icon:typeof LayoutDashboard;paths:string[];secondary:NavItem[]};

const areas:Area[]=[
  {
    href:'/',
    label:'Inicio',
    Icon:LayoutDashboard,
    paths:['/'],
    secondary:[],
  },
  {
    href:'/transactions/',
    label:'Movimientos',
    Icon:ArrowLeftRight,
    paths:['/transactions/','/analytics/','/accounts/','/banking/','/cost-centers/'],
    secondary:[
      {href:'/transactions/',label:'Movimientos'},
      {href:'/analytics/',label:'Análisis'},
      {href:'/accounts/',label:'Cuentas'},
    ],
  },
  {
    href:'/wealth/',
    label:'Patrimonio',
    Icon:WalletCards,
    paths:['/wealth/','/insurance/','/investments/','/markets/','/history/','/tax/'],
    secondary:[
      {href:'/wealth/',label:'Resumen'},
      {href:'/wealth/#casa',label:'Casa'},
      {href:'/insurance/',label:'Seguros y protección'},
      {href:'/investments/',label:'Inversiones'},
      {href:'/markets/',label:'Mercado'},
      {href:'/tax/',label:'Fiscalidad'},
      {href:'/history/',label:'Histórico'},
    ],
  },
  {
    href:'/actions/',
    label:'Decisiones',
    Icon:Sparkles,
    paths:['/actions/','/decisions/','/goals/','/tools/','/forecast/','/contracts/'],
    secondary:[
      {href:'/actions/',label:'Para ti'},
      {href:'/goals/',label:'Objetivos'},
      {href:'/tools/',label:'Simular'},
      {href:'/decisions/',label:'Mis decisiones'},
    ],
  },
];

const configurationPaths=['/settings/','/documents/','/system/','/developer/','/onboarding/'];
const configurationNav:NavItem[]=[
  {href:'/settings/',label:'General'},
  {href:'/documents/',label:'Datos y fuentes'},
  {href:'/system/',label:'Privacidad y copias'},
  {href:'/developer/',label:'Avanzado'},
];

function matches(path:string,paths:string[]){
  if(paths.length===1&&paths[0]==='/')return path==='/';
  return paths.some(prefix=>path.startsWith(prefix));
}

function navLinkClass(active:boolean){
  return `flex min-w-max items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium ${active?'bg-[var(--brand)] text-white':'text-[var(--muted)] hover:bg-[var(--surface-2)] hover:text-[var(--text)]'}`;
}

function ContextNav({label,items,path,onHashChange}:{label:string;items:NavItem[];path:string;onHashChange?:(hash:string)=>void}){
  if(!items.length)return null;
  return <nav aria-label={`Navegación de ${label}`} className="mb-6 overflow-x-auto">
    <div className="inline-flex min-w-full gap-1 rounded-2xl border border-[var(--border)] bg-white p-1 sm:min-w-0">
      {items.map(item=>{
        const [itemPath,itemHash='']=item.href.split('#');
        const [currentPath,currentHash='']=path.split('#');
        const active=itemHash?currentPath===itemPath&&currentHash===itemHash:currentPath.startsWith(itemPath)&&!currentHash;
        return <Link
          key={item.href}
          href={item.href}
          onClick={()=>onHashChange?.(itemHash)}
          aria-current={active?'page':undefined}
          className={`rounded-xl px-3 py-2 text-sm font-semibold ${active?'bg-[var(--brand)] text-white':'text-[var(--muted)] hover:bg-[var(--surface-2)] hover:text-[var(--text)]'}`}
        >
          {item.label}
        </Link>;
      })}
    </div>
  </nav>;
}

export function Shell({children}:{children:React.ReactNode}){
  const path=usePathname();
  const [hash,setHash]=useState('');
  useEffect(()=>{
    const update=()=>setHash(window.location.hash.replace(/^#/,''));
    update();
    window.addEventListener('hashchange',update);
    return ()=>window.removeEventListener('hashchange',update);
  },[path]);
  const contextPath=hash?path+'#'+hash:path;
  const activeArea=areas.find(area=>matches(path,area.paths));
  const inConfiguration=matches(path,configurationPaths);

  return <div className="min-h-screen lg:grid lg:grid-cols-[224px_1fr]">
    <aside className="border-b border-[var(--border)] bg-white lg:sticky lg:top-0 lg:flex lg:h-screen lg:flex-col lg:border-b-0 lg:border-r">
      <div className="flex items-center gap-3 px-5 py-5">
        <div className="grid size-10 place-items-center rounded-xl bg-[var(--brand)] text-white"><Gauge size={22}/></div>
        <div>
          <div className="font-bold">Financito</div>
          <div className="text-xs text-[var(--muted)]">Privado · local</div>
        </div>
      </div>

      <nav aria-label="Navegación principal" className="flex gap-1 overflow-x-auto px-3 pb-3 lg:flex-col lg:overflow-visible">
        {areas.map(area=>{
          const active=matches(path,area.paths);
          const Icon=area.Icon;
          return <Link key={area.href} href={area.href} aria-current={active?'page':undefined} className={navLinkClass(active)}>
            <Icon size={18}/>{area.label}
          </Link>;
        })}
      </nav>

      <div className="hidden px-5 py-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-[var(--muted)] lg:block">Utilidades</div>
      <nav aria-label="Utilidades" className="flex gap-1 overflow-x-auto border-t border-[var(--border)] px-3 py-3 lg:flex-col lg:overflow-visible">
        <Link href="/search/" className={navLinkClass(path.startsWith('/search/'))}><Search size={18}/>Buscar</Link>
        <Link href="/chat/" className={navLinkClass(path.startsWith('/chat/'))}><Bot size={18}/>Preguntar</Link>
      </nav>

      <div className="lg:mt-auto">
        <nav aria-label="Configuración" className="border-t border-[var(--border)] px-3 py-3">
          <Link href="/settings/" className={navLinkClass(inConfiguration)}><Settings size={18}/>Configuración</Link>
        </nav>
      </div>
    </aside>

    <main className="min-w-0 p-4 md:p-7 lg:p-9">
      {activeArea&&activeArea.href!=='/'?<ContextNav label={activeArea.label} items={activeArea.secondary} path={contextPath} onHashChange={setHash}/>:null}
      {inConfiguration?<ContextNav label="Configuración" items={configurationNav} path={path}/>:null}
      {children}
    </main>
  </div>;
}
