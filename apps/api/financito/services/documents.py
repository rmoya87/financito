from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import json
import mimetypes
import re

from docx import Document as DocxDocument
from openpyxl import load_workbook
from pypdf import PdfReader
from PIL import Image
from pillow_heif import register_heif_opener
import pytesseract
from sqlalchemy import delete,select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Document,ExtractedFact

register_heif_opener()
Image.MAX_IMAGE_PIXELS=50_000_000
MAX_DOCUMENT_BYTES=50*1024*1024
MAX_PDF_PAGES=500
SUPPORTED_SUFFIXES={".pdf",".png",".jpg",".jpeg",".heic",".tiff",".bmp",".docx",".xlsx",".xlsm",".csv",".txt",".json"}

@dataclass(frozen=True)
class IndexedDocument:
    document:Document
    facts_created:int
    chunks_created:int

def store_uploaded_document(filename:str,content:bytes)->Path:
    if len(content)>MAX_DOCUMENT_BYTES:
        raise ValueError("File too large")
    original=Path(filename or "documento").name
    suffix=Path(original).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError(f"Unsupported document type: {suffix or 'sin extensión'}")
    stem=re.sub(r"[^A-Za-z0-9._ -]+","_",Path(original).stem).strip(" ._") or "documento"
    upload_dir=settings.vault_dir/"uploads"
    upload_dir.mkdir(parents=True,exist_ok=True)
    candidate=upload_dir/(stem+suffix)
    counter=2
    while candidate.exists():
        candidate=upload_dir/(f"{stem} ({counter}){suffix}")
        counter+=1
    candidate.write_bytes(content)
    return candidate


def safe_path(path:Path)->Path:
    expanded=path.expanduser()
    if expanded.is_symlink():raise ValueError("Symlink documents are not accepted")
    resolved=expanded.resolve(strict=True);vault=settings.vault_dir.resolve()
    if resolved!=vault and vault not in resolved.parents:raise ValueError("Document is outside configured vault")
    if not resolved.is_file():raise ValueError("Document path is not a file")
    if resolved.stat().st_size>MAX_DOCUMENT_BYTES:raise ValueError("Document exceeds the 50 MB local ingestion limit")
    return resolved

def extract_content(path:Path)->tuple[str,int,list[str]|None]:
    suffix=path.suffix.lower()
    if suffix==".pdf":
        reader=PdfReader(str(path))
        if len(reader.pages)>MAX_PDF_PAGES:raise ValueError("PDF exceeds the 500 page ingestion limit")
        pages=[(page.extract_text() or "") for page in reader.pages]
        return "\n\n".join(pages),len(pages),pages
    if suffix in {".txt",".csv",".json"}:return path.read_text(encoding="utf-8",errors="replace"),1,None
    if suffix==".docx":
        doc=DocxDocument(str(path));return "\n".join(p.text for p in doc.paragraphs),1,None
    if suffix in {".xlsx",".xlsm"}:
        wb=load_workbook(path,read_only=True,data_only=True);lines=[]
        for ws in wb.worksheets:
            lines.append(f"[{ws.title}]")
            for row in ws.iter_rows(values_only=True):lines.append(" | ".join("" if v is None else str(v) for v in row))
        return "\n".join(lines),1,None
    if suffix in {".png",".jpg",".jpeg",".heic",".tiff",".bmp"}:
        image=Image.open(path);image.verify();image=Image.open(path)
        return pytesseract.image_to_string(image,lang="spa+eng"),1,None
    raise ValueError(f"Unsupported document type: {suffix}")

def detect_language(text:str)->tuple[str,float]:
    sample=(" "+re.sub(r"\s+"," ",text[:50000].lower())+" ")
    es=sum(sample.count(" "+w+" ") for w in ("de","la","el","y","en","para","con","del","una","por"))
    en=sum(sample.count(" "+w+" ") for w in ("the","and","of","to","in","for","with","from","is","a"))
    if es==0 and en==0:return "unknown",0.3
    if es>=en:return "es",min(.98,.60+(es-en+1)/max(10,es+en))
    return "en",min(.98,.60+(en-es+1)/max(10,es+en))

def classify_document(text:str,file_name:str)->tuple[str,float]:
    sample=(file_name+" "+text[:100000]).lower()
    strong_signals=[
        ("mortgage",("préstamo hipotecario","prestamo hipotecario","hipoteca","fein","fiae","fia e")),
        ("insurance",("condiciones particulares de la póliza","condiciones particulares de la poliza","póliza de seguro","poliza de seguro")),
        ("bank_statement",("extracto bancario","saldo contable","fecha valor")),
        ("investment_statement",("cartera de valores","valor liquidativo","participaciones","isin")),
        ("tax",("agencia tributaria","modelo 100","declaración de la renta","declaracion de la renta")),
        ("energy",("punto de suministro","potencia contratada","término de energía","termino de energia")),
        ("telecom",("fibra","línea móvil","linea movil","datos móviles","datos moviles")),
        ("loan",("préstamo personal","prestamo personal")),
    ]
    for kind,signals in strong_signals:
        hits=sum(1 for signal in signals if signal in sample)
        if hits:
            return kind,min(.98,.82+.04*min(hits,4))
    groups=[
        ("mortgage",("fein","fia e","fiae","hipoteca","préstamo hipotecario","prestamo hipotecario","euribor","amortización anticipada")),
        ("insurance",("póliza","poliza","asegurado","cobertura","siniestro","franquicia","prima anual")),
        ("bank_statement",("extracto","saldo disponible","saldo contable","fecha valor","movimientos","iban")),
        ("investment_statement",("isin","cartera de valores","valor liquidativo","participaciones","dividendo","plusvalía","plusvalia")),
        ("tax",("agencia tributaria","irpf","modelo 100","declaración de la renta","declaracion de la renta")),
        ("energy",("kwh","potencia contratada","punto de suministro","peaje de acceso","término de energía")),
        ("telecom",("fibra","línea móvil","linea movil","datos móviles","permanencia","gb")),
        ("loan",("préstamo personal","prestamo personal","tin","tae","cuota mensual","cuadro de amortización")),
        ("contract",("contrato","condiciones particulares","renovación","renovacion","preaviso")),
    ]
    best=("unknown",0)
    for kind,keywords in groups:
        hits=sum(1 for k in keywords if k in sample)
        if hits>best[1]:best=(kind,hits)
    if best[1]==0:return "unknown",.35
    return best[0],min(.97,.58+.10*best[1])

def _context(text:str,start:int,end:int)->str:
    left=max(0,start-80);right=min(len(text),end+120)
    return re.sub(r"\s+"," ",text[left:right]).strip()[:255]

def _normalize_number(raw:str)->str:
    value=str(raw).strip().replace(" ","")
    if "," in value and "." in value:
        if value.rfind(",")>value.rfind("."):
            return value.replace(".","").replace(",",".")
        return value.replace(",","")
    if "," in value:
        return value.replace(",",".")
    if value.count(".")>1:
        return value.replace(".","")
    return value

def extract_contract_facts(text:str,source_page:int|None=None)->list[dict]:
    facts=[]
    patterns=[
        ("cancellation_notice_days",r"(?:preaviso|antelaci[oó]n|comunicar(?:lo)?\s+con)\D{0,80}(\d{1,3})\s*d[ií]as","days",.78),
        ("early_exit_penalty",r"(?:penalizaci[oó]n|comisi[oó]n(?:\s+por\s+(?:cancelaci[oó]n|subrogaci[oó]n|amortizaci[oó]n))?|compensaci[oó]n por reembolso|coste de cancelaci[oó]n)\D{0,120}(\d+[\.,]?\d*)\s*(?:€|euros?)","EUR",.78),
        ("annual_cost",r"(?:prima anual|coste anual|cuota anual)\D{0,70}(\d+[\.,]?\d*)\s*(?:€|euros?)","EUR",.76),
        ("monthly_cost",r"(?:cuota mensual|mensualidad)\D{0,70}(\d+[\.,]?\d*)\s*(?:€|euros?)","EUR",.72),
        ("deductible",r"(?:franquicia)\D{0,60}(\d+[\.,]?\d*)\s*(?:€|euros?)","EUR",.78),
        ("nominal_rate",r"(?:\bTIN\b|tipo nominal)\D{0,60}(\d+[\.,]?\d*)\s*%","percent",.76),
        ("apr_rate",r"(?:\bTAE\b)\D{0,60}(\d+[\.,]?\d*)\s*%","percent",.78),
        ("remaining_principal",r"(?:capital\s+pendiente|saldo\s+pendiente|principal\s+pendiente)\D{0,80}(\d{1,3}(?:[\.\s]\d{3})*(?:,\d{1,2})?|\d+(?:[\.,]\d+)?)\s*(?:€|euros?)","EUR",.84),
        ("monthly_payment",r"(?:cuota\s+(?:mensual|actual)|mensualidad)\D{0,80}(\d{1,3}(?:[\.\s]\d{3})*(?:,\d{1,2})?|\d+(?:[\.,]\d+)?)\s*(?:€|euros?)","EUR",.82),
        ("remaining_months",r"(?:plazo\s+pendiente|meses\s+pendientes|quedan)\D{0,60}(\d{1,4})\s*meses","months",.84),
    ]
    lowered=text.lower()
    for key,pattern,unit,confidence in patterns:
        for match in re.finditer(pattern,lowered,re.I):
            raw=_normalize_number(match.group(1))
            facts.append({"fact_type":"contract_term","key":key,"value":raw,"unit":unit,"confidence":confidence,"source_page":source_page,"source_section":_context(text,match.start(),match.end())})
    semantic_patterns=[
        ("reference_index",r"\b(eur[ií]bor(?:\s+a\s+\d+\s+meses?)?|irph)\b","text",.82),
        ("interest_type",r"\b(tipo\s+fijo|tipo\s+variable|tipo\s+mixto|inter[eé]s\s+fijo|inter[eé]s\s+variable|inter[eé]s\s+mixto)\b","text",.72),
    ]
    for key,pattern,unit,confidence in semantic_patterns:
        for match in re.finditer(pattern,lowered,re.I):
            value=re.sub(r"\s+"," ",match.group(1)).strip()
            facts.append({"fact_type":"mortgage_term","key":key,"value":value,"unit":unit,"confidence":confidence,"source_page":source_page,"source_section":_context(text,match.start(),match.end())})

    mortgage_number_patterns=[
        ("differential_rate",r"(?:diferencial(?:\s+(?:del|de))?|m[aá]s\s+diferencial(?:\s+(?:del|de))?)\D{0,30}(\d+[\.,]?\d*)\s*%","percent",.80),
        ("mortgage_term_years",r"(?:plazo(?:\s+(?:de|total\s+de))?)\D{0,25}(\d{1,3})\s*a[nñ]os","years",.82),
        ("rate_review_months",r"(?:revisi[oó]n(?:\s+del\s+tipo)?(?:\s+cada)?)\D{0,25}(\d{1,3})\s*meses","months",.78),
        ("opening_fee_percent",r"(?:comisi[oó]n\s+de\s+apertura)\D{0,45}(\d+[\.,]?\d*)\s*%","percent",.84),
        ("early_repayment_fee_percent",r"(?:compensaci[oó]n\s+por\s+reembolso\s+anticipado|comisi[oó]n\s+por\s+(?:amortizaci[oó]n|reembolso)\s+anticipad[oa])\D{0,90}(\d+[\.,]?\d*)\s*%","percent",.84),
        ("subrogation_fee_percent",r"(?:comisi[oó]n|compensaci[oó]n)\s+(?:por\s+)?subrogaci[oó]n\D{0,90}(\d+[\.,]?\d*)\s*%","percent",.86),
        ("cancellation_fee_percent",r"(?:comisi[oó]n|penalizaci[oó]n|compensaci[oó]n)\s+(?:por\s+)?cancelaci[oó]n\D{0,90}(\d+[\.,]?\d*)\s*%","percent",.82),
    ]
    for key,pattern,unit,confidence in mortgage_number_patterns:
        for match in re.finditer(pattern,lowered,re.I):
            raw=_normalize_number(match.group(1))
            facts.append({"fact_type":"mortgage_term","key":key,"value":raw,"unit":unit,"confidence":confidence,"source_page":source_page,"source_section":_context(text,match.start(),match.end())})
    linked_patterns=[
        ("linked_salary",r"(?:domiciliaci[oó]n de n[oó]mina|n[oó]mina domiciliada)"),
        ("linked_home_insurance",r"(?:seguro de hogar|seguro hogar)"),
        ("linked_life_insurance",r"(?:seguro de vida|seguro vida)"),
        ("linked_card",r"(?:tarjeta de cr[eé]dito|tarjeta de d[eé]bito|uso de tarjeta)"),
        ("linked_pension_plan",r"(?:plan de pensiones|plan de previsi[oó]n)"),
    ]
    linked_rate_patterns=[
        ("linked_home_insurance_rate_penalty_pp",[
            r"(?:seguro de hogar|seguro hogar).{0,180}?(?:se a[nñ]ade|aumenta|incrementa|margen adicional|pierde(?:s)? (?:una )?bonificaci[oó]n de)\D{0,40}(\d+[\.,]?\d*)\s*%",
            r"(\d+[\.,]?\d*)\s*%\D{0,80}(?:por|sin|al no (?:tener|renovar)|bonificaci[oó]n).{0,80}(?:seguro de hogar|seguro hogar)",
        ]),
        ("linked_life_insurance_rate_penalty_pp",[
            r"(?:seguro de vida|seguro vida).{0,180}?(?:se a[nñ]ade|aumenta|incrementa|margen adicional|pierde(?:s)? (?:una )?bonificaci[oó]n de)\D{0,40}(\d+[\.,]?\d*)\s*%",
            r"(\d+[\.,]?\d*)\s*%\D{0,80}(?:por|sin|al no (?:tener|renovar)|bonificaci[oó]n).{0,80}(?:seguro de vida|seguro vida)",
        ]),
        ("linked_salary_rate_penalty_pp",[
            r"(?:n[oó]mina|domiciliaci[oó]n de n[oó]mina).{0,180}?(?:se a[nñ]ade|aumenta|incrementa|margen adicional|pierde(?:s)? (?:una )?bonificaci[oó]n de)\D{0,40}(\d+[\.,]?\d*)\s*%",
            r"(\d+[\.,]?\d*)\s*%\D{0,80}(?:por|sin|al no (?:tener|domiciliar)|bonificaci[oó]n).{0,80}(?:n[oó]mina|domiciliaci[oó]n de n[oó]mina)",
        ]),
    ]
    for key,pattern in linked_patterns:
        match=re.search(pattern,lowered,re.I)
        if match:
            facts.append({"fact_type":"linked_product","key":key,"value":"mentioned","unit":"boolean_signal","confidence":.62,"source_page":source_page,"source_section":_context(text,match.start(),match.end())})
    for key,patterns in linked_rate_patterns:
        for pattern in patterns:
            match=re.search(pattern,lowered,re.I)
            if match:
                facts.append({"fact_type":"linked_product","key":key,"value":match.group(1).replace(",","."),"unit":"percentage_points","confidence":.82,"source_page":source_page,"source_section":_context(text,match.start(),match.end())})
                break
    for key,pattern in [
        ("permanence_end_date",r"(?:fin de )?permanencia.{0,100}?(\d{1,2}[/-]\d{1,2}[/-]\d{4})"),
        ("renewal_date",r"renovaci[oó]n.{0,100}?(\d{1,2}[/-]\d{1,2}[/-]\d{4})"),
    ]:
        for match in re.finditer(pattern,lowered,re.I):
            facts.append({"fact_type":"contract_term","key":key,"value":match.group(1),"unit":"date","confidence":.70,"source_page":source_page,"source_section":_context(text,match.start(),match.end())})
    return facts

def _derive_facts(session:Session,doc:Document,text_value:str,pages:list[str]|None)->int:
    session.execute(delete(ExtractedFact).where(ExtractedFact.document_id==doc.id,ExtractedFact.user_verified.is_(False)))
    verified_keys={(r.key,r.source_page) for r in session.scalars(select(ExtractedFact).where(ExtractedFact.document_id==doc.id,ExtractedFact.user_verified.is_(True))).all()}
    lang,lang_conf=detect_language(text_value)
    if ("language",1) not in verified_keys:
        session.add(ExtractedFact(document_id=doc.id,fact_type="document_metadata",key="language",value_json=json.dumps({"value":lang},ensure_ascii=False),confidence=str(lang_conf),status="inferred",source_page=1,user_verified=False))
    count=0
    units=list(enumerate(pages,1)) if pages else [(1,text_value)]
    for page_number,body in units:
        for fact in extract_contract_facts(body,page_number):
            if (fact["key"],fact["source_page"]) in verified_keys:
                continue
            session.add(ExtractedFact(document_id=doc.id,fact_type=fact["fact_type"],key=fact["key"],value_json=json.dumps({"value":fact["value"],"unit":fact["unit"]},ensure_ascii=False),confidence=str(fact["confidence"]),status="inferred",source_page=fact["source_page"],source_section=fact["source_section"],user_verified=False));count+=1
    return count


def reprocess_document(session:Session,doc:Document)->IndexedDocument:
    path=safe_path(Path(doc.file_path));text_value,page_count,pages=extract_content(path)
    doc.extracted_text=text_value;doc.page_count=page_count;doc.sha256=sha256(path.read_bytes()).hexdigest();doc.status="indexed"
    kind,_=classify_document(text_value,path.name)
    if doc.document_type in {"unknown","contract"} or kind!="unknown":doc.document_type=kind
    count=_derive_facts(session,doc,text_value,pages)
    from .rag import index_document_chunks
    from .evidence import synchronize_document_evidence
    chunks=index_document_chunks(session,doc,pages)
    synchronize_document_evidence(session,doc)
    session.flush();return IndexedDocument(doc,count,chunks)

def index_document(session:Session,source_path:str,document_type:str="unknown")->IndexedDocument:
    path=safe_path(Path(source_path));digest=sha256(path.read_bytes()).hexdigest()
    existing=session.scalar(select(Document).where(Document.sha256==digest))
    if existing:return reprocess_document(session,existing)
    text_value,page_count,pages=extract_content(path)
    auto_type,type_conf=classify_document(text_value,path.name)
    final_type=auto_type if document_type in {"","unknown","contract"} else document_type
    doc=Document(file_path=str(path),file_name=path.name,mime_type=mimetypes.guess_type(path.name)[0],sha256=digest,document_type=final_type,status="indexed",page_count=page_count,extracted_text=text_value)
    session.add(doc);session.flush()
    count=_derive_facts(session,doc,text_value,pages)
    session.add(ExtractedFact(document_id=doc.id,fact_type="document_metadata",key="document_type_confidence",value_json=json.dumps({"value":str(type_conf)},ensure_ascii=False),confidence=str(type_conf),status="inferred",source_page=1,user_verified=False))
    from .rag import index_document_chunks
    from .evidence import synchronize_document_evidence
    chunks=index_document_chunks(session,doc,pages)
    synchronize_document_evidence(session,doc)
    return IndexedDocument(doc,count,chunks)
