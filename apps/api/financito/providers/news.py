from __future__ import annotations
import httpx
class GdeltNewsProvider:
    BASE="https://api.gdeltproject.org/api/v2/doc/doc"
    def search(self,query:str,limit:int=20)->list[dict]:
        with httpx.Client(timeout=20) as c:r=c.get(self.BASE,params={"query":query,"mode":"ArtList","maxrecords":min(limit,50),"format":"json","sort":"HybridRel"});r.raise_for_status();data=r.json()
        return [{"title":a.get("title"),"url":a.get("url"),"source":a.get("domain"),"published_at":a.get("seendate"),"language":a.get("language")} for a in data.get("articles",[])]
