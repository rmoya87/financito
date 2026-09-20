'use client';

import {FormEvent,useState} from 'react';
import {useMutation,useQuery,useQueryClient} from '@tanstack/react-query';
import {apiGet,apiMutate} from '@/lib/api';
import {PageHeader} from '@/components/page-header';
import {Card} from '@/components/ui/card';
import {EmptyState,ErrorState} from '@/components/ui/states';

type Quote={symbol:string;price:string;provider:string;as_of:string|null;delayed:boolean};
type News={items:{title:string;url:string;source:string;published_at:string}[]};
type CryptoMetrics={coin_id:string;metrics:{volatility:number|null;max_drawdown:number;sharpe:number|null;sortino:number|null;var_95?:number;cvar_95?:number};observations:number;provider:string};
type Analysis={security_id:string|null;security:string|null;event_type:string;sentiment:number;impact_level:string;confidence:number;method_version:string;rationale:string};
type LocalNews={items:{id:string;headline:string;url:string;source:string;published_at:string;reliability:number;analysis:Analysis[]}[]};
type Portfolio={id:string;name:string};
type TrackedAsset={security_id:string;name:string;identifier:string|null;asset_class:string;currency:string;tracking_state:string;provider_asset_id:string|null;owned:boolean;quantity:string;average_cost:string;cost_basis:string;current_price:string|null;current_value:string|null;unrealized_pnl:string|null;unrealized_return:string|null;realized_pnl:string;dividends:string;total_result:string|null;price_provider:string|null;price_as_of:string|null;price_fetched_at:string|null;price_delayed:boolean|null};

function sentimentLabel(value:number){return value>.15?'positivo':value<-.15?'negativo':'neutral'}

export default function MarketsPage(){
  const qc=useQueryClient();
  const [symbol,setSymbol]=useState('AAPL');
  const [coin,setCoin]=useState('bitcoin');
  const [newsQ,setNewsQ]=useState('markets');
  const [cik,setCik]=useState('0000320193');
  const [trackedForm,setTrackedForm]=useState({asset_class:'stock',name:'',identifier:'',owned:'no',portfolio_id:'',quantity:'',purchase_price:'',purchase_date:new Date().toISOString().slice(0,10),fees:'0',currency:'EUR',fx_rate:'1'});
  const portfolios=useQuery({queryKey:['portfolios'],queryFn:()=>apiGet<Portfolio[]>('/api/v1/portfolios')});
  const tracked=useQuery({queryKey:['tracked-assets'],queryFn:()=>apiGet<TrackedAsset[]>('/api/v1/tracked-assets')});
  const quote=useMutation({mutationFn:()=>apiGet<Quote>('/api/v1/market/quote/'+encodeURIComponent(symbol))});
  const crypto=useMutation({mutationFn:()=>apiGet<any>('/api/v1/crypto/price?ids='+encodeURIComponent(coin)+'&vs_currency=eur')});
  const cryptoMetrics=useMutation({mutationFn:()=>apiGet<CryptoMetrics>('/api/v1/crypto/metrics/'+encodeURIComponent(coin)+'?vs_currency=eur&days=90')});
  const news=useMutation({mutationFn:()=>apiGet<News>('/api/v1/news/search?q='+encodeURIComponent(newsQ))});
  const ingest=useMutation({mutationFn:()=>apiMutate<{inserted:number;discovered:number}>('/api/v1/news/ingest?q='+encodeURIComponent(newsQ),'POST'),onSuccess:()=>qc.invalidateQueries({queryKey:['local-news']})});
  const local=useQuery({queryKey:['local-news'],queryFn:()=>apiGet<LocalNews>('/api/v1/news/local?limit=30')});
  const sec=useMutation({mutationFn:()=>apiGet<any>('/api/v1/fundamentals/sec/'+encodeURIComponent(cik))});
  const saveTracked=useMutation({mutationFn:()=>apiMutate<TrackedAsset>('/api/v1/tracked-assets','POST',{asset_class:trackedForm.asset_class,name:trackedForm.name,identifier:trackedForm.identifier,owned:trackedForm.owned==='yes',portfolio_id:trackedForm.portfolio_id||null,quantity:trackedForm.owned==='yes'?trackedForm.quantity:null,purchase_price:trackedForm.owned==='yes'?trackedForm.purchase_price:null,purchase_date:trackedForm.owned==='yes'?trackedForm.purchase_date:null,fees:trackedForm.fees||'0',fx_rate:trackedForm.fx_rate||'1',currency:trackedForm.currency,provider_asset_id:trackedForm.asset_class==='crypto'?trackedForm.identifier:null,notes:null}),onSuccess:()=>{setTrackedForm({...trackedForm,name:'',identifier:'',quantity:'',purchase_price:'',fees:'0',fx_rate:'1'});qc.invalidateQueries({queryKey:['tracked-assets']});qc.invalidateQueries({queryKey:['portfolios']});qc.invalidateQueries({queryKey:['securities']})}});
  const refreshTracked=useMutation({mutationFn:(id:string)=>apiMutate('/api/v1/tracked-assets/'+id+'/refresh?include_history=false','POST'),onSuccess:()=>{qc.invalidateQueries({queryKey:['tracked-assets']});qc.invalidateQueries({queryKey:['portfolios']})}});
  return <>
    <PageHeader title="Mercados y fuentes" description="Datos externos bajo demanda, con proveedor visible. Los análisis derivados se calculan localmente y no son predicciones."/>
    <Card className="mb-4">
      <h2 className="font-bold">Mis acciones y cripto</h2>
      <p className="mt-1 text-sm text-[var(--muted)]">Guarda activos que tienes o que solo quieres seguir. Si lo tienes, Financito usa tu cantidad y precio de compra para calcular coste, valor actual y resultado con el último precio real guardado.</p>
      <form className="mt-4 grid gap-2 md:grid-cols-4" onSubmit={(e:FormEvent)=>{e.preventDefault();saveTracked.mutate()}}>
        <select aria-label="Tipo de activo seguido" className="fin-input" value={trackedForm.asset_class} onChange={e=>setTrackedForm({...trackedForm,asset_class:e.target.value})}><option value="stock">Acción</option><option value="etf">ETF</option><option value="fund">Fondo</option><option value="crypto">Cripto</option></select>
        <input aria-label="Nombre del activo" className="fin-input" placeholder="Nombre" value={trackedForm.name} onChange={e=>setTrackedForm({...trackedForm,name:e.target.value})} required/>
        <input aria-label="Identificador del activo" className="fin-input" placeholder={trackedForm.asset_class==='crypto'?'CoinGecko ID, ej. bitcoin':'Ticker, ej. AAPL'} value={trackedForm.identifier} onChange={e=>setTrackedForm({...trackedForm,identifier:e.target.value})} required/>
        <select aria-label="Tenencia del activo" className="fin-input" value={trackedForm.owned} onChange={e=>setTrackedForm({...trackedForm,owned:e.target.value})}><option value="no">No lo tengo · solo seguir</option><option value="yes">Sí, lo tengo</option></select>
        <select aria-label="Divisa del activo" className="fin-input" value={trackedForm.currency} onChange={e=>setTrackedForm({...trackedForm,currency:e.target.value})}><option value="EUR">EUR</option><option value="USD">USD</option><option value="GBP">GBP</option><option value="CHF">CHF</option></select>
        {trackedForm.owned==='yes'&&<>
          <select aria-label="Cartera del activo" className="fin-input" value={trackedForm.portfolio_id} onChange={e=>setTrackedForm({...trackedForm,portfolio_id:e.target.value})}><option value="">Cartera Principal automática</option>{portfolios.data?.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select>
          <input aria-label="Cantidad comprada" className="fin-input" type="number" step="any" placeholder="Cantidad" value={trackedForm.quantity} onChange={e=>setTrackedForm({...trackedForm,quantity:e.target.value})} required/>
          <input aria-label="Precio de compra" className="fin-input" type="number" step="any" placeholder="Precio de compra" value={trackedForm.purchase_price} onChange={e=>setTrackedForm({...trackedForm,purchase_price:e.target.value})} required/>
          <input aria-label="Fecha de compra" className="fin-input" type="date" value={trackedForm.purchase_date} onChange={e=>setTrackedForm({...trackedForm,purchase_date:e.target.value})} required/>
          <input aria-label="Comisiones de compra" className="fin-input" type="number" step=".01" placeholder="Comisiones" value={trackedForm.fees} onChange={e=>setTrackedForm({...trackedForm,fees:e.target.value})}/>
          <input aria-label="Tipo de cambio a EUR en la compra" className="fin-input" type="number" step="any" placeholder="FX compra (1 si EUR)" value={trackedForm.fx_rate} onChange={e=>setTrackedForm({...trackedForm,fx_rate:e.target.value})}/>
        </>}
        <button className="fin-button md:col-span-4" disabled={saveTracked.isPending}>{saveTracked.isPending?'Guardando…':'Guardar activo'}</button>
      </form>
      {saveTracked.error&&<div className="mt-3"><ErrorState error={saveTracked.error}/></div>}
      {refreshTracked.error&&<div className="mt-3"><ErrorState error={refreshTracked.error}/></div>}
      <div className="mt-5 grid gap-3 lg:grid-cols-2">
        {tracked.data?.length?tracked.data.map(a=><div key={a.security_id} className="rounded-xl bg-[var(--surface-2)] p-4 text-sm">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div><strong>{a.name}</strong><div className="text-xs text-[var(--muted)]">{a.asset_class} · {a.identifier||a.provider_asset_id||'sin identificador'} · {a.owned?'lo tienes':'solo seguimiento'}</div></div>
            <button className="fin-button secondary py-1.5 text-xs" disabled={refreshTracked.isPending} onClick={()=>refreshTracked.mutate(a.security_id)}>Actualizar precio</button>
          </div>
          <div className="mt-3 grid grid-cols-2 gap-2">
            <div><span className="text-[var(--muted)]">Precio actual</span><div className="font-semibold">{a.current_price===null?'n/d':a.current_price+' '+a.currency}</div></div>
            <div><span className="text-[var(--muted)]">Precio medio compra</span><div className="font-semibold">{a.owned?a.average_cost+' '+a.currency:'—'}</div></div>
            {a.owned&&<>
              <div><span className="text-[var(--muted)]">Cantidad</span><div className="font-semibold">{a.quantity}</div></div>
              <div><span className="text-[var(--muted)]">Valor actual</span><div className="font-semibold">{a.current_value===null?'n/d':a.current_value+' '+a.currency}</div></div>
              <div><span className="text-[var(--muted)]">Resultado no realizado</span><div className="font-semibold">{a.unrealized_pnl===null?'n/d':a.unrealized_pnl+' '+a.currency}{a.unrealized_return!==null?' · '+(Number(a.unrealized_return)*100).toFixed(2)+'%':''}</div></div>
              <div><span className="text-[var(--muted)]">Resultado total registrado</span><div className="font-semibold">{a.total_result===null?'n/d':a.total_result+' '+a.currency}</div></div>
              <div><span className="text-[var(--muted)]">Realizado</span><div className="font-semibold">{a.realized_pnl} {a.currency}</div></div>
              <div><span className="text-[var(--muted)]">Dividendos</span><div className="font-semibold">{a.dividends} {a.currency}</div></div>
            </>}
          </div>
          <div className="mt-3 text-xs text-[var(--muted)]">{a.price_provider?(a.price_provider+' · precio '+(a.price_as_of?new Date(a.price_as_of).toLocaleString():'sin fecha')):'Aún no hay precio de mercado guardado. Pulsa Actualizar precio.'}</div>
        </div>):<EmptyState>No has guardado acciones o cripto todavía.</EmptyState>}
      </div>
    </Card>

    <div className="grid gap-4 xl:grid-cols-2">
      <Card>
        <h2 className="font-bold">Cotización</h2>
        <form className="mt-3 flex gap-2" onSubmit={(e:FormEvent)=>{e.preventDefault();quote.mutate()}}>
          <label className="sr-only" htmlFor="market-symbol">Ticker</label>
          <input id="market-symbol" className="fin-input" value={symbol} onChange={e=>setSymbol(e.target.value)}/>
          <button className="fin-button">Consultar</button>
        </form>
        {quote.error&&<div className="mt-3"><ErrorState error={quote.error}/></div>}
        {quote.data&&<div className="mt-4"><div className="text-2xl font-bold">{quote.data.price}</div><div className="text-xs text-[var(--muted)]">{quote.data.provider} · {quote.data.as_of||'fecha no informada'} · {quote.data.delayed?'dato retrasado':'sin marca de retraso'}</div></div>}
      </Card>
      <Card>
        <h2 className="font-bold">Cripto</h2>
        <form className="mt-3 flex gap-2" onSubmit={(e:FormEvent)=>{e.preventDefault();crypto.mutate();cryptoMetrics.mutate()}}>
          <label className="sr-only" htmlFor="crypto-id">Activo cripto</label>
          <input id="crypto-id" className="fin-input" value={coin} onChange={e=>setCoin(e.target.value)}/>
          <button className="fin-button">Precio y riesgo</button>
        </form>
        {(crypto.error||cryptoMetrics.error)&&<div className="mt-3"><ErrorState error={(crypto.error||cryptoMetrics.error)!}/></div>}
        {crypto.data&&<pre className="mt-3 overflow-auto rounded-xl bg-[var(--surface-2)] p-3 text-xs">{JSON.stringify(crypto.data,null,2)}</pre>}
        {cryptoMetrics.data&&<div className="mt-3 grid grid-cols-2 gap-2 text-sm"><div>Volatilidad anual <strong>{cryptoMetrics.data.metrics.volatility===null?'n/d':(cryptoMetrics.data.metrics.volatility*100).toFixed(1)+'%'}</strong></div><div>Drawdown <strong>{(cryptoMetrics.data.metrics.max_drawdown*100).toFixed(1)}%</strong></div><div>Sharpe <strong>{cryptoMetrics.data.metrics.sharpe===null?'n/d':cryptoMetrics.data.metrics.sharpe.toFixed(2)}</strong></div><div>Muestras <strong>{cryptoMetrics.data.observations}</strong></div></div>}
      </Card>
      <Card>
        <h2 className="font-bold">SEC EDGAR</h2>
        <form className="mt-3 flex gap-2" onSubmit={(e:FormEvent)=>{e.preventDefault();sec.mutate()}}>
          <label className="sr-only" htmlFor="sec-cik">CIK</label>
          <input id="sec-cik" className="fin-input" value={cik} onChange={e=>setCik(e.target.value)}/>
          <button className="fin-button">Fundamentales</button>
        </form>
        {sec.error&&<div className="mt-3"><ErrorState error={sec.error}/></div>}
        {sec.data&&<pre className="mt-3 max-h-72 overflow-auto rounded-xl bg-[var(--surface-2)] p-3 text-xs">{JSON.stringify(sec.data,null,2)}</pre>}
      </Card>
      <Card>
        <h2 className="font-bold">Buscar noticias</h2>
        <form className="mt-3 flex gap-2" onSubmit={(e:FormEvent)=>{e.preventDefault();news.mutate()}}>
          <label className="sr-only" htmlFor="news-query">Consulta de noticias</label>
          <input id="news-query" className="fin-input" value={newsQ} onChange={e=>setNewsQ(e.target.value)}/>
          <button className="fin-button">Buscar</button>
        </form>
        <button className="fin-button secondary mt-2 w-full" onClick={()=>ingest.mutate()} disabled={ingest.isPending}>Guardar y analizar localmente</button>
        {ingest.data&&<div className="mt-2 text-xs text-[var(--muted)]">{ingest.data.inserted} nuevas de {ingest.data.discovered} encontradas.</div>}
        <div className="mt-3 space-y-2">{news.data?.items.slice(0,8).map(n=><a key={n.url} href={n.url} target="_blank" rel="noreferrer" className="block rounded-xl bg-[var(--surface-2)] p-3 text-sm"><strong>{n.title}</strong><div className="text-xs text-[var(--muted)]">{n.source} · {n.published_at}</div></a>)}</div>
      </Card>
      <Card className="xl:col-span-2">
        <h2 className="font-bold">Noticias guardadas y análisis local</h2>
        <p className="mt-1 text-sm text-[var(--muted)]">Sentimiento/impacto se obtienen mediante reglas versionadas; no representan probabilidad de movimiento del precio.</p>
        <div className="mt-4 grid gap-3 lg:grid-cols-2">
          {local.data?.items.length?local.data.items.map(item=><a key={item.id} href={item.url} target="_blank" rel="noreferrer" className="rounded-xl bg-[var(--surface-2)] p-4 text-sm">
            <strong>{item.headline}</strong>
            <div className="mt-1 text-xs text-[var(--muted)]">{item.source} · {new Date(item.published_at).toLocaleString()}</div>
            <div className="mt-3 space-y-2">{item.analysis.length?item.analysis.map((a,i)=><div key={i} className="rounded-lg bg-white/70 p-2 text-xs">
              <div><strong>{a.security||'Sin entidad vinculada'}</strong> · {a.event_type} · impacto {a.impact_level} · sentimiento {sentimentLabel(a.sentiment)}</div>
              <div className="mt-1 text-[var(--muted)]">confianza {Math.round(a.confidence*100)}% · {a.method_version} · {a.rationale}</div>
            </div>):<div className="text-xs text-[var(--muted)]">Pendiente de análisis local.</div>}</div>
          </a>):<EmptyState>No hay noticias guardadas.</EmptyState>}
        </div>
      </Card>
    </div>
  </>
}
