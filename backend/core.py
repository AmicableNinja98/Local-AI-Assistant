import os
import sys
import json
import time
import subprocess
import mysql.connector
import psutil
from openai import OpenAI
from ddgs import DDGS
from dotenv import load_dotenv
from pathlib import Path
import requests
from bs4 import BeautifulSoup
import re
import shutil
import glob

# ── Configuración ──────────────────────────────────────────────────────────────

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

RUTA_LLAMA  = os.getenv("RUTA_LLAMA")
RUTA_MODELO = os.getenv("RUTA_MODELO")
GPU_LAYERS  = int(os.getenv("GPU_LAYERS", 24))

DB_CONFIG = {
    "host":     os.getenv("DB_HOST","localhost"),
    "user":     os.getenv("DB_USER","root"),
    "password": os.getenv("DB_PASSWORD",""),
    "database": os.getenv("DB_NAME","asistente_ia")
}

client = OpenAI(base_url="http://localhost:8080/v1", api_key="sk-no-key-required")

# ── Base de datos ──────────────────────────────────────────────────────────────

def _db():
    return mysql.connector.connect(**DB_CONFIG)

def obtener_nombre_usuario():
    try:
        conn = _db(); cur = conn.cursor()
        cur.execute("SELECT valor FROM usuario WHERE clave = 'nombre_usuario'")
        res = cur.fetchone(); cur.close(); conn.close()
        return res[0] if res else "Usuario"
    except Exception:
        return "Usuario"

def obtener_nombre_asistente():
    try:
        conn = _db(); cur = conn.cursor()
        cur.execute("SELECT valor FROM usuario WHERE clave = 'nombre_asistente'")
        res = cur.fetchone(); cur.close(); conn.close()
        return res[0] if res else "Asistente"
    except Exception:
        return "Asistente"

# ── Herramientas ───────────────────────────────────────────────────────────────

def ayuda_asistente():
    return """
====================================================================
📋 FUNCIONES DISPONIBLES
====================================================================
1. 💬 Conversación libre en español o inglés.
2. 🔍 Búsqueda web automática para información reciente. También puedes forzarla con '/buscar [consulta]'.
3. 👤 Recuerdo tu nombre gracias a MariaDB.
4. ⚽ Gestión deportiva (jugadores, equipos, torneos).
5. 📊 Ver base de datos: pídeme un resumen.
6. ❓ Ayuda: escribe '/ayuda' o pregúntame qué puedo hacer.
7. 🖥️  Abrir aplicaciones: 'Abre Steam', 'Abre Discord', etc.
   Si no conozco la ruta te la pediré y la recordaré para siempre.
===================================================================="""

def registrar_jugador(nombre, edad=None, posicion=None):
    try:
        conn = _db(); cur = conn.cursor()
        cur.execute("INSERT INTO jugadores (nombre, edad, posicion) VALUES (%s, %s, %s)", (nombre, edad, posicion))
        conn.commit(); cur.close(); conn.close()
        return f"Jugador '{nombre}' registrado correctamente."
    except Exception as e:
        return f"Error al registrar jugador: {e}"

def crear_equipo(nombre):
    try:
        conn = _db(); cur = conn.cursor()
        cur.execute("INSERT INTO equipos (nombre) VALUES (%s)", (nombre,))
        conn.commit(); cur.close(); conn.close()
        return f"Equipo '{nombre}' creado correctamente."
    except Exception as e:
        return f"Error al crear equipo: {e}"

def asociar_jugador_a_equipo(nombre_jugador, nombre_equipo):
    try:
        conn = _db(); cur = conn.cursor()
        cur.execute("SELECT id FROM jugadores WHERE nombre LIKE %s", (f"%{nombre_jugador}%",))
        j = cur.fetchone()
        cur.execute("SELECT id FROM equipos WHERE nombre LIKE %s", (f"%{nombre_equipo}%",))
        e = cur.fetchone()
        if not j: return f"No encontré al jugador '{nombre_jugador}'."
        if not e: return f"No encontré al equipo '{nombre_equipo}'."
        cur.execute("INSERT INTO equipo_jugadores (equipo_id, jugador_id) VALUES (%s, %s)", (e[0], j[0]))
        conn.commit(); cur.close(); conn.close()
        return f"{nombre_jugador} asignado al equipo {nombre_equipo}."
    except Exception as ex:
        return f"Error: {ex}"

def crear_torneo(nombre, fecha_inicio=None):
    try:
        conn = _db(); cur = conn.cursor()
        cur.execute("INSERT INTO torneos (nombre, fecha_inicio) VALUES (%s, %s)", (nombre, fecha_inicio))
        conn.commit(); cur.close(); conn.close()
        return f"Torneo '{nombre}' creado."
    except Exception as e:
        return f"Error al crear torneo: {e}"

def inscribir_equipo_en_torneo(nombre_equipo, nombre_torneo):
    try:
        conn = _db(); cur = conn.cursor()
        cur.execute("SELECT id FROM equipos WHERE nombre LIKE %s", (f"%{nombre_equipo}%",))
        e = cur.fetchone()
        cur.execute("SELECT id FROM torneos WHERE nombre LIKE %s", (f"%{nombre_torneo}%",))
        t = cur.fetchone()
        if not e: return f"No existe el equipo '{nombre_equipo}'."
        if not t: return f"No existe el torneo '{nombre_torneo}'."
        cur.execute("INSERT INTO torneo_equipos (torneo_id, equipo_id) VALUES (%s, %s)", (t[0], e[0]))
        conn.commit(); cur.close(); conn.close()
        return f"Equipo '{nombre_equipo}' inscrito en '{nombre_torneo}'."
    except Exception as ex:
        return f"Error: {ex}"

def listar_todo_lo_guardado():
    try:
        conn = _db(); cur = conn.cursor()
        cur.execute("SELECT nombre, posicion FROM jugadores"); jugadores = cur.fetchall()
        cur.execute("SELECT nombre FROM equipos"); equipos = cur.fetchall()
        cur.execute("SELECT nombre, estado FROM torneos"); torneos = cur.fetchall()
        cur.close(); conn.close()
        res  = "--- REGISTROS ACTUALES ---\n"
        res += f"Jugadores: {', '.join([j[0] for j in jugadores]) if jugadores else 'Ninguno'}\n"
        res += f"Equipos: {', '.join([e[0] for e in equipos]) if equipos else 'Ninguno'}\n"
        res += f"Torneos: {', '.join([f'{t[0]} ({t[1]})' for t in torneos]) if torneos else 'Ninguno'}\n"
        return res
    except Exception as e:
        return f"Error: {e}"

def buscar_en_internet(consulta):
    try:
        with DDGS() as ddgs:
            resultados = list(ddgs.text(consulta, max_results=3))
            return "\n".join([f"Fuente: {r['href']}\n{r['body']}" for r in resultados])
    except Exception:
        return "No se pudo obtener información de internet."
    
def leer_pagina_web(url: str) -> str:
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Remove scripts, styles and nav clutter
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        texto = soup.get_text(separator="\n")
        # Clean up blank lines
        lineas = [l.strip() for l in texto.splitlines() if l.strip()]
        contenido = "\n".join(lineas)

        # Cap at 3000 characters so it fits the model's context
        return contenido[:3000] + ("..." if len(contenido) > 3000 else "")
    except Exception as e:
        return f"No se pudo leer la página: {e}"
    
def _buscar_app_en_sistema(nombre: str) -> str | None:
    """Tries to find an app automatically on Windows before asking the user."""
    nombre_lower = nombre.lower()

    # 1. Check system PATH
    en_path = shutil.which(nombre_lower) or shutil.which(nombre_lower + ".exe")
    if en_path:
        return en_path

    # 2. Search Start Menu shortcuts
    start_menu_dirs = [
        os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"),
        os.path.expandvars(r"%PROGRAMDATA%\Microsoft\Windows\Start Menu\Programs"),
    ]
    for base in start_menu_dirs:
        for ext in ("*.lnk", "*.exe"):
            coincidencias = glob.glob(os.path.join(base, "**", ext), recursive=True)
            for ruta in coincidencias:
                if nombre_lower in os.path.basename(ruta).lower():
                    return ruta

    # 3. Search common install directories
    dirs_comunes = [
        r"C:\Program Files",
        r"C:\Program Files (x86)",
        os.path.expandvars(r"%LOCALAPPDATA%"),
    ]
    for base in dirs_comunes:
        coincidencias = glob.glob(os.path.join(base, "**", f"*{nombre_lower}*.exe"), recursive=True)
        if coincidencias:
            return coincidencias[0]

    return None


def obtener_ruta_app(nombre: str) -> str | None:
    """Looks up an app path in the database."""
    try:
        conn = _db(); cur = conn.cursor()
        cur.execute("SELECT ruta FROM aplicaciones WHERE LOWER(nombre) = %s", (nombre.lower(),))
        res = cur.fetchone(); cur.close(); conn.close()
        return res[0] if res else None
    except Exception:
        return None


def guardar_ruta_app(nombre: str, ruta: str) -> str:
    """Saves or updates an app path in the database."""
    try:
        conn = _db(); cur = conn.cursor()
        cur.execute(
            "INSERT INTO aplicaciones (nombre, ruta) VALUES (%s, %s) "
            "ON DUPLICATE KEY UPDATE ruta = VALUES(ruta)",
            (nombre.lower(), ruta)
        )
        conn.commit(); cur.close(); conn.close()
        return f"Ruta de '{nombre}' guardada correctamente."
    except Exception as e:
        return f"Error al guardar ruta: {e}"


def abrir_aplicacion(nombre: str) -> dict:
    """
    Tries to open an app. Returns a dict instead of a string because
    it may need to ask the user for the path.
    {
      "estado": "abierta" | "no_encontrada" | "error",
      "mensaje": str,
      "app": str
    }
    """
    # 1. Check database
    ruta = obtener_ruta_app(nombre)

    # 2. If not in DB, search system automatically
    if not ruta:
        ruta_auto = _buscar_app_en_sistema(nombre)
        if ruta_auto:
            guardar_ruta_app(nombre, ruta_auto)
            ruta = ruta_auto

    # 3. Try to launch if found
    if ruta:
        try:
            os.startfile(ruta)
            return {"estado": "abierta", "mensaje": f"'{nombre}' abierta correctamente.", "app": nombre}
        except Exception as e:
            return {"estado": "error", "mensaje": f"Se encontró '{nombre}' pero no se pudo abrir: {e}", "app": nombre}

    # 4. Not found anywhere — need to ask user
    return {"estado": "no_encontrada", "mensaje": f"No encontré '{nombre}' en la base de datos ni en el sistema.", "app": nombre}

# ── Definición de herramientas para el modelo ─────────────────────────────────

TOOLS = [
    {"type": "function", "function": {"name": "ayuda_asistente",        "description": "Muestra las capacidades del asistente.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
    "name": "buscar_en_internet",
    "description": (
        "Busca información actualizada en internet. "
        "Úsala SIEMPRE que el usuario pregunte sobre eventos, noticias, personas, "
        "precios, resultados deportivos, o cualquier cosa que pueda haber cambiado "
        "después de 2022. No respondas de memoria si el tema es reciente."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "consulta": {"type": "string", "description": "La búsqueda a realizar"}
        },
        "required": ["consulta"]
    }
    }},
    {"type": "function", "function": {
    "name": "leer_pagina_web",
    "description": (
        "Lee el contenido completo de una URL específica. "
        "Úsala cuando el usuario proporcione un enlace concreto o cuando "
        "necesites obtener datos detallados de una página web específica."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "URL completa de la página a leer"}
        },
        "required": ["url"]
    }
    }},
    {"type": "function", "function": {
    "name": "abrir_aplicacion",
    "description": "Abre una aplicación instalada en el PC del usuario.",
    "parameters": {
        "type": "object",
        "properties": {
            "nombre": {"type": "string", "description": "Nombre de la aplicación a abrir (ej: steam, discord, chrome)"}
        },
        "required": ["nombre"]
    }
    }},
    {"type": "function", "function": {"name": "registrar_jugador",       "description": "Registra un jugador en la base de datos.", "parameters": {"type": "object", "properties": {"nombre": {"type": "string"}, "edad": {"type": "integer"}, "posicion": {"type": "string"}}, "required": ["nombre"]}}},
    {"type": "function", "function": {"name": "crear_equipo",            "description": "Crea un equipo deportivo.", "parameters": {"type": "object", "properties": {"nombre": {"type": "string"}}, "required": ["nombre"]}}},
    {"type": "function", "function": {"name": "asociar_jugador_a_equipo","description": "Asigna un jugador a un equipo.", "parameters": {"type": "object", "properties": {"nombre_jugador": {"type": "string"}, "nombre_equipo": {"type": "string"}}, "required": ["nombre_jugador", "nombre_equipo"]}}},
    {"type": "function", "function": {"name": "crear_torneo",            "description": "Registra un torneo.", "parameters": {"type": "object", "properties": {"nombre": {"type": "string"}, "fecha_inicio": {"type": "string"}}, "required": ["nombre"]}}},
    {"type": "function", "function": {"name": "inscribir_equipo_en_torneo","description": "Inscribe un equipo en un torneo.", "parameters": {"type": "object", "properties": {"nombre_equipo": {"type": "string"}, "nombre_torneo": {"type": "string"}}, "required": ["nombre_equipo", "nombre_torneo"]}}},
    {"type": "function", "function": {"name": "listar_todo_lo_guardado", "description": "Muestra todos los registros guardados.", "parameters": {"type": "object", "properties": {}}}},
]

FUNCIONES_MAPA = {
    "ayuda_asistente":          ayuda_asistente,
    "buscar_en_internet": buscar_en_internet,
    "leer_pagina_web": leer_pagina_web,
    "registrar_jugador":        registrar_jugador,
    "crear_equipo":             crear_equipo,
    "asociar_jugador_a_equipo": asociar_jugador_a_equipo,
    "crear_torneo":             crear_torneo,
    "inscribir_equipo_en_torneo": inscribir_equipo_en_torneo,
    "listar_todo_lo_guardado":  listar_todo_lo_guardado,
    "abrir_aplicacion": abrir_aplicacion,
}

# ── Servidor llama.cpp ─────────────────────────────────────────────────────────

def iniciar_servidor():
    print("🔧 Iniciando servidor llama.cpp...")
    proceso = subprocess.Popen(
        [RUTA_LLAMA, "-m", RUTA_MODELO, "-c", "8192", "-ngl", str(GPU_LAYERS), "--port", "8080"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    time.sleep(10)
    return proceso

def cerrar_servidor(proceso):
    if proceso and proceso.poll() is None:
        try:
            padre = psutil.Process(proceso.pid)
            for hijo in padre.children(recursive=True):
                hijo.kill()
            padre.kill()
        except Exception:
            pass

# ── Sesión — interfaz pública para cualquier UI ───────────────────────────────

# Palabras clave que indican que el usuario quiere info reciente
PALABRAS_ACTUALES = [
    "actual", "ahora", "hoy", "este año", "2024", "2025", "2026",
    "último", "ultima", "reciente", "clasificación", "resultado",
    "goleador", "temporada", "noticias", "precio", "estreno"
]

def _necesita_busqueda(texto: str) -> bool:
    texto = texto.lower()
    return any(p in texto for p in PALABRAS_ACTUALES)

class AsistenteSession:
    """
    La UI sólo usa estos tres métodos:
        session.iniciar()  → dict con saludo inicial
        session.manejar(texto_usuario)  → dict con la respuesta
        session.cerrar()
    
    Formato de respuesta:
        {
          "tipo":       "saludo" | "respuesta" | "herramienta" | "ayuda" | "adios" | "error",
          "texto":      str,       # texto para mostrar al usuario
          "herramienta": str|None, # nombre de la herramienta ejecutada (si aplica)
          "terminado":  bool       # True cuando el asistente se despide
        }
    """

    def __init__(self):
        self.proceso_servidor = None
        self.historial = []
        self.nombre_usuario = "Usuario"
        self.nombre_asistente = "Asistente"
        self.activo = False
        self._app_pendiente = None

    def iniciar(self):
        self.proceso_servidor = iniciar_servidor()
        self.nombre_usuario   = obtener_nombre_usuario()
        self.nombre_asistente = obtener_nombre_asistente()
        self.activo = True
        self.historial = [
            {"role": "system", "content": (
                f"Eres un asistente personal de IA llamado {self.nombre_asistente}. "
                f"El dueño se llama {self.nombre_usuario}. "
                f"Cuando te pregunten cómo te llamas, responde siempre '{self.nombre_asistente}'. "
                "Eres bilingüe (inglés/español). "
                "Tu conocimiento interno llega hasta 2022. "
                "Para información reciente usa 'buscar_en_internet'. "
                "Si el usuario te da una URL específica o te dice que fuentes puedes usar, usa SIEMPRE 'leer_pagina_web' "
                "para leer su contenido real en lugar de intentar responder de memoria. "
                "Nunca inventes datos — si no encuentras la información, dilo claramente."
                "No hace falta  que le digas al usuario que tienes que buscar en internet o leer una pagina web,"
                "simplemente hazlo"
                "Tienes acceso a herramientas para gestionar torneos deportivos. "
                "Si te preguntan qué puedes hacer, invoca 'ayuda_asistente'."
                "Si el usuario pide abrir una aplicación, programa o juego, usa SIEMPRE 'abrir_aplicacion'. "
                "Nunca respondas que no puedes abrir aplicaciones — tienes esa capacidad. "
            )}
        ]
        return {
            "tipo": "saludo",
            "texto": f"¡Hola {self.nombre_usuario}! Soy {self.nombre_asistente}, tu asistente local.\n"
                     "Escribe '/ayuda' para ver mis capacidades o 'salir' para apagarme.",
            "herramienta": None,
            "terminado": False
        }

    def manejar(self, texto_usuario: str) -> dict:
        texto_usuario = texto_usuario.strip()

        # Atajos de comando que no necesitan pasar por el modelo
        if texto_usuario.lower() == "salir":
            self.activo = False
            return {
                "tipo": "adios",
                "texto": f"¡Hasta luego {self.nombre_usuario}! {self.nombre_asistente} se apaga...",
                "herramienta": None,
                "terminado": True
            }

        if texto_usuario.lower() == "/ayuda":
            return {
                "tipo": "ayuda",
                "texto": ayuda_asistente(),
                "herramienta": None,
                "terminado": False
            }
        
        # User is providing a path for a pending app
        if hasattr(self, "_app_pendiente") and self._app_pendiente:
            ruta = texto_usuario.strip().strip('"')
            if os.path.exists(ruta):
                guardar_ruta_app(self._app_pendiente, ruta)
                nombre = self._app_pendiente
                self._app_pendiente = None
                try:
                    os.startfile(ruta)
                    return {"tipo": "herramienta",
                            "texto": f"Ruta guardada y '{nombre}' abierta correctamente. "
                                    "La próxima vez la abriré automáticamente.",
                            "herramienta": "abrir_aplicacion", "terminado": False}
                except Exception as e:
                    return {"tipo": "error", "texto": f"Ruta guardada pero no se pudo abrir: {e}",
                            "herramienta": None, "terminado": False}
            else:
                return {"tipo": "respuesta",
                        "texto": f"No encontré ningún archivo en esa ruta. Comprueba que sea correcta e inténtalo de nuevo.",
                        "herramienta": None, "terminado": False}
        
        # Detect app opening intent directly without relying on the model
        PALABRAS_ABRIR = ["abre ", "abrir ", "open ", "lanza ", "lanzar ", "ejecuta ", "ejecutar ", "inicia ", "iniciar "]
        texto_lower = texto_usuario.lower()

        if any(texto_lower.startswith(p) or f" {p}" in texto_lower for p in PALABRAS_ABRIR):
            # Extract app name by removing the trigger word
            nombre_app = texto_usuario
            for p in PALABRAS_ABRIR:
                nombre_app = re.sub(p, "", nombre_app, flags=re.IGNORECASE).strip()

            # Remove common filler words
            for filler in ["la aplicación", "la aplicacion", "el programa", "el juego", "la app", "por favor", "porfavor"]:
                nombre_app = re.sub(filler, "", nombre_app, flags=re.IGNORECASE).strip()

            # Check if the user also provided a path in the same message
            ruta_inline = None
            path_patterns = [
                r'(?:la ruta es|ruta:|path:|this is the path|the path is|su ruta es|está en|esta en)\s*["\']?([\w:\\\/\s\.\-\_]+\.exe)["\']?',
                r'["\']?((?:[A-Za-z]:\\|\/)[^\s"\']+\.exe)["\']?',
            ]
            for pattern in path_patterns:
                match = re.search(pattern, texto_usuario, re.IGNORECASE)
                if match:
                    ruta_inline = match.group(1).strip().strip('"\'')
                    # Remove the path portion from the app name
                    nombre_app = texto_usuario[:match.start()].strip()
                    for p in PALABRAS_ABRIR:
                        nombre_app = re.sub(p, "", nombre_app, flags=re.IGNORECASE).strip()
                    for filler in ["la aplicación", "la aplicacion", "el programa", "el juego", "la app",
                                "la ruta es", "ruta:", "path:", "this is the path", "the path is",
                                "su ruta es", "está en", "esta en", ",", "por favor", "porfavor"]:
                        nombre_app = re.sub(filler, "", nombre_app, flags=re.IGNORECASE).strip()
                    nombre_app = nombre_app.strip(" .,")
                    break

            if nombre_app:
                # If path was provided inline, save it and launch directly
                if ruta_inline:
                    if os.path.exists(ruta_inline):
                        guardar_ruta_app(nombre_app, ruta_inline)
                        try:
                            os.startfile(ruta_inline)
                            return {
                                "tipo": "herramienta",
                                "texto": f"Ruta guardada y '{nombre_app}' abierta correctamente. "
                                        "La próxima vez la abriré automáticamente.",
                                "herramienta": "abrir_aplicacion",
                                "terminado": False
                            }
                        except Exception as e:
                            return {
                                "tipo": "error",
                                "texto": f"Ruta guardada pero no se pudo abrir '{nombre_app}': {e}",
                                "herramienta": None,
                                "terminado": False
                            }
                    else:
                        return {
                            "tipo": "respuesta",
                            "texto": f"Guardé el nombre '{nombre_app}' pero no encontré ningún archivo en:\n{ruta_inline}\n"
                                    "Comprueba que la ruta sea correcta e inténtalo de nuevo.",
                            "herramienta": None,
                            "terminado": False
                        }

                # No path provided — use existing lookup logic
                resultado = abrir_aplicacion(nombre_app)
                if resultado["estado"] == "no_encontrada":
                    self._app_pendiente = resultado["app"]
                    return {
                        "tipo": "respuesta",
                        "texto": f"No encontré '{resultado['app']}' automáticamente.\n"
                                f"¿Puedes decirme la ruta completa del ejecutable?\n"
                                f"(Ej: C:\\Program Files\\App\\app.exe)\n"
                                f"O puedes decirme directamente: 'Abre {resultado['app']}, la ruta es C:\\...\\app.exe'",
                        "herramienta": "abrir_aplicacion",
                        "terminado": False
                    }
                return {
                    "tipo": "herramienta",
                    "texto": resultado["mensaje"],
                    "herramienta": "abrir_aplicacion",
                    "terminado": False
                }

        # Búsqueda web directa
        if texto_usuario.startswith("/buscar "):
            query = texto_usuario[8:]
            datos = buscar_en_internet(query)
            contexto = (f"Pregunta: {query}\nContexto de internet:\n{datos}\n"
                        "Responde basándote estrictamente en estos datos sin inventar nada.")
            self.historial.append({"role": "user", "content": contexto})
        else:
            self.historial.append({"role": "user", "content": texto_usuario})

        urls = re.findall(r'https?://\S+', texto_usuario)
        if urls:
            url = urls[0]
            contenido = leer_pagina_web(url)
            pregunta_sin_url = texto_usuario.replace(url, "").strip()
            self.historial.append({"role": "user", "content":
                f"Contenido real de {url}:\n{contenido}\n\n"
                f"Usando ÚNICAMENTE este contenido, responde: {pregunta_sin_url or texto_usuario}\n"
                "Sé específico con nombres, cifras y fechas. No inventes nada."
            })
            try:
                respuesta = client.chat.completions.create(
                    model="local-model", messages=self.historial
                )
                respuesta_final = respuesta.choices[0].message.content
                self.historial.append({"role": "assistant", "content": respuesta_final})
                return {"tipo": "herramienta", "texto": respuesta_final,
                        "herramienta": "leer_pagina_web", "terminado": False}
            except Exception as e:
                return {"tipo": "error", "texto": f"Error: {e}",
                        "herramienta": None, "terminado": False}

        # Llamada al modelo
        try:
            completion = client.chat.completions.create(
                model="local-model",
                messages=self.historial,
                tools=TOOLS,
                tool_choice="auto",
                temperature=0.4
            )
            mensaje_ia = completion.choices[0].message

            # El modelo quiere ejecutar una herramienta
            if mensaje_ia.tool_calls:
                tool_call = mensaje_ia.tool_calls[0]
                nombre_func = tool_call.function.name
                argumentos  = json.loads(tool_call.function.arguments)
                funcion = FUNCIONES_MAPA.get(nombre_func)
                # abrir_aplicacion is handled separately below, skip here
                resultado = (funcion(**argumentos) if funcion else "Herramienta no encontrada.") \
                            if nombre_func != "abrir_aplicacion" else None

                # Ayuda: respuesta directa sin segunda llamada al modelo
                if nombre_func == "ayuda_asistente":
                    self.historial.append({"role": "assistant", "content": "He mostrado el menú de ayuda."})
                    return {"tipo": "ayuda", "texto": resultado, "herramienta": nombre_func, "terminado": False}
                
                if nombre_func in ("buscar_en_internet", "leer_pagina_web"):
                    self.historial.append(mensaje_ia)
                    self.historial.append({"role": "tool", "tool_call_id": tool_call.id, "name": nombre_func, "content": resultado})
                    self.historial.append({"role": "user", "content":
                        "Usando ÚNICAMENTE la información obtenida anteriormente, "
                        "responde la pregunta original con datos concretos y específicos. "
                        "No uses frases como 'según mis fuentes' ni dejes campos vacíos con corchetes. "
                        "Si la información no está en los resultados, dilo claramente."
                    })
                    segunda = client.chat.completions.create(model="local-model", messages=self.historial)
                    respuesta_final = segunda.choices[0].message.content
                    self.historial.append({"role": "assistant", "content": respuesta_final})
                    return {"tipo": "herramienta", "texto": respuesta_final, "herramienta": nombre_func, "terminado": False}
                
                if nombre_func == "abrir_aplicacion":
                    resultado = abrir_aplicacion(**argumentos)
                    if resultado["estado"] == "no_encontrada":
                        # Store pending app name in session and ask user for path
                        self._app_pendiente = resultado["app"]
                        self.historial.append({"role": "assistant", "content": resultado["mensaje"]})
                        return {
                            "tipo": "respuesta",
                            "texto": f"No encontré '{resultado['app']}' automáticamente. "
                                    f"¿Puedes decirme la ruta completa del ejecutable? "
                                    f"(Ej: C:\\Program Files\\App\\app.exe)",
                            "herramienta": nombre_func,
                            "terminado": False
                        }
                    self.historial.append({"role": "assistant", "content": resultado["mensaje"]})
                    return {"tipo": "herramienta", "texto": resultado["mensaje"], "herramienta": nombre_func, "terminado": False}
                
                # Resto de herramientas: segunda llamada para respuesta natural
                self.historial.append(mensaje_ia)
                self.historial.append({"role": "tool", "tool_call_id": tool_call.id, "name": nombre_func, "content": resultado})
                segunda = client.chat.completions.create(model="local-model", messages=self.historial)
                respuesta_final = segunda.choices[0].message.content
                self.historial.append({"role": "assistant", "content": respuesta_final})
                return {"tipo": "herramienta", "texto": respuesta_final, "herramienta": nombre_func, "terminado": False}

            # Respuesta normal sin herramienta
            respuesta = mensaje_ia.content
            modelo_finge_buscar = any(frase in respuesta.lower() for frase in [
                "buscar en internet", "buscar en la web", "consultando fuentes",
                "según mis fuentes", "luego de buscar", "he encontrado en internet"
            ])

            if modelo_finge_buscar or _necesita_busqueda(texto_usuario):
                # Forzar búsqueda real
                datos = buscar_en_internet(texto_usuario)
                self.historial.append({"role": "user", "content":
                    f"Resultados reales de búsqueda web:\n{datos}\n\n"
                    "Responde la pregunta original usando SÓLO estos datos. "
                    "Sé específico con nombres, cifras y fechas. "
                    "No dejes nada entre corchetes ni digas que no tienes información."
                })
                segunda = client.chat.completions.create(model="local-model", messages=self.historial)
                respuesta_final = segunda.choices[0].message.content
                self.historial.append({"role": "assistant", "content": respuesta_final})
                return {"tipo": "herramienta", "texto": respuesta_final, "herramienta": "buscar_en_internet", "terminado": False}

            # Respuesta normal sin búsqueda necesaria
            self.historial.append({"role": "assistant", "content": respuesta})
            return {"tipo": "respuesta", "texto": respuesta, "herramienta": None, "terminado": False}

        except Exception as e:
            return {"tipo": "error", "texto": f"Error de comunicación con el modelo: {e}", "herramienta": None, "terminado": False}

    def cerrar(self):
        self.activo = False
        cerrar_servidor(self.proceso_servidor)