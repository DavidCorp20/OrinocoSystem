# Auth Testing Playbook — ControlPyme

## Credenciales
Ver /app/memory/test_credentials.md (admin: arenas.david1@gmail.com / ControlPyme2026!).

## Paso 1: Verificación MongoDB
```
mongosh
use test_database
db.users.findOne({email: "arenas.david1@gmail.com"}, {password_hash: 1})
```
El hash debe empezar con `$2b$` (bcrypt). Deben existir índices: users.email (único), login_attempts.identifier.

## Paso 2: Pruebas de API
```
BASE=https://dashboard-control-31.preview.emergentagent.com
curl -c cookies.txt -X POST $BASE/api/auth/login -H "Content-Type: application/json" -d '{"email":"arenas.david1@gmail.com","password":"ControlPyme2026!"}'
curl -b cookies.txt $BASE/api/auth/me
```
- Login devuelve {user, business, access_token, refresh_token} y fija cookies access_token + refresh_token (httpOnly).
- /me con cookies devuelve el mismo usuario + business ("Ferretería El Candado").
- Alternativa Bearer: usar el access_token del JSON: `curl -H "Authorization: Bearer <token>" $BASE/api/auth/me`.

## Paso 3: Flujo protegido
- GET /api/dashboard sin cookie/token → 401.
- POST /api/auth/login con password incorrecta 5 veces → la 6ª devuelve 429 (bloqueo 15 min).
- POST /api/auth/register con email existente → 400.
- POST /api/auth/register con email nuevo → 200, business null; luego POST /api/business crea el negocio (onboarding).

## Paso 4: Aislamiento multi-tenant
- Usuario A y usuario B con negocios distintos: GET /api/products de cada uno solo muestra sus propios productos.
