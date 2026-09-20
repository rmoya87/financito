# ADR-001 — WebApp local-first

Status: Accepted

## Context

Financito necesita una interfaz moderna, rápida y multiplataforma manteniendo datos financieros en el equipo.

## Decision

Usar Next.js + React + TypeScript + TailwindCSS + shadcn/ui para presentación, comunicándose con una API FastAPI en localhost.

## Consequences

Ventajas:
- ecosistema UI maduro;
- fácil evolución a PWA;
- diseño consistente;
- separación clara del dominio.

Costes:
- dos runtimes;
- necesidad de securizar loopback;
- empaquetado desktop futuro requiere trabajo adicional.
