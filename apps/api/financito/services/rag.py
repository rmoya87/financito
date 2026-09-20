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

def index_document_chunks(session:Session,document:Document)->int:
    ids=session.scalars(select(DocumentChunk.id).where(DocumentChunk.document_id==document.id)).all()
    if ids: session.execute(text("DELETE FROM document_chunk_fts WHERE document_id=:d"),{"d":document.id});session.execute(delete(DocumentChunk).where(DocumentChunk.document_id==document.id))
    texts=chunks_for(document.extracted_text);vectors=None
    try:vectors=embed(texts) if texts else None
    except Exception:vectors=None
    for i,body in enumerate(texts):
        chunk=DocumentChunk(document_id=document.id,page_start=None,page_end=None,text=body,token_count=max(1,len(body.split())),chunk_index=i,embedding_model=None if vectors is None else "ollama-local",embedding_version="v1" if vectors else None,embedding_json=None if vectors is None else json.dumps(vectors[i]))
        session.add(chunk);session.flush()
        session.execute(text("INSERT INTO document_chunk_fts(chunk_id,document_id,text,heading,section) VALUES(:c,:d,:t,'','')"),{"c":chunk.id,"d":document.id,"t":body})
    return len(texts)

def _cos(a:list[float],b:list[float])->float:
    if not a or not b or len(a)!=len(b):return 0.0
    dot=sum(x*y for x,y in zip(a,b));na=math.sqrt(sum(x*x for x in a));nb=math.sqrt(sum(y*y for y in b));return 0.0 if not na or not nb else dot/(na*nb)

def search(session:Session,query:str,limit:int=8)->list[dict]:
    tokens=re.findall(r"[\wáéíóúüñÁÉÍÓÚÜÑ]{2,}",query)
    match=" OR ".join('"'+t.replace('"','')+'"' for t in tokens) or '""'
    lexical=[]
    try:
        lexical=session.execute(text("SELECT chunk_id, bm25(document_chunk_fts) score FROM document_chunk_fts WHERE document_chunk_fts MATCH :q ORDER BY score LIMIT :n"),{"q":match,"n":limit*3}).all()
    except Exception:lexical=[]
    vector=[]
    try:
        qv=embed(query)[0]
        candidates=session.scalars(select(DocumentChunk).where(DocumentChunk.embedding_json.is_not(None))).all()
        vector=sorted(((c.id,_cos(qv,json.loads(c.embedding_json or "[]"))) for c in candidates),key=lambda x:x[1],reverse=True)[:limit*3]
    except Exception:vector=[]
    scores={}
    for rank,(cid,_) in enumerate(lexical):scores[cid]=scores.get(cid,0)+1/(60+rank+1)
    for rank,(cid,_) in enumerate(vector):scores[cid]=scores.get(cid,0)+1/(60+rank+1)
    if not scores:
        rows=session.scalars(select(DocumentChunk).where(DocumentChunk.text.ilike(f"%{query[:80]}%")).limit(limit)).all()
    else:
        chosen=[cid for cid,_ in sorted(scores.items(),key=lambda x:x[1],reverse=True)[:limit]]
        rows=session.scalars(select(DocumentChunk).where(DocumentChunk.id.in_(chosen))).all();rows.sort(key=lambda c:chosen.index(c.id))
    docs={d.id:d for d in session.scalars(select(Document).where(Document.id.in_({c.document_id for c in rows}))).all()}
    return [{"chunk_id":c.id,"document_id":c.document_id,"document_name":docs[c.document_id].file_name if c.document_id in docs else "documento","page_start":c.page_start,"page_end":c.page_end,"text":c.text,"score":scores.get(c.id,0)} for c in rows]
