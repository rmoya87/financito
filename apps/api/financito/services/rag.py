from __future__ import annotations
import json,re,math
from sqlalchemy import delete,select,text
from sqlalchemy.orm import Session
from ..models import Document
from ..models_extended import DocumentChunk
from .local_ai import embed

def chunks_for(text_value:str,max_chars:int=2600,overlap:int=300)->list[str]:
    paras=[p.strip() for p in re.split(r"\n\s*\n",text_value) if p.strip()]
    out=[];buf=""
    for p in paras:
        if buf and len(buf)+len(p)+2>max_chars:
            out.append(buf);buf=buf[-overlap:]+"\n\n"+p
        else:buf=(buf+"\n\n"+p).strip()
    if buf:out.append(buf)
    return out or ([text_value[:max_chars]] if text_value.strip() else [])

def _vec_table(dim:int)->str:
    if dim<1 or dim>10000:raise ValueError("Invalid vector dimension")
    return "document_chunk_vec_"+str(dim)

def _vec_insert(session:Session,chunk_id:str,vector:list[float])->None:
    table=_vec_table(len(vector))
    try:
        session.execute(text(f"CREATE VIRTUAL TABLE IF NOT EXISTS {table} USING vec0(chunk_id TEXT PRIMARY KEY, embedding float[{len(vector)}])"))
        session.execute(text(f"INSERT OR REPLACE INTO {table}(chunk_id,embedding) VALUES(:c,:e)"),{"c":chunk_id,"e":json.dumps(vector)})
    except Exception:
        # sqlite-vec is an acceleration path; embeddings remain persisted for portable fallback.
        pass

def index_document_chunks(session:Session,document:Document,pages:list[str]|None=None)->int:
    existing=session.scalars(select(DocumentChunk).where(DocumentChunk.document_id==document.id)).all()
    for old in existing:
        if old.embedding_json:
            try:
                dim=len(json.loads(old.embedding_json));session.execute(text(f"DELETE FROM {_vec_table(dim)} WHERE chunk_id=:c"),{"c":old.id})
            except Exception:pass
    if existing:
        session.execute(text("DELETE FROM document_chunk_fts WHERE document_id=:d"),{"d":document.id})
        session.execute(delete(DocumentChunk).where(DocumentChunk.document_id==document.id))
    units=list(enumerate(pages,1)) if pages else [(None,document.extracted_text)]
    prepared=[]
    for page_number,body in units:
        for part in chunks_for(body):prepared.append((page_number,part))
    texts=[body for _,body in prepared]
    vectors=None
    try:vectors=embed(texts) if texts else None
    except Exception:vectors=None
    for i,(page_number,body) in enumerate(prepared):
        vector=None if vectors is None else vectors[i]
        chunk=DocumentChunk(document_id=document.id,page_start=page_number,page_end=page_number,text=body,token_count=max(1,len(body.split())),chunk_index=i,embedding_model=None if vector is None else "ollama:"+str(len(vector)),embedding_version="v1" if vector else None,embedding_json=None if vector is None else json.dumps(vector))
        session.add(chunk);session.flush()
        session.execute(text("INSERT INTO document_chunk_fts(chunk_id,document_id,text,heading,section) VALUES(:c,:d,:t,'','')"),{"c":chunk.id,"d":document.id,"t":body})
        if vector is not None:_vec_insert(session,chunk.id,vector)
    return len(prepared)

def _cos(a:list[float],b:list[float])->float:
    if not a or not b or len(a)!=len(b):return 0.0
    dot=sum(x*y for x,y in zip(a,b));na=math.sqrt(sum(x*x for x in a));nb=math.sqrt(sum(y*y for y in b));return 0.0 if not na or not nb else dot/(na*nb)

def _vector_search(session:Session,query_vector:list[float],limit:int)->list[tuple[str,float]]:
    table=_vec_table(len(query_vector))
    try:
        rows=session.execute(text(f"SELECT chunk_id,distance FROM {table} WHERE embedding MATCH :e AND k=:k ORDER BY distance"),{"e":json.dumps(query_vector),"k":limit}).all()
        return [(r[0],1.0/(1.0+float(r[1]))) for r in rows]
    except Exception:
        candidates=session.scalars(select(DocumentChunk).where(DocumentChunk.embedding_json.is_not(None))).all()
        return sorted(((c.id,_cos(query_vector,json.loads(c.embedding_json or "[]"))) for c in candidates),key=lambda x:x[1],reverse=True)[:limit]

def search(session:Session,query:str,limit:int=8,*,use_vector:bool=True,vector_timeout:float=6)->list[dict]:
    tokens=re.findall(r"[\wáéíóúüñÁÉÍÓÚÜÑ]{2,}",query)
    match=" OR ".join('"'+t.replace('"','')+'"' for t in tokens) or '""'
    lexical=[]
    try:lexical=session.execute(text("SELECT chunk_id,bm25(document_chunk_fts) score FROM document_chunk_fts WHERE document_chunk_fts MATCH :q ORDER BY score LIMIT :n"),{"q":match,"n":limit*4}).all()
    except Exception:lexical=[]
    vector=[]
    # La búsqueda textual es inmediata y suficiente para coincidencias claras.
    # Solo consultamos Ollama cuando el llamador lo permite y faltan resultados
    # léxicos; así Buscar/Preguntar no quedan bloqueados por un embedding lento.
    if use_vector and len(lexical)<limit:
        try:vector=_vector_search(session,embed(query,timeout=vector_timeout)[0],limit*4)
        except Exception:vector=[]
    scores={}
    for rank,(cid,_) in enumerate(lexical):scores[cid]=scores.get(cid,0)+1/(60+rank+1)
    for rank,(cid,_) in enumerate(vector):scores[cid]=scores.get(cid,0)+1/(60+rank+1)
    candidate_ids=[cid for cid,_ in sorted(scores.items(),key=lambda x:x[1],reverse=True)[:limit*3]]
    if candidate_ids:
        rows=session.scalars(select(DocumentChunk).where(DocumentChunk.id.in_(candidate_ids))).all()
    else:
        rows=session.scalars(select(DocumentChunk).where(DocumentChunk.text.ilike("%"+query[:80]+"%")).limit(limit)).all()
    qtokens={x.lower() for x in tokens}
    def rerank(c:DocumentChunk)->float:
        ctokens=set(re.findall(r"\w+",c.text.lower()))
        overlap=len(qtokens&ctokens)/max(1,len(qtokens))
        return scores.get(c.id,0)+overlap*.03
    rows=sorted(rows,key=rerank,reverse=True)[:limit]
    docs={d.id:d for d in session.scalars(select(Document).where(Document.id.in_({c.document_id for c in rows}))).all()}
    return [{"chunk_id":c.id,"document_id":c.document_id,"document_name":docs[c.document_id].file_name if c.document_id in docs else "documento","page_start":c.page_start,"page_end":c.page_end,"text":c.text,"score":rerank(c)} for c in rows]
