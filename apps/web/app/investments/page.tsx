'use client';

import {FormEvent,useState} from 'react';
import {useMutation,useQuery,useQueryClient} from '@tanstack/react-query';
import {apiGet,apiMutate,apiUpload} from '@/lib/api';
import {PageHeader} from '@/components/page-header';
import {Card} from '@/components/ui/card';
import {Money} from '@/components/ui/money';
import {EmptyState,ErrorState} from '@/components/ui/states';

type Position={security_id:string;quantity:string;average_cost:string;price:string;value:string;unrealized_pnl:string};
type P={id:string;name:string;base_currency:string;market_value:string;cost_basis:string;unrealized_pnl:string;positions:Position[]};
type S={id:string;name:string;symbol:string|null;asset_class:string;currency:string};
type Exposure={portfolio_id:string;market_value:string;by_asset_class:{asset_class:string;value:string;weight:string}[];positions:{security_id:string;name:string;symbol:string|null;value:string;weight:string}[];concentration_hhi:string;largest_position_weight:string};
type Performance={portfolio_id:string;mwr:number|null;twr:number|null;observations:number;coverage:number;current_value:string;first_trade?:string;last_trade?:string;assumptions:string[]};
type Fit={fit_score:number;proposed_weight:string;post_asset_class_weight:string;post_security_weight:string;components:Record<string,number>;warnings:string[];notice:string};
type ImportResult={file_name:string;inserted:number;skipped:number;created_securities:number;realized_pnl:string};
type CorpAction={id:string;security_id:string;action_type:string;effective_date:string;value:string;currency:string;notes:string|null;applied:boolean};
type InsightItem={title:string;detail:string;pages:number[];impact?:string};type DocInsight={document_id:string;file_name:string;document_type:string;analysis:{summary:string;confidence:string;optimization_opportunities:InsightItem[];negotiation_points:InsightItem[];comparison_requirements:InsightItem[];risks:InsightItem[];cross_area_impacts:InsightItem[]}};

export default function InvestmentsPage(){
  const qc=useQueryClient();
  const ps=useQuery({queryKey:['portfolios'],queryFn:()=>apiGet<P[]>('/api/v1/portfolios')});
  const ss=useQuery({queryKey:['securities'],queryFn:()=>apiGet<S[]>('/api/v1/securities')});
  const [pn,setPn]=useState('Principal');
  const [sec,setSec]=useState({name:'',symbol:'',asset_class:'stock'});
  const [trade,setTrade]=useState({portfolio_id:'',security_id:'',side:'buy',quantity:'',price:'',fees:'0',executed_at:new Date().toISOString().slice(0,16)});
  const [selectedPortfolio,setSelectedPortfolio]=useState('');
  const [fitSecurity,setFitSecurity]=useState('');
  const [fitWeight,setFitWeight]=useState('0.10');
  const [brokerFile,setBrokerFile]=useState<File|null>(null);
  const [action,setAction]=useState({security_id:'',action_type:'dividend',effective_date:new Date().toISOString().slice(0,10),value:'',notes:''});

  const exposure=useQuery({queryKey:['portfolio-exposure',selectedPortfolio],queryFn:()=>apiGet<Exposure>('/api/v1/portfolios/'+selectedPortfolio+'/exposure'),enabled:!!selectedPortfolio});
  const performance=useQuery({queryKey:['portfolio-performance',selectedPortfolio],queryFn:()=>apiGet<Performance>('/api/v1/portfolios/'+selectedPortfolio+'/performance'),enabled:!!selectedPortfolio});
  const fit=useQuery({queryKey:['portfolio-fit',selectedPortfolio,fitSecurity,fitWeight],queryFn:()=>apiGet<Fit>('/api/v1/portfolios/'+selectedPortfolio+'/fit/'+fitSecurity+'?proposed_weight='+encodeURIComponent(fitWeight)),enabled:!!selectedPortfolio&&!!fitSecurity});
  const actions=useQuery({queryKey:['corporate-actions',selectedPortfolio],queryFn:()=>apiGet<CorpAction[]>('/api/v1/portfolios/'+selectedPortfolio+'/corporate-actions'),enabled:!!selectedPortfolio});
  const documentInsights=useQuery({queryKey:['document-insights','investment_statement'],queryFn:()=>apiGet<DocInsight[]>('/api/v1/document-insights?document_type=investment_statement')});

  const addP=useMutation({mutationFn:()=>apiMutate('/api/v1/portfolios','POST',{name:pn,base_currency:'EUR'}),onSuccess:()=>qc.invalidateQueries({queryKey:['portfolios']})});
  const addS=useMutation({mutationFn:()=>apiMutate('/api/v1/securities','POST',{...sec,currency:'EUR',isin:null}),onSuccess:()=>qc.invalidateQueries({queryKey:['securities']})});
  const addT=useMutation({mutationFn:()=>apiMutate('/api/v1/trades','POST',{...trade,fx_rate:'1',currency:'EUR',executed_at:new Date(trade.executed_at).toISOString()}),onSuccess:()=>{qc.invalidateQueries({queryKey:['portfolios']});qc.invalidateQueries({queryKey:['portfolio-exposure']});qc.invalidateQueries({queryKey:['portfolio-performance']})}});
  const refresh=useMutation({mutationFn:(securityId:string)=>apiMutate('/api/v1/market/security/'+securityId+'/refresh?include_history=true','POST'),onSuccess:()=>{qc.invalidateQueries({queryKey:['portfolios']});qc.invalidateQueries({queryKey:['portfolio-exposure']});qc.invalidateQueries({queryKey:['portfolio-performance']})}});
  const broker=useMutation<ImportResult>({mutationFn:async()=>{if(!brokerFile||!selectedPortfolio)throw new Error('Selecciona cartera y CSV');const form=new FormData();form.append('file',brokerFile);return apiUpload<ImportResult>('/api/v1/portfolios/'+selectedPortfolio+'/imports/broker',form)},onSuccess:()=>{qc.invalidateQueries({queryKey:['portfolios']});qc.invalidateQueries({queryKey:['securities']});qc.invalidateQueries({queryKey:['portfolio-exposure']});qc.invalidateQueries({queryKey:['portfolio-performance']})}});
  const addAction=useMutation({mutationFn:()=>apiMutate('/api/v1/portfolios/'+selectedPortfolio+'/corporate-actions','POST',{portfolio_id:selectedPortfolio,...action,currency:'EUR',notes:action.notes||null}),onSuccess:()=>{setAction({...action,value:'',notes:''});qc.invalidateQueries({queryKey:['corporate-actions',selectedPortfolio]});qc.invalidateQueries({queryKey:['portfolios']});qc.invalidateQueries({queryKey:['portfolio-performance',selectedPortfolio]})}});

  return <>
    <PageHeader title="Inversiones" description="Carteras, FIFO, importación de broker, valoración, performance y concentración. Los indicadores de fit no son recomendaciones de inversión."/>
    <div className="grid gap-4 xl:grid-cols-3">
      <Card>
        <h2 className="font-bold">Cartera</h2>
        <form className="mt-3 flex gap-2" onSubmit={(e:FormEvent)=>{e.preventDefault();addP.mutate()}}>
          <label className="sr-only" htmlFor="portfolio-name">Nombre de cartera</label>
          <input id="portfolio-name" className="fin-input" value={pn} onChange={e=>setPn(e.target.value)}/>
          <button className="fin-button">Crear</button>
        </form>
      </Card>
      <Card>
        <h2 className="font-bold">Activo</h2>
        <form className="mt-3 space-y-2" onSubmit={(e:FormEvent)=>{e.preventDefault();addS.mutate()}}>
          <label className="sr-only" htmlFor="security-name">Nombre</label><input id="security-name" className="fin-input" placeholder="Nombre" value={sec.name} onChange={e=>setSec({...sec,name:e.target.value})}/>
          <label className="sr-only" htmlFor="security-symbol">Ticker</label><input id="security-symbol" className="fin-input" placeholder="Ticker" value={sec.symbol} onChange={e=>setSec({...sec,symbol:e.target.value})}/>
          <label className="sr-only" htmlFor="security-class">Clase</label><select id="security-class" className="fin-input" value={sec.asset_class} onChange={e=>setSec({...sec,asset_class:e.target.value})}><option value="stock">Acción</option><option value="etf">ETF</option><option value="fund">Fondo</option><option value="bond">Bono</option><option value="crypto">Cripto</option><option value="cash">Liquidez</option></select>
          <button className="fin-button w-full">Añadir</button>
        </form>
      </Card>
      <Card>
        <h2 className="font-bold">Operación</h2>
        <form className="mt-3 space-y-2" onSubmit={(e:FormEvent)=>{e.preventDefault();addT.mutate()}}>
          <label className="sr-only" htmlFor="trade-portfolio">Cartera</label><select id="trade-portfolio" className="fin-input" value={trade.portfolio_id} onChange={e=>setTrade({...trade,portfolio_id:e.target.value})}><option value="">Cartera…</option>{ps.data?.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select>
          <label className="sr-only" htmlFor="trade-security">Activo</label><select id="trade-security" className="fin-input" value={trade.security_id} onChange={e=>setTrade({...trade,security_id:e.target.value})}><option value="">Activo…</option>{ss.data?.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}</select>
          <div className="grid grid-cols-2 gap-2"><select aria-label="Tipo de operación" className="fin-input" value={trade.side} onChange={e=>setTrade({...trade,side:e.target.value})}><option value="buy">Compra</option><option value="sell">Venta</option></select><input aria-label="Cantidad" className="fin-input" placeholder="Cantidad" value={trade.quantity} onChange={e=>setTrade({...trade,quantity:e.target.value})}/></div>
          <input aria-label="Precio" className="fin-input" placeholder="Precio" value={trade.price} onChange={e=>setTrade({...trade,price:e.target.value})}/>
          <input aria-label="Fecha y hora" className="fin-input" type="datetime-local" value={trade.executed_at} onChange={e=>setTrade({...trade,executed_at:e.target.value})}/>
          <button className="fin-button w-full">Registrar</button>
        </form>
      </Card>
    </div>

    {(refresh.error||broker.error)&&<div className="mt-4"><ErrorState error={(refresh.error||broker.error)!}/></div>}

    <Card className="mt-4">
      <h2 className="font-bold">Importar CSV de broker</h2>
      <p className="mt-1 text-sm text-[var(--muted)]">Columnas reconocidas en ES/EN: fecha, compra/venta, ticker, cantidad, precio y opcionalmente nombre, clase, comisión, divisa y FX. La importación es idempotente y usa FIFO.</p>
      <div className="mt-3 grid gap-2 md:grid-cols-[1fr_1fr_auto]">
        <select aria-label="Cartera para importar" className="fin-input" value={selectedPortfolio} onChange={e=>setSelectedPortfolio(e.target.value)}><option value="">Cartera…</option>{ps.data?.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select>
        <input aria-label="CSV de broker" type="file" accept=".csv,text/csv" className="fin-input" onChange={e=>setBrokerFile(e.target.files?.[0]||null)}/>
        <button className="fin-button" disabled={!brokerFile||!selectedPortfolio||broker.isPending} onClick={()=>broker.mutate()}>Importar</button>
      </div>
      {broker.data&&<div className="mt-3 text-sm text-[var(--muted)]">{broker.data.inserted} operaciones nuevas · {broker.data.skipped} omitidas · {broker.data.created_securities} activos creados · P&L realizado importado <Money value={broker.data.realized_pnl}/></div>}
    </Card>

    <Card className="mt-4">
      <div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="font-bold">Conclusiones de documentos de inversión</h2><p className="mt-1 text-sm text-[var(--muted)]">La IA local señala comisiones, costes, riesgos y puntos de comparación visibles en extractos o contratos. No estima rentabilidades futuras.</p></div><a className="text-xs underline" href="/documents/">Añadir documentos</a></div>
      <div className="mt-4 grid gap-3 md:grid-cols-2">{documentInsights.data?.length?documentInsights.data.map(x=><div key={x.document_id} className="rounded-xl bg-[var(--surface-2)] p-3 text-sm"><div className="flex items-start justify-between gap-3"><strong>{x.file_name}</strong><a className="text-xs underline" href={'/documents/?document='+encodeURIComponent(x.document_id)}>Evidencia</a></div><p className="mt-2 text-xs">{x.analysis.summary}</p>{x.analysis.optimization_opportunities?.length>0&&<div className="mt-2 rounded-lg bg-[var(--brand-soft)] p-2 text-xs"><strong>Oportunidad:</strong> {x.analysis.optimization_opportunities.slice(0,2).map(i=>i.title||i.detail).join(' · ')}</div>}{x.analysis.comparison_requirements?.length>0&&<div className="mt-2 text-xs"><strong>Para comparar:</strong> {x.analysis.comparison_requirements.slice(0,2).map(i=>i.title||i.detail).join(' · ')}</div>}{x.analysis.risks?.length>0&&<div className="mt-2 text-xs"><strong>Riesgo/condición:</strong> {x.analysis.risks.slice(0,2).map(i=>i.title||i.detail).join(' · ')}</div>}</div>):<EmptyState>Añade extractos o contratos de inversión para analizarlos localmente.</EmptyState>}</div>
    </Card>

    <Card className="mt-4">
      <h2 className="font-bold">Dividendos y splits</h2>
      <p className="mt-1 text-sm text-[var(--muted)]">Para dividendos, el valor es el efectivo total recibido. Para splits, el valor es el ratio nuevas/antiguas (2 para 2:1, 0.5 para 1:2). Al guardar se reconstruyen FIFO y posiciones cronológicamente.</p>
      <form className="mt-3 grid gap-2 md:grid-cols-5" onSubmit={(e:FormEvent)=>{e.preventDefault();addAction.mutate()}}>
        <select aria-label="Cartera de corporate action" className="fin-input" value={selectedPortfolio} onChange={e=>setSelectedPortfolio(e.target.value)}><option value="">Cartera…</option>{ps.data?.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select>
        <select aria-label="Activo de corporate action" className="fin-input" value={action.security_id} onChange={e=>setAction({...action,security_id:e.target.value})}><option value="">Activo…</option>{ss.data?.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}</select>
        <select aria-label="Tipo de corporate action" className="fin-input" value={action.action_type} onChange={e=>setAction({...action,action_type:e.target.value})}><option value="dividend">Dividendo</option><option value="split">Split</option></select>
        <input aria-label="Fecha corporate action" type="date" className="fin-input" value={action.effective_date} onChange={e=>setAction({...action,effective_date:e.target.value})}/>
        <input aria-label={action.action_type==='split'?'Ratio split':'Efectivo recibido'} className="fin-input" value={action.value} onChange={e=>setAction({...action,value:e.target.value})} placeholder={action.action_type==='split'?'Ratio (2 = 2:1)':'Efectivo total'}/>
        <input aria-label="Notas corporate action" className="fin-input md:col-span-4" value={action.notes} onChange={e=>setAction({...action,notes:e.target.value})} placeholder="Notas / fuente"/>
        <button className="fin-button" disabled={!selectedPortfolio||!action.security_id||!action.value||addAction.isPending}>Guardar</button>
      </form>
      <div className="mt-3 space-y-2">{actions.data?.length?actions.data.map(a=>{const s=ss.data?.find(x=>x.id===a.security_id);return <div key={a.id} className="flex flex-wrap justify-between gap-2 rounded-xl bg-[var(--surface-2)] p-3 text-sm"><span><strong>{a.action_type==='split'?'Split':'Dividendo'}</strong> · {s?.name||a.security_id} · {a.effective_date}</span><span>{a.action_type==='split'?'ratio '+a.value:<Money value={a.value}/>} · {a.applied?'aplicado':'pendiente'}</span></div>}):<EmptyState>Sin dividendos o splits registrados para la cartera seleccionada.</EmptyState>}</div>
    </Card>

    <div className="mt-4 space-y-4">
      {ps.data?.length?ps.data.map(p=><Card key={p.id}>
        <div className="flex flex-wrap justify-between gap-3"><div><div className="font-bold">{p.name}</div><div className="text-sm text-[var(--muted)]">Coste <Money value={p.cost_basis}/> · P&L <Money value={p.unrealized_pnl}/></div></div><div className="text-xl font-bold"><Money value={p.market_value}/></div></div>
        <div className="mt-4 space-y-2">{p.positions.map(x=>{const s=ss.data?.find(s=>s.id===x.security_id);const ret=Number(x.average_cost)>0?(Number(x.price)-Number(x.average_cost))/Number(x.average_cost):null;return <div key={x.security_id} className="rounded-xl bg-[var(--surface-2)] p-3 text-sm"><div className="flex flex-wrap items-start justify-between gap-2"><div><strong>{s?.name||x.security_id}</strong>{s?.symbol&&<span className="text-[var(--muted)]"> · {s.symbol}</span>}<div className="mt-1 text-xs text-[var(--muted)]">{x.quantity} uds · compra media <Money value={x.average_cost}/> · actual <Money value={x.price}/></div></div><div className="text-right"><div className="font-semibold"><Money value={x.value}/></div><div className="text-xs text-[var(--muted)]">P&L <Money value={x.unrealized_pnl}/>{ret===null?'':' · '+(ret*100).toFixed(2)+'%'}</div></div></div>{s?.symbol&&<button className="mt-2 text-xs underline" onClick={()=>refresh.mutate(x.security_id)}>Actualizar precio real</button>}</div>})}</div>
        <button className="fin-button secondary mt-3" onClick={()=>setSelectedPortfolio(p.id)}>Analizar cartera</button>
        {selectedPortfolio===p.id&&<div className="mt-4 grid gap-4 xl:grid-cols-3">
          <div className="rounded-xl border border-[var(--border)] p-4">
            <div className="text-sm font-semibold">Concentración</div>
            {exposure.data?<><div className="mt-1 text-xs text-[var(--muted)]">Mayor posición {(Number(exposure.data.largest_position_weight)*100).toFixed(1)}% · HHI {Number(exposure.data.concentration_hhi).toFixed(3)}</div><div className="mt-3 space-y-1">{exposure.data.by_asset_class.map(x=><div key={x.asset_class} className="flex justify-between text-sm"><span>{x.asset_class}</span><span>{(Number(x.weight)*100).toFixed(1)}%</span></div>)}</div></>:<div className="mt-2 text-sm text-[var(--muted)]">Calculando…</div>}
          </div>
          <div className="rounded-xl border border-[var(--border)] p-4">
            <div className="text-sm font-semibold">Performance</div>
            {performance.data?<div className="mt-2 text-sm"><div>MWR anual: <strong>{performance.data.mwr===null?'n/d':(performance.data.mwr*100).toFixed(2)+'%'}</strong></div><div>TWR observado: <strong>{performance.data.twr===null?'n/d':(performance.data.twr*100).toFixed(2)+'%'}</strong></div><div>Cobertura de precios: <strong>{(performance.data.coverage*100).toFixed(0)}%</strong></div><div className="mt-2 text-xs text-[var(--muted)]">{performance.data.assumptions.join(' ')}</div></div>:<div className="mt-2 text-sm text-[var(--muted)]">Calculando…</div>}
          </div>
          <div className="rounded-xl border border-[var(--border)] p-4">
            <div className="text-sm font-semibold">Encaje de candidato</div>
            <div className="mt-2 space-y-2"><select aria-label="Activo candidato" className="fin-input" value={fitSecurity} onChange={e=>setFitSecurity(e.target.value)}><option value="">Activo…</option>{ss.data?.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}</select><input aria-label="Peso propuesto" className="fin-input" value={fitWeight} onChange={e=>setFitWeight(e.target.value)} placeholder="0.10"/></div>
            {fit.data&&<div className="mt-3 text-sm"><div>Fit estructural <strong>{Math.round(fit.data.fit_score*100)}/100</strong></div><div className="text-xs text-[var(--muted)]">Peso activo tras operación {(Number(fit.data.post_security_weight)*100).toFixed(1)}% · clase {(Number(fit.data.post_asset_class_weight)*100).toFixed(1)}%</div>{fit.data.warnings.map((w,i)=><div key={i} className="mt-1 text-xs">{w}</div>)}<div className="mt-2 text-xs text-[var(--muted)]">{fit.data.notice}</div></div>}
          </div>
        </div>}
      </Card>):<EmptyState>Crea una cartera para empezar.</EmptyState>}
    </div>
  </>
}
