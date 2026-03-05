# Prueba Tecnica: Data & Ops Generalist Intern
**Puesto:** Pasante Generalista de Datos / Operaciones — Equipo de Crecimiento

---

## Parte 1 — SQL

- Las "ultimas 8 semanas" se calculan desde el inicio de la semana actual hacia atras usando `DATE_TRUNC`.
- El gasto de marketing se asocia al canal por `mkt_master.source` y los desembolsos por `app_master.mkt_source`.
- Si un canal no tuvo desembolsos en una semana, el CAC se reporta como NULL con una nota explicativa en lugar de generar un error.
- El gasto desperdiciado es una estimacion basada en costo-por-clic promedio de cada campana, ya que `mkt_master` no tiene costo exacto por usuario.

---

### 1a) CAC Semanal por Canal

```sql
WITH weekly_spend AS (
    SELECT
        DATE_TRUNC('week', stats_day)  AS week_start,
        source                          AS channel,
        SUM(spend)                      AS total_spend
    FROM mkt_master
    WHERE stats_day >= DATE_TRUNC('week', CURRENT_DATE) - INTERVAL '8 weeks'
    GROUP BY 1, 2
),

weekly_disbursements AS (
    SELECT
        DATE_TRUNC('week', booking_created_at)  AS week_start,
        mkt_source                               AS channel,
        COUNT(*)                                 AS total_disbursements
    FROM app_master
    WHERE booking = TRUE
      AND booking_created_at >= DATE_TRUNC('week', CURRENT_DATE) - INTERVAL '8 weeks'
    GROUP BY 1, 2
)

SELECT
    COALESCE(s.week_start,  d.week_start)  AS week_start,
    COALESCE(s.channel,     d.channel)     AS channel,
    COALESCE(s.total_spend, 0)             AS total_spend_mxn,
    COALESCE(d.total_disbursements, 0)     AS total_disbursements,
    CASE
        WHEN COALESCE(d.total_disbursements, 0) = 0
        THEN NULL
        ELSE ROUND(COALESCE(s.total_spend, 0) / d.total_disbursements, 2)
    END AS cac_mxn,
    CASE
        WHEN COALESCE(d.total_disbursements, 0) = 0
        THEN 'Sin desembolsos esa semana'
        ELSE NULL
    END AS nota
FROM weekly_spend s
FULL OUTER JOIN weekly_disbursements d
    ON  s.week_start = d.week_start
    AND s.channel    = d.channel
ORDER BY week_start DESC, channel;
```

**Por que FULL OUTER JOIN:** puede haber semanas con gasto pero cero desembolsos, o desembolsos sin gasto registrado.

**Por que NULLIF / COALESCE:** para manejar la division por cero sin que la query falle ni devuelva NULLs sin explicacion.

---

### 1b) Gasto Desperdiciado en Solicitantes Existentes

```sql
WITH borrowers AS (
    SELECT DISTINCT user_id
    FROM app_master
    WHERE booking = TRUE
),

clicks_on_borrowers AS (
    SELECT
        m.source                            AS channel,
        m.clicked_user_id,
        m.spend / NULLIF(m.clicks, 0)       AS cost_per_click
    FROM mkt_master m
    INNER JOIN borrowers b
        ON m.clicked_user_id = b.user_id
    WHERE m.stats_day >= CURRENT_DATE - INTERVAL '30 days'
)

SELECT
    channel,
    COUNT(DISTINCT clicked_user_id)         AS usuarios_desperdiciados,
    ROUND(SUM(cost_per_click), 2)           AS gasto_desperdiciado_mxn
FROM clicks_on_borrowers
GROUP BY channel
ORDER BY gasto_desperdiciado_mxn DESC;
```

**Supuesto:** el gasto desperdiciado es una estimacion basada en costo-por-clic promedio (`spend / clicks`) de cada fila de campana. No se tiene el costo exacto por usuario desde `mkt_master`.

---

### 1c) Exportacion para Exclusion de Audiencias

```sql
SELECT DISTINCT ON (a.user_id)
    a.email,
    a.phone,
    a.user_id,
    DATE(a.booking_created_at)  AS disbursement_date
FROM app_master a
WHERE a.booking = TRUE
  AND a.email   IS NOT NULL
  AND a.phone   IS NOT NULL
ORDER BY a.user_id, a.booking_created_at DESC;
```

**Por que DISTINCT ON:** si un usuario tiene multiples prestamos, se toma el mas reciente. Meta rechazaria duplicados y contaria doble al usuario en la audiencia.

---

## Parte 2 — Python + Automatizacion

### 2a) Script de Exportacion

> **El codigo completo se adjunta como `export.py`.**

El script hace lo siguiente:

1. Carga credenciales desde `.env` usando `python-dotenv` — las credenciales nunca se escriben directo en el codigo.
2. Conecta a PostgreSQL via `SQLAlchemy` (recomendado por pandas para evitar warnings de DBAPI2).
3. Ejecuta la query de la Parte 1c.
4. Exporta el resultado a un CSV con nombre dinamico: `exclusion_audience_YYYY-MM-DD.csv`.

**Librerias utilizadas:** `sqlalchemy`, `pandas`, `psycopg2-binary`, `python-dotenv`, `requests`, `hashlib`.

**Variables de entorno requeridas en `.env`:**
```
DB_HOST=localhost
DB_PORT=5433
DB_NAME=fintech_test
DB_USER=postgres
DB_PASSWORD=fintech123
META_ACCESS_TOKEN=EAABxxxxxx...
META_AD_ACCOUNT_ID=act_XXXXXXXXXX
```

**Como correrlo:**
```bash
python3 -m venv venv
source venv/bin/activate
pip install sqlalchemy pandas psycopg2-binary python-dotenv requests
python3 export.py
```

---

### 2b) Meta API Upload

> **La implementacion completa del upload esta incluida en el archivo `export.py` adjunto.**  
> A continuacion se describe el flujo y las decisiones de diseno.

**Flujo de integracion:**

1. **Autenticacion:** token de acceso de larga duracion (60 dias) o System User token (sin expiracion), guardado en `.env`. Nunca hardcodeado en el codigo.

2. **Crear la audiencia:**
```
POST https://graph.facebook.com/v19.0/{AD_ACCOUNT_ID}/customaudiences
```
Meta responde con un `audience_id` que se usa en el siguiente paso.

3. **Hasheo de datos:** antes de enviar, email y telefono se convierten a SHA-256. Meta requiere esto para proteger la privacidad del usuario — compara hashes con los de sus propios usuarios, nadie ve los datos en texto plano.

4. **Subir usuarios:**
```
POST https://graph.facebook.com/v19.0/{audience_id}/users
```
Payload:
```json
{
  "payload": {
    "schema": ["EMAIL", "PHONE"],
    "data": [
      ["sha256_email_1", "sha256_phone_1"],
      ["sha256_email_2", "sha256_phone_2"]
    ]
  },
  "access_token": "EAABxxxxxx..."
}
```

**Manejo de errores implementado en el script:**

| Error | Accion |
|---|---|
| `429 Rate Limit` | Esperar y reintentar — Meta permite ~200 llamadas/hora |
| `400 Datos invalidos` | Verificar que los hashes esten en lowercase y sin espacios |
| `190 Token expirado` | Renovar el long-lived token |
| Mas de 10,000 usuarios | Dividir en chunks de 10,000 por llamada (implementado en el script) |

---

### 2c) Programación de Tareas

Se presentan dos opciones segun el perfil tecnico del equipo. Ambas logran el mismo objetivo: correr `export.py` automaticamente todos los dias sin intervencion manual.

---

**Opcion 1 — GitHub Actions**

GitHub Actions ejecuta el script en los servidores de GitHub en un horario definido. No se necesita servidor propio.

```yaml
name: Exclusion Audience Diaria

on:
  schedule:
    - cron: '0 8 * * *'   # 8am UTC = 2am Mexico

jobs:
  exportar:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install sqlalchemy pandas psycopg2-binary python-dotenv requests
      - name: Correr script
        env:
          DB_HOST:            ${{ secrets.DB_HOST }}
          DB_PORT:            ${{ secrets.DB_PORT }}
          DB_NAME:            ${{ secrets.DB_NAME }}
          DB_USER:            ${{ secrets.DB_USER }}
          DB_PASSWORD:        ${{ secrets.DB_PASSWORD }}
          META_ACCESS_TOKEN:  ${{ secrets.META_ACCESS_TOKEN }}
          META_AD_ACCOUNT_ID: ${{ secrets.META_AD_ACCOUNT_ID }}
        run: python export.py
```

> Las credenciales se guardan en **GitHub → Settings → Secrets and variables → Actions**. GitHub las inyecta como variables de entorno al momento de correr — nadie puede verlas, ni los admins del repo.

Ventajas: sin servidor propio, historial de ejecuciones con logs, alertas automaticas por email si falla, 2,000 minutos gratis al mes.

---

**Opcion 2 — N8N (recomendada para equipo no tecnico)**

N8N es una herramienta de automatizacion visual open source. El flujo se construye conectando nodos graficamente, sin escribir codigo. Ideal si el equipo de growth quiere operar la automatizacion sin depender del equipo tecnico.

**Flujo de nodos en N8N:**

```
[ Schedule Trigger ]  -->  [ Execute Command ]  -->  [ IF: exito? ]
  Todos los dias                                           |          |
  a las 2am              python3 export.py               SI         NO
                                                          |          |
                                               [ Slack: OK ]  [ Slack: ERROR + log ]
```

**Descripcion de cada nodo:**

1. **Schedule Trigger** — define la frecuencia. Se configura visualmente: cada dia, hora especifica, dia de la semana. No hay que recordar la sintaxis de cron.

2. **Execute Command** — corre el script Python en el servidor donde esta instalado N8N:
   ```
   cd /ruta/prueba_tecnica && source venv/bin/activate && python3 export.py
   ```

3. **IF** — revisa si el comando termino con exit code 0 (exito) o distinto de 0 (error).

4. **Slack / Email** — notifica al equipo automaticamente con el resultado. Si fallo, incluye el mensaje de error para diagnosticar rapido.

Ventajas: interfaz visual sin codigo, historial de ejecuciones con logs graficos, alertas integradas a Slack/email, facil de modificar por cualquier persona del equipo.

Desventajas: requiere tener N8N instalado en un servidor (self-hosted) o pagar el plan cloud (~$20 USD/mes).

---

**Comparativa**

| Criterio | GitHub Actions | N8N |
|---|---|---|
| Costo | Gratis (2,000 min/mes) | Gratis self-hosted / $20 USD cloud |
| Servidor propio | No | Si (self-hosted) |
| Requiere codigo | Si (YAML) | No (visual) |
| Logs / historial | Automatico | Automatico |
| Alertas de fallo | Si (email) | Si (Slack/email) |
| Perfil ideal | Equipo con GitHub | Equipo de growth no tecnico |

---

## Parte 3 — Diseño y Razonamiento

### 3a) Otras Audiencias Utiles

**Audiencia 1 — Solicitantes Rechazados (Lookalike Seed)**

```sql
SELECT email, phone
FROM app_master
WHERE approved = FALSE
  AND application_day >= CURRENT_DATE - INTERVAL '90 days'
```

- **Por que es valiosa:** los rechazados mostraron intencion de compra fuerte. Meta puede construir un Lookalike del 1% con este segmento para encontrar perfiles similares que si califiquen, mejorando la calidad de prospectos y reduciendo el CAC.
- **Frecuencia:** semanal.

---

**Audiencia 2 — Drop-offs (Solicitud Iniciada pero No Completada)**

```sql
SELECT email, phone
FROM app_master
WHERE (approved IS NULL OR booking = FALSE)
  AND application_day >= CURRENT_DATE - INTERVAL '30 days'
```

- **Por que es valiosa:** ya mostraron interes concreto. El CAC de retargeting a drop-offs suele ser 3-5x menor que adquirir usuarios nuevos.
- **Frecuencia:** diaria.

---

**Audiencia 3 — Borrowers con Prestamo Pagado (Upsell / Reactivacion)**

```sql
SELECT a.email, a.phone
FROM app_master a
JOIN users u ON a.user_id = u.id
WHERE a.booking = TRUE
  AND u.status = 'active'
  AND a.booking_created_at <= CURRENT_DATE - INTERVAL '60 days'
```

- **Por que es valiosa:** ya confiaron en la marca, pasaron KYC y demostraron que pagan. LTV 2-4x mayor que clientes nuevos.
- **Frecuencia:** semanal.

---

### 3b) Debugging — TikTok Spend Data Desaparecio

**Paso 1 — Confirmar en la BD:**

```sql
SELECT source, MAX(stats_day) AS ultimo_dato, COUNT(*) AS filas, SUM(spend) AS gasto
FROM mkt_master
WHERE stats_day >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY source ORDER BY source;
```

**Paso 2 — Acotar fecha exacta:**

```sql
SELECT stats_day, COUNT(*) AS filas, SUM(spend) AS gasto
FROM mkt_master WHERE source = 'tiktok'
GROUP BY stats_day ORDER BY stats_day DESC;
```

**Paso 3 — Arbol de decision:**

1. ¿Hay datos en TikTok Ads Manager? → Si: problema en pipeline. No: problema en cuenta/campanas.
2. ¿El token de API expiro? (~30 dias) → Si: renovar. No: revisar logs del ETL.

**Causas mas comunes:** token expirado, ETL fallando silenciosamente, cambio en la API de TikTok, credenciales de cuenta cambiadas.

**Prevencion:**
```sql
-- Alerta si algun canal no tiene datos en los ultimos 2 dias
SELECT source FROM mkt_master
GROUP BY source
HAVING MAX(stats_day) < CURRENT_DATE - INTERVAL '2 days';
```

---

### 3c) Exclusion en Tiempo Real via Webhook

**Tecnologia:** FastAPI (Python) — asincrono, rapido de implementar, mismo stack que el proyecto.

**Payload entrante:**
```json
{
  "event":        "loan_disbursed",
  "user_id":      "USR001",
  "email":        "ana.garcia@gmail.com",
  "phone":        "5512345001",
  "amount":       15000,
  "currency":     "MXN",
  "disbursed_at": "2026-03-04T17:30:00Z",
  "signature":    "sha256=abc123..."
}
```

**Arquitectura:**
```
Sistema interno -> POST /webhook/loan-disbursed
                -> Validar firma HMAC
                -> Hashear email/phone en SHA-256
                -> POST /{audience_id}/users -> Meta API
                -> Guardar log en BD
                -> 200 OK
```

**Edge cases:**

| Caso | Solucion |
|---|---|
| Meta falla | Cola de reintentos con backoff exponencial |
| Request falso | Validar firma HMAC, rechazar con 401 |
| Usuario duplicado | Deduplicar por user_id |
| Timeout de Meta | Responder 200 inmediatamente, procesar async |
| Token expirado | Monitorear y renovar automaticamente |

**Recomendacion:** mantener webhook + batch diario juntos. El webhook hace la exclusion en tiempo real; el batch es la red de seguridad. Juntos garantizan que ningun borrower quede sin excluir.

---

*Supuestos generales: las queries fueron validadas contra PostgreSQL 16 con datos de prueba representativos de una fintech.*
