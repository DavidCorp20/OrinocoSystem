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

## Implementado (2026-08-28, iteración 1 + fixes iteración 2 + iteración 3)
- Auth completo (registro/login/logout/me/refresh) + admin arenas.david1@gmail.com (propietario + superadmin de plataforma).
- Onboarding progresivo 5 pasos (nombre → rubro → moneda → productos opcionales → listo).
- Dashboard: semáforo, 4 KPIs con equivalente en Bs, comparación período anterior, tendencia 14 días, alertas stock, productos estrella, ventas recientes, recomendaciones accionables, botón grande "Venta rápida" (POS).
- POS Venta rápida: buscador/escáner de código de barras (keyboard-wedge, Enter agrega), carrito con +/-, cliente+RIF, total USD+Bs, cobro → factura automática.
- Buscador de productos (nombre/SKU/barcode) en ventas y compras; unidad de medida visible (kg/unidad).
- Facturación venezolana: ventas F-000001+ y compras C-000001+ con RIF emisor/cliente/proveedor, IVA 16% incluido (base imponible desglosada), tasa BCV del día y total en Bs; modal + impresión 80mm. Numeración fiscal sin huecos (número se asigna tras confirmar stock; compensación de stock si un ítem falla).
- Tasa BCV: automática desde bcv.today (cache 1h, fallback a última conocida) o manual; precios duales USD/Bs en dashboard, productos, ventas y facturas; pill en header sincronizado en vivo vía AuthContext.
- Roles: propietario (todo + equipo + configuración), administrador (operación completa), vendedor (ventas/productos/movimientos). Página Equipo (crear/eliminar usuarios). Guards backend (require_roles) + frontend (RANK + NoAccess).
- Plataforma (superadmin): KPIs (negocios, activos, nuevos 30d, gastos del mes), tabla de negocios con activar/desactivar (login 403 si deshabilitado), gastos de plataforma CRUD, overview sin N+1.
- 4 negocios demo: Ferretería El Candado (admin), Kiosco La Esquina (abarrotes VE), Verdulería Doña Rosa (por kg), Repuestos El Pistón (autopartes). Todos con 30 días de ventas, compras, gastos, movimientos y barcodes.
- Productos: CRUD, búsqueda, filtro, importar/exportar CSV, precios USD+Bs, badges de stock.
- Finanzas/Reportes/Asistente IA "Pyme" (GPT 5.4 Mini streaming) como en iteración 1.
- Tipografía de números profesional (Plus Jakarta Sans tabular-nums, sin monospace).
- Testing: 85/85 pytest + 4 iteraciones e2e. Bugs corregidos: brute-force por email, costo ponderado, numeración fiscal, N+1 plataforma, pill BCV stale, overlay ResizeObserver, roles en header, barcodes faltantes, tenants TEST_ purgados.

## Backlog priorizado
### P0 (siguiente iteración sugerida)
- Edición/anulación de ventas y compras (reversar stock y marcar factura como anulada).
- Impresora térmica 80mm real (formato listo, falta integración con drivers del navegador/print service).
### P1
- Cámara del teléfono como escáner (hoy: lectores keyboard-wedge; la UI ya soporta entrada directa).
- Clientes y proveedores como entidades propias (hoy son campos de texto en facturas).
- Analítica avanzada: ABC, rotación, rentabilidad por producto (datos ya disponibles en stats.py).
- Export PDF de facturas y reportes, recuperación de contraseña por email (Resend).
- Roles adicionales (solo-consulta) y permisos granulares por módulo.
### P2
- Predicciones ML con histórico real (forecast demanda/agotamiento ya estimado por reglas).
- Planes SaaS (gratuito/básico/pro) con cobro (Stripe), métricas MRR/churn, app móvil.
- Multi-moneda completa (hoy: USD base + Bs referencial por tasa).

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
