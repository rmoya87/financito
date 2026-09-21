from __future__ import annotations

import time
import httpx


class GdeltNewsProvider:
    BASE="https://api.gdeltproject.org/api/v2/doc/doc"
    CACHE_SECONDS=600
    _cache:dict[str,tuple[float,list[dict]]]={}

    def search(self,query:str,limit:int=20)->list[dict]:
        normalized=" ".join(query.split()).strip()
        key=normalized.lower()+"|"+str(min(limit,50))
        now=time.monotonic()
        cached=self._cache.get(key)
        if cached and now-cached[0]<self.CACHE_SECONDS:
            return cached[1]

        params={"query":normalized,"mode":"ArtList","maxrecords":min(limit,50),"format":"json","sort":"HybridRel"}
        last_error:Exception|None=None
        for attempt in range(2):
            try:
                with httpx.Client(timeout=20,headers={"User-Agent":"Financito/0.3 local-personal-finance"}) as client:
                    response=client.get(self.BASE,params=params)
                if response.status_code==429:
                    last_error=RuntimeError("La fuente de noticias está limitando temporalmente las consultas.")
                    if attempt==0:
                        retry_after=response.headers.get("Retry-After")
                        try:delay=min(2.0,max(0.5,float(retry_after))) if retry_after else 1.0
                        except ValueError:delay=1.0
                        time.sleep(delay)
                        continue
                    break
                response.raise_for_status()
                data=response.json()
                rows=[{
                    "title":item.get("title"),
                    "url":item.get("url"),
                    "source":item.get("domain"),
                    "published_at":item.get("seendate"),
                    "language":item.get("language"),
                } for item in data.get("articles",[]) if item.get("url")]
                self._cache[key]=(time.monotonic(),rows)
                return rows
            except httpx.HTTPError as exc:
                last_error=exc
                if attempt==0:
                    time.sleep(0.5)
                    continue
                break

        if cached:
            return cached[1]
        if isinstance(last_error,RuntimeError):
            raise last_error
        raise RuntimeError("No se pudo actualizar la fuente pública de noticias. Se conservarán las noticias locales ya guardadas.")
