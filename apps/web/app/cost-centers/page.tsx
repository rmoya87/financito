'use client';

import {FormEvent,useMemo,useState} from 'react';
import {useMutation,useQuery,useQueryClient} from '@tanstack/react-query';
import {apiGet,apiMutate} from '@/lib/api';
import {PageHeader} from '@/components/page-header';
import {Card} from '@/components/ui/card';
import {Money} from '@/components/ui/money';
import {EmptyState,ErrorState} from '@/components/ui/states';

type LinkRow={id:string;entity_type:string;entity_id:string;allocation_percentage:string};
type Center={id:string;name:string;type:string;parent_id:string|null;links:LinkRow[]};
type Summary={
  id:string;name:string;period_start:string;period_end:string;observed_linked_spend:string;monthly_average_spend:string;
  annual_linked_commitments:string;reference_asset_value:string;reference_debt:string;unpriced_links:{type:string;id:string}[]
};
type Category={id:string;name:string;system_key:string};
type Contract={id:string;provider_name:string};
type Policy={id:string;insurance_type:string};
type Asset={id:string;name:string};
type Liability={id:string;name:string};

export default function CostCentersPage(){
  const qc=useQueryClient();
  const centers=useQuery({queryKey:['cost-centers'],queryFn:()=>apiGet<Center[]>('/api/v1/cost-centers')});
  const categories=useQuery({queryKey:['categories'],queryFn:()=>apiGet<Category[]>('/api/v1/categories')});
  const contracts=useQuery({queryKey:['contracts'],queryFn:()=>apiGet<Contract[]>('/api/v1/contracts')});
  const policies=useQuery({queryKey:['insurance'],queryFn:()=>apiGet<Policy[]>('/api/v1/insurance')});
  const assets=useQuery({queryKey:['assets'],queryFn:()=>apiGet<Asset[]>('/api/v1/assets')});
  const liabilities=useQuery({queryKey:['liabilities'],queryFn:()=>apiGet<Liability[]>('/api/v1/liabilities')});

  const [selected,setSelected]=useState('');
  const summary=useQuery({queryKey:['cost-center-summary',selected],queryFn:()=>apiGet<Summary>('/api/v1/cost-centers/'+selected+'/summary'),enabled:!!selected});
  const [name,setName]=useState('');
  const [link,setLink]=useState({entity_type:'category',entity_id:'',allocation_percentage:'100'});

  const invalidate=()=>{
    qc.invalidateQueries({queryKey:['cost-centers']});
    qc.invalidateQueries({queryKey:['cost-center-summary',selected]});
  };
  const create=useMutation({
    mutationFn:()=>apiMutate<{id:string}>('/api/v1/cost-centers','POST',{name,center_type:'life_area',metadata:{}}),
    onSuccess:r=>{setName('');setSelected(r.id);qc.invalidateQueries({queryKey:['cost-centers']})},
  });
  const addLink=useMutation({
    mutationFn:()=>apiMutate('/api/v1/cost-center-links','POST',{cost_center_id:selected,...link}),
    onSuccess:()=>{setLink({...link,entity_id:''});invalidate()},
  });
  const removeLink=useMutation({
    mutationFn:(id:string)=>apiMutate('/api/v1/cost-center-links/'+id,'DELETE'),
    onSuccess:invalidate,
  });

  const options=useMemo(()=>{
    if(link.entity_type==='category')return categories.data?.map(x=>({id:x.id,label:x.name}));
    if(link.entity_type==='contract')return contracts.data?.map(x=>({id:x.id,label:x.provider_name}));
    if(link.entity_type==='insurance_policy')return policies.data?.map(x=>({id:x.id,label:x.insurance_type}));
    if(link.entity_type==='asset')return assets.data?.map(x=>({id:x.id,label:x.name}));
    return liabilities.data?.map(x=>({id:x.id,label:x.name}));
  },[link.entity_type,categories.data,contracts.data,policies.data,assets.data,liabilities.data]);

  const selectedCenter=centers.data?.find(c=>c.id===selected);
  const names=useMemo(()=>{
    const map=new Map<string,string>();
    categories.data?.forEach(x=>map.set('category:'+x.id,x.name));
    contracts.data?.forEach(x=>map.set('contract:'+x.id,x.provider_name));
    policies.data?.forEach(x=>map.set('insurance_policy:'+x.id,x.insurance_type));
    assets.data?.forEach(x=>map.set('asset:'+x.id,x.name));
    liabilities.data?.forEach(x=>map.set('liability:'+x.id,x.name));
    return map;
  },[categories.data,contracts.data,policies.data,assets.data,liabilities.data]);

  return <>
    <PageHeader
      title="Centros de coste"
      description="Agrupa gastos por una finalidad real —por ejemplo Vivienda, Coche o Familia— aunque procedan de varias categorías, contratos o productos."
    />

    <Card className="mb-4">
      <h2 className="font-bold">Cómo funciona</h2>
      <p className="mt-2 text-sm text-[var(--muted)]">
        Un centro no cambia la categoría contable del movimiento. Sirve para responder «¿cuánto me cuesta realmente la vivienda?» o «¿cuánto gasto en el coche?».
        Si vinculas una categoría, todos sus movimientos actuales y futuros entrarán automáticamente en el centro. Puedes asignar un porcentaje si un coste se comparte entre varias áreas.
      </p>
      <div className="mt-3 grid gap-2 text-xs sm:grid-cols-3">
        <div className="rounded-xl bg-[var(--surface-2)] p-3"><strong>1. Crea el área</strong><div className="mt-1 text-[var(--muted)]">Ej. Vivienda, Familia, Coche o un proyecto.</div></div>
        <div className="rounded-xl bg-[var(--surface-2)] p-3"><strong>2. Vincula categorías</strong><div className="mt-1 text-[var(--muted)]">Es la forma normal de agrupar gasto recurrente.</div></div>
        <div className="rounded-xl bg-[var(--surface-2)] p-3"><strong>3. Añade referencias</strong><div className="mt-1 text-[var(--muted)]">Contratos, seguros, activos o deuda completan la visión.</div></div>
      </div>
    </Card>

    <div className="grid gap-4 xl:grid-cols-[340px_1fr]">
      <div className="space-y-4">
        <Card>
          <h2 className="font-bold">Nuevo centro</h2>
          <form className="mt-3 flex gap-2" onSubmit={(e:FormEvent)=>{e.preventDefault();create.mutate()}}>
            <input className="fin-input" aria-label="Nombre del centro de coste" value={name} onChange={e=>setName(e.target.value)} placeholder="Ej. Vivienda" required/>
            <button className="fin-button" disabled={create.isPending}>Crear</button>
          </form>
          {create.error&&<div className="mt-3"><ErrorState error={create.error}/></div>}
        </Card>

        <Card>
          <h2 className="font-bold">Centros</h2>
          <div className="mt-3 space-y-2">{centers.data?.length?centers.data.map(center=>
            <button key={center.id} className={'w-full rounded-xl p-3 text-left '+(selected===center.id?'bg-[var(--brand-soft)]':'bg-[var(--surface-2)]')} onClick={()=>setSelected(center.id)}>
              <strong>{center.name}</strong>
              <div className="text-xs text-[var(--muted)]">{center.links.length} vínculo(s)</div>
            </button>
          ):<EmptyState>Crea un centro para empezar a agrupar costes.</EmptyState>}</div>
        </Card>
      </div>

      <div className="space-y-4">
        {!selected?<EmptyState>Selecciona un centro para configurarlo y ver su coste.</EmptyState>:<>
          <Card>
            <h2 className="font-bold">Qué incluye {selectedCenter?.name||'este centro'}</h2>
            <p className="mt-1 text-sm text-[var(--muted)]">Empieza por categorías. Los elementos que vincules aquí se incorporan automáticamente al resumen.</p>
            <form className="mt-3 grid gap-2 md:grid-cols-[180px_1fr_140px_auto]" onSubmit={(e:FormEvent)=>{e.preventDefault();addLink.mutate()}}>
              <select className="fin-input" aria-label="Tipo de entidad" value={link.entity_type} onChange={e=>setLink({...link,entity_type:e.target.value,entity_id:''})}>
                <option value="category">Categoría de gasto</option>
                <option value="contract">Contrato</option>
                <option value="insurance_policy">Póliza</option>
                <option value="asset">Activo</option>
                <option value="liability">Deuda</option>
              </select>
              <select className="fin-input" aria-label="Entidad a vincular" value={link.entity_id} onChange={e=>setLink({...link,entity_id:e.target.value})} required>
                <option value="">Selecciona elemento…</option>
                {options?.map(x=><option key={x.id} value={x.id}>{x.label}</option>)}
              </select>
              <input className="fin-input" aria-label="Porcentaje de asignación" type="number" min="0.1" max="100" step=".1" value={link.allocation_percentage} onChange={e=>setLink({...link,allocation_percentage:e.target.value})}/>
              <button className="fin-button" disabled={addLink.isPending}>Vincular</button>
            </form>
            {addLink.error&&<div className="mt-3"><ErrorState error={addLink.error}/></div>}

            <div className="mt-4 space-y-2">{selectedCenter?.links.length?selectedCenter.links.map(row=>
              <div key={row.id} className="flex items-center justify-between gap-3 rounded-xl bg-[var(--surface-2)] p-3 text-sm">
                <div>
                  <strong>{names.get(row.entity_type+':'+row.entity_id)||row.entity_type}</strong>
                  <div className="text-xs text-[var(--muted)]">{row.entity_type==='category'?'Categoría automática':row.entity_type.replaceAll('_',' ')} · {Number(row.allocation_percentage).toLocaleString('es-ES',{maximumFractionDigits:1})}%</div>
                </div>
                <button className="text-xs underline" onClick={()=>removeLink.mutate(row.id)}>Quitar</button>
              </div>
            ):<EmptyState>Aún no has vinculado ningún coste. Añade una categoría para que el centro empiece a calcularse.</EmptyState>}</div>
          </Card>

          <Card>
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div><h2 className="font-bold">Resumen real</h2><p className="mt-1 text-sm text-[var(--muted)]">Gasto observado en los últimos 12 meses más compromisos y referencias vinculadas.</p></div>
              {summary.data&&<div className="text-xs text-[var(--muted)]">{new Date(summary.data.period_start).toLocaleDateString('es-ES')} — {new Date(summary.data.period_end).toLocaleDateString('es-ES')}</div>}
            </div>
            {summary.error?<div className="mt-3"><ErrorState error={summary.error}/></div>:summary.data&&<div className="mt-4 grid gap-4 sm:grid-cols-2">
              <div className="rounded-xl bg-[var(--surface-2)] p-4"><div className="text-xs text-[var(--muted)]">Gasto últimos 12 meses</div><strong className="text-xl"><Money value={summary.data.observed_linked_spend}/></strong></div>
              <div className="rounded-xl bg-[var(--surface-2)] p-4"><div className="text-xs text-[var(--muted)]">Media mensual</div><strong className="text-xl"><Money value={summary.data.monthly_average_spend}/></strong></div>
              <div><div className="text-xs text-[var(--muted)]">Compromisos anuales vinculados</div><strong><Money value={summary.data.annual_linked_commitments}/></strong></div>
              <div><div className="text-xs text-[var(--muted)]">Valor de activos asociado</div><strong><Money value={summary.data.reference_asset_value}/></strong></div>
              <div><div className="text-xs text-[var(--muted)]">Deuda asociada</div><strong><Money value={summary.data.reference_debt}/></strong></div>
            </div>}
          </Card>
        </>}
      </div>
    </div>
  </>;
}
