import os
import sys
import json
import time
import subprocess
import mysql.connector
import psutil
from openai import OpenAI
from duckduckgo_search import DDGS
from dotenv import load_dotenv

# ── Configuración ──────────────────────────────────────────────────────────────

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
2. 🔍 Búsqueda web: escribe '/buscar [consulta]'
3. 👤 Recuerdo tu nombre gracias a MariaDB.
4. ⚽ Gestión deportiva (jugadores, equipos, torneos).
5. 📊 Ver base de datos: pídeme un resumen.
6. ❓ Ayuda: escribe '/ayuda' o pregúntame qué puedo hacer.
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

# ── Definición de herramientas para el modelo ─────────────────────────────────

TOOLS = [
    {"type": "function", "function": {"name": "ayuda_asistente",        "description": "Muestra las capacidades del asistente.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "registrar_jugador",       "description": "Registra un jugador en la base de datos.", "parameters": {"type": "object", "properties": {"nombre": {"type": "string"}, "edad": {"type": "integer"}, "posicion": {"type": "string"}}, "required": ["nombre"]}}},
    {"type": "function", "function": {"name": "crear_equipo",            "description": "Crea un equipo deportivo.", "parameters": {"type": "object", "properties": {"nombre": {"type": "string"}}, "required": ["nombre"]}}},
    {"type": "function", "function": {"name": "asociar_jugador_a_equipo","description": "Asigna un jugador a un equipo.", "parameters": {"type": "object", "properties": {"nombre_jugador": {"type": "string"}, "nombre_equipo": {"type": "string"}}, "required": ["nombre_jugador", "nombre_equipo"]}}},
    {"type": "function", "function": {"name": "crear_torneo",            "description": "Registra un torneo.", "parameters": {"type": "object", "properties": {"nombre": {"type": "string"}, "fecha_inicio": {"type": "string"}}, "required": ["nombre"]}}},
    {"type": "function", "function": {"name": "inscribir_equipo_en_torneo","description": "Inscribe un equipo en un torneo.", "parameters": {"type": "object", "properties": {"nombre_equipo": {"type": "string"}, "nombre_torneo": {"type": "string"}}, "required": ["nombre_equipo", "nombre_torneo"]}}},
    {"type": "function", "function": {"name": "listar_todo_lo_guardado", "description": "Muestra todos los registros guardados.", "parameters": {"type": "object", "properties": {}}}},
]

FUNCIONES_MAPA = {
    "ayuda_asistente":          ayuda_asistente,
    "registrar_jugador":        registrar_jugador,
    "crear_equipo":             crear_equipo,
    "asociar_jugador_a_equipo": asociar_jugador_a_equipo,
    "crear_torneo":             crear_torneo,
    "inscribir_equipo_en_torneo": inscribir_equipo_en_torneo,
    "listar_todo_lo_guardado":  listar_todo_lo_guardado,
}

# ── Servidor llama.cpp ─────────────────────────────────────────────────────────

def iniciar_servidor():
    print("🔧 Iniciando servidor llama.cpp...")
    proceso = subprocess.Popen(
        [RUTA_LLAMA, "-m", RUTA_MODELO, "-c", "4096", "-ngl", str(GPU_LAYERS), "--port", "8080"],
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
                "Eres bilingüe (inglés/español). Tienes acceso a herramientas para gestionar "
                "torneos deportivos e internet. Si te preguntan qué puedes hacer, invoca 'ayuda_asistente'."
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

        # Búsqueda web directa
        if texto_usuario.startswith("/buscar "):
            query = texto_usuario[8:]
            datos = buscar_en_internet(query)
            contexto = (f"Pregunta: {query}\nContexto de internet:\n{datos}\n"
                        "Responde basándote estrictamente en estos datos sin inventar nada.")
            self.historial.append({"role": "user", "content": contexto})
        else:
            self.historial.append({"role": "user", "content": texto_usuario})

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
                funcion     = FUNCIONES_MAPA.get(nombre_func)
                resultado   = funcion(**argumentos) if funcion else "Herramienta no encontrada."

                # Ayuda: respuesta directa sin segunda llamada al modelo
                if nombre_func == "ayuda_asistente":
                    self.historial.append({"role": "assistant", "content": "He mostrado el menú de ayuda."})
                    return {"tipo": "ayuda", "texto": resultado, "herramienta": nombre_func, "terminado": False}

                # Resto de herramientas: segunda llamada para respuesta natural
                self.historial.append(mensaje_ia)
                self.historial.append({"role": "tool", "tool_call_id": tool_call.id, "name": nombre_func, "content": resultado})
                segunda = client.chat.completions.create(model="local-model", messages=self.historial)
                respuesta_final = segunda.choices[0].message.content
                self.historial.append({"role": "assistant", "content": respuesta_final})
                return {"tipo": "herramienta", "texto": respuesta_final, "herramienta": nombre_func, "terminado": False}

            # Respuesta normal sin herramienta
            respuesta = mensaje_ia.content
            self.historial.append({"role": "assistant", "content": respuesta})
            return {"tipo": "respuesta", "texto": respuesta, "herramienta": None, "terminado": False}

        except Exception as e:
            return {"tipo": "error", "texto": f"Error de comunicación con el modelo: {e}", "herramienta": None, "terminado": False}

    def cerrar(self):
        self.activo = False
        cerrar_servidor(self.proceso_servidor)