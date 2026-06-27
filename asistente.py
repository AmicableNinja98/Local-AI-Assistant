import os
import json
import mysql.connector
from openai import OpenAI
from duckduckgo_search import DDGS
import subprocess
import sys
import psutil

RUTA_LLAMA   = r"C:\llama-cpp\llama-server.exe"
RUTA_MODELO  = r"C:\llama-cpp\models\meta-llama-3.1-8b-instruct-abliterated.Q5_K_M.gguf"
GPU_LAYERS   = 24

# Conexión al servidor local de llama.cpp
client = OpenAI(base_url="http://localhost:8080/v1", api_key="sk-no-key-required")

# Configuración de la base de datos MariaDB
DB_CONFIG = {
    "host": "localhost",
    "user": "root",          
    "password": "mariocabron17",  # PON AQUÍ TU CONTRASEÑA DE MARIADB
    "database": "asistente_ia"
}

def conectar_db():
    return mysql.connector.connect(**DB_CONFIG)

def iniciar_servidor():
    """Starts llama-server as a subprocess and returns the process handle."""
    print("🔧 Iniciando servidor llama.cpp...")
    proceso = subprocess.Popen(
        [RUTA_LLAMA, "-m", RUTA_MODELO, "-c", "4096",
         "-ngl", str(GPU_LAYERS), "--port", "8080"],
        stdout=subprocess.DEVNULL,   # hides server output; remove to see it
        stderr=subprocess.DEVNULL
    )
    print("⏳ Esperando que cargue el modelo (5 segundos)...")
    import time; time.sleep(5)
    print("✅ Servidor listo.\n")
    return proceso

# =====================================================================
# FUNCIONES DE BASE DE DATOS Y AYUDA (HERRAMIENTAS PARA LA IA)
# =====================================================================

def obtener_nombre_usuario():
    try:
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute("SELECT valor FROM usuario WHERE clave = 'nombre_usuario'")
        res = cursor.fetchone()
        cursor.close()
        conn.close()
        return res[0] if res else "Usuario"
    except Exception:
        return "Usuario"

def obtener_nombre_asistente():
    try:
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute("SELECT valor FROM usuario WHERE clave = 'nombre_asistente'")
        res = cursor.fetchone()
        cursor.close()
        conn.close()
        return res[0] if res else "Asistente"
    except Exception:
        return "Asistente"

def ayuda_asistente():
    """Devuelve la lista detallada de funciones del asistente."""
    menu = """
====================================================================
📋 MENÚ DE FUNCIONES DISPONIBLES EN EL ASISTENTE
====================================================================
1. 💬 Conversación libre: Háblame en español o inglés de lo que quieras.
2. 🔍 Búsqueda en Internet: Escribe '/buscar [tu duda]' para obtener información real y actualizada de la web.
3. 👤 Gestión de Nombre: Recuerdo cómo te llamas gracias a MariaDB.
4. ⚽ Gestión Deportiva (Automática en el chat):
   - Registrar jugadores (Ej: "Añade al jugador Messi de 38 años delantero")
   - Crear equipos (Ej: "Crea el equipo Barça")
   - Asociar jugadores a equipos (Ej: "Pon a Messi en el Barça")
   - Crear torneos (Ej: "Crea el torneo Liga Española")
   - Inscribir equipos en torneos (Ej: "Inscribe al Barça en la Liga Española")
5. 📊 Ver Base de Datos: Pídeme que te muestre un resumen de lo guardado.
6. ❓ Ayuda: Escribe '/ayuda' o pídeme las funciones para ver este menú.
====================================================================
"""
    return menu

def registrar_jugador(nombre, edad=None, posicion=None):
    try:
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO jugadores (nombre, edad, posicion) VALUES (%s, %s, %s)",
            (nombre, edad, posicion)
        )
        conn.commit()
        cursor.close()
        conn.close()
        return f"Éxito: Jugador '{nombre}' registrado correctamente."
    except Exception as e:
        return f"Error al registrar jugador: {e}"

def crear_equipo(nombre):
    try:
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO equipos (nombre) VALUES (%s)", (nombre,))
        conn.commit()
        cursor.close()
        conn.close()
        return f"Éxito: Equipo '{nombre}' creado correctamente."
    except Exception as e:
        return f"Error al crear equipo: {e}"

def asociar_jugador_a_equipo(nombre_jugador, nombre_equipo):
    try:
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM jugadores WHERE nombre LIKE %s", (f"%{nombre_jugador}%",))
        j_id = cursor.fetchone()
        cursor.execute("SELECT id FROM equipos WHERE nombre LIKE %s", (f"%{nombre_equipo}%",))
        e_id = cursor.fetchone()
        
        if not j_id: return f"Error: No encontré al jugador '{nombre_jugador}'."
        if not e_id: return f"Error: No encontré al equipo '{nombre_equipo}'."
        
        cursor.execute("INSERT INTO equipo_jugadores (equipo_id, jugador_id) VALUES (%s, %s)", (e_id[0], j_id[0]))
        conn.commit()
        cursor.close()
        conn.close()
        return f"Éxito: Se ha asignado a {nombre_jugador} al equipo {nombre_equipo}."
    except Exception as e:
        return f"Error al asociar jugador al equipo: {e}"

def crear_torneo(nombre, fecha_inicio=None):
    try:
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO torneos (nombre, fecha_inicio) VALUES (%s, %s)", (nombre, fecha_inicio))
        conn.commit()
        cursor.close()
        conn.close()
        return f"Éxito: Torneo '{nombre}' iniciado/planificado."
    except Exception as e:
        return f"Error al crear torneo: {e}"

def inscribir_equipo_en_torneo(nombre_equipo, nombre_torneo):
    try:
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM equipos WHERE nombre LIKE %s", (f"%{nombre_equipo}%",))
        e_id = cursor.fetchone()
        cursor.execute("SELECT id FROM torneos WHERE nombre LIKE %s", (f"%{nombre_torneo}%",))
        t_id = cursor.fetchone()
        
        if not e_id: return f"Error: No existe el equipo '{nombre_equipo}'."
        if not t_id: return f"Error: No existe el torneo '{nombre_torneo}'."
        
        cursor.execute("INSERT INTO torneo_equipos (torneo_id, equipo_id) VALUES (%s, %s)", (t_id[0], e_id[0]))
        conn.commit()
        cursor.close()
        conn.close()
        return f"Éxito: Equipo '{nombre_equipo}' inscrito en '{nombre_torneo}'."
    except Exception as e:
        return f"Error al inscribir equipo: {e}"

def listar_todo_lo_guardado():
    try:
        conn = conectar_db()
        cursor = conn.cursor()
        
        cursor.execute("SELECT nombre, posicion FROM jugadores")
        jugadores = cursor.fetchall()
        
        cursor.execute("SELECT nombre FROM equipos")
        equipos = cursor.fetchall()
        
        cursor.execute("SELECT nombre, estado FROM torneos")
        torneos = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        res = "--- REGISTROS ACTUALES ---\n"
        res += f"Jugadores: {', '.join([j[0] for j in jugadores]) if jugadores else 'Ninguno'}\n"
        res += f"Equipos: {', '.join([e[0] for e in equipos]) if equipos else 'Ninguno'}\n"
        res += f"Torneos: {', '.join([f'{t[0]} ({t[1]})' for t in torneos]) if torneos else 'Ninguno'}\n"
        return res
    except Exception as e:
        return f"Error al consultar datos generales: {e}"

def buscar_en_internet(consulta):
    try:
        with DDGS() as ddgs:
            resultados = [r for r in ddgs.text(consulta, max_results=3)]
            contexto = "\n".join([f"Fuente: {r['href']}\nContenido: {r['body']}" for r in resultados])
            return contexto
    except Exception:
        return "No se pudo obtener información de internet en este momento."

# =====================================================================
# DECLARACIÓN DE HERRAMIENTAS PARA LLAMA.CPP
# =====================================================================

tools = [
    {
        "type": "function",
        "function": {
            "name": "ayuda_asistente",
            "description": "Muestra la lista de funciones y capacidades del asistente cuando el usuario pregunta qué puede hacer o qué funciones tiene.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "registrar_jugador",
            "description": "Registra un nuevo jugador deportivo en la base de datos local.",
            "parameters": {
                "type": "object",
                "properties": {
                    "nombre": {"type": "string", "description": "Nombre completo del jugador"},
                    "edad": {"type": "integer", "description": "Edad del jugador (opcional)"},
                    "posicion": {"type": "string", "description": "Posición en la que juega (ej. Delantero, Portero) (opcional)"}
                },
                "required": ["nombre"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "crear_equipo",
            "description": "Crea un nuevo equipo deportivo en el sistema.",
            "parameters": {
                "type": "object",
                "properties": {
                    "nombre": {"type": "string", "description": "Nombre del equipo"}
                },
                "required": ["nombre"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "asociar_jugador_a_equipo",
            "description": "Une a un jugador existente con un equipo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "nombre_jugador": {"type": "string", "description": "Nombre o parte del nombre del jugador"},
                    "nombre_equipo": {"type": "string", "description": "Nombre del equipo"}
                },
                "required": ["nombre_jugador", "nombre_equipo"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "crear_torneo",
            "description": "Registra un nuevo campeonato o torneo deportivo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "nombre": {"type": "string", "description": "Nombre del torneo"},
                    "fecha_inicio": {"type": "string", "description": "Fecha estimada en formato AAAA-MM-DD (opcional)"}
                },
                "required": ["nombre"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "inscribir_equipo_en_torneo",
            "description": "Inscribe un equipo para que participe en un torneo específico.",
            "parameters": {
                "type": "object",
                "properties": {
                    "nombre_equipo": {"type": "string", "description": "Nombre del equipo"},
                    "nombre_torneo": {"type": "string", "description": "Nombre del torneo"}
                },
                "required": ["nombre_equipo", "nombre_torneo"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "listar_todo_lo_guardado",
            "description": "Muestra un resumen de todos los jugadores, equipos y torneos registrados.",
            "parameters": {"type": "object", "properties": {}}
        }
    }
]

FUNCIONES_MAPA = {
    "ayuda_asistente": ayuda_asistente,
    "registrar_jugador": registrar_jugador,
    "crear_equipo": crear_equipo,
    "asociar_jugador_a_equipo": asociar_jugador_a_equipo,
    "crear_torneo": crear_torneo,
    "inscribir_equipo_en_torneo": inscribir_equipo_en_torneo,
    "listar_todo_lo_guardado": listar_todo_lo_guardado
}

# =====================================================================
# BUCLE PRINCIPAL DEL CHAT
# =====================================================================

def cerrar_servidor(proceso_servidor):
    if proceso_servidor and proceso_servidor.poll() is None:
        print("🔌 Cerrando servidor llama.cpp...")
        try:
            # Kill the server and all its child processes
            padre = psutil.Process(proceso_servidor.pid)
            for hijo in padre.children(recursive=True):
                hijo.kill()
            padre.kill()
            print("✅ Servidor cerrado correctamente.")
        except Exception as e:
            print(f"⚠️ No se pudo cerrar el servidor limpiamente: {e}")

def chatear(proceso_servidor = None):
    nombre_dueno = obtener_nombre_usuario()
    nombre_asistente = obtener_nombre_asistente()

    # 🌟 PASO 1: SALUDO AL INICIAR EL ASISTENTE
    print(f"\n🤖 ¡Hola {nombre_dueno}! Soy {nombre_asistente}, tu asistente local.")
    print("Escribe '/ayuda' en cualquier momento para ver mis capacidades.")
    print("Escribe 'salir' para apagar el asistente.")
    
    historial = [
        {"role": "system", "content": f"Eres un asistente personal de IA ejecutándose localmente. El dueño se llama {nombre_dueno}. Eres bilingüe (inglés/español). Tienes acceso a herramientas para gestionar torneos deportivos e internet. Si te preguntan qué puedes hacer, invoca la función 'ayuda_asistente'."}
    ]

    while True:
        usuario = input("\nTú: ")
        if usuario.lower() == 'salir':
            print(f"🤖 ¡Hasta luego {nombre_dueno}! {nombre_asistente} se apaga...")
            break
            
        # Atajo rápido de ayuda por comando directo
        if usuario.lower() == '/ayuda':
            print(ayuda_asistente())
            continue
            
        if usuario.startswith("/buscar "):
            query = usuario.replace("/buscar ", "")
            print("🔍 Buscando en internet...")
            datos_web = buscar_en_internet(query)
            contexto = f"Pregunta: {query}\nContexto extraído de internet:\n{datos_web}\nPor favor, responde basándote estrictamente en los datos anteriores sin inventar nada."
            historial.append({"role": "user", "content": contexto})
        else:
            historial.append({"role": "user", "content": usuario})
            
        try:
            completion = client.chat.completions.create(
                model="local-model",
                messages=historial,
                tools=tools,
                tool_choice="auto",
                temperature=0.4
            )
            
            mensaje_ia = completion.choices[0].message
            
            if mensaje_ia.tool_calls:
                for tool_call in mensaje_ia.tool_calls:
                    nombre_func = tool_call.function.name
                    argumentos = json.loads(tool_call.function.arguments)
                    
                    print(f"⚙️ [IA ejecutando herramienta interna: {nombre_func}]")
                    
                    funcion_a_llamar = FUNCIONES_MAPA.get(nombre_func)
                    if funcion_a_llamar:
                        resultado_db = funcion_a_llamar(**argumentos)
                        
                        # Si es la función de ayuda, la imprimimos directamente de forma bonita
                        if nombre_func == "ayuda_asistente":
                            print(resultado_db)
                            historial.append({"role": "assistant", "content": "Te he mostrado el menú de ayuda con mis funciones disponibles."})
                            continue
                        
                        historial.append(mensaje_ia)
                        historial.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": nombre_func,
                            "content": resultado_db
                        })
                        
                        segunda_llamada = client.chat.completions.create(
                            model="local-model",
                            messages=historial
                        )
                        respuesta_final = segunda_llamada.choices[0].message.content
                        print(f"\n🤖 Asistente: {respuesta_final}")
                        historial.append({"role": "assistant", "content": respuesta_final})
            else:
                respuesta = mensaje_ia.content
                print(f"\n🤖 Asistente: {respuesta}")
                historial.append({"role": "assistant", "content": respuesta})
                
        except Exception as e:
            print(f"\n❌ Error en la comunicación con el modelo: {e}")
        
        finally:
            cerrar_servidor(proceso_servidor)

if __name__ == "__main__":
    proceso_servidor = iniciar_servidor()
    chatear(proceso_servidor)