# Prueba para Llevar a Casa: Pasante de Datos & Operaciones

**Puesto:** Pasante Generalista de Datos / Operaciones — Equipo de Crecimiento
**Tiempo estimado:** ~2 horas
**Entregable:** Un solo documento (Google Doc, Notion, PDF o repositorio de GitHub) con tus respuestas. Incluye SQL, código y explicaciones escritas claramente etiquetadas por sección.

---

## Contexto

Trabajas en una fintech en México que adquiere usuarios a través de anuncios en Meta (Facebook/Instagram), Google y TikTok. El embudo de usuarios se ve así:

```
Impresión de Anuncio → Clic → Visita → Registro → Solicitud → Aprobación → Préstamo Desembolsado
```

Tienes acceso a una base de datos PostgreSQL con las siguientes tablas:

```sql
-- Datos de gasto en marketing (una fila por día por campaña)
mkt_master (
  stats_day DATE,
  source TEXT,              -- 'meta', 'google', 'tiktok'
  ad_campaign_name TEXT,
  spend NUMERIC,            -- MXN (Pesos Mexicanos)
  impressions INT,
  clicks INT
)

-- Datos de solicitudes y conversiones
app_master (
  application_day DATE,
  user_id TEXT,
  email TEXT,
  phone TEXT,
  mkt_source TEXT,          -- 'meta', 'google', 'tiktok', 'wom'
  approved BOOLEAN,
  booking BOOLEAN,          -- true = préstamo fue desembolsado
  booking_created_at TIMESTAMPTZ
)

-- Datos de usuarios
users (
  id TEXT,
  email TEXT,
  phone TEXT,
  created_at TIMESTAMPTZ,
  status TEXT                -- 'active', 'rejected', 'expired'
)
```

---

## Parte 1 — SQL (~30 min)

Escribe consultas SQL para lo siguiente. Indica los supuestos que hagas.

### 1a) CAC Semanal por Canal

Calcula el **CAC semanal (Costo por Préstamo Desembolsado)** por canal para las últimas 8 semanas.

- CAC = Gasto Total / Total de Desembolsos
- Maneja las semanas en que un canal tiene cero desembolsos (la consulta no debe fallar ni devolver nulos sin explicación).

### 1b) Gasto Desperdiciado en Solicitantes Existentes

Encuentra usuarios que ya recibieron un préstamo (`booking = true`) pero siguen siendo impactados por anuncios — específicamente, usuarios que aparecen en la actividad de clics de `mkt_master` en los últimos 30 días.

Para esta pregunta, asume que `mkt_master` tiene una columna adicional `clicked_user_id TEXT` que vincula los clics a usuarios conocidos.

Devuelve: cuántos usuarios existen **por canal**, y cuál es el **gasto estimado que se está desperdiciando** en ellos.

### 1c) Exportación para Exclusión de Audiencias

Escribe una consulta que genere un resultado listo para CSV de todos los usuarios con un préstamo desembolsado. La salida debe tener exactamente estas columnas:

| Columna | Descripción |
|--------|-------------|
| `email` | Correo electrónico del usuario |
| `phone` | Teléfono del usuario |
| `user_id` | ID del usuario |
| `disbursement_date` | Fecha en que se desembolsó el préstamo |

Este archivo será subido a Meta como lista de exclusión de Audiencias Personalizadas.

---

## Parte 2 — Python + Automatización (~45 min)

### 2a) Script de Exportación

Escribe un script de Python que:

1. Se conecte a una base de datos PostgreSQL usando credenciales desde variables de entorno
2. Ejecute la consulta de la Parte 1c
3. Exporte el resultado a un archivo CSV llamado `exclusion_audience_YYYY-MM-DD.csv` (usando la fecha de hoy)

Usa las librerías que prefieras. El código debe ser ejecutable.

### 2b) Subida a la API de Meta

Extiende el script (o describe en pseudocódigo) cómo subirías ese CSV como una **Audiencia Personalizada** a Meta para exclusión de anuncios.

No necesitas una clave API funcional — describe o codifica:

- Qué endpoints de la API de Meta usarías
- Cómo funciona la autenticación (tokens de acceso, configuración de app)
- Cómo se ve el payload de la solicitud
- Cómo manejarías errores (límites de tasa, datos inválidos, etc.)

### 2c) Programación de Tareas

¿Cómo programarías este script para que se ejecute automáticamente cada día?

Describe al menos **dos enfoques** (p. ej., cron, N8N, Airflow, AWS Lambda, GitHub Actions, etc.) y recomienda cuál elegirías para un equipo de crecimiento pequeño. Explica por qué.

---

## Parte 3 — Diseño y Razonamiento (~20 min)

### 3a) Otras Audiencias Útiles

Más allá de excluir a los solicitantes existentes, nombra **3 otras audiencias** que automatizarías para generar y sincronizar con Meta.

Para cada una, explica:

- Qué datos usarías para construirla
- Por qué es valiosa para el crecimiento
- Con qué frecuencia la actualizarías

### 3b) Depuración de un Pipeline de Datos

El equipo de marketing reporta que **los datos de gasto de TikTok dejaron de aparecer** hace aproximadamente 2 semanas. Todo lo demás parece normal.

Explica cómo investigarías esto:

- ¿Qué revisarías primero?
- ¿En qué orden?
- ¿Qué herramientas o consultas usarías?

### 3c) Exclusión en Tiempo Real vía Webhook

En lugar de esperar la exportación diaria por lotes, te piden construir un sistema que **inmediatamente** agregue a un usuario a la audiencia de exclusión de Meta en el momento en que se desembolsa un préstamo.

Esquematiza la arquitectura:

- ¿Qué tecnología usarías para el endpoint del webhook?
- ¿Cómo se ve el payload entrante?
- ¿Cómo se dispara la actualización de la API de Meta?
- ¿Qué manejo de errores o casos extremos importan?

Un diagrama o arquitectura en viñetas está bien — no buscamos código de producción aquí.

---

## Qué Evaluamos

| Área | Lo que buscamos |
|------|----------------------|
| **SQL** | Joins correctos, agregaciones, manejo de casos extremos, formato limpio |
| **Python** | Código funcional, manejo de variables de entorno, elección de librerías |
| **APIs / Webhooks** | Comprensión de flujos REST, patrones de autenticación, diseño de payloads |
| **Automatización** | Conocimiento práctico de programación de tareas, razonamiento sobre trade-offs |
| **Pensamiento de Negocio** | ¿Puedes conectar el trabajo técnico con el impacto en crecimiento? |
| **Comunicación** | Explicaciones claras, supuestos declarados, entregable organizado |

No hay preguntas trampa. Nos importa más **cómo piensas y construyes** que la perfección. Si no estás seguro de algo, declara tu supuesto y sigue adelante.

¡Buena suerte!
