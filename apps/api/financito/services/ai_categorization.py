from __future__ import annotations
import math
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..models import CategorizationAudit,Category,Transaction
from . import local_ai
from .categorization import KEYWORDS,categorize_transaction,ensure_categories,normalize_text

CATEGORY_HINTS={
    "income":"ingreso cobro intereses abono",
    "salary":"nómina salario sueldo payroll",
    "refunds":"devolución reembolso refund retrocesión",
    "housing":"hipoteca alquiler comunidad vivienda hogar muebles reparación",
    "groceries":"supermercado alimentación mercado compra doméstica",
    "restaurants":"restaurante bar cafetería comida a domicilio",
    "transport":"transporte público taxi tren metro autobús movilidad",
    "vehicle":"gasolina combustible coche parking peaje taller itv carga vehículo",
    "utilities":"electricidad gas agua energía suministros",
    "telecom":"teléfono internet fibra móvil telecomunicaciones",
    "insurance":"seguro póliza prima aseguradora",
    "health":"farmacia médico hospital clínica dentista fisioterapia salud",
    "personal_care":"peluquería barbería estética perfumería cuidado personal",
    "education":"colegio academia universidad libros educación material escolar",
    "family":"guardería juguetes pañales hijos familia",
    "pets":"veterinario mascota pienso perro gato",
    "sports":"gimnasio deporte crossfit pádel fútbol natación",
    "leisure":"cine teatro entradas ocio videojuegos entretenimiento",
    "technology":"tecnología electrónica ordenador móvil hardware",
    "shopping":"compras tienda ropa comercio",
    "subscriptions":"suscripción cuota recurrente streaming software",
    "travel":"hotel vuelo viaje alojamiento aerolínea",
    "taxes":"impuesto tasa hacienda ayuntamiento tributo ibi",
    "bank_fees":"comisión bancaria mantenimiento tarjeta fee",
    "debt":"préstamo crédito financiación cuota deuda",
    "donations":"donación donativo ONG solidaridad",
    "investments":"broker inversión fondo acciones valores",
    "savings":"ahorro aportación plan ahorro",
    "transfers":"transferencia traspaso bizum entre cuentas",
}

def _tx_text(tx:Transaction)->str:
    return normalize_text(f"{'ingreso' if tx.amount>0 else 'gasto'}. comercio {tx.merchant_raw or ''}. concepto {tx.description_raw}")

def _cos(a:list[float],b:list[float])->float:
    if not a or not b or len(a)!=len(b):return -1.0
    dot=sum(x*y for x,y in zip(a,b));na=math.sqrt(sum(x*x for x in a));nb=math.sqrt(sum(y*y for y in b))
    return -1.0 if not na or not nb else dot/(na*nb)

def _embed_batched(texts:list[str],size:int=128)->list[list[float]]:
    out=[]
    for i in range(0,len(texts),size):out.extend(local_ai.embed(texts[i:i+size]))
    return out

def _prototype_texts(session:Session,categories:dict[str,Category])->tuple[list[str],list[str]]:
    keyword_map={key:" ".join(words) for key,words in KEYWORDS}
    examples=session.scalars(select(Transaction).where(Transaction.user_verified.is_(True),Transaction.category_id.is_not(None)).order_by(Transaction.updated_at.desc()).limit(1000)).all()
    by_category={};id_to_key={c.id:k for k,c in categories.items()}
    for tx in examples:
        key=id_to_key.get(tx.category_id or "")
        if key and len(by_category.setdefault(key,[]))<12:by_category[key].append(_tx_text(tx))
    keys=[];texts=[]
    for key,category in categories.items():
        if key=="other":continue
        texts.append(normalize_text(f"Categoría {category.name}. {CATEGORY_HINTS.get(key,'')} {keyword_map.get(key,'')} Ejemplos confirmados: {' | '.join(by_category.get(key,[]))}"));keys.append(key)
    return keys,texts

def _record_change(session:Session,tx:Transaction,previous:str|None,method:str,confidence:Decimal)->None:
    if previous==tx.category_id:return
    session.add(CategorizationAudit(transaction_id=tx.id,previous_category_id=previous,new_category_id=tx.category_id,method=method,confidence=confidence,changed_by="local_ai"))

def _apply_embedding(session:Session,targets:list[Transaction],categories:dict[str,Category])->tuple[int,list[Transaction],str|None]:
    if not targets:return 0,[],None
    keys,prototypes=_prototype_texts(session,categories)
    try:vectors=_embed_batched(prototypes+[_tx_text(tx) for tx in targets])
    except Exception as exc:return 0,targets,str(exc)
    pvec=vectors[:len(keys)];tvec=vectors[len(keys):];applied=0;unresolved=[]
    for tx,vector in zip(targets,tvec):
        scores=sorted(((key,_cos(vector,pv)) for key,pv in zip(keys,pvec)),key=lambda x:x[1],reverse=True)
        if not scores:unresolved.append(tx);continue
        best_key,best=scores[0];second=scores[1][1] if len(scores)>1 else -1.0;margin=best-second
        if best<0.60 or margin<0.045:unresolved.append(tx);continue
        previous=tx.category_id;tx.category_id=categories[best_key].id
        confidence=Decimal(str(min(.89,max(.72,.72+(best-.60)*.35+margin*.40)))).quantize(Decimal("0.0001"))
        tx.categorization_method="ai_embedding";tx.categorization_confidence=confidence;_record_change(session,tx,previous,"ai_embedding",confidence);applied+=1
    session.flush();return applied,unresolved,None

def _apply_llm(session:Session,targets:list[Transaction],categories:dict[str,Category],limit:int)->tuple[int,list[Transaction],str|None]:
    selected=targets[:max(0,limit)];untouched=targets[len(selected):]
    if not selected:return 0,targets,None
    category_lines=", ".join(f"{key}={cat.name}" for key,cat in categories.items());applied=0;failed=set()
    for i in range(0,len(selected),35):
        batch=selected[i:i+35]
        payload=[{"id":tx.id,"amount":str(tx.amount),"currency":tx.currency,"merchant":tx.merchant_raw,"description":tx.description_raw} for tx in batch]
        prompt=("Clasifica movimientos bancarios personales. Devuelve SOLO JSON con la forma "
                '{"items":[{"id":"...","category":"system_key","confidence":0.0,"reason":"breve"}]}. '
                "No inventes categorías. Si no hay evidencia suficiente usa category=other y confidence<=0.60. "
                "Una devolución puede pertenecer a la categoría del gasto original y no necesariamente a ingresos. "
                f"Categorías válidas: {category_lines}. Movimientos: {payload}")
        try:data=local_ai.generate_json(prompt,timeout=240)
        except Exception as exc:return applied,targets,str(exc)
        by_id={str(x.get("id")):x for x in data.get("items",[]) if isinstance(x,dict)}
        for tx in batch:
            item=by_id.get(tx.id)
            if not item:failed.add(tx.id);continue
            key=str(item.get("category",""))
            try:raw=float(item.get("confidence",0))
            except Exception:raw=0
            if key not in categories or key=="other" or raw<.72:failed.add(tx.id);continue
            previous=tx.category_id;tx.category_id=categories[key].id
            confidence=Decimal(str(min(.86,max(.72,raw)))).quantize(Decimal("0.0001"))
            tx.categorization_method="ai_llm";tx.categorization_confidence=confidence;_record_change(session,tx,previous,"ai_llm",confidence);applied+=1
    session.flush();return applied,[tx for tx in selected if tx.id in failed]+untouched,None

def improve_categorization(session:Session,limit:int=3000,llm_limit:int=80)->dict:
    categories=ensure_categories(session)
    rows=session.scalars(select(Transaction).where(Transaction.user_verified.is_(False),Transaction.categorization_confidence<Decimal("0.70")).order_by(Transaction.booking_date.desc(),Transaction.created_at.desc()).limit(max(1,min(limit,10000)))).all()
    learned=0;still=[]
    for tx in rows:
        before=tx.categorization_method;categorize_transaction(session,tx)
        if tx.categorization_method=="learned_merchant" and before!="learned_merchant":learned+=1
        if tx.categorization_confidence<Decimal("0.70"):still.append(tx)
    ai=local_ai.status();emb=llm=0;emb_err=llm_err=None
    if still and ai.get("available") and ai.get("embedding_ready"):emb,still,emb_err=_apply_embedding(session,still,categories)
    if still and ai.get("available") and ai.get("chat_ready"):llm,still,llm_err=_apply_llm(session,still,categories,llm_limit)
    return {"considered":len(rows),"learned_merchant":learned,"embedding":emb,"llm":llm,"unresolved":len(still),"ai":{"available":bool(ai.get("available")),"chat_model":ai.get("configured_model"),"chat_ready":bool(ai.get("chat_ready")),"embedding_model":ai.get("embedding_model"),"embedding_ready":bool(ai.get("embedding_ready"))},"warnings":[x for x in [None if ai.get("available") else "Ollama no está disponible.",None if ai.get("embedding_ready") else "El modelo de embeddings configurado no está instalado/disponible.",None if ai.get("chat_ready") else "El modelo de chat configurado no está instalado/disponible.",f"Embeddings: {emb_err}" if emb_err else None,f"LLM: {llm_err}" if llm_err else None] if x]}
