# stock-flow — Documentación

Sistema web multiempresa para gestión de **inventario y ventas**. Cada empresa administra sus sucursales, productos, stock, ventas y usuarios; una plataforma central (superusuario) administra las empresas y sus suscripciones.

---

## 1. Stack y requisitos

| Componente | Versión / valor |
|---|---|
| Lenguaje | Python 3.14 |
| Framework | Django 6.1 |
| Base de datos | SQLite (`db.sqlite3`) |
| Zona horaria | `America/Bogota` · `USE_TZ = True` |
| Idioma / formato | `es-co` (miles `.`, decimales `,`) |
| Export Excel | `openpyxl` 3.1.5 |
| Frontend | Bootstrap 5.3, DataTables, Select2, SweetAlert2, Chart.js (todo por CDN) |

Dependencias en `requirements.txt`: `Django`, `openpyxl` (+ `asgiref`, `sqlparse`, `tzdata`, `et-xmlfile`).

---

## 2. Puesta en marcha local

```bash
python -m venv env
env\Scripts\activate            # Windows
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser  # crea el usuario de plataforma
python manage.py runserver
```

- Correr tests: `python manage.py test`
- Chequeo rápido: `python manage.py check`
- **Migraciones**: las genera y aplica el desarrollador manualmente (`makemigrations` / `migrate`).

---

## 3. Arquitectura

Proyecto Django `stock_flow` con las apps bajo el paquete `apps/` (cada una registrada como `apps.<nombre>`):

| App | Responsabilidad | Prefijo URL |
|---|---|---|
| `apps.accounts` | Usuario custom, login/logout, gestión de usuarios (superuser) y de empleados (admin) | `/` |
| `apps.companies` | Empresas, sucursales, suscripciones y pagos | `/companies/` |
| `apps.inventory` | Productos, stock por sucursal, movimientos de stock | `/inventory/` |
| `apps.sales` | Ventas con carrito multi-producto | `/sales/` |
| `apps.core` | Dashboard (Inicio), Reportes, middleware/context-processor/utilidades transversales | `/home/` |

`stock_flow/urls.py` incluye las 5 apps; `apps.accounts` toma la raíz (`/` → login).

### Estructura de `apps.core`

- `views.py` — `dashboard`, `reports` (+ `_reporte_xlsx`)
- `stats.py` — cálculo de KPIs y agregados (reutilizado por Inicio y Reportes)
- `utils.py` — `filtrar_por_fecha(queryset, request, field, default_from, default_to)`
- `middleware.py` — `SubscriptionLockMiddleware`
- `context_processors.py` — `subscription_flags` → variable `solo_lectura` en templates
- `templatetags/money.py` — filtro `pesos`
- `templates/` — `layout.html`, `home.html`, `reports.html`, `includes/` (sidebar, topbar, kpi)

---

## 4. Modelo de datos

### accounts

**`CustomUser`** (`AUTH_USER_MODEL`, `AbstractBaseUser` + `PermissionsMixin`) — login por `username`.

| Campo | Notas |
|---|---|
| `email`, `username` | únicos; `username` es el identificador de login |
| `first_name`, `last_name`, `phone_number` | opcionales |
| `role` | `admin` / `manager` / `employee` (default `employee`) |
| `company` (FK → Company) | **solo** para `admin` |
| `branch` (FK → Branch) | **solo** para `manager` / `employee` |
| `is_active` | baja lógica |

**Regla de negocio** (`CustomUser.clean()`, se valida con `full_clean()` en las vistas): un `admin` se vincula por `company` (sin `branch`); un `manager`/`employee` se vincula por `branch` (sin `company`).

**`EmployeePermission`** — OneToOne con `CustomUser`, **solo existe para manager/employee** (el `admin` tiene acceso total por rol). Flags: `can_manage_inventory`, `can_manage_sales`, `can_manage_employees`, `can_view_reports`. Guarda `branch`, `granted_by`, `updated_at`.

### companies

**`Company`** — `name` (único global), `nit` (opcional), `phone_number`, `is_active`.

**`Branch`** — pertenece a una `Company`; `name` único **por empresa**; `address`, `is_active`.

**`Subscription`** — OneToOne con `Company`.

| Elemento | Detalle |
|---|---|
| `monthly_price` | default `30000` |
| `paid_until` | fecha hasta la que está paga |
| `DIAS_AVISO` | `7` — margen para avisar el vencimiento |
| `dias_restantes` / `dias_vencida` | propiedades calculadas |
| `estado` | `pagada` · `pendiente` (≤ 7 días) · `vencida` (< 0) |
| `registrar_pago(meses, user)` | corre `paid_until`; el período nuevo arranca desde hoy si ya venció, o desde `paid_until` si sigue vigente; crea un `SubscriptionPayment` en transacción |

**`SubscriptionPayment`** — historial: `months`, `amount`, `period_start`, `period_end`, `registered_by`.

### inventory

**`ProductModel`** — catálogo a nivel empresa: `company`, `sku` (único por empresa), `name`, `brand`, `price`, `is_active`. El precio vive acá, no por sucursal.

**`BranchStock`** — saldo de un producto en **una** sucursal: `product`, `branch`, `stock`, `is_active`. Único por `(product, branch)`. `clean()` valida que producto y sucursal sean de la misma empresa.

**`StockMovement`** — rastro de cada cambio de stock: `branch_stock`, `type` (`IN` entrada / `OUT` salida / `SALE` venta), `quantity`, `reason`, `user`, `created_at`. El saldo actual sigue en `BranchStock.stock`; esto es el historial.

### sales

**`Sale`** — cabecera: `branch`, `user` (vendedor), `created_at`. `total()` se **calcula** sumando los `SaleItem` (no se guarda).

**`SaleItem`** — línea de venta: `sale`, `product`, `quantity`, `unit_price` (se copia del producto al vender; ventas pasadas no cambian si luego cambia el precio). `subtotal() = quantity * unit_price`.

### Relaciones (resumen)

```
Company 1─N Branch 1─N BranchStock N─1 ProductModel
Company 1─1 Subscription 1─N SubscriptionPayment
Company 1─N CustomUser(admin)      Branch 1─N CustomUser(manager/employee)
CustomUser 1─1 EmployeePermission
Branch 1─N Sale 1─N SaleItem N─1 ProductModel
BranchStock 1─N StockMovement
```

---

## 5. Roles y permisos

| Rol | Alcance | Cómo se vincula |
|---|---|---|
| **Superusuario** | Toda la plataforma: todas las empresas, sucursales, usuarios; suscripciones y pagos | `is_superuser=True` |
| **Administrador** (`admin`) | Toda **su** empresa (todas las sucursales) | FK `company` |
| **Gerente** (`manager`) | **Su** sucursal | FK `branch` + `EmployeePermission` |
| **Empleado** (`employee`) | **Su** sucursal | FK `branch` + `EmployeePermission` |

- El `admin` tiene acceso total dentro de su empresa **por rol** (no necesita `EmployeePermission`).
- `manager`/`employee` acceden a cada módulo según sus flags `can_manage_*` / `can_view_reports`. El chequeo es **server-side** (decorador `@permiso_modulo`), no solo visual en el sidebar.
- Regla extra en Empleados: **solo el `admin` puede crear/gestionar gerentes**. Un gestor no-admin (con `can_manage_employees`) solo maneja **empleados de su propia sucursal** y solo puede otorgarles `can_manage_inventory` / `can_manage_sales` (nunca `can_manage_employees` ni `can_view_reports`).

### Helpers de alcance (transversales)

| Helper | Ubicación | Qué devuelve |
|---|---|---|
| `empresa_del_usuario(user)` | `apps/companies/utils.py` | `admin` → `user.company`; resto → `user.branch.company` |
| `sucursales_del_usuario(user)` | `apps/inventory/utils.py` | manager/empleado → su sucursal; admin → activas de su empresa; superuser → todas activas |
| `resolver_empresa(request, user)` | `apps/inventory/utils.py` | empresa de trabajo; el superuser sin empresa la elige por `?company=` |

---

## 6. Suscripciones y bloqueo por vencimiento

Cobro mensual **sin pasarela**: el superusuario registra pagos a mano y eso corre `paid_until`.

- Empresa nueva → se le crea la `Subscription` automáticamente (`paid_until = hoy + 1 mes`).
- El superusuario puede editar `paid_until` / `monthly_price` desde editar-empresa (para pruebas) y registrar pagos desde el listado de empresas.
- **Aviso** (toast en Inicio): se muestra a los 7 días previos y después del vencimiento, **1 vez por login** y luego cada 24 h. Lo ven **todos los roles** de la empresa (no solo el admin). El superusuario nunca lo ve.

### Bloqueo cuando la suscripción está `vencida` (3 capas)

| Capa | Archivo | Efecto |
|---|---|---|
| `SubscriptionLockMiddleware.process_view` | `apps/core/middleware.py` | bloquea POST (catch-all) |
| decorador `@bloquea_si_vencida` | `apps/accounts/decorators.py` | GET y POST de las vistas de alta/edición → renderiza `sin_acceso.html` (403) |
| context processor `subscription_flags` | `apps/core/context_processors.py` | expone `solo_lectura` → los templates ocultan botones y muestran "Sin acceso" |

El superusuario y `account:logout` quedan siempre exentos. `request_empresa_bloqueada(request)` memoiza el resultado en el request.

---

## 7. Módulos funcionales

### 7.1 Autenticación — `apps.accounts`

Login por `username` (`LOGIN_URL = 'login'`), patrón SweetAlert (render + `redirect_url`, el JS navega al cerrar). Logout por POST desde el sidebar.

- Contraseñas hasheadas (`set_password`); los `AUTH_PASSWORD_VALIDATORS` se aplican también al alta de usuarios/empleados desde la app.
- Usuarios `is_active=False` no entran (lo filtra `ModelBackend`).
- **Freno de fuerza bruta**: tras 8 fallos de login desde una misma IP en 15 min, se bloquea esa IP durante lo que resta de la ventana (cache de Django).

### 7.2 Empresas y sucursales — `apps.companies`

- `company:list` — listado (solo superuser) con columna Suscripción y botón "Registrar pago".
- `company:create` / `company:update` — alta/edición; el update permite agregar sucursales y (superuser) editar la suscripción.
- `company:info` — **Info. compañía**: página de solo lectura para todos los roles menos superuser (datos de la empresa, sucursales, estado de suscripción e historial de pagos).
- `company:register_payment` — registrar un pago (superuser).
- Endpoint `company:get_branches_by_company` — sucursales de una empresa (para selects dependientes).

### 7.3 Usuarios (plataforma) — `apps.accounts` (superuser)

`account:list` / `create` / `update` / `deactivate` / `activate`. Ve **todos** los usuarios de todas las empresas, con columna empresa/sucursal, rol y permisos. Si el rol es Administrador, los permisos no se piden (acceso total automático).

### 7.4 Empleados (empresa) — `apps.accounts` (admin / `can_manage_employees`)

`account:employees` + `employee_create/update/deactivate/activate`. Decorador `@gestor_empleados_required` (acepta `permitir_superuser=True` solo en el listado).

- **Admin**: gerentes y empleados de toda su empresa.
- **Gestor no-admin** (`can_manage_employees`): solo empleados de **su sucursal** (`empleados_de_empresa` filtra por `branch_id` del actor), y con delegación de permisos limitada (ver §5).
- **Superusuario**: ve gerentes y empleados de **todas** las empresas (columna Empresa), en **solo lectura** (sin "Crear empleado" ni acciones).

### 7.5 Inventario — `apps.inventory`

- **Productos** (`inventory:product_list` + `create/update/active/inactive_product`): al crear un producto se genera un `BranchStock` por sucursal (SKU único por empresa, autogenerado). Validación: no se admite otro producto con el mismo **nombre + marca** (case-insensitive) en la misma empresa. El listado muestra **una fila por producto** con las sucursales/stock apiladas en la celda (`{% regroup %}`). `active_product` / `inactive_product` son **POST + CSRF** y verifican que el producto sea de la empresa del usuario.
- **Movimientos** (`inventory:movement_list` + `create_movement`): historial de entradas/salidas/ventas con filtro por rango de fechas. Columna `#` correlativa por pantalla (no expone el id de BD).
- `LOW_STOCK = 5` — umbral de "stock bajo".

### 7.6 Ventas — `apps.sales`

- `sales:sale_list` — listado con filtro por fechas y columna `#` correlativa.
- `sales:create_sale` — **carrito multi-producto**: una venta acepta varios productos; cada `SaleItem` congela el `unit_price`. Al confirmar se descuenta stock y se generan `StockMovement` tipo `SALE`.
- Picker de producto con Select2 (búsqueda). El superusuario elige empresa → sucursal antes de vender.

### 7.7 Inicio (dashboard) — `apps.core` · `dashboard` → `home.html`

Hero header con saludo (iniciales, rol, fecha en `es-co`) + tarjetas KPI y mini-tablas, según rol:

- **Usuario de empresa** (`resumen_negocio`): sección **Ventas** (Vendido hoy / este mes / Total vendido — cada una con su conteo), sección **Inventario** (valor del stock, productos sin stock, con stock bajo), y mini-tablas "Últimas ventas" / "Últimos movimientos".
- **Superusuario** (`resumen_plataforma`): empresas, empresas activas, sucursales, productos, usuarios, suscripciones vencidas y por vencer.
- Toast de suscripción (ver §6).

### 7.8 Reportes — `apps.core` · `reports` → `reports.html`

Acceso: superuser / `admin` / `can_view_reports` (si no, redirige a Inicio). Enlace en el sidebar.

- **Filtro por rango de fechas** (`filtrar_por_fecha`), por defecto **el mes en curso**.
- **Resumen del período**: nº de ventas, total vendido, ticket promedio, unidades vendidas.
- **Gráfica** (Chart.js): ventas por día — barras de **Total ($)** (eje izq.) + línea de **Unidades** (eje der.).
- **Ventas por sucursal** (tabla) y **Top 10 productos** (unidades + total).
- **Movimientos del período**: entradas / salidas / ventas (conteo + unidades).
- **Stock actual** (no depende del rango): valor, sin stock, stock bajo.
- **Exportar a Excel** (`?export=xlsx`): `.xlsx` con `openpyxl` — título + período, encabezado con estilo, columnas `Fecha · Sucursal · Vendedor · Productos · Unidades · Total`, formato de fecha y moneda, autofiltro, panel congelado y fila **TOTAL** que suma unidades y valor.

Toda la lógica de agregación vive en `apps/core/stats.py` (`reporte_negocio`, `resumen_negocio`, `resumen_plataforma`, helper `_stock_actual`).

---

## 8. Convenciones transversales

| Elemento | Detalle |
|---|---|
| `@permiso_modulo("can_manage_inventory" / "can_manage_sales" / "can_view_reports")` | decorador en `apps/accounts/decorators.py`. Deja pasar a superuser, admin de negocio o a quien tenga el flag; si no, rebota al dashboard. Se aplica a **todas** las vistas de inventario, ventas y reportes (no solo en el sidebar). Va debajo de `@login_required` |
| `filtrar_por_fecha` | lee `?date_from` / `?date_to` (inclusive); acepta `default_from` / `default_to`; devuelve `(qs, date_from, date_to)` |
| filtro `pesos` (`{% load money %}`) | monto completo hasta el millón (`$225.000,00`); de ahí abreviado: `$1,1M`, `$1,1B` |
| `includes/kpi.html` | tarjeta KPI reutilizable — params: `icon`, `value`, `label`, `tone` (`danger`/`warning`), `money`, `sub` |
| `{% block scripts %}` | en `layout.html`, al final del body — para JS por página (lo usa Reportes con Chart.js) |
| Columna `#` en listados | `{{ forloop.counter }}` (correlativo visible), nunca el `id` de BD |
| DataTables | tablas con clase `js-datatable`; **nunca** filas `{% empty %}` con `colspan` dentro de ellas (rompen DataTables) |
| Patrón SweetAlert redirect | la vista renderiza con `redirect_url` en el contexto; el JS navega al cerrar el modal |
| Baja lógica | casi todo usa `is_active` en vez de borrar |

---

## 9. Testing

`python manage.py test` — **92 tests** (accounts 24 · companies 18 · inventory 24 · core 17 · sales 9).

Cubren: reglas company/branch del usuario, permisos por rol, alcance por empresa/sucursal, duplicados de producto, carrito de ventas y descuento de stock, suscripción (estados, pago, bloqueo, toast), dashboard KPIs, Reportes (permisos, totales, filtro de fechas, export `.xlsx`) y **seguridad** (gate `@permiso_modulo` server-side, IDOR de producto, `active/inactive_product` solo POST, escalada de gestor, contraseña débil rechazada, throttle de login).

---

## 10. Seguridad

Medidas aplicadas:

- **Autenticación**: todas las vistas exigen `@login_required`; login por `username` con contraseña hasheada; usuarios `is_active=False` no entran.
- **Autorización server-side**: `@superuser_required` (gestión de empresas/usuarios), `@gestor_empleados_required` (empleados), `@permiso_modulo(...)` (inventario / ventas / reportes). Los permisos ya **no** dependen del sidebar.
- **Aislamiento entre empresas**: empresa/sucursal salen del usuario logueado, no del POST; `update_product` / `active_product` / `inactive_product` verifican que el producto sea de la empresa del usuario; querysets acotados + `get_object_or_404`.
- **CSRF**: middleware activo; todas las acciones que cambian estado son `POST` con token (`active/inactive_product`, `active/inactive_branch`, bajas de usuario/empleado, logout).
- **Contraseñas**: `AUTH_PASSWORD_VALIDATORS` se aplican también al crear usuarios/empleados desde la app (largo mínimo, no numérica, no común).
- **Fuerza bruta**: el login bloquea una IP tras 8 fallos en 15 min (cache de Django; con varios procesos conviene un cache compartido tipo Redis).
- **Delegación de permisos**: un gestor no-admin solo puede otorgar `can_manage_inventory` / `can_manage_sales` a empleados de **su** sucursal (nunca `can_manage_employees` ni `can_view_reports`).
- **Admin de Django**: `CustomUser` usa `UserAdmin` (hash de contraseña de solo lectura, no texto plano).
- **Cabeceras / cookies**: `X-Frame-Options: DENY`, `SECURE_CONTENT_TYPE_NOSNIFF`, sesión HttpOnly de 8 h; con `DEBUG=False` se activan `SECURE_SSL_REDIRECT`, `SESSION/CSRF_COOKIE_SECURE` y HSTS.
- **Export Excel**: los textos que empiezan con `= + - @` se neutralizan para evitar formula injection.

Configuración para desplegar (variables de entorno):

| Variable | Uso |
|---|---|
| `DJANGO_SECRET_KEY` | clave secreta (rotar la del repo) |
| `DJANGO_DEBUG` | `0` en producción |
| `DJANGO_ALLOWED_HOSTS` | hosts, coma-separados |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | orígenes https, coma-separados |

Verificación: `python manage.py check --deploy`.

---

## 11. Notas y pendientes conocidos

- No hay pasarela de pago: la gestión de suscripciones es manual por el superusuario.
- `requirements.txt` conviene mantenerlo en **UTF-8** (si se regenera con `>` en PowerShell queda en UTF-16 y pip puede fallar).
- El botón desactivar/activar empresa en el listado apunta a `action="#"` (no implementado).
- El freno de login usa el cache local (por proceso); para producción multi-proceso, configurar un cache compartido.
- `docs/` está en `.gitignore`: este archivo no se versiona (sacar `docs/` del ignore si se quiere en el repo).
- Rama de trabajo actual: `refactor/clean-code`.
