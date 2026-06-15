# Manual de instalación y uso — BotLinkedIn

Guía paso a paso para **copiar este repositorio** y dejar el bot **funcionando**:
configuración de la API key, el modelo de IA y cómo subir tu hoja de vida.

> Los comandos están en **Windows PowerShell**. Al final hay equivalentes para
> macOS/Linux donde cambian.

---

## 1. Requisitos previos

- **Git** — https://git-scm.com/downloads
- **Python 3.11 o superior** (probado con 3.12) — https://www.python.org/downloads/
  - En el instalador de Windows marca **"Add Python to PATH"**.
- Conexión a internet.
- **(Opcional) Node.js** — solo si vas a usar el backend `agent` (Claude Code).
  Para la opción recomendada (OpenRouter) **no hace falta**.

Verifica que estén instalados:
```powershell
git --version
python --version
```

---

## 2. Copiar (clonar) el repositorio

```powershell
git clone https://github.com/alvaroivanh/BotLinkedIn.git
cd BotLinkedIn
```

---

## 3. Crear el entorno virtual e instalar dependencias

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .
```

> Si `Activate.ps1` da error de permisos, ejecuta una vez:
> `Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned` y reintenta.
> (Alternativa sin activar: usa siempre `.\.venv\Scripts\python.exe` en lugar de `python`.)

Instala el navegador que usa la automatización (necesario para *auto-postularse*):
```powershell
python -m playwright install chromium
```

---

## 4. Configurar el archivo `.env`

Crea tu archivo de configuración a partir del ejemplo:
```powershell
Copy-Item .env.example .env
```

Abre `.env` con el bloc de notas y configura la IA. **Elige UNA opción:**

### Opción A — OpenRouter + Gemini Flash (recomendada: barata y simple)
```env
AI_BACKEND=openrouter
OPENROUTER_API_KEY=sk-or-v1-tu-clave-aqui
OPENROUTER_MODEL=google/gemini-2.5-flash-lite
```

**Cómo obtener la API key de OpenRouter:**
1. Entra a https://openrouter.ai e inicia sesión (Google/GitHub/correo).
2. Ve a **Keys** (https://openrouter.ai/keys) → **Create Key** → copia la clave `sk-or-v1-...`.
3. Añade saldo en **Credits** (con USD 5 alcanza para muchísimo; Gemini Flash cuesta céntimos).
4. Pega la clave en `OPENROUTER_API_KEY`.

**Cambiar el modelo de IA:** edita `OPENROUTER_MODEL`. Opciones útiles:
| Modelo | Notas |
|---|---|
| `google/gemini-2.5-flash-lite` | El más liviano y económico (por defecto) |
| `google/gemini-2.5-flash` | Algo más capaz |
| `google/gemini-3.1-flash-lite` | Versión más nueva |

### Opción B — Anthropic (Claude)
```env
AI_BACKEND=api
ANTHROPIC_API_KEY=sk-ant-tu-clave-aqui
CLAUDE_MODEL=claude-sonnet-4-6
```
La key se crea en https://console.anthropic.com/settings/keys (requiere saldo).

### Credenciales de LinkedIn (OPCIONAL)
Solo se necesitan para **auto-postularse**. La **búsqueda de empleos NO las necesita**.
```env
LINKEDIN_EMAIL=tu@correo.com
LINKEDIN_PASSWORD=tu_contraseña
```

> 🔒 **Seguridad:** el archivo `.env` contiene secretos y ya está en `.gitignore`,
> así que **no se sube a GitHub**. No lo compartas ni lo subas a ningún sitio.

---

## 5. Poner el bot en marcha

### Opción 1 — Dashboard web (recomendada)
```powershell
python -m src.main dashboard start
```
Abre en tu navegador: **http://127.0.0.1:8000**
(Para detenerlo: `Ctrl + C` en la terminal.)

### Opción 2 — Línea de comandos (CLI)
```powershell
python -m src.main --help
```
En Windows también puedes usar el lanzador incluido: `.\bot.ps1 --help`

---

## 6. Subir tu Hoja de Vida (HV)

**No necesitas dejar el PDF en ninguna carpeta manualmente.** Hay dos formas:

### Forma A — Desde el chat del dashboard (la más fácil) 📎
1. Abre el dashboard → sección **Asistente**.
2. Haz clic en el **clip 📎** y selecciona tu HV en **PDF**.
3. Envía el mensaje. El bot **la sube, la guarda** en `data/resumes/` y la **procesa con IA** automáticamente.

### Forma B — Desde la terminal (CLI)
```powershell
python -m src.main resume parse "C:\ruta\a\tu_cv.pdf"
```
Verás una tabla con tus datos extraídos (nombre, skills, experiencia, etc.).
Solo se admite **PDF**.

Para ver la HV ya cargada:
```powershell
python -m src.main resume show
```

> La HV se guarda **una vez** en la base de datos local (`data/botlinkedin.db`).
> Si subes una nueva, reemplaza a la anterior.

---

## 7. Usar el bot

Desde el **dashboard** (http://127.0.0.1:8000):
- **Empleos → Nueva Búsqueda:** escribe o elige una **sugerencia** (basada en tu HV),
  filtra por fecha (3 días / semana / mes) y plataformas (LinkedIn, Indeed, Glassdoor,
  Computrabajo, elempleo). La tabla tiene **paginación, orden y filtros por columna**.
- Haz clic en el **título** de un empleo para ver la oferta en un recuadro.
- Botón ✉️ en cada empleo: **generar carta de presentación**.
- **Asistente:** chatea con el reclutador/headhunter virtual.

Desde la **CLI** (equivalentes):
```powershell
python -m src.main search run --keywords "abogado corporativo" --location "Bogota" --platform linkedin,computrabajo,elempleo
python -m src.main letter cover <ID_DEL_EMPLEO>
python -m src.main apply status
```

---

## 8. Reiniciar tras cambios

Si actualizas el código o el `.env`:
1. Detén el servidor con `Ctrl + C`.
2. Vuelve a lanzarlo: `python -m src.main dashboard start`
3. En el navegador, refresca con **Ctrl + F5**.

---

## 9. Problemas frecuentes

| Síntoma | Solución |
|---|---|
| *"No hay API key configurada"* | Revisa `AI_BACKEND` y la key correspondiente en `.env`; reinicia el servidor. |
| Búsqueda devuelve 0 empleos | LinkedIn limita búsquedas seguidas; usa términos más amplios o espera unos segundos. |
| Acentos/caracteres raros en consola Windows | Usa el lanzador `.\bot.ps1` (fuerza UTF-8). |
| `playwright` da error al postularse | Ejecuta `python -m playwright install chromium`. |
| No aparecen sugerencias | Sube primero tu HV (clip 📎 o `resume parse`). |

---

## Equivalentes para macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e .
python -m playwright install chromium
cp .env.example .env        # luego edita .env
python -m src.main dashboard start
```
