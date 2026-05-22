# Decisiones de seguridad en el pipeline de CI

_Última actualización: 2026-05-22_

Este documento recoge las decisiones de seguridad no obvias tomadas en el pipeline de CI,
el razonamiento detrás de cada una y las condiciones bajo las que deberían revisarse.

---

## 1. Trivy: `ignore-unfixed: true`

**Dónde**: `ci-main.yml` → job `docker-build-push` → step `Trivy scan`

**Qué hace**: Trivy escanea las imágenes Docker de producción buscando CVEs con severidad
CRITICAL o HIGH. Con `ignore-unfixed: true`, solo bloquea el pipeline cuando existe un parche
disponible para el CVE encontrado. Los CVEs sin fix publicado se siguen reportando en el
Security tab de GitHub pero no impiden el despliegue.

**Por qué se tomó esta decisión**: La imagen base `python:3.12-slim` usa Debian como OS.
Debian publica parches con cierto retraso respecto al descubrimiento de CVEs. Al mergear
el primer pipeline de producción (2026-05-22), Trivy bloqueó por `ncurses CVE-2025-69720`
(buffer overflow, HIGH) para el que Debian aún no tenía parche. Bloquear el deploy por un
CVE que no podemos solucionar es ruido que destruye la utilidad del pipeline.

**Lo que sigue bloqueando**: cualquier CVE CRITICAL o HIGH con fix disponible, tanto en
paquetes del OS como en dependencias Python/npm de la aplicación.

**Lo que NO bloquea**: CVEs en paquetes del OS base (Debian) para los que aún no existe
parche publicado upstream. Estos siguen visibles en GitHub → Security → Code scanning.

**Cuándo revisar esta decisión**:
- Si se cambia la imagen base a `python:3.12-alpine` (Alpine tiene mucha menor superficie
  de ataque y menos CVEs sin fix; es la mejora natural a medio plazo).
- Si aparece un CVE crítico sin fix que requiera acción manual (e.g. eliminar el paquete
  afectado o usar una imagen distinta).

**Alternativa pendiente**: migrar a `python:3.12-alpine` reduciría drásticamente los CVEs
de OS. Requiere validar que `libpq-dev` y las dependencias de compilación funcionen igual
en Alpine. Anotado como mejora futura en el roadmap de seguridad.

---

## 2. npm audit: `--omit=dev --audit-level=high`

**Dónde**: `quality(-core).yml` → job `Dependency audit` → step `npm audit (production deps)`

**Qué hace**: audita solo las dependencias de producción (excluye devDependencies) y solo
falla ante vulnerabilidades HIGH o CRITICAL.

**Por qué**: las devDependencies (vite, rollup, eslint, prettier…) son herramientas de
build que no llegan a la imagen de producción ni al navegador del usuario final. Auditarlas
con el mismo umbral que las deps de producción genera falsos positivos constantes (vite y
rollup tienen CVEs frecuentes en versiones menores que no afectan a producción).

**Lo que sigue vigilando**: axios, vue, pinia, chart.js y cualquier otra dependencia que
se empaqueta y se sirve al navegador.

**Cuándo revisar**: si alguna devDependency se usa en un contexto donde su output llega
a producción (e.g. un script de build que genera código ejecutado en servidor).

---

## 3. pip-audit: dependencias Python sin umbral de severidad

**Dónde**: `quality(-core).yml` → job `Dependency audit` → step `pip-audit (backend)`

**Qué hace**: `pip-audit -r requirements.txt` falla ante cualquier CVE conocido,
independientemente de la severidad.

**Por qué**: a diferencia de npm, el backend Python corre en servidor con acceso a la base
de datos. El umbral de tolerancia debe ser cero — cualquier CVE en una dependencia Python
de producción debe resolverse antes de mergear.

**Historial**: Django 6.0.2 tenía 10 CVEs (PYSEC-2026-*, CVE-2026-*) cuando se activó el
pipeline (2026-05-22). Se actualizó a 6.0.5 para pasar el check.

---

## Herramientas activas en el pipeline

| Herramienta | Dónde corre | Qué cubre | Bloquea merge |
|-------------|-------------|-----------|---------------|
| Gitleaks | `quality.yml` — PRs | Secretos en historial git | Sí |
| pip-audit | `quality.yml` — PRs | CVEs en deps Python | Sí (cualquier severidad) |
| npm audit | `quality.yml` — PRs | CVEs en deps npm producción | Sí (HIGH+) |
| CodeQL | `codeql.yml` — PRs + cron | SAST Python + TypeScript | No (informativo) |
| Trivy | `ci-main.yml` — push main | CVEs en imágenes Docker | Sí (HIGH+ con fix) |

CodeQL no bloquea el merge porque sus resultados tardan más y son más apropiados para
revisión manual en el Security tab. Se evalúa su inclusión como check requerido cuando
el proyecto tenga más contribuidores externos.
