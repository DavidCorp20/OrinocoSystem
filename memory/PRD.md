# ControlPyme — PRD

## Problem statement original
Plataforma web SaaS para pequeños y medianos negocios (tiendas, bodegas, ferreterías, papelerías, salones de belleza, emprendimientos) que centraliza productos, inventario (entradas/salidas), ventas, compras, finanzas simplificadas, dashboard inteligente con semáforo 🟢🟡🔴, alertas de stock, analítica, predicciones ML, asistente IA, reportes y educación. Pregunta central: "¿Cómo está mi negocio y qué debería hacer ahora?". Filosofía: "Simple para el usuario, profesional por dentro". Prioridad: facilidad de uso + valor + datos confiables + escalabilidad.

## Decisiones del usuario (iteración 1)
- Alcance: MVP completo (sección 26 del brief).
- Auth: email/contraseña con JWT (cookies httpOnly SameSite=Lax + Bearer fallback).
- Asistente IA: GPT 5.4 Mini vía Emergent LLM Key (streaming SSE).
- Idioma/moneda: Español + USD (moneda configurable en onboarding).
- Roles: solo propietario (1 usuario por negocio).

## Arquitectura
- Backend: FastAPI (puerto 8001, prefijo /api), MongoDB (motor), ids UUID string (sin ObjectId en respuestas), PyJWT + bcrypt, protección anti-fuerza-bruta por email (5 intentos → 429, 15 min), índices por business_id (multi-tenant).
- IA: emergentintegrations LlmChat `openai/gpt-5.4-mini`, contexto del negocio inyectado en system prompt, historial en MongoDB, SSE con X-Accel-Buffering:no.
- Frontend: React 19 + react-router 7 + Tailwind + shadcn/ui + recharts + sonner. Paleta: verde #0D5C3A sobre fondo bone #FAF9F5, sidebar slate oscuro; fuentes Plus Jakarta Sans / Manrope / JetBrains Mono.
- Módulos backend: database.py, security.py, models.py, stats.py (KPIs + contexto IA), routes_{auth,business,products,inventory,sales,purchases,expenses,dashboard,assistant}.py, seed.py (demo "Ferretería El Candado").
- Reglas de negocio implementadas: venta → valida stock (update condicional atómico $inc con $gte) → descuenta → costo/margen → movimiento auditoría → alerta stock bajo. Compra → suma stock → costo promedio ponderado → movimiento. Movimiento manual → ajuste con auditoría (usuario, stock resultante). Alerta: stock <= mínimo. Estimación de agotamiento: ritmo de venta 30d.

## Personas
- Propietario de PYME sin conocimientos contables/tecnológicos; quiere respuestas accionables, no números crudos.

## Implementado (2026-08-28, iteración 1 + fixes iteración 2)
- Auth completo (registro/login/logout/me/refresh) + admin arenas.david1@gmail.com sembrado + negocio demo con 12 productos, 30 días de ventas, compras, gastos y movimientos.
- Onboarding progresivo 5 pasos (nombre → rubro → moneda → productos opcionales → listo).
- Dashboard: semáforo, 4 KPIs, comparación período anterior, tendencia 14 días, alertas stock, productos estrella, ventas recientes, recomendaciones accionables con causa.
- Productos: CRUD, búsqueda, filtro categoría, importar/exportar CSV, badges de estado de stock.
- Movimientos: entradas/salidas con motivos, historial con usuario y stock resultante, export CSV.
- Ventas: multi-item con descuento, método de pago, descuento de stock atómico, toasts de alerta, export CSV.
- Compras: multi-item, costo promedio ponderado, no pisa proveedor existente, export CSV.
- Finanzas: ingresos/gastos/ganancia/margen con explicaciones en lenguaje simple, gráfico 8 semanas, gastos por categoría, CRUD gastos, export CSV.
- Reportes: 5 reportes con filtro de fechas y descarga CSV.
- Asistente "Pyme": chat flotante con streaming, quick prompts, respuestas basadas SOLO en datos del negocio, historial persistente.
- Testing: 46/46 pytest + retest e2e completo (2 iteraciones). Bugs corregidos: brute-force por email (era IP de ingress rotativa), costo ponderado, timestamps futuros del seed, testids duplicados móvil, formato es-ES de margen, markdown crudo del asistente.

## Backlog priorizado
### P0 (siguiente iteración sugerida)
- Edición/anulación de ventas y compras (reversar stock).
- Eliminar CORS_ORIGINS muerto del .env (clave protegida del template; evaluar).
### P1
- Roles multi-usuario (admin, vendedor, consulta) — arquitectura ya aislada por business_id.
- Analítica avanzada: ABC, rotación, rentabilidad por producto (datos ya disponibles en stats.py).
- Clientes y proveedores como entidades propias.
- Export PDF, recuperación de contraseña por email (Resend).
### P2
- Predicciones ML con histórico real (forecast demanda/agotamiento ya estimado por reglas).
- Planes SaaS (gratuito/básico/pro), métricas MRR/churn, código de barras, app móvil.

## Riesgos conocidos
- Concurrencia extrema en stock mitigada con updates condicionales; falta transacción multi-doc si se escala.
- Clave CORS_ORIGINS="*" sin usar (heredada del template; server.py usa FRONTEND_URL explícito).
- Asistente depende del saldo de la Emergent LLM Key del usuario.

## Credenciales
Ver /app/memory/test_credentials.md. Suite de tests: /app/backend/tests/ (46 tests). Playbooks: /app/auth_testing.md.

## Próximos pasos
1. Validación con usuario real del demo + feedback de UX.
2. Decidir P0 de la siguiente iteración (anulación de ventas o roles).
3. Analytics avanzado (ABC/rotación) una vez acumulado histórico real.
