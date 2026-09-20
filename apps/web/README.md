# Financito WebApp

WebApp local implementada con Next.js 16.3 LTS, React 19.3, TypeScript, Tailwind CSS 4.3 y TanStack Query. Se exporta estáticamente para que FastAPI sirva UI y API desde un único origen local.

```bash
cd apps/web
npm install
npm run typecheck
npm run build
```

No contiene reglas financieras críticas: todos los cálculos se solicitan a `/api/v1`.
