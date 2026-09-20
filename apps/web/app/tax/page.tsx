'use client';
import {FormEvent,useEffect,useState} from 'react';
import {useMutation,useQuery,useQueryClient} from '@tanstack/react-query';
import {apiGet,apiMutate} from '@/lib/api';
import {PageHeader} from '@/components/page-header';
import {Card} from '@/components/ui/card';
import {Money} from '@/components/ui/money';
import {EmptyState,ErrorState} from '@/components/ui/states';

type Profile={
  jurisdiction:string;tax_year:number;autonomous_community:string|null;filing_status:string|null;adults:number;
  dependent_children:number;children_under_three:number;primary_residence:boolean|null;employment_income:string|null;
  social_security_contributions:string|null;employment_deductible_expenses:string|null;tax_withholdings:string|null;
  interest_income:string;other_general_income:string;carried_forward_savings_losses:string;pension_contributions:string;
};
type Missing={field:string;label:string;why:string};
type Estimate={
  jurisdiction:string;tax_year:number;rules_version:string;status:string;profile:Profile;
  known_information:{employment_income:string;employment_income_source:string;realized_investment_pnl:string;dividends:string;mortgages_detected:number};
  missing_information:Missing[];
  calculation:{general_base:string|null;state_general_tax:string|null;regional_general_tax:string|null;regional_rules_supported:boolean;savings_base:string;savings_tax:string;estimated_total_tax:string|null;withholdings:string|null;estimated_balance:string|null};
  assumptions:string[];normative_sources:{name:string;url:string;scope:string}[];
};
type InsightItem={title:string;detail:string;pages:number[];impact?:string};
type DocInsight={document_id:string;file_name:string;analysis:{summary:string;optimization_opportunities:InsightItem[];missing_information:InsightItem[];comparison_requirements:InsightItem[];risks:InsightItem[]}};

const currentYear=new Date().getFullYear();
const empty=(year:number):Profile=>({
  jurisdiction:'ES',tax_year:year,autonomous_community:null,filing_status:null,adults:1,dependent_children:0,children_under_three:0,primary_residence:null,
  employment_income:null,social_security_contributions:null,employment_deductible_expenses:null,tax_withholdings:null,
  interest_income:'0',other_general_income:'0',carried_forward_savings_losses:'0',pension_contributions:'0',
});

export default function TaxPage(){
  const qc=useQueryClient();
  const [year,setYear]=useState(currentYear);
  const profile=useQuery({queryKey:['tax-profile',year],queryFn:()=>apiGet<Profile>('/api/v1/tax/profile?jurisdiction=ES&tax_year='+year)});
  const [form,setForm]=useState<Profile>(empty(currentYear));
  useEffect(()=>{if(profile.data)setForm(profile.data)},[profile.data]);

  const save=useMutation({
    mutationFn:()=>apiMutate<Profile>('/api/v1/tax/profile','PUT',form),
    onSuccess:data=>{setForm(data);qc.setQueryData(['tax-profile',year],data)},
  });
  const estimate=useMutation({mutationFn:()=>apiMutate<Estimate>('/api/v1/tax/estimate','POST',{jurisdiction:'ES',tax_year:year})});
  const insights=useQuery({queryKey:['document-insights','tax'],queryFn:()=>apiGet<DocInsight[]>('/api/v1/document-insights?document_type=tax')});

  function update<K extends keyof Profile>(key:K,value:Profile[K]){setForm({...form,[key]:value})}
  function submit(e:FormEvent){e.preventDefault();save.mutate(undefined,{onSuccess:()=>estimate.mutate()})}

  return <>
    <PageHeader title="Fiscalidad" description="Estimación fiscal trazable con datos de Financito, perfil del hogar y reglas normativas versionadas. Los datos que falten se muestran explícitamente."/>

    <Card>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div><h2 className="font-bold">Ejercicio y datos que faltan</h2><p className="mt-1 text-sm text-[var(--muted)]">Financito reutiliza nóminas, inversiones, dividendos, hipotecas y documentación. Completa solo lo que no puede inferirse con seguridad.</p></div>
        <label className="text-sm">Ejercicio
          <select className="fin-input mt-1 min-w-32" value={year} onChange={e=>{const y=Number(e.target.value);setYear(y);setForm(empty(y));estimate.reset()}}>
            {[currentYear,currentYear-1,currentYear-2].map(y=><option key={y} value={y}>{y}</option>)}
          </select>
        </label>
      </div>

      <form className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-3" onSubmit={submit}>
        <label className="text-sm">Comunidad autónoma
          <select className="fin-input mt-1" value={form.autonomous_community||''} onChange={e=>update('autonomous_community',e.target.value||null)}>
            <option value="">Selecciona…</option><option value="Madrid">Comunidad de Madrid</option><option value="Otra">Otra comunidad</option>
          </select>
        </label>
        <label className="text-sm">Tipo de declaración
          <select className="fin-input mt-1" value={form.filing_status||''} onChange={e=>update('filing_status',(e.target.value||null) as Profile['filing_status'])}>
            <option value="">Selecciona…</option><option value="individual">Individual</option><option value="joint">Conjunta</option>
          </select>
        </label>
        <label className="text-sm">Adultos en el hogar
          <input className="fin-input mt-1" type="number" min="1" max="4" value={form.adults} onChange={e=>update('adults',Number(e.target.value))}/>
        </label>
        <label className="text-sm">Descendientes a cargo
          <input className="fin-input mt-1" type="number" min="0" value={form.dependent_children} onChange={e=>update('dependent_children',Number(e.target.value))}/>
        </label>
        <label className="text-sm">De ellos, menores de 3 años
          <input className="fin-input mt-1" type="number" min="0" max={form.dependent_children} value={form.children_under_three} onChange={e=>update('children_under_three',Number(e.target.value))}/>
        </label>
        <label className="text-sm">Vivienda habitual
          <select className="fin-input mt-1" value={form.primary_residence===null?'':form.primary_residence?'yes':'no'} onChange={e=>update('primary_residence',e.target.value===''?null:e.target.value==='yes')}>
            <option value="">Sin confirmar</option><option value="yes">Sí</option><option value="no">No</option>
          </select>
        </label>
        <label className="text-sm">Rendimientos del trabajo (€)
          <input className="fin-input mt-1" type="number" step=".01" value={form.employment_income??''} onChange={e=>update('employment_income',e.target.value||null)} placeholder="Vacío = usar nóminas detectadas"/>
        </label>
        <label className="text-sm">Cotizaciones Seguridad Social (€)
          <input className="fin-input mt-1" type="number" step=".01" value={form.social_security_contributions??''} onChange={e=>update('social_security_contributions',e.target.value||null)}/>
        </label>
        <label className="text-sm">Gastos deducibles del trabajo (€)
          <input className="fin-input mt-1" type="number" step=".01" value={form.employment_deductible_expenses??''} onChange={e=>update('employment_deductible_expenses',e.target.value||null)}/>
        </label>
        <label className="text-sm">Retenciones soportadas (€)
          <input className="fin-input mt-1" type="number" step=".01" value={form.tax_withholdings??''} onChange={e=>update('tax_withholdings',e.target.value||null)}/>
        </label>
        <label className="text-sm">Intereses bancarios (€)
          <input className="fin-input mt-1" type="number" step=".01" value={form.interest_income} onChange={e=>update('interest_income',e.target.value)}/>
        </label>
        <label className="text-sm">Otros rendimientos generales (€)
          <input className="fin-input mt-1" type="number" step=".01" value={form.other_general_income} onChange={e=>update('other_general_income',e.target.value)}/>
        </label>
        <label className="text-sm">Pérdidas del ahorro pendientes (€)
          <input className="fin-input mt-1" type="number" step=".01" value={form.carried_forward_savings_losses} onChange={e=>update('carried_forward_savings_losses',e.target.value)}/>
        </label>
        <label className="text-sm">Aportaciones a pensiones (€)
          <input className="fin-input mt-1" type="number" step=".01" value={form.pension_contributions} onChange={e=>update('pension_contributions',e.target.value)}/>
        </label>
        <button className="fin-button self-end" disabled={save.isPending||estimate.isPending}>Guardar y recalcular</button>
      </form>
      {(save.error||profile.error)&&<div className="mt-3"><ErrorState error={(save.error||profile.error)!}/></div>}
    </Card>

    <Card className="mt-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div><h2 className="font-bold">Estimación {year}</h2><p className="mt-1 text-sm text-[var(--muted)]">Las cifras se calculan con reglas deterministas; la IA no inventa tipos, mínimos ni deducciones.</p></div>
        <button className="fin-button secondary" onClick={()=>estimate.mutate()} disabled={estimate.isPending}>Recalcular</button>
      </div>
      {estimate.error&&<div className="mt-3"><ErrorState error={estimate.error}/></div>}
      {estimate.data?<div className="mt-4 space-y-4">
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-xl bg-[var(--surface-2)] p-4"><div className="text-xs text-[var(--muted)]">Trabajo usado</div><strong><Money value={estimate.data.known_information.employment_income}/></strong><div className="text-xs text-[var(--muted)]">{estimate.data.known_information.employment_income_source}</div></div>
          <div className="rounded-xl bg-[var(--surface-2)] p-4"><div className="text-xs text-[var(--muted)]">P&L inversiones</div><strong><Money value={estimate.data.known_information.realized_investment_pnl}/></strong></div>
          <div className="rounded-xl bg-[var(--surface-2)] p-4"><div className="text-xs text-[var(--muted)]">Base del ahorro</div><strong><Money value={estimate.data.calculation.savings_base}/></strong><div className="text-xs text-[var(--muted)]">Cuota estimada <Money value={estimate.data.calculation.savings_tax}/></div></div>
          <div className="rounded-xl bg-[var(--surface-2)] p-4"><div className="text-xs text-[var(--muted)]">Resultado frente a retenciones</div><strong><Money value={estimate.data.calculation.estimated_balance}/></strong><div className="text-xs text-[var(--muted)]">{estimate.data.calculation.estimated_balance===null?'Aún faltan datos':'Positivo = importe adicional estimado'}</div></div>
        </div>
        {estimate.data.calculation.estimated_total_tax!==null&&<div className="rounded-xl border border-[var(--border)] p-4"><div className="text-sm text-[var(--muted)]">Cuota estimada total antes de deducciones no modeladas</div><div className="text-2xl font-bold"><Money value={estimate.data.calculation.estimated_total_tax}/></div><div className="mt-1 text-xs text-[var(--muted)]">Base general: <Money value={estimate.data.calculation.general_base}/> · parte estatal: <Money value={estimate.data.calculation.state_general_tax}/> · parte autonómica: <Money value={estimate.data.calculation.regional_general_tax}/>.</div></div>}
        <div><h3 className="font-semibold">Información pendiente</h3><div className="mt-2 grid gap-2 md:grid-cols-2">{estimate.data.missing_information.length?estimate.data.missing_information.map(x=><div key={x.field} className="rounded-xl bg-[var(--surface-2)] p-3 text-sm"><strong>{x.label}</strong><div className="mt-1 text-xs text-[var(--muted)]">{x.why}</div></div>):<div className="text-sm text-[var(--muted)]">No faltan datos básicos para esta estimación.</div>}</div></div>
        <details className="rounded-xl bg-[var(--surface-2)] p-3 text-sm"><summary className="cursor-pointer font-semibold">Hipótesis, normativa y límites</summary><ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-[var(--muted)]">{estimate.data.assumptions.map((x,i)=><li key={i}>{x}</li>)}</ul><div className="mt-3 space-y-1">{estimate.data.normative_sources.map(x=><a key={x.url} className="block text-xs underline" href={x.url} target="_blank" rel="noreferrer">{x.name} · {x.scope}</a>)}</div><div className="mt-2 text-xs">Versión de reglas: {estimate.data.rules_version}</div></details>
      </div>:<EmptyState>Guarda el perfil fiscal o pulsa Recalcular para ver qué información conoce Financito y qué falta.</EmptyState>}
    </Card>

    <Card className="mt-4">
      <div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="font-bold">Conclusiones de documentación fiscal</h2><p className="mt-1 text-sm text-[var(--muted)]">La IA local resume datos y condiciones visibles y los mantiene separados de las reglas fiscales deterministas.</p></div><a className="text-xs underline" href="/documents/">Añadir documentos</a></div>
      <div className="mt-4 grid gap-3 md:grid-cols-2">{insights.data?.length?insights.data.map(x=><div key={x.document_id} className="rounded-xl bg-[var(--surface-2)] p-3 text-sm"><div className="flex items-start justify-between gap-3"><strong>{x.file_name}</strong><a className="text-xs underline" href={'/documents/?document='+encodeURIComponent(x.document_id)}>Evidencia</a></div><p className="mt-2 text-xs">{x.analysis.summary}</p>{x.analysis.optimization_opportunities?.length>0&&<div className="mt-2 rounded-lg bg-[var(--brand-soft)] p-2 text-xs"><strong>A revisar:</strong> {x.analysis.optimization_opportunities.slice(0,2).map(i=>i.title||i.detail).join(' · ')}</div>}{x.analysis.missing_information?.length>0&&<div className="mt-2 text-xs"><strong>Falta:</strong> {x.analysis.missing_information.slice(0,2).map(i=>i.title||i.detail).join(' · ')}</div>}</div>):<EmptyState>Añade declaraciones, certificados o documentación fiscal para disponer de más contexto local.</EmptyState>}</div>
    </Card>
  </>;
}
