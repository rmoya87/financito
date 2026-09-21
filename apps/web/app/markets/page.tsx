'use client';

import {FormEvent,useMemo,useState} from 'react';
import {useMutation,useQuery,useQueryClient} from '@tanstack/react-query';
import {CartesianGrid,Line,LineChart,ResponsiveContainer,Tooltip,XAxis,YAxis} from 'recharts';
import {apiGet,apiMutate} from '@/lib/api';
import {PageHeader} from '@/components/page-header';
import {Card} from '@/components/ui/card';
import {Money} from '@/components/ui/money';
import {EmptyState,ErrorState} from '@/components/ui/states';

type Quote={symbol:string;price:string;provider:string;as_of:string|null;delayed:boolean};
type CryptoPrice={provider?:string;assets?:{id:string;currency:string;price?:number|null;market_cap?:number|null;volume_24h?:number|null;change_24h_pct?:number|null;last_updated_at?:number|null}[]};
type CryptoMetrics={coin_id:string;metrics?:{volatility?:number|null;max_drawdown?:number|null;sharpe?:number|null;sortino?:number|null;var_95?:number;cvar_95?:number};observations?:number;provider?:string};
type SecData={cik:string;entity_name:string;provider:string;facts:Record<string,{value:number;unit:string;period_end:string|null;filed:string|null;form:string|null;accession:string|null}>};
type Analysis={security_id:string|null;security:string|null;event_type:string;sentiment:number;impact_level:string;confidence:number;method_version:string;rationale:string};
type LocalNews={items:{id:string;headline:string;url:string;source:string;published_at:string;reliability:number;analysis:Analysis[]}[]};
type Portfolio={id:string;name:string};
type Simulation={started_at:string;invested_amount:string;entry_price:string;quantity:string;current_value:string|null;pnl:string|null;return:string|null};
type TrackedAsset={
  security_id:string;name:string;identifier:string|null;asset_class:string;currency:string;tracking_state:string;provider_asset_id:string|null;
  owned:boolean;quantity:string;average_cost:string;cost_basis:string;current_price:string|null;current_value:string|null;unrealized_pnl:string|null;
  unrealized_return:string|null;realized_pnl:string;dividends:string;total_result:string|null;price_provider:string|null;price_as_of:string|null;
  price_fetched_at:string|null;price_delayed:boolean|null;price_age_minutes:number|null;price_stale:boolean;simulation:Simulation|null
};
type SimHistory={security_id:string;simulation:null|{started_at:string;invested_amount:string;entry_price:string;quantity:string;currency:string};rows:{timestamp:string;price:string;value:string;pnl:string;return:string;provider:string}[]};
type TrackedHistory={security_id:string;name:string;identifier:string|null;currency:string;owned:boolean;rows:{timestamp:string;close:string;currency:string;provider:string;is_delayed:boolean}[]};
type RefreshAll={refreshed:{security_id:string;quote:unknown}[];failed:{security_id:string;error:string}[];assets:TrackedAsset[]};
type Research={
  query:string;ingest:{inserted:number;discovered:number};
  brief:{summary:string;facts:{headline:string;source:string;published_at:string;url:string;linked_assets:string[];event_types:string[];impact_levels:string[]}[];portfolio_impacts:{asset?:string;observation?:string;possible_effects?:string|any[];evidence_headlines?:string[]}[];risks:string[];watch:string[];method:string;ai_available:boolean;ai_warning?:string}
};

function sentimentLabel(value:number){return value>.15?'positivo':value<-.15?'negativo':'neutral'}
function pct(value:string|null){return value===null?'—':(Number(value)*100).toLocaleString('es-ES',{maximumFractionDigits:2})+'%'}
function seriesColor(id:string){
  let hash=0;
  for(let i=0;i<id.length;i++)hash=((hash<<5)-hash)+id.charCodeAt(i);
  return 'hsl('+Math.abs(hash%360)+' 65% 42%)';
}

export default function MarketsPage(){
  const qc=useQueryClient();
  const [symbol,setSymbol]=useState('AAPL');
  const [coin,setCoin]=useState('bitcoin');
  const [newsQ,setNewsQ]=useState('mercados');
  const [cik,setCik]=useState('0000320193');
  const [trackedForm,setTrackedForm]=useState({asset_class:'stock',name:'',identifier:'',owned:'no',portfolio_id:'',quantity:'',purchase_price:'',purchase_date:new Date().toISOString().slice(0,10),fees:'0',currency:'EUR',fx_rate:'1'});
  const [simAmounts,setSimAmounts]=useState<Record<string,string>>({});
  const [selectedSimulation,setSelectedSimulation]=useState('');

  const portfolios=useQuery({queryKey:['portfolios'],queryFn:()=>apiGet<Portfolio[]>('/api/v1/portfolios')});
  const tracked=useQuery({queryKey:['tracked-assets'],queryFn:()=>apiGet<TrackedAsset[]>('/api/v1/tracked-assets')});
  const trackedHistory=useQuery({queryKey:['tracked-assets-history'],queryFn:()=>apiGet<TrackedHistory[]>('/api/v1/tracked-assets/history?days=365')});
  const local=useQuery({queryKey:['local-news'],queryFn:()=>apiGet<LocalNews>('/api/v1/news/local?limit=30')});
  const simHistory=useQuery({queryKey:['simulation-history',selectedSimulation],queryFn:()=>apiGet<SimHistory>('/api/v1/tracked-assets/'+selectedSimulation+'/simulation-history'),enabled:!!selectedSimulation});

  const quote=useMutation({mutationFn:()=>apiGet<Quote>('/api/v1/market/quote/'+encodeURIComponent(symbol))});
  const crypto=useMutation({mutationFn:()=>apiGet<CryptoPrice>('/api/v1/crypto/price?ids='+encodeURIComponent(coin)+'&vs_currency=eur')});
  const cryptoMetrics=useMutation({mutationFn:()=>apiGet<CryptoMetrics>('/api/v1/crypto/metrics/'+encodeURIComponent(coin)+'?vs_currency=eur&days=90')});
  const sec=useMutation({mutationFn:()=>apiGet<SecData>('/api/v1/fundamentals/sec/'+encodeURIComponent(cik))});
  const research=useMutation({
    mutationFn:()=>apiMutate<Research>('/api/v1/news/research?q='+encodeURIComponent(newsQ),'POST'),
    onSuccess:()=>qc.invalidateQueries({queryKey:['local-news']}),
  });

  const saveTracked=useMutation({
    mutationFn:()=>apiMutate<TrackedAsset>('/api/v1/tracked-assets','POST',{
      asset_class:trackedForm.asset_class,name:trackedForm.name,identifier:trackedForm.identifier,owned:trackedForm.owned==='yes',
      portfolio_id:trackedForm.portfolio_id||null,quantity:trackedForm.owned==='yes'?trackedForm.quantity:null,
      purchase_price:trackedForm.owned==='yes'?trackedForm.purchase_price:null,purchase_date:trackedForm.owned==='yes'?trackedForm.purchase_date:null,
      fees:trackedForm.fees||'0',fx_rate:trackedForm.fx_rate||'1',currency:trackedForm.currency,
      provider_asset_id:trackedForm.asset_class==='crypto'?trackedForm.identifier:null,notes:null,
    }),
    onSuccess:()=>{setTrackedForm({...trackedForm,name:'',identifier:'',quantity:'',purchase_price:'',fees:'0',fx_rate:'1'});qc.invalidateQueries({queryKey:['tracked-assets']});qc.invalidateQueries({queryKey:['portfolios']});qc.invalidateQueries({queryKey:['securities']})},
  });
  const refreshTracked=useMutation({
    mutationFn:(id:string)=>apiMutate('/api/v1/tracked-assets/'+id+'/refresh?include_history=true','POST'),
    onSuccess:()=>{qc.invalidateQueries({queryKey:['tracked-assets']});qc.invalidateQueries({queryKey:['tracked-assets-history']});qc.invalidateQueries({queryKey:['portfolios']});qc.invalidateQueries({queryKey:['simulation-history']})},
  });
  const refreshAll=useMutation({
    mutationFn:()=>apiMutate<RefreshAll>('/api/v1/tracked-assets/refresh-all?include_history=true','POST'),
    onSuccess:()=>{qc.invalidateQueries({queryKey:['tracked-assets']});qc.invalidateQueries({queryKey:['tracked-assets-history']});qc.invalidateQueries({queryKey:['portfolios']});qc.invalidateQueries({queryKey:['simulation-history']})},
  });
  const startSimulation=useMutation({
    mutationFn:({id,amount}:{id:string;amount:string})=>apiMutate<TrackedAsset>('/api/v1/tracked-assets/'+id+'/simulation','POST',{amount}),
    onSuccess:(_,vars)=>{setSelectedSimulation(vars.id);qc.invalidateQueries({queryKey:['tracked-assets']});qc.invalidateQueries({queryKey:['simulation-history',vars.id]})},
  });
  const removeTracked=useMutation({
    mutationFn:(id:string)=>apiMutate('/api/v1/tracked-assets/'+id+'/unfollow','POST'),
    onSuccess:(_,id)=>{if(selectedSimulation===id)setSelectedSimulation('');qc.invalidateQueries({queryKey:['tracked-assets']})},
  });

  const simulations=useMemo(()=>tracked.data?.filter(a=>a.simulation)||[],[tracked.data]);
  const simulatedTotals=useMemo(()=>simulations.reduce((acc,a)=>{
    acc.invested+=Number(a.simulation?.invested_amount||0);
    acc.current+=Number(a.simulation?.current_value||a.simulation?.invested_amount||0);
    acc.pnl+=Number(a.simulation?.pnl||0);
    return acc;
  },{invested:0,current:0,pnl:0}),[simulations]);
  const chartData=useMemo(()=>simHistory.data?.rows.map(r=>({date:new Date(r.timestamp).toLocaleDateString('es-ES'),value:Number(r.value),pnl:Number(r.pnl)}))||[],[simHistory.data]);
  const trackedChart=useMemo(()=>{
    const byDate=new Map<string,Record<string,string|number>>();
    for(const asset of trackedHistory.data||[]){
      const rows=[...asset.rows].sort((a,b)=>a.timestamp.localeCompare(b.timestamp));
      const base=Number(rows[0]?.close||0);
      if(!base)continue;
      for(const row of rows){
        const key=row.timestamp.slice(0,10);
        const point=byDate.get(key)||{date:key};
        point[asset.security_id]=(Number(row.close)/base-1)*100;
        byDate.set(key,point);
      }
    }
    return [...byDate.values()].sort((a,b)=>String(a.date).localeCompare(String(b.date)));
  },[trackedHistory.data]);
  const historySeries=useMemo(()=>(trackedHistory.data||[]).filter(x=>x.rows.length>0),[trackedHistory.data]);

  const cryptoRow=Array.isArray(crypto.data?.assets)?crypto.data?.assets?.[0]:undefined;
  const cryptoRisk=cryptoMetrics.data?.metrics;

  return <>
    <PageHeader title="Mercados e inversiones seguidas" description="Carteras reales y simuladas persistentes, precios externos normalizados y noticias analizadas contra tus activos. Los escenarios no son predicciones ni recomendaciones."/>

    {simulations.length>0&&<Card className="mb-4">
      <div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="font-bold">Cartera simulada</h2><p className="mt-1 text-sm text-[var(--muted)]">Agrupa todas tus compras hipotéticas guardadas. Cada activo conserva su fecha y precio real de entrada.</p></div><div className="text-xs text-[var(--muted)]">{simulations.length} activo(s) simulados</div></div>
      <div className="mt-4 grid gap-3 sm:grid-cols-3"><div className="rounded-xl bg-[var(--surface-2)] p-3"><div className="text-xs text-[var(--muted)]">Invertido hipotético</div><strong><Money value={simulatedTotals.invested}/></strong></div><div className="rounded-xl bg-[var(--surface-2)] p-3"><div className="text-xs text-[var(--muted)]">Valor actual</div><strong><Money value={simulatedTotals.current}/></strong></div><div className="rounded-xl bg-[var(--surface-2)] p-3"><div className="text-xs text-[var(--muted)]">Resultado</div><strong><Money value={simulatedTotals.pnl}/></strong></div></div>
    </Card>}

    {historySeries.length>0&&<Card className="mb-4">
      <div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="font-bold">Evolución de los valores que sigues</h2><p className="mt-1 text-sm text-[var(--muted)]">Compara el cambio porcentual de cada activo durante los últimos 12 meses desde su primer precio disponible. Se normaliza a 0% para que activos con precios y divisas distintas sean comparables.</p></div><div className="text-xs text-[var(--muted)]">{historySeries.length} serie(s)</div></div>
      {trackedChart.length>1?<div className="mt-4 h-80"><ResponsiveContainer width="100%" height="100%"><LineChart data={trackedChart}><CartesianGrid strokeDasharray="3 3"/><XAxis dataKey="date" tickFormatter={v=>new Date(String(v)+'T00:00:00').toLocaleDateString('es-ES',{month:'short',year:'2-digit'})}/><YAxis tickFormatter={v=>Number(v).toLocaleString('es-ES',{maximumFractionDigits:0})+'%'}/><Tooltip labelFormatter={v=>new Date(String(v)+'T00:00:00').toLocaleDateString('es-ES')} formatter={(v,name)=>[Number(v).toLocaleString('es-ES',{maximumFractionDigits:2})+'%',historySeries.find(x=>x.security_id===String(name))?.name||String(name)]}/>{historySeries.map(asset=><Line key={asset.security_id} type="monotone" dataKey={asset.security_id} name={asset.security_id} stroke={seriesColor(asset.security_id)} strokeWidth={2.5} dot={false} connectNulls/>)}</LineChart></ResponsiveContainer></div>:<EmptyState>Aún no hay dos fechas de precio suficientes para dibujar la evolución.</EmptyState>}
      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-2 text-xs">{historySeries.map(asset=><div key={asset.security_id} className="flex items-center gap-2"><span aria-hidden="true" className="inline-block h-2.5 w-2.5 rounded-full" style={{background:seriesColor(asset.security_id)}}></span><span>{asset.name} · {asset.identifier||'sin ticker'}</span></div>)}</div>
      <div className="mt-3 overflow-auto"><table className="w-full min-w-[520px] text-xs"><thead><tr className="text-left text-[var(--muted)]"><th className="p-2">Activo</th><th className="p-2">Primer dato</th><th className="p-2">Último dato</th><th className="p-2">Fuente última</th></tr></thead><tbody>{historySeries.map(asset=><tr key={asset.security_id} className="border-t border-[var(--border)]"><td className="p-2 font-medium">{asset.name}</td><td className="p-2">{new Date(asset.rows[0].timestamp).toLocaleDateString('es-ES')}</td><td className="p-2">{new Date(asset.rows[asset.rows.length-1].timestamp).toLocaleDateString('es-ES')}</td><td className="p-2">{asset.rows[asset.rows.length-1].provider}</td></tr>)}</tbody></table></div>
    </Card>}

    <Card className="mb-4">
      <div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="font-bold">Mis activos</h2><p className="mt-1 text-sm text-[var(--muted)]">Registra una tenencia real o sigue un activo. Si no lo tienes puedes iniciar una compra simulada y ver cómo habría evolucionado.</p></div><button className="fin-button secondary" disabled={refreshAll.isPending||!tracked.data?.length} onClick={()=>refreshAll.mutate()}>{refreshAll.isPending?'Actualizando…':'Actualizar precios e histórico'}</button></div>
      <form className="mt-4 grid gap-2 md:grid-cols-4" onSubmit={(e:FormEvent)=>{e.preventDefault();saveTracked.mutate()}}>
        <select aria-label="Tipo de activo seguido" className="fin-input" value={trackedForm.asset_class} onChange={e=>setTrackedForm({...trackedForm,asset_class:e.target.value})}><option value="stock">Acción</option><option value="etf">ETF</option><option value="fund">Fondo</option><option value="crypto">Cripto</option><option value="bond">Bono</option></select>
        <input aria-label="Nombre del activo" className="fin-input" placeholder="Nombre" value={trackedForm.name} onChange={e=>setTrackedForm({...trackedForm,name:e.target.value})} required/>
        <input aria-label="Identificador del activo" className="fin-input" placeholder={trackedForm.asset_class==='crypto'?'CoinGecko ID, ej. bitcoin':'Ticker, ej. AAPL'} value={trackedForm.identifier} onChange={e=>setTrackedForm({...trackedForm,identifier:e.target.value})} required/>
        <select aria-label="Tenencia del activo" className="fin-input" value={trackedForm.owned} onChange={e=>setTrackedForm({...trackedForm,owned:e.target.value})}><option value="no">Solo seguir / simular</option><option value="yes">Lo tengo realmente</option></select>
        <select aria-label="Divisa del activo" className="fin-input" value={trackedForm.currency} onChange={e=>setTrackedForm({...trackedForm,currency:e.target.value})}><option value="EUR">EUR</option><option value="USD">USD</option><option value="GBP">GBP</option><option value="CHF">CHF</option></select>
        {trackedForm.owned==='yes'&&<>
          <select aria-label="Cartera del activo" className="fin-input" value={trackedForm.portfolio_id} onChange={e=>setTrackedForm({...trackedForm,portfolio_id:e.target.value})}><option value="">Cartera Principal automática</option>{portfolios.data?.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select>
          <label className="text-xs text-[var(--muted)]">Cantidad que tienes<input aria-label="Cantidad comprada" className="fin-input mt-1" type="number" step="any" placeholder={trackedForm.asset_class==='crypto'?'Ej. 0,025 BTC':'Ej. 10 acciones'} value={trackedForm.quantity} onChange={e=>setTrackedForm({...trackedForm,quantity:e.target.value})} required/></label>
          <label className="text-xs text-[var(--muted)]">Precio pagado por unidad<input aria-label="Precio de compra" className="fin-input mt-1" type="number" step="any" placeholder="Precio por BTC/acción/participación" value={trackedForm.purchase_price} onChange={e=>setTrackedForm({...trackedForm,purchase_price:e.target.value})} required/></label>
          <input aria-label="Fecha de compra" className="fin-input" type="date" value={trackedForm.purchase_date} onChange={e=>setTrackedForm({...trackedForm,purchase_date:e.target.value})} required/>
          <input aria-label="Comisiones de compra" className="fin-input" type="number" step=".01" placeholder="Comisiones" value={trackedForm.fees} onChange={e=>setTrackedForm({...trackedForm,fees:e.target.value})}/>
          <input aria-label="Tipo de cambio a EUR en la compra" className="fin-input" type="number" step="any" placeholder="FX compra (1 si EUR)" value={trackedForm.fx_rate} onChange={e=>setTrackedForm({...trackedForm,fx_rate:e.target.value})}/>
        </>}
        <button className="fin-button md:col-span-4" disabled={saveTracked.isPending}>{saveTracked.isPending?'Guardando…':'Guardar activo'}</button>
      </form>
      {(saveTracked.error||refreshTracked.error||refreshAll.error||startSimulation.error||removeTracked.error)&&<div className="mt-3"><ErrorState error={(saveTracked.error||refreshTracked.error||refreshAll.error||startSimulation.error||removeTracked.error)!}/></div>}
      {refreshAll.data&&<div className="mt-3 rounded-xl bg-[var(--surface-2)] p-3 text-sm">
        <strong>Actualización terminada:</strong> {refreshAll.data.refreshed.length} activo(s) actualizados.
        {refreshAll.data.failed.length>0&&<div className="mt-1 text-xs text-[var(--muted)]">{refreshAll.data.failed.length} no se pudieron actualizar por la fuente externa: {refreshAll.data.failed.map(x=>x.error).join(' · ')}</div>}
      </div>}

      <div className="mt-5 grid gap-3 lg:grid-cols-2">
        {tracked.data?.length?tracked.data.map(a=><div key={a.security_id} className="rounded-xl bg-[var(--surface-2)] p-4 text-sm">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div><strong>{a.name}</strong><div className="text-xs text-[var(--muted)]">{a.asset_class} · {a.identifier||a.provider_asset_id||'sin identificador'} · {a.owned?'posición real':'seguimiento'}</div></div>
            <div className="flex gap-2"><button className="fin-button secondary py-1.5 text-xs" disabled={refreshTracked.isPending} onClick={()=>refreshTracked.mutate(a.security_id)}>Actualizar</button>{!a.owned&&<button className="text-xs underline" onClick={()=>removeTracked.mutate(a.security_id)}>Dejar de seguir</button>}</div>
          </div>
          <div className="mt-3 grid grid-cols-2 gap-2">
            <div><span className="text-[var(--muted)]">Precio actual</span><div className="font-semibold"><Money value={a.current_price} currency={a.currency}/></div></div>
            {a.owned?<><div><span className="text-[var(--muted)]">Precio medio compra</span><div className="font-semibold"><Money value={a.average_cost} currency={a.currency}/></div></div><div><span className="text-[var(--muted)]">Cantidad</span><div className="font-semibold">{Number(a.quantity).toLocaleString('es-ES',{maximumFractionDigits:8})}</div></div><div><span className="text-[var(--muted)]">Valor actual</span><div className="font-semibold"><Money value={a.current_value} currency={a.currency}/></div></div><div><span className="text-[var(--muted)]">P&L no realizado</span><div className="font-semibold"><Money value={a.unrealized_pnl} currency={a.currency}/> · {pct(a.unrealized_return)}</div></div><div><span className="text-[var(--muted)]">P&L realizado + dividendos</span><div className="font-semibold"><Money value={Number(a.realized_pnl)+Number(a.dividends)} currency={a.currency}/></div></div></>:<>
              <div><span className="text-[var(--muted)]">Simulación</span><div className="font-semibold">{a.simulation?'Activa desde '+new Date(a.simulation.started_at).toLocaleDateString('es-ES'):'No iniciada'}</div></div>
            </>}
          </div>

          {!a.owned&&<div className="mt-3 rounded-xl bg-white p-3">
            {a.simulation?<div className="grid gap-2 sm:grid-cols-3 text-xs"><div><span className="text-[var(--muted)]">Entrada</span><div><Money value={a.simulation.entry_price} currency={a.currency}/></div></div><div><span className="text-[var(--muted)]">Valor simulado</span><div><Money value={a.simulation.current_value} currency={a.currency}/></div></div><div><span className="text-[var(--muted)]">Resultado</span><div><Money value={a.simulation.pnl} currency={a.currency}/> · {pct(a.simulation.return)}</div></div></div>:null}
            <div className="mt-2 flex gap-2"><input className="fin-input" type="number" step=".01" min="0.01" aria-label={'Importe simulado '+a.name} placeholder="Importe hipotético" value={simAmounts[a.security_id]||''} onChange={e=>setSimAmounts({...simAmounts,[a.security_id]:e.target.value})}/><button className="fin-button py-2 text-xs" disabled={!simAmounts[a.security_id]||startSimulation.isPending} onClick={()=>startSimulation.mutate({id:a.security_id,amount:simAmounts[a.security_id]})}>{a.simulation?'Reiniciar simulación':'Simular compra'}</button></div>
            {a.simulation&&<button className="mt-2 text-xs underline" onClick={()=>setSelectedSimulation(a.security_id)}>Ver evolución simulada</button>}
          </div>}

          {a.owned&&<div className="mt-3 text-xs"><a className="underline" href="/investments/">Registrar otra compra, venta o dividendo</a></div>}
          <div className="mt-3 text-xs text-[var(--muted)]">{a.price_provider?(a.price_provider+' · '+(a.price_as_of?new Date(a.price_as_of).toLocaleString('es-ES'):'fecha no informada')+(a.price_stale?' · precio desactualizado':'')):'Aún no hay un precio de mercado guardado.'}</div>
        </div>):<EmptyState>No has guardado activos todavía.</EmptyState>}
      </div>
    </Card>

    {selectedSimulation&&<Card className="mb-4">
      <div className="flex items-start justify-between gap-3"><div><h2 className="font-bold">Evolución de la compra simulada</h2><p className="mt-1 text-sm text-[var(--muted)]">Valor de la misma cantidad hipotética desde el momento en que inició la simulación.</p></div><button className="text-xs underline" onClick={()=>setSelectedSimulation('')}>Cerrar</button></div>
      {chartData.length?<div className="mt-4 h-72"><ResponsiveContainer width="100%" height="100%"><LineChart data={chartData}><CartesianGrid strokeDasharray="3 3"/><XAxis dataKey="date"/><YAxis/><Tooltip formatter={(v)=>new Intl.NumberFormat('es-ES',{style:'currency',currency:'EUR'}).format(Number(v))}/><Line type="monotone" dataKey="value" name="Valor simulado" stroke="var(--chart-income)" strokeWidth={3} dot={false}/></LineChart></ResponsiveContainer></div>:<EmptyState>Aún no hay histórico suficiente para dibujar la evolución.</EmptyState>}
    </Card>}

    <div className="grid gap-4 xl:grid-cols-2">
      <Card>
        <h2 className="font-bold">Cotización</h2>
        <form className="mt-3 flex gap-2" onSubmit={(e:FormEvent)=>{e.preventDefault();quote.mutate()}}><input className="fin-input" aria-label="Ticker" placeholder="Ticker, ej. AAPL" value={symbol} onChange={e=>setSymbol(e.target.value.trim().toUpperCase())}/><button className="fin-button">Consultar</button></form><div className="mt-1 text-[11px] text-[var(--muted)]">Usa el ticker real del mercado. Por ejemplo, Apple es AAPL; un ticker inexistente como AAPPL se rechazará sin guardar una cotización falsa.</div>
        {quote.error&&<div className="mt-3"><ErrorState error={quote.error}/></div>}
        {quote.data&&<div className="mt-4"><div className="text-2xl font-bold"><Money value={quote.data.price}/></div><div className="text-xs text-[var(--muted)]">{quote.data.provider} · {quote.data.as_of?new Date(quote.data.as_of).toLocaleString('es-ES'):'fecha no informada'} · {quote.data.delayed?'dato retrasado':'sin marca de retraso'}</div></div>}
      </Card>

      <Card>
        <h2 className="font-bold">Cripto</h2>
        <form className="mt-3 flex gap-2" onSubmit={(e:FormEvent)=>{e.preventDefault();crypto.mutate();cryptoMetrics.mutate()}}><input className="fin-input" aria-label="Activo cripto" value={coin} onChange={e=>setCoin(e.target.value)}/><button className="fin-button">Precio y riesgo</button></form>
        {(crypto.error||cryptoMetrics.error)&&<div className="mt-3"><ErrorState error={(crypto.error||cryptoMetrics.error)!}/></div>}
        {cryptoRow&&<div className="mt-4 grid gap-2 sm:grid-cols-2 text-sm"><div><span className="text-[var(--muted)]">Precio</span><div className="text-xl font-bold"><Money value={cryptoRow.price??null} currency={cryptoRow.currency||'EUR'}/></div></div><div><span className="text-[var(--muted)]">Cambio 24 h</span><div className="font-semibold">{cryptoRow.change_24h_pct==null?'—':cryptoRow.change_24h_pct.toLocaleString('es-ES',{maximumFractionDigits:2})+'%'}</div></div><div><span className="text-[var(--muted)]">Capitalización</span><div className="font-semibold"><Money value={cryptoRow.market_cap??null} currency={cryptoRow.currency||'EUR'}/></div></div><div><span className="text-[var(--muted)]">Volumen 24 h</span><div className="font-semibold"><Money value={cryptoRow.volume_24h??null} currency={cryptoRow.currency||'EUR'}/></div></div><div className="text-xs text-[var(--muted)] sm:col-span-2">Fuente {crypto.data?.provider||'CoinGecko'}{cryptoRow.last_updated_at?' · '+new Date(cryptoRow.last_updated_at*1000).toLocaleString('es-ES'):''}</div></div>}
        {cryptoMetrics.data&&cryptoRisk&&<div className="mt-3 grid grid-cols-2 gap-2 text-sm"><div>Volatilidad anual <strong>{cryptoRisk.volatility==null?'—':(cryptoRisk.volatility*100).toLocaleString('es-ES',{maximumFractionDigits:1})+'%'}</strong></div><div>Drawdown <strong>{cryptoRisk.max_drawdown==null?'—':(cryptoRisk.max_drawdown*100).toLocaleString('es-ES',{maximumFractionDigits:1})+'%'}</strong></div><div>Sharpe <strong>{cryptoRisk.sharpe==null?'—':cryptoRisk.sharpe.toLocaleString('es-ES',{maximumFractionDigits:2})}</strong></div><div>Muestras <strong>{(cryptoMetrics.data.observations??0).toLocaleString('es-ES')}</strong></div></div>}
        {crypto.data&&!cryptoRow&&!crypto.error&&<div className="mt-3 text-sm text-[var(--muted)]">La fuente no ha devuelto datos para ese identificador. Usa el ID de CoinGecko, por ejemplo <strong>bitcoin</strong> o <strong>ethereum</strong>.</div>}
      </Card>

      <Card>
        <h2 className="font-bold">Fundamentales SEC EDGAR</h2>
        <form className="mt-3 flex gap-2" onSubmit={(e:FormEvent)=>{e.preventDefault();sec.mutate()}}><input className="fin-input" aria-label="CIK" value={cik} onChange={e=>setCik(e.target.value)}/><button className="fin-button">Consultar</button></form>
        {sec.error&&<div className="mt-3"><ErrorState error={sec.error}/></div>}
        {sec.data&&<div className="mt-4"><div className="font-semibold">{sec.data.entity_name}</div><div className="text-xs text-[var(--muted)]">CIK {sec.data.cik} · {sec.data.provider}</div><div className="mt-3 space-y-2">{Object.entries(sec.data.facts).map(([name,fact])=><div key={name} className="flex flex-wrap justify-between gap-2 rounded-xl bg-[var(--surface-2)] p-3 text-sm"><div><strong>{name.replaceAll(/([A-Z])/g,' $1').trim()}</strong><div className="text-xs text-[var(--muted)]">{fact.period_end||'periodo no informado'} · presentado {fact.filed||'—'} · {fact.form||'—'}</div></div><div className="font-semibold">{fact.unit==='USD'?<Money value={fact.value} currency="USD"/>:Number(fact.value).toLocaleString('es-ES')} <span className="text-xs text-[var(--muted)]">{fact.unit==='USD'?'':fact.unit}</span></div></div>)}</div></div>}
      </Card>

      <Card>
        <h2 className="font-bold">Buscar y analizar noticias</h2>
        <p className="mt-1 text-sm text-[var(--muted)]">Una sola búsqueda guarda las noticias, vincula entidades y, si tu IA local funciona, separa hechos de posibles impactos sobre tus activos.</p>
        <form className="mt-3 flex gap-2" onSubmit={(e:FormEvent)=>{e.preventDefault();research.mutate()}}><input className="fin-input" aria-label="Consulta de noticias" value={newsQ} onChange={e=>setNewsQ(e.target.value)}/><button className="fin-button" disabled={research.isPending}>{research.isPending?'Buscando…':'Buscar y analizar'}</button></form>
        {research.error&&<div className="mt-3"><ErrorState error={research.error}/></div>}
        {research.data&&<div className="mt-4 space-y-3"><div className="rounded-xl bg-[var(--brand-soft)] p-3 text-sm"><strong>Resumen</strong><div className="mt-1">{research.data.brief.summary}</div><div className="mt-2 text-[11px] text-[var(--muted)]">{research.data.ingest.inserted} nuevas de {research.data.ingest.discovered} encontradas · método {research.data.brief.method}{research.data.brief.ai_available?' · IA local disponible':' · sin IA local'}</div></div>{research.data.brief.portfolio_impacts?.map((x,i)=><div key={i} className="rounded-xl bg-[var(--surface-2)] p-3 text-xs"><strong>{x.asset||'Impacto transversal'}</strong>{x.observation&&<div className="mt-1">{x.observation}</div>}{x.possible_effects&&<div className="mt-1 text-[var(--muted)]">Escenarios: {Array.isArray(x.possible_effects)?x.possible_effects.join(' · '):x.possible_effects}</div>}</div>)}{research.data.brief.risks.length>0&&<div className="text-xs"><strong>Riesgos / límites:</strong> {research.data.brief.risks.join(' · ')}</div>}{research.data.brief.watch.length>0&&<div className="text-xs"><strong>Qué vigilar:</strong> {research.data.brief.watch.join(' · ')}</div>}<div className="space-y-2">{research.data.brief.facts.slice(0,8).map(x=><a key={x.url} href={x.url} target="_blank" rel="noreferrer" className="block rounded-xl border border-[var(--border)] p-3 text-xs"><strong>{x.headline}</strong><div className="mt-1 text-[var(--muted)]">{x.source} · {new Date(x.published_at).toLocaleString('es-ES')}{x.linked_assets.length?' · '+x.linked_assets.join(', '):''}</div></a>)}</div></div>}
      </Card>

      <Card className="xl:col-span-2">
        <h2 className="font-bold">Noticias guardadas</h2>
        <p className="mt-1 text-sm text-[var(--muted)]">La clasificación de evento y sentimiento es contexto estructurado; no se presenta como probabilidad de subida o bajada.</p>
        <div className="mt-4 grid gap-3 lg:grid-cols-2">{local.data?.items.length?local.data.items.map(item=><a key={item.id} href={item.url} target="_blank" rel="noreferrer" className="rounded-xl bg-[var(--surface-2)] p-4 text-sm"><strong>{item.headline}</strong><div className="mt-1 text-xs text-[var(--muted)]">{item.source} · {new Date(item.published_at).toLocaleString('es-ES')}</div><div className="mt-3 space-y-2">{item.analysis.length?item.analysis.map((a,i)=><div key={i} className="rounded-lg bg-white p-2 text-xs"><div><strong>{a.security||'Sin activo vinculado'}</strong> · {a.event_type.replaceAll('_',' ')} · impacto {a.impact_level} · tono {sentimentLabel(a.sentiment)}</div><div className="mt-1 text-[var(--muted)]">confianza {Math.round(a.confidence*100)}% · {a.rationale}</div></div>):<div className="text-xs text-[var(--muted)]">Sin señales suficientes para vincularla a un activo.</div>}</div></a>):<EmptyState>No hay noticias guardadas.</EmptyState>}</div>
      </Card>
    </div>
  </>;
}
