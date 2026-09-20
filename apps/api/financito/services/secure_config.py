from __future__ import annotations

import os
from dataclasses import dataclass

SERVICE = "Financito"

_KEYS = {
    "enable_banking_app_id": "provider.enable_banking.app_id",
    "enable_banking_private_key": "provider.enable_banking.private_key",
    "alpha_vantage_api_key": "provider.alpha_vantage.api_key",
    "coingecko_demo_key": "provider.coingecko.demo_key",
    "sec_user_agent": "provider.sec.user_agent",
}

_ENV = {
    "enable_banking_app_id": "FINANCITO_ENABLE_BANKING_APP_ID",
    "enable_banking_private_key": "FINANCITO_ENABLE_BANKING_PRIVATE_KEY_PEM",
    "alpha_vantage_api_key": "FINANCITO_ALPHA_VANTAGE_KEY",
    "coingecko_demo_key": "FINANCITO_COINGECKO_DEMO_KEY",
    "sec_user_agent": "FINANCITO_SEC_USER_AGENT",
}

def _keyring():
    try:
        import keyring
        return keyring
    except Exception:
        return None

def get_secret(name:str)->str|None:
    if name not in _KEYS:
        raise KeyError(name)
    kr=_keyring()
    if kr is not None:
        try:
            value=kr.get_password(SERVICE,_KEYS[name])
            if value:
                return value
        except Exception:
            pass
    value=os.getenv(_ENV[name],"").strip()
    return value or None

def set_secret(name:str,value:str|None)->None:
    if name not in _KEYS:
        raise KeyError(name)
    kr=_keyring()
    if kr is None:
        raise RuntimeError("No secure credential store is available")
    try:
        if value is None or not value.strip():
            try:
                kr.delete_password(SERVICE,_KEYS[name])
            except Exception:
                pass
            return
        kr.set_password(SERVICE,_KEYS[name],value)
    except Exception as exc:
        raise RuntimeError("Could not write secret to the system credential store") from exc

def provider_status()->dict:
    return {
        "enable_banking":{
            "app_id":bool(get_secret("enable_banking_app_id")),
            "private_key":bool(get_secret("enable_banking_private_key")),
        },
        "alpha_vantage":{"api_key":bool(get_secret("alpha_vantage_api_key"))},
        "coingecko":{"demo_key":bool(get_secret("coingecko_demo_key"))},
        "sec":{"user_agent":bool(get_secret("sec_user_agent"))},
    }


def clear_all_secrets()->list[str]:
    cleared=[]
    for name in _KEYS:
        try:
            set_secret(name,None)
            cleared.append(name)
        except RuntimeError:
            continue
    return cleared
