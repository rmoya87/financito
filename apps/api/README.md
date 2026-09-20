# Financito Local API

Backend local implementado con Python, FastAPI, Pydantic, SQLAlchemy y SQLite. Es la única capa autorizada para cálculos financieros, acceso a datos privados, documentos y adapters.

## Desarrollo

```bash
cd apps/api
pip install -e '.[dev]'
FINANCITO_ALLOW_PLAINTEXT_SQLITE=1 PYTHONPATH=. pytest
FINANCITO_ALLOW_PLAINTEXT_SQLITE=1 PYTHONPATH=. uvicorn financito.main:app --host 127.0.0.1 --port 8765
```

Nunca usar `0.0.0.0`. El almacenamiento SQLite sin cifrar está limitado a desarrollo/tests; ver `docs/IMPLEMENTATION_STATUS.md`.
