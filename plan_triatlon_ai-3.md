# Plan Técnico: Sistema de Análisis de Entrenamiento Triatlón con IA

## Resumen del proyecto

Sistema local que extrae datos de entrenamientos y competiciones desde Garmin Connect, calcula métricas de rendimiento, y usa IA (Claude) para generar análisis, planes de entrenamiento personalizados y recomendaciones dietéticas adaptadas a la carga del día. La interfaz principal es un bot de Telegram que el usuario controla desde el móvil o el portátil.

El usuario practica triatlón (natación, ciclismo y running). Dispone de reloj Garmin con GPS y pulsómetro, sin medidor de potencia.

---

## Principios de diseño

- **Local first**: todos los datos y scripts corren en el portátil del usuario. Nada en la nube salvo Telegram como puente de comunicación.
- **Código limpio y desacoplado**: cada capa es independiente y sustituible. Ejemplo: la capa de IA puede pasar de Claude Code (POC) a Claude API sin tocar el resto del sistema.
- **Datos abiertos**: todo se almacena en JSON. Legible por humanos, por scripts y por cualquier IA.
- **Extensible**: arquitectura preparada para añadir interfaz visual, base de datos o despliegue en servidor en el futuro.

---

## Arquitectura general

```
Garmin Connect
      ↓
[1] garmin-connect-cli  (extracción de datos, sin coste de tokens)
      ↓
[2] JSONs /data/activities  (raw data por actividad)
      ↓
[3] Script de métricas Python  (cálculo CTL/ATL, zonas FC, volumen...)
      ↓
[4] JSONs /data/metrics  (métricas calculadas, listas para la IA)
      ↓
[5] Capa IA  (Claude Code --print en POC / Claude API en producción)
      ↓
[6] JSONs /data/plans  (planes propuestos, validados y con estado de cumplimiento)
      ↓
[7] Bot de Telegram  (interfaz conversacional, corre en el portátil)
      ↑↓
Usuario (móvil o terminal)
```

---

## Piezas del sistema

### [1] Extracción de datos — garmin-connect-cli

**Qué es:** CLI open source (github.com/eddmann/garmin-connect-cli) que se autentica en Garmin Connect con las credenciales del usuario y descarga actividades y métricas de salud.

**Por qué esta herramienta:** soporta output JSON nativo, tiene un comando `garmin-connect context` específico para generar contexto para LLMs, expone métricas clave para triatlón (VO2 max, HRV, training readiness, training load) y sigue filosofía Unix (composable con pipes y jq).

**No consume tokens de Claude.** Es una herramienta independiente.

**Datos que extrae (relevantes para triatlón):**
- Actividades: tipo (run/bike/swim), distancia, duración, FC media/máx, splits, fecha
- Métricas de salud: VO2 max, HRV, training readiness, training load, sueño
- Historial de competiciones si están registradas como actividades

**Instalación:**
```bash
curl -fsSL https://raw.githubusercontent.com/eddmann/garmin-connect-cli/main/install.sh | sh
garmin-connect auth login
```

**Uso típico desde el bot:**
```bash
garmin-connect activities list --limit 20 --json
garmin-connect context --json
garmin-connect health sleep --json
```

---

### [2] Almacenamiento — JSONs locales

**Estructura de directorios:**
```
/data
  /activities        # raw data por actividad, un JSON por entrada
  /metrics           # métricas calculadas (semanales, mensuales)
  /plans
    /training        # planes de entrenamiento propuestos y su estado
    /diet            # planes de dieta diaria
  /history           # log de cumplimiento real vs planificado
  profile.json       # perfil personal del usuario (estático, cargado siempre)
  journal.json       # diario de sensaciones post-entreno
```

**Estructura de una actividad (ejemplo):**
```json
{
  "id": "abc123",
  "date": "2025-06-01",
  "type": "running",
  "distance_km": 12.5,
  "duration_min": 62,
  "hr_avg": 148,
  "hr_max": 172,
  "pace_avg": "4:58",
  "zones": { "z1": 10, "z2": 35, "z3": 40, "z4": 12, "z5": 3 },
  "source": "garmin"
}
```

**Estructura de un plan de entrenamiento:**
```json
{
  "id": "plan_2025W23",
  "week": "2025-W23",
  "generated_at": "2025-06-01",
  "status": "validado",
  "sessions": [
    {
      "day": "lunes",
      "type": "running",
      "description": "Rodaje suave 45min Z2",
      "target_hr_zone": "Z2",
      "status": "completado",
      "actual_activity_id": "abc123"
    }
  ],
  "notes_user": "Cambié el miércoles por el jueves por trabajo"
}
```

**Estructura del perfil personal:**
```json
{
  "name": "Mateo",
  "sports": ["triathlon", "running", "cycling", "swimming"],
  "available_days": ["lunes", "martes", "jueves", "sabado", "domingo"],
  "max_hours_per_week": 10,
  "target_races": [
    { "name": "Triatlón X", "date": "2025-09-15", "distance": "olimpico" }
  ],
  "injuries_history": [],
  "dietary_restrictions": [],
  "notes": "Nunca grabo gimnasio en Garmin"
}
```

---

### [3] Script de métricas — Python

**Qué hace:** lee los JSONs de actividades y genera métricas calculadas que la IA usará como contexto.

**Métricas calculadas:**

| Métrica | Descripción |
|---------|-------------|
| CTL (Chronic Training Load) | Forma física acumulada últimas 6 semanas |
| ATL (Acute Training Load) | Fatiga aguda última semana |
| TSB (Training Stress Balance) | CTL - ATL, indica si estás fresco o cargado |
| Volumen semanal por deporte | Km y horas de run/bike/swim esta semana vs semanas anteriores |
| Distribución de zonas FC | % de tiempo en cada zona Z1-Z5 |
| Tendencia VO2 max | Evolución en últimas 8 semanas |
| Ratio cumplimiento | % de sesiones del plan ejecutadas |

**Output:** un JSON `/data/metrics/current.json` con todas las métricas listas para pasar a la IA.

**Se ejecuta automáticamente** después de cada `/sync` del bot.

---

### [4] Perfil personal — profile.json

JSON estático que la IA **siempre carga** en cada llamada. Contiene:
- Datos del usuario (deportes, disponibilidad, limitaciones)
- Competiciones objetivo con fecha y distancia
- Historial de lesiones relevantes
- Preferencias y restricciones dietéticas

Permite que las recomendaciones sean personalizadas y no genéricas. El usuario lo edita manualmente o a través del bot.

---

### [5] Capa IA — Claude (desacoplada)

**Esta capa está completamente desacoplada.** Cambiar de POC a producción solo requiere modificar esta pieza.

#### POC — Claude Code `--print` mode

El bot ejecuta Claude Code en modo no interactivo pasándole el contexto como prompt:

```bash
claude --print "$(cat prompt_template.txt) $(cat data/metrics/current.json)"
```

Claude Code puede también leer y escribir ficheros directamente del filesystem, lo que permite guardar el plan generado sin lógica extra.

**Importante:** usar la cuenta de trabajo solo para el POC. No es el uso previsto de Claude Code y puede ir contra los términos del plan corporativo si se automatiza en producción.

#### Producción — Claude API

Llamada directa desde Python usando la API de Anthropic:

```python
import anthropic

client = anthropic.Anthropic(api_key="ANTHROPIC_API_KEY")

def ask_claude(prompt: str) -> str:
    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text
```

El coste estimado es mínimo: cada análisis semanal es menos de 5.000 tokens (~0,02€).

**Prompts del sistema (ejemplos):**

- **Análisis semanal:** recibe métricas + historial de planes + perfil → devuelve análisis de forma, tendencias y observaciones
- **Plan semanal:** recibe métricas + perfil + competición objetivo + historial → devuelve plan de 7 días con sesiones detalladas
- **Dieta del día:** recibe plan de entrenamiento del día + carga acumulada + preferencias → devuelve propuesta de dieta adaptada
- **Alerta sobreentrenamiento:** si TSB < -30, aviso automático con recomendación de descanso

---

### [6] Persistencia de planes

Cada plan generado por la IA se guarda en `/data/plans/` con estado `propuesto`. El usuario lo revisa en el bot y puede:
- **Validar**: cambia estado a `validado`
- **Modificar**: edita sesiones y guarda con estado `modificado`
- **Rechazar**: genera uno nuevo

Después de cada `/sync`, el script de métricas cruza las actividades reales de Garmin con el plan validado y actualiza el estado de cada sesión (`completado` / `fallido` / `pendiente`).

La IA, en la siguiente iteración, carga el historial de cumplimiento para ajustar las recomendaciones futuras.

---

### [7] Diario de sensaciones — journal.json

El usuario puede añadir notas post-entreno desde el bot:
```
/note "Piernas muy pesadas, dormí mal anoche"
```

Se guarda con fecha y la IA lo carga como contexto adicional. Esto permite calibrar la carga real más allá de los datos de Garmin.

---

### [8] Bot de Telegram

**Qué es:** script Python que corre en el portátil del usuario. Usa la librería `python-telegram-bot`. Usa **polling** (no necesita IP pública ni servidor).

**Requisito:** el portátil debe estar encendido para que el bot responda.

**Comandos disponibles:**

| Comando | Acción |
|---------|--------|
| `/sync` | Descarga nuevas actividades de Garmin y recalcula métricas |
| `/status` | Resumen de forma actual (CTL/ATL/TSB + volumen semanal) |
| `/analyze` | Análisis completo con IA de las últimas semanas |
| `/plan` | Genera plan de entrenamiento para la semana siguiente |
| `/plan validate` | Valida el plan propuesto |
| `/diet` | Dieta del día según carga de entrenamiento |
| `/note <texto>` | Añade entrada al diario de sensaciones |
| `/races` | Lista competiciones objetivo configuradas |
| `/help` | Lista de comandos disponibles |
| chat libre | Cualquier pregunta en lenguaje natural, la IA responde con contexto cargado |

**El chat libre** carga automáticamente métricas actuales + perfil + últimos planes antes de llamar a la IA, para que cualquier pregunta tenga contexto completo.

---

## Fases de implementación

### Fase 1 — POC (prioridad)
1. Instalar y autenticar `garmin-connect-cli`
2. Script Python de extracción que vuelca actividades en JSONs locales
3. Script de métricas básico (volumen semanal, zonas FC)
4. Integración con Claude Code `--print` para análisis simple
5. Bot de Telegram con comandos `/sync`, `/status`, `/analyze`

### Fase 2 — Core completo
1. Métricas avanzadas (CTL/ATL/TSB)
2. Generación y persistencia de planes de entrenamiento
3. Diario de sensaciones
4. Validación/modificación de planes desde el bot
5. Cruce automático plan vs realidad tras `/sync`

### Fase 3 — Dieta y periodización
1. Módulo de recomendaciones dietéticas
2. Lógica de periodización (fases base/construcción/pico/tapering según competición objetivo)
3. Alertas automáticas de sobreentrenamiento

### Fase 4 — Migración a producción (si el POC funciona bien)
1. Cambiar capa IA de Claude Code a Claude API (cambio mínimo, una función)
2. Evaluar migración a Raspberry Pi para disponibilidad 24/7
3. Evaluar añadir interfaz visual (dashboard web o app)

---

## Stack tecnológico

| Componente | Tecnología |
|------------|------------|
| Lenguaje principal | Python 3.10+ |
| Extracción Garmin | garmin-connect-cli (CLI externa) |
| Almacenamiento | JSON local |
| IA (POC) | Claude Code `--print` mode |
| IA (producción) | Claude API (`anthropic` Python SDK) |
| Bot de mensajería | python-telegram-bot |
| Ejecución de comandos | subprocess (Python estándar) |
| Containerización | Docker + docker-compose |
| Gestión de credenciales | python-dotenv + fichero .env |

---

## Decisiones de diseño tomadas

- **JSON sobre CSV**: las actividades tienen estructura anidada (splits por deporte, zonas FC, etc.) que CSV no representa bien.
- **garmin-connect-cli sobre python-garminconnect**: la CLI ya está construida, mantenida, soporta JSON nativo y tiene un comando específico para generar contexto LLM.
- **Bot de Telegram sobre CLI pura**: permite uso desde el móvil sin SSH. El bot corre en el portátil vía polling, sin necesidad de servidor ni IP pública.
- **Local sobre nube**: privacidad, coste cero de infraestructura, datos bajo control del usuario.
- **Claude Code `--print` para POC**: evita coste de API key durante el desarrollo. El código está desacoplado para migrar fácilmente.
- **Sin RAG**: el volumen de datos (métricas resumidas + plan semanal) cabe cómodamente en el contexto de Claude. No es necesaria recuperación semántica.
- **Docker**: el sistema completo se dockeriza para ser portable entre máquinas con `docker compose up`. Los datos persisten en un volumen montado.
- **Credenciales en `.env`**: ninguna credencial se hardcodea ni se sube a GitHub. `.env.example` documenta qué variables son necesarias.

---

## Docker y portabilidad

El sistema se dockeriza completo para facilitar moverlo entre máquinas (portátil → Raspberry Pi → VPS) con cero fricción.

**Estructura:**
```
docker-compose.yml       # orquesta el bot + scripts
Dockerfile               # imagen Python con dependencias
/data                    # volumen montado → datos persisten entre reinicios
.env                     # credenciales locales, NUNCA sube a GitHub
.env.example             # plantilla vacía, SÍ sube a GitHub
```

**docker-compose.yml (esquema):**
```yaml
services:
  bot:
    build: .
    volumes:
      - ./data:/app/data   # JSONs persisten en el host
    env_file:
      - .env
    restart: unless-stopped
```

**Para mover el sistema a otra máquina:**
```bash
# Copiar la carpeta del proyecto (incluye /data con todos los JSONs)
rsync -av proyecto/ usuario@nuevamaquina:~/proyecto/

# En la nueva máquina
docker compose up -d
```

---

## Gestión de credenciales

Todas las credenciales se gestionan mediante variables de entorno. **Nunca se hardcodean en el código ni se suben a GitHub.**

**Fichero `.env` (local, en `.gitignore`):**
```env
TELEGRAM_BOT_TOKEN=tu_token_aqui
GARMIN_USERNAME=tu_email_garmin
GARMIN_PASSWORD=tu_password_garmin
ANTHROPIC_API_KEY=tu_api_key_si_se_usa
```

**Fichero `.env.example` (sube a GitHub, sin valores):**
```env
TELEGRAM_BOT_TOKEN=
GARMIN_USERNAME=
GARMIN_PASSWORD=
ANTHROPIC_API_KEY=
```

**`.gitignore` debe incluir siempre:**
```
.env
/data/          # opcional: si no quieres subir datos personales
```

---

## Notas para el agente implementador

- Empezar siempre por la Fase 1. No implementar fases posteriores hasta que la anterior funcione.
- La capa IA debe ser una función/módulo independiente con interfaz clara: recibe un prompt string, devuelve un string. Así el cambio POC → producción es trivial.
- Los scripts deben poder ejecutarse tanto desde el bot como desde terminal directamente (útil para desarrollo y debugging).
- Usar variables de entorno para credenciales (Telegram token, API key de Anthropic si se usa, credenciales Garmin).
- El bot debe manejar errores de forma amigable: si Garmin no responde, si la IA tarda, etc.
- Documentar el formato exacto de cada JSON para que en el futuro sea fácil añadir una base de datos o interfaz visual.
