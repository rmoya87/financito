from __future__ import annotations
def score(fundamentals:float|None,valuation:float|None,growth:float|None,quality:float|None,momentum:float|None,risk:float|None,portfolio_fit:float|None)->dict:
    components={"fundamentals":fundamentals,"valuation":valuation,"growth":growth,"quality":quality,"momentum":momentum,"risk":risk,"portfolio_fit":portfolio_fit}
    available={k:max(0.0,min(1.0,v)) for k,v in components.items() if v is not None}
    if len(available)<3:return {"status":"needs_more_data","score":None,"components":components,"confidence":"low"}
    weights={"fundamentals":.18,"valuation":.16,"growth":.12,"quality":.16,"momentum":.10,"risk":.16,"portfolio_fit":.12};den=sum(weights[k] for k in available);result=sum(available[k]*weights[k] for k in available)/den
    return {"status":"ready","score":result,"components":components,"confidence":"medium" if len(available)<7 else "high","notice":"Score analítico, no orden de compra ni promesa de rentabilidad."}
