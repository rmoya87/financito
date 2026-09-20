from __future__ import annotations

from collections import defaultdict
from threading import Lock

_lock=Lock()
_stats=defaultdict(lambda:{"count":0,"errors":0,"total_ms":0.0,"max_ms":0.0,"last_ms":0.0})

def record(method:str,path:str,status:int,duration_ms:float)->None:
    key=f"{method.upper()} {path}"
    with _lock:
        row=_stats[key]
        row["count"]+=1
        if status>=400:row["errors"]+=1
        row["total_ms"]+=duration_ms
        row["max_ms"]=max(row["max_ms"],duration_ms)
        row["last_ms"]=duration_ms

def snapshot(limit:int=50)->list[dict]:
    with _lock:
        rows=[]
        for key,row in _stats.items():
            count=max(1,int(row["count"]))
            rows.append({
                "route":key,
                "count":int(row["count"]),
                "errors":int(row["errors"]),
                "avg_ms":round(float(row["total_ms"])/count,2),
                "max_ms":round(float(row["max_ms"]),2),
                "last_ms":round(float(row["last_ms"]),2),
            })
    return sorted(rows,key=lambda x:(x["avg_ms"],x["count"]),reverse=True)[:max(1,min(limit,200))]
