# ADR-004 — IA local desacoplada

Status: Accepted

## Decision

No depender de APIs cloud de IA para datos privados. Implementar LocalLLMProvider con adapters para Ollama, llama.cpp y MLX cuando sea apropiado.

## Consequences

- mayor privacidad;
- cero coste por token;
- variación de rendimiento según hardware;
- ModelRouter necesario.
