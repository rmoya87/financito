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

function sentimentLabel(value:number){return value>.15?'positivo':value<-.15?'negativo':'neutral'}

export default function MarketsPage(){
  const qc=useQueryClient();
  const [symbol,setSymbol]=useState('AAPL');
  const [coin,setCoin]=useState('bitcoin');
  const [newsQ,setNewsQ]=useState('markets');
  const [cik,setCik]=useState('0000320193');
  const quote=useMutation({mutationFn:()=>apiGet<Quote>('/api/v1/market/quote/'+encodeURIComponent(symbol))});
  const crypto=useMutation({mutationFn:()=>apiGet<any>('/api/v1/crypto/price?ids='+encodeURIComponent(coin)+'&vs_currency=eur')});
  const cryptoMetrics=useMutation({mutationFn:()=>apiGet<CryptoMetrics>('/api/v1/crypto/metrics/'+encodeURIComponent(coin)+'?vs_currency=eur&days=90')});
  const news=useMutation({mutationFn:()=>apiGet<News>('/api/v1/news/search?q='+encodeURIComponent(newsQ))});
  const ingest=useMutation({mutationFn:()=>apiMutate<{inserted:number;discovered:number}>('/api/v1/news/ingest?q='+encodeURIComponent(newsQ),'POST'),onSuccess:()=>qc.invalidateQueries({queryKey:['local-news']})});
  const local=useQuery({queryKey:['local-news'],queryFn:()=>apiGet<LocalNews>('/api/v1/news/local?limit=30')});
  const sec=useMutation({mutationFn:()=>apiGet<any>('/api/v1/fundamentals/sec/'+encodeURIComponent(cik))});
  return <>
    <PageHeader title="Mercados y fuentes" description="Datos externos bajo demanda, con proveedor visible. Los análisis derivados se calculan localmente y no son predicciones."/>
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
