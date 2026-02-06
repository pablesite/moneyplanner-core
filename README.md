# moneyplanner

Gestor de patrimonio personal con frontend en Vue y backend en Django/DRF. Incluye docker-compose para desarrollo local, seeders mínimos y utilidades de backup/restore de PostgreSQL.

**Stack**
1. Frontend: Vue 3 + Vite
2. Backend: Django + DRF + SimpleJWT
3. DB: PostgreSQL 16
4. Infra local: Docker Compose

**Requisitos**
1. Docker Desktop
2. Git Bash (solo para scripts de backup/restore en Windows)

**Arranque rápido (Docker)**
1. Crea el archivo `backend/.env` con las variables mínimas.
2. Levanta todo con Docker Compose.

```bash
docker compose up --build
```

Endpoints locales:
1. Frontend: `http://localhost:5173`
2. Backend API: `http://localhost:8000`

**Variables de entorno**
El backend lee `backend/.env`. Ejemplo mínimo recomendado:

```env
DJANGO_SECRET_KEY=dev-insecure-secret
DJANGO_DEBUG=1
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
CORS_ALLOWED_ORIGINS=http://localhost:5173

DB_NAME=saas
DB_USER=saas
DB_PASSWORD=saas
DB_HOST=db
DB_PORT=5432

SEED_CREATE_ADMIN=1
SEED_ADMIN_USERNAME=admin
SEED_ADMIN_EMAIL=admin@example.com
SEED_ADMIN_PASSWORD=admin
SEED_FORCE_ADMIN_PASSWORD=0
```

Notas:
1. Si cambias `DB_*`, asegúrate de alinear también `POSTGRES_*` en `docker-compose.yml` o usa los valores por defecto.
2. `CORS_ALLOWED_ORIGINS` debe incluir el origen del frontend.

**Seeders (datos iniciales)**
Al arrancar con Docker, el backend ejecuta automáticamente:
1. `python manage.py migrate`
2. `python manage.py seed`

El seeder crea o asegura:
1. Un usuario admin (configurable por `SEED_*`).
2. Tipos de cambio FX mínimos.
3. Índices de IPC base y actual.

Puedes ejecutarlo manualmente así:

```bash
docker compose exec backend python manage.py seed
```

**Migraciones**
En Docker se ejecutan automáticamente al arrancar. Si cambias modelos:

```bash
docker compose exec backend python manage.py makemigrations
docker compose exec backend python manage.py migrate
```

**Backup y restore de base de datos (local dev)**
Scripts seguros para PostgreSQL en Docker. Recomendado usar Git Bash en Windows.

Crear backup:

```bash
"C:\Program Files\Git\usr\bin\bash.exe" scripts/db_dump.sh
```

Alternativa en Windows (CMD directo):

```bat
dump-db.cmd
```

Restaurar el último backup:

```bash
"C:\Program Files\Git\usr\bin\bash.exe" scripts/db_restore_latest.sh
```

Alternativa en Windows (CMD directo):

```bat
restore-db.cmd
```

Puedes configurar opciones locales en `scripts/.env`:
1. `DB_CONTAINER` (por defecto `saas_db`)
2. `DB_NAME` (por defecto `saas`)
3. `DB_USER` (por defecto `saas`)
4. `DB_DUMP_DIR` (por defecto `backups`)

Notas:
1. Los dumps se verifican con `pg_restore -l` antes de restaurar.
2. Se crea un backup de seguridad automáticamente antes de restaurar.
3. La restauración reinicia el contenedor `backend`.

**Primeros pasos en la app**
1. Inicia sesión con el usuario admin creado por el seeder.
2. Ve a Personas y crea miembros familiares.
3. Revisa Titularidades: las individuales se generan automáticamente.
4. Crea Activos y Pasivos y asígnales una titularidad.
5. Vuelve a Patrimonio para ver el resumen y desglose.

**Troubleshooting rápido**
1. Puertos ocupados: cambia los puertos en `docker-compose.yml`.
2. La API no responde: revisa logs con `docker compose logs -f backend`.
3. Problemas de CORS: ajusta `CORS_ALLOWED_ORIGINS` en `backend/.env`.
