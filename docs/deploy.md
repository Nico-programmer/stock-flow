# stock-flow — Guía de despliegue (contexto para otro chat)

> **Cómo usar este documento:** pegá este archivo completo al inicio de un chat nuevo
> (Claude Code u otro asistente) antes de pedir ayuda con el deploy. Le da todo el
> contexto del proyecto y el plan, para que no tenga que explorar el repo desde cero.
> Complementa a `docs/documentacion.md` (funcionamiento de la app); este archivo es
> **solo despliegue**.

---

## 0. TL;DR

- Es un proyecto **Django 6.1 / Python 3.14** funcionalmente terminado y con tests (92, todos verdes).
- La **seguridad de aplicación ya está reforzada** y las settings **ya leen variables de entorno**.
- Falta la **plomería de producción**: base de datos PostgreSQL, servidor WSGI (Gunicorn), archivos estáticos (WhiteNoise), HTTPS y `requirements.txt` en condiciones.
- Objetivo de esta guía: dejar el proyecto corriendo en un servidor real.

**Importante para el asistente que reciba esto:** el archivo `CLAUDE.md` del repo pide "no correr
`makemigrations` / `migrate`" — eso es una preferencia de aprendizaje del dueño para el trabajo
**de desarrollo**. Para **desplegar**, ejecutar `migrate` y `collectstatic` es obligatorio y está
permitido. No generes migraciones nuevas salvo que cambien modelos.

---

## 1. Qué es el proyecto

Sistema web multiempresa de **inventario y ventas**. Una plataforma central (superusuario)
administra empresas y sus suscripciones mensuales; cada empresa administra sus sucursales,
productos, stock, ventas y usuarios.

| Componente | Valor |
|---|---|
| Lenguaje | Python 3.14 |
| Framework | Django 6.1 |
| BD actual | SQLite (`db.sqlite3`, gitignored) → **migrar a PostgreSQL** |
| Usuario | modelo custom `apps.accounts.CustomUser` (`AUTH_USER_MODEL = 'accounts.CustomUser'`), login por `username`, `REQUIRED_FIELDS = ['email']` |
| Zona horaria | `America/Bogota`, `USE_TZ = True` |
| Idioma / formato | `es-co` (miles `.`, decimales `,`) |
| Frontend | Bootstrap 5.3, DataTables, Select2, SweetAlert2, Chart.js — **todo por CDN** (el navegador los baja; el server no los sirve) |
| Dep. Python extra | `openpyxl` (export a Excel de reportes) |

### Estructura

```
stock_flow/            # proyecto (settings.py, urls.py, wsgi.py)
apps/                  # paquete; cada app registrada como apps.<nombre>
  accounts/            # auth, usuarios, empleados
  companies/           # empresas, sucursales, suscripciones, pagos
  inventory/           # productos, stock por sucursal, movimientos
  sales/               # ventas con carrito multi-producto
  core/                # dashboard, reportes, middleware/context-processor
static/                # CSS/JS propios (STATICFILES_DIRS)
templates/ y apps/templates/   # templates
manage.py
requirements.txt       # ⚠️ hoy en UTF-16 e incompleto (ver §4)
db.sqlite3             # gitignored
docs/                  # ⚠️ gitignored — este archivo no se versiona
```

- URLs: `/` → login (`apps.accounts`), `/companies/`, `/inventory/`, `/sales/`, `/home/` (dashboard + `/home/reports/`), `/admin/`.
- Middleware propio: `apps.core.middleware.SubscriptionLockMiddleware` (último de la lista).
- Context processor propio: `apps.core.context_processors.subscription_flags`.

---

## 2. Estado actual de `settings.py` (lo que YA está)

`stock_flow/settings.py` ya fue preparado para producción parcialmente:

```python
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "django-insecure-...")   # fallback solo dev
DEBUG      = _env_bool("DJANGO_DEBUG", True)                               # default True (dev)
ALLOWED_HOSTS = env "DJANGO_ALLOWED_HOSTS" (coma-sep)  # default localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS = env "DJANGO_CSRF_TRUSTED_ORIGINS" (coma-sep)

# Siempre:
X_FRAME_OPTIONS = 'DENY'
SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_AGE = 60*60*8          # 8 h
SESSION_SAVE_EVERY_REQUEST = True

# Solo si NOT DEBUG:
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')   # detrás de proxy TLS

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'  # no envía de verdad
DATABASES = { 'default': sqlite3 db.sqlite3 }                     # ⚠️ hardcodeado
```

Variables de entorno que **ya se leen**:

| Variable | Uso | Ejemplo prod |
|---|---|---|
| `DJANGO_SECRET_KEY` | clave secreta | (50+ chars aleatorios) |
| `DJANGO_DEBUG` | `0` en producción | `0` |
| `DJANGO_ALLOWED_HOSTS` | hosts | `midominio.com,www.midominio.com` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | orígenes https | `https://midominio.com,https://www.midominio.com` |

`python manage.py check --deploy` con `DJANGO_DEBUG=0` y las vars puestas debe quedar limpio
salvo `security.W009` mientras el `SECRET_KEY` sea el de dev.

---

## 3. Lo que FALTA (tareas de deploy)

En orden sugerido:

1. **`requirements.txt`** → reescribir en **UTF-8** y agregar dependencias de prod (§4).
2. **`settings.py`** → `STATIC_ROOT`, WhiteNoise, `DATABASES` por env, `LOGGING` mínimo, (opcional) cache Redis (§5).
3. **PostgreSQL** → crear BD/usuario, setear `DATABASE_URL`, `migrate` (§6).
4. **Estáticos** → `collectstatic` (§7).
5. **Gunicorn + servicio** (systemd) o PaaS (§8).
6. **Nginx + HTTPS** (Certbot) si es VPS (§9).
7. **Superusuario, smoke test, checklist final** (§10).

### No es necesario tocar
- Migraciones: están todas generadas y aplicadas; `makemigrations --check` da "No changes".
- Seguridad de aplicación: ya reforzada (ver `docs/documentacion.md` §10).
- Media: el proyecto **no sube archivos** (no hay `FileField`/`ImageField`); `MEDIA_*` puede quedar como está.

---

## 4. `requirements.txt` (reescribir en UTF-8)

El actual está en **UTF-16** (se creó con `>` de PowerShell) y pip puede fallar. Contenido nuevo:

```
Django==6.1
openpyxl==3.1.5
gunicorn==23.0.0
whitenoise==6.7.0
psycopg[binary]==3.2.3
dj-database-url==2.3.0
```

(`asgiref`, `sqlparse`, `tzdata`, `et-xmlfile` entran solos como dependencias.)

Crear en UTF-8 (PowerShell):
```powershell
@'
Django==6.1
openpyxl==3.1.5
gunicorn==23.0.0
whitenoise==6.7.0
psycopg[binary]==3.2.3
dj-database-url==2.3.0
'@ | Set-Content -Encoding utf8 requirements.txt
```

> Nota Windows: `gunicorn` no corre en Windows. Para probar local en Windows se usa
> `runserver`; Gunicorn es solo para el servidor Linux.

---

## 5. Cambios a `settings.py` para deploy

Aplicar estos añadidos (no romper lo que ya está):

### 5.1 Estáticos con WhiteNoise

```python
# En MIDDLEWARE, JUSTO después de SecurityMiddleware:
'whitenoise.middleware.WhiteNoiseMiddleware',

# Cerca de STATIC_URL / STATICFILES_DIRS:
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
```

### 5.2 Base de datos por variable de entorno

```python
import dj_database_url

DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",   # fallback dev
        conn_max_age=600,
        conn_health_checks=True,
    )
}
```
Con `DATABASE_URL=postgres://usuario:pass@host:5432/stockflow` en el entorno de prod.

### 5.3 Logging mínimo a consola (para ver errores en el servicio)

```python
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django.request": {"handlers": ["console"], "level": "ERROR", "propagate": False},
    },
}
```

### 5.4 (Opcional) Cache compartido para el throttle de login

El freno de fuerza bruta del login usa el cache de Django. Con **varios workers de Gunicorn**
el `LocMemCache` por defecto es por-proceso (el throttle se debilita). Si hay Redis:

```python
if os.environ.get("REDIS_URL"):
    CACHES = {"default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": os.environ["REDIS_URL"],
    }}
```
No es bloqueante: sin Redis, funciona igual (throttle por worker).

### 5.5 (Opcional) Email real

`EMAIL_BACKEND` es de consola (no envía). El proyecto **no tiene flujo de "olvidé mi contraseña"**,
así que no es urgente. Si se quiere, configurar SMTP por env.

---

## 6. PostgreSQL

```bash
sudo -u postgres psql
CREATE DATABASE stockflow;
CREATE USER stockflow WITH PASSWORD 'una-clave-fuerte';
ALTER ROLE stockflow SET client_encoding TO 'utf8';
ALTER ROLE stockflow SET timezone TO 'America/Bogota';
GRANT ALL PRIVILEGES ON DATABASE stockflow TO stockflow;
\q
```
`DATABASE_URL=postgres://stockflow:una-clave-fuerte@localhost:5432/stockflow`

Luego:
```bash
python manage.py migrate
```
> No hay datos que migrar desde SQLite (la BD dev es de pruebas). Si se quisiera, sería
> `dumpdata` / `loaddata`, pero lo normal acá es arrancar limpio.

---

## 7. Estáticos

```bash
python manage.py collectstatic --noinput   # genera staticfiles/ que sirve WhiteNoise
```
`staticfiles/` debe estar en `.gitignore` (agregarlo si no está).

---

## 8. Servidor de aplicación

### Opción A — VPS (Ubuntu) con Gunicorn + systemd

`/etc/systemd/system/stockflow.service`:
```ini
[Unit]
Description=stock-flow (gunicorn)
After=network.target

[Service]
User=deploy
WorkingDirectory=/home/deploy/stock-flow
EnvironmentFile=/home/deploy/stock-flow/.env
ExecStart=/home/deploy/stock-flow/env/bin/gunicorn stock_flow.wsgi:application \
    --bind 127.0.0.1:8000 --workers 3 --timeout 60
Restart=always

[Install]
WantedBy=multi-user.target
```

`.env` (chmod 600, NO se versiona):
```
DJANGO_SECRET_KEY=...50+ chars...
DJANGO_DEBUG=0
DJANGO_ALLOWED_HOSTS=midominio.com,www.midominio.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://midominio.com,https://www.midominio.com
DATABASE_URL=postgres://stockflow:...@localhost:5432/stockflow
```
Generar la clave: `python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"`

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now stockflow
sudo systemctl status stockflow
```

### Opción B — PaaS (Render / Railway / Fly.io)

Más rápido para empezar. Config típica:
- **Build:** `pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate`
- **Start:** `gunicorn stock_flow.wsgi:application`
- **Env vars:** las de §2 + `DATABASE_URL` (la BD Postgres del propio PaaS) + `PYTHON_VERSION=3.14`.
- WhiteNoise sirve los estáticos (no hace falta bucket).

---

## 9. Nginx + HTTPS (solo VPS)

`/etc/nginx/sites-available/stockflow`:
```nginx
server {
    listen 80;
    server_name midominio.com www.midominio.com;
    client_max_body_size 5M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;   # lo usa SECURE_PROXY_SSL_HEADER
    }
}
```
```bash
sudo ln -s /etc/nginx/sites-available/stockflow /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d midominio.com -d www.midominio.com
```
WhiteNoise ya sirve los estáticos vía Gunicorn, así que no hace falta un `location /static/`
en Nginx (se puede agregar para performance, apuntando a `staticfiles/`).

Con Certbot + `DJANGO_DEBUG=0`, `SECURE_SSL_REDIRECT` y HSTS quedan activos automáticamente.

---

## 10. Puesta a punto final

```bash
python manage.py check --deploy        # debe quedar sin warnings
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser       # pide username y email (en ese orden), luego password
```

Smoke test:
- [ ] `https://midominio.com/` carga el login por HTTPS (redirige desde http).
- [ ] Login del superusuario → dashboard "Plataforma".
- [ ] Crear una empresa con una sucursal → se crea su suscripción sola.
- [ ] Crear un producto, registrar un movimiento y una venta.
- [ ] `/home/reports/` y "Descargar Excel".
- [ ] Estáticos (CSS propio) cargan (revisar consola del navegador, 200 en `/static/...`).
- [ ] `systemctl status stockflow` y logs sin errores.

Checklist de config:
- [ ] `DJANGO_DEBUG=0`
- [ ] `DJANGO_SECRET_KEY` fuerte y único
- [ ] `DJANGO_ALLOWED_HOSTS` con el dominio real
- [ ] `DJANGO_CSRF_TRUSTED_ORIGINS` con `https://`
- [ ] `DATABASE_URL` a Postgres
- [ ] `.env` con permisos 600 y fuera de git
- [ ] `staticfiles/` en `.gitignore`
- [ ] Backups de la BD (cron `pg_dump`)

---

## 11. Gotchas específicos de este repo

- **`docs/` está en `.gitignore`** → esta guía no se versiona; se comparte a mano.
- **`requirements.txt` en UTF-16** → reescribir en UTF-8 (§4) o pip puede romper.
- **`CLAUDE.md`** pide no correr `migrate` — es preferencia de *desarrollo* del dueño; en deploy hay que correrlo.
- **Login por `username`**, no email. `createsuperuser` pide `username` y luego `email`.
- **`apps/` es un paquete** (`apps/__init__.py`); `AppConfig.name = 'apps.<x>'`.
- **Frontend por CDN**: si el entorno de deploy bloquea salida a internet del *cliente*, el CSS/JS no cargan. No afecta al servidor, sí al navegador del usuario.
- **`SESSION_COOKIE_AGE = 8h`** con `SESSION_SAVE_EVERY_REQUEST` → sesión deslizante de 8 horas.
- **Throttle de login** en cache local: con varios workers, sin Redis, es por worker (§5.4).
- **Timezone/locale**: `America/Bogota` + `es-co`. El servidor no necesita locale del SO instalado (Django lo maneja), pero conviene `tzdata` (ya está en requirements).
- El botón activar/desactivar **empresa** en el listado tiene `action="#"` (feature sin implementar) — no rompe nada.

---

## 12. Estado de verificación (al momento de escribir esto)

- `python manage.py test` → **92/92 OK**.
- `python manage.py check` → sin issues.
- `python manage.py check --deploy` (DEBUG=0 + envs) → solo `W009` hasta poner `SECRET_KEY` real.
- `python manage.py makemigrations --check` → "No changes detected".
- Rama: `refactor/clean-code`.
