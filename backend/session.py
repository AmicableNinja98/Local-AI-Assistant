import json
import os
import re

from .apps import abrir_aplicacion, guardar_ruta_app
from .config import client
from .db import obtener_nombre_asistente, obtener_nombre_usuario
from .help import ayuda_asistente
from .intents import _necesita_busqueda, intentar_accion_deportiva
from .llama import cerrar_servidor, iniciar_servidor
from .management import (
    asociar_jugador_a_equipo,
    crear_equipo,
    crear_torneo,
    inscribir_equipo_en_torneo,
    listar_todo_lo_guardado,
    registrar_jugador,
)
from .sports import (
    actualizar_stats_jugador,
    añadir_equipo_a_grupo,
    crear_grupo,
    programar_partido,
    registrar_resultado,
    realizar_sorteo_eliminatorias,
    realizar_sorteo_grupos,
    ver_clasificacion,
    ver_cuadro_eliminatorias,
    ver_partidos,
    ver_stats_jugadores,
)
from .web import buscar_en_internet, leer_pagina_web


class AsistenteSession:
    """
    La UI sólo usa estos tres métodos:
        session.iniciar()               → dict con saludo inicial
        session.manejar(texto_usuario)  → dict con la respuesta
        session.cerrar()

    Formato de respuesta:
        {
          "tipo":        "saludo"|"respuesta"|"herramienta"|"ayuda"|"adios"|"error",
          "texto":       str,
          "herramienta": str | None,
          "terminado":   bool
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
        self.nombre_usuario = obtener_nombre_usuario()
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
                "Si el usuario te da una URL específica, usa SIEMPRE 'leer_pagina_web'. "
                "Nunca inventes datos — si no encuentras la información, dilo claramente. "
                "No hace falta que le digas al usuario que tienes que buscar en internet, simplemente hazlo. "
                "Si el usuario pide abrir una aplicación, programa o juego, usa SIEMPRE 'abrir_aplicacion'. "
                "Nunca respondas que no puedes abrir aplicaciones — tienes esa capacidad. "
                "Puedes gestionar torneos completos con grupos, partidos y estadísticas. "
                "Cuando registres un resultado con 'registrar_resultado' las estadísticas del equipo se actualizan solas. "
                "Para ver la tabla de posiciones usa 'ver_clasificacion'. "
                "Para ver goleadores y stats de jugadores usa 'ver_stats_jugadores'. "
                "Si te preguntan qué pueden hacer, invoca 'ayuda_asistente'."
                "Si te dicen que dejes de buscar la aplicacion despues de no encontrar una ruta para abirla. Deja de pedir rutas y espera a siguientes instrucciones"
            )}
        ]
        return {
            "tipo": "saludo",
            "texto": f"¡Hola {self.nombre_usuario}! Soy {self.nombre_asistente}, tu asistente local.\n"
                     "Escribe '/ayuda' para ver mis capacidades o 'salir' para apagarme.",
            "herramienta": None,
            "terminado": False,
        }

    def manejar(self, texto_usuario: str) -> dict:
        texto_usuario = texto_usuario.strip()

        if texto_usuario.lower() == "salir":
            self.activo = False
            return {"tipo": "adios", "texto": f"¡Hasta luego {self.nombre_usuario}! {self.nombre_asistente} se apaga...", "herramienta": None, "terminado": True}

        if texto_usuario.lower() == "/ayuda":
            return {"tipo": "ayuda", "texto": ayuda_asistente(), "herramienta": None, "terminado": False}

        if self._app_pendiente:
            texto = texto_usuario.strip().lower()
            app_pendiente = self._app_pendiente
            if any(texto in frase for frase in ["cancelar", "cancel", "no", "nah", "nada", "omitir", "ignorar"]):
                self._app_pendiente = None
                return {
                    "tipo": "respuesta",
                    "texto": f"Entendido. He cancelado la solicitud de ruta para '{app_pendiente}' y espero nuevas instrucciones.",
                    "herramienta": None,
                    "terminado": False,
                }

            ruta = texto_usuario.strip().strip('"\'')
            if os.path.exists(ruta):
                guardar_ruta_app(self._app_pendiente, ruta)
                nombre = self._app_pendiente
                self._app_pendiente = None
                try:
                    os.startfile(ruta)
                    return {"tipo": "herramienta", "texto": f"Ruta guardada y '{nombre}' abierta correctamente. La próxima vez la abriré automáticamente.", "herramienta": "abrir_aplicacion", "terminado": False}
                except Exception as e:
                    return {"tipo": "error", "texto": f"Ruta guardada pero no se pudo abrir: {e}", "herramienta": None, "terminado": False}
            return {"tipo": "respuesta", "texto": "No encontré ningún archivo en esa ruta. Comprueba que sea correcta e inténtalo de nuevo o escribe 'cancelar' para detener esta tarea.", "herramienta": None, "terminado": False}

        PALABRAS_ABRIR = ["abre ", "abrir ", "open ", "lanza ", "lanzar ", "ejecuta ", "ejecutar ", "inicia ", "iniciar "]
        texto_lower = texto_usuario.lower()

        if any(texto_lower.startswith(p) or f" {p}" in texto_lower for p in PALABRAS_ABRIR):
            nombre_app = texto_usuario
            for p in PALABRAS_ABRIR:
                nombre_app = re.sub(p, "", nombre_app, flags=re.IGNORECASE).strip()
            for filler in ["la aplicación", "la aplicacion", "el programa", "el juego", "la app", "por favor", "porfavor"]:
                nombre_app = re.sub(filler, "", nombre_app, flags=re.IGNORECASE).strip()

            ruta_inline = None
            path_patterns = [
                r'(?:la ruta es|ruta:|path:|this is the path|the path is|su ruta es|está en|esta en)\s*["\']?([\w:\\/\s\.\-\_]+\.exe)["\']?',
                r'["\']?((?:[A-Za-z]:\\|\/)[^\s"\']+\.exe)["\']?',
            ]
            for pattern in path_patterns:
                match = re.search(pattern, texto_usuario, re.IGNORECASE)
                if match:
                    ruta_inline = match.group(1).strip().strip('"\'')
                    nombre_app = texto_usuario[:match.start()].strip()
                    for p in PALABRAS_ABRIR:
                        nombre_app = re.sub(p, "", nombre_app, flags=re.IGNORECASE).strip()
                    for filler in ["la aplicación", "la aplicacion", "el programa", "el juego", "la app", "la ruta es", "ruta:", "path:", "this is the path", "the path is", "su ruta es", "está en", "esta en", ",", "por favor", "porfavor"]:
                        nombre_app = re.sub(filler, "", nombre_app, flags=re.IGNORECASE).strip()
                    nombre_app = nombre_app.strip(" .,")
                    break

            if nombre_app:
                if ruta_inline:
                    if os.path.exists(ruta_inline):
                        guardar_ruta_app(nombre_app, ruta_inline)
                        try:
                            os.startfile(ruta_inline)
                            return {"tipo": "herramienta", "texto": f"Ruta guardada y '{nombre_app}' abierta correctamente. La próxima vez la abriré automáticamente.", "herramienta": "abrir_aplicacion", "terminado": False}
                        except Exception as e:
                            return {"tipo": "error", "texto": f"Ruta guardada pero no se pudo abrir '{nombre_app}': {e}", "herramienta": None, "terminado": False}
                    return {"tipo": "respuesta", "texto": f"Guardé el nombre '{nombre_app}' pero no encontré ningún archivo en:\n{ruta_inline}\nComprueba que la ruta sea correcta e inténtalo de nuevo.", "herramienta": None, "terminado": False}

                resultado = abrir_aplicacion(nombre_app)
                if resultado["estado"] == "no_encontrada":
                    self._app_pendiente = resultado["app"]
                    return {"tipo": "respuesta", "texto": f"No encontré '{resultado['app']}' automáticamente.\n¿Puedes decirme la ruta completa del ejecutable?\n(Ej: C:\\Program Files\\App\\app.exe)\nO dime directamente: 'Abre {resultado['app']}, la ruta es C:\\...\\app.exe'", "herramienta": "abrir_aplicacion", "terminado": False}
                return {"tipo": "herramienta", "texto": resultado["mensaje"], "herramienta": "abrir_aplicacion", "terminado": False}

        accion = intentar_accion_deportiva(self, texto_usuario)
        if accion:
            return accion

        if texto_usuario.startswith("/buscar "):
            query = texto_usuario[8:]
            datos = buscar_en_internet(query)
            contexto = (f"Pregunta: {query}\nContexto de internet:\n{datos}\nResponde basándote estrictamente en estos datos sin inventar nada.")
            self.historial.append({"role": "user", "content": contexto})
        else:
            self.historial.append({"role": "user", "content": texto_usuario})

        urls = re.findall(r'https?://\S+', texto_usuario)
        if urls:
            url = urls[0]
            contenido = leer_pagina_web(url)
            pregunta_sin_url = texto_usuario.replace(url, "").strip()
            if contenido.startswith("PAGINA_JS_DETECTADA"):
                dominio = url.split("/")[2]
                contenido = buscar_en_internet(f"site:{dominio} {pregunta_sin_url or 'informacion'}")
            self.historial.append({"role": "user", "content": f"Contenido real de {url}:\n{contenido}\n\nUsando ÚNICAMENTE este contenido, responde: {pregunta_sin_url or texto_usuario}\nSé específico con nombres, cifras y fechas. No inventes nada."})
            if len(self.historial) > 14:
                self.historial = [self.historial[0]] + self.historial[-12:]
            try:
                respuesta = client.chat.completions.create(model="local-model", messages=self.historial)
                respuesta_final = respuesta.choices[0].message.content
                self.historial.append({"role": "assistant", "content": respuesta_final})
                return {"tipo": "herramienta", "texto": respuesta_final, "herramienta": "leer_pagina_web", "terminado": False}
            except Exception as e:
                return {"tipo": "error", "texto": f"Error: {e}", "herramienta": None, "terminado": False}

        if len(self.historial) > 14:
            self.historial = [self.historial[0]] + self.historial[-12:]

        try:
            completion = client.chat.completions.create(
                model="local-model",
                messages=self.historial,
                tools=TOOLS,
                tool_choice="auto",
                temperature=0.4,
            )
            mensaje_ia = completion.choices[0].message

            if mensaje_ia.tool_calls:
                tool_call = mensaje_ia.tool_calls[0]
                nombre_func = tool_call.function.name
                argumentos = json.loads(tool_call.function.arguments)
                funcion = FUNCIONES_MAPA.get(nombre_func)
                resultado = (funcion(**argumentos) if funcion else "Herramienta no encontrada.") if nombre_func != "abrir_aplicacion" else None

                if nombre_func == "ayuda_asistente":
                    self.historial.append({"role": "assistant", "content": "He mostrado el menú de ayuda."})
                    return {"tipo": "ayuda", "texto": ayuda_asistente(), "herramienta": nombre_func, "terminado": False}

                if nombre_func in ("buscar_en_internet", "leer_pagina_web"):
                    self.historial.append(mensaje_ia)
                    self.historial.append({"role": "tool", "tool_call_id": tool_call.id, "name": nombre_func, "content": resultado})
                    self.historial.append({"role": "user", "content": "Usando ÚNICAMENTE la información obtenida anteriormente, responde la pregunta original con datos concretos y específicos. No uses frases como 'según mis fuentes' ni dejes campos vacíos con corchetes. Si la información no está en los resultados, dilo claramente."})
                    segunda = client.chat.completions.create(model="local-model", messages=self.historial)
                    respuesta_final = segunda.choices[0].message.content
                    self.historial.append({"role": "assistant", "content": respuesta_final})
                    return {"tipo": "herramienta", "texto": respuesta_final, "herramienta": nombre_func, "terminado": False}

                if nombre_func == "abrir_aplicacion":
                    resultado = abrir_aplicacion(**argumentos)
                    if resultado["estado"] == "no_encontrada":
                        self._app_pendiente = resultado["app"]
                        self.historial.append({"role": "assistant", "content": resultado["mensaje"]})
                        return {"tipo": "respuesta", "texto": f"No encontré '{resultado['app']}' automáticamente. ¿Puedes decirme la ruta completa del ejecutable?\n(Ej: C:\\Program Files\\App\\app.exe)", "herramienta": nombre_func, "terminado": False}
                    self.historial.append({"role": "assistant", "content": resultado["mensaje"]})
                    return {"tipo": "herramienta", "texto": resultado["mensaje"], "herramienta": nombre_func, "terminado": False}

                self.historial.append(mensaje_ia)
                self.historial.append({"role": "tool", "tool_call_id": tool_call.id, "name": nombre_func, "content": str(resultado)})
                segunda = client.chat.completions.create(model="local-model", messages=self.historial)
                respuesta_final = segunda.choices[0].message.content
                self.historial.append({"role": "assistant", "content": respuesta_final})
                return {"tipo": "herramienta", "texto": respuesta_final, "herramienta": nombre_func, "terminado": False}

            respuesta = mensaje_ia.content
            modelo_finge_buscar = any(frase in respuesta.lower() for frase in [
                "buscar en internet", "buscar en la web", "consultando fuentes",
                "según mis fuentes", "luego de buscar", "he encontrado en internet",
            ])

            if modelo_finge_buscar or _necesita_busqueda(texto_usuario):
                datos = buscar_en_internet(texto_usuario)
                self.historial.append({"role": "user", "content": f"Resultados reales de búsqueda web:\n{datos}\n\nResponde la pregunta original usando SÓLO estos datos. Sé específico con nombres, cifras y fechas. No dejes nada entre corchetes ni digas que no tienes información."})
                segunda = client.chat.completions.create(model="local-model", messages=self.historial)
                respuesta_final = segunda.choices[0].message.content
                self.historial.append({"role": "assistant", "content": respuesta_final})
                return {"tipo": "herramienta", "texto": respuesta_final, "herramienta": "buscar_en_internet", "terminado": False}

            self.historial.append({"role": "assistant", "content": respuesta})
            return {"tipo": "respuesta", "texto": respuesta, "herramienta": None, "terminado": False}

        except Exception as e:
            return {"tipo": "error", "texto": f"Error de comunicación con el modelo: {e}", "herramienta": None, "terminado": False}

    def cerrar(self):
        self.activo = False
        cerrar_servidor(self.proceso_servidor)


TOOLS = [
    {"type": "function", "function": {"name": "ayuda_asistente", "description": "Muestra las capacidades del asistente.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "buscar_en_internet", "description": "Busca información actualizada en internet. Úsala SIEMPRE que el usuario pregunte sobre eventos, noticias, personas, precios, resultados deportivos, o cualquier cosa que pueda haber cambiado después de 2022.", "parameters": {"type": "object", "properties": {"consulta": {"type": "string"}}, "required": ["consulta"]}}},
    {"type": "function", "function": {"name": "leer_pagina_web", "description": "Lee el contenido completo de una URL específica.", "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}}},
    {"type": "function", "function": {"name": "abrir_aplicacion", "description": "Abre una aplicación instalada en el PC del usuario.", "parameters": {"type": "object", "properties": {"nombre": {"type": "string"}}, "required": ["nombre"]}}},
    {"type": "function", "function": {"name": "registrar_jugador", "description": "Registra un jugador.", "parameters": {"type": "object", "properties": {"nombre": {"type": "string"}, "edad": {"type": "integer"}, "posicion": {"type": "string"}}, "required": ["nombre"]}}},
    {"type": "function", "function": {"name": "crear_equipo", "description": "Crea un equipo deportivo.", "parameters": {"type": "object", "properties": {"nombre": {"type": "string"}}, "required": ["nombre"]}}},
    {"type": "function", "function": {"name": "asociar_jugador_a_equipo", "description": "Asigna un jugador a un equipo.", "parameters": {"type": "object", "properties": {"nombre_jugador": {"type": "string"}, "nombre_equipo": {"type": "string"}}, "required": ["nombre_jugador", "nombre_equipo"]}}},
    {"type": "function", "function": {"name": "crear_torneo", "description": "Crea un torneo.", "parameters": {"type": "object", "properties": {"nombre": {"type": "string"}, "fecha_inicio": {"type": "string"}}, "required": ["nombre"]}}},
    {"type": "function", "function": {"name": "inscribir_equipo_en_torneo", "description": "Inscribe un equipo en un torneo.", "parameters": {"type": "object", "properties": {"nombre_equipo": {"type": "string"}, "nombre_torneo": {"type": "string"}}, "required": ["nombre_equipo", "nombre_torneo"]}}},
    {"type": "function", "function": {"name": "listar_todo_lo_guardado", "description": "Muestra todos los registros guardados.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "crear_grupo", "description": "Crea un grupo dentro de un torneo.", "parameters": {"type": "object", "properties": {"nombre_torneo": {"type": "string"}, "nombre_grupo": {"type": "string"}}, "required": ["nombre_torneo", "nombre_grupo"]}}},
    {"type": "function", "function": {"name": "añadir_equipo_a_grupo", "description": "Añade un equipo a un grupo de un torneo.", "parameters": {"type": "object", "properties": {"nombre_equipo": {"type": "string"}, "nombre_grupo": {"type": "string"}, "nombre_torneo": {"type": "string"}}, "required": ["nombre_equipo", "nombre_grupo", "nombre_torneo"]}}},
    {"type": "function", "function": {"name": "programar_partido", "description": "Programa un partido entre dos equipos.", "parameters": {"type": "object", "properties": {"nombre_torneo": {"type": "string"}, "nombre_local": {"type": "string"}, "nombre_visitante": {"type": "string"}, "fecha": {"type": "string"}, "fase": {"type": "string"}, "nombre_grupo": {"type": "string"}}, "required": ["nombre_torneo", "nombre_local", "nombre_visitante"]}}},
    {"type": "function", "function": {"name": "registrar_resultado", "description": "Registra el resultado de un partido y actualiza estadísticas automáticamente.", "parameters": {"type": "object", "properties": {"nombre_torneo": {"type": "string"}, "nombre_local": {"type": "string"}, "nombre_visitante": {"type": "string"}, "goles_local": {"type": "integer"}, "goles_visitante": {"type": "integer"}}, "required": ["nombre_torneo", "nombre_local", "nombre_visitante", "goles_local", "goles_visitante"]}}},
    {"type": "function", "function": {"name": "ver_clasificacion", "description": "Muestra la tabla de posiciones de un torneo, opcionalmente por grupo.", "parameters": {"type": "object", "properties": {"nombre_torneo": {"type": "string"}, "nombre_grupo": {"type": "string"}}, "required": ["nombre_torneo"]}}},
    {"type": "function", "function": {"name": "ver_partidos", "description": "Muestra los partidos de un torneo.", "parameters": {"type": "object", "properties": {"nombre_torneo": {"type": "string"}, "estado": {"type": "string", "enum": ["programado", "jugado"]}, "fase": {"type": "string"}}, "required": ["nombre_torneo"]}}},
    {"type": "function", "function": {"name": "actualizar_stats_jugador", "description": "Añade estadísticas a un jugador en un torneo.", "parameters": {"type": "object", "properties": {"nombre_jugador": {"type": "string"}, "nombre_torneo": {"type": "string"}, "goles": {"type": "integer"}, "asistencias": {"type": "integer"}, "tarjetas_amarillas": {"type": "integer"}, "tarjetas_rojas": {"type": "integer"}, "partidos_jugados": {"type": "integer"}}, "required": ["nombre_jugador", "nombre_torneo"]}}},
    {"type": "function", "function": {"name": "ver_stats_jugadores", "description": "Muestra las estadísticas de jugadores en un torneo.", "parameters": {"type": "object", "properties": {"nombre_torneo": {"type": "string"}, "top": {"type": "integer"}}, "required": ["nombre_torneo"]}}},
    {"type": "function", "function": {"name": "realizar_sorteo_grupos", "description": "Realiza el sorteo de grupos de un torneo automáticamente según el número de equipos inscritos.", "parameters": {"type": "object", "properties": {"nombre_torneo": {"type": "string"}, "semilla": {"type": "integer"}}, "required": ["nombre_torneo"]}}},
    {"type": "function", "function": {"name": "realizar_sorteo_eliminatorias", "description": "Genera el cuadro de eliminatorias desde los clasificados de la fase de grupos.", "parameters": {"type": "object", "properties": {"nombre_torneo": {"type": "string"}, "clasificados_por_grupo": {"type": "integer"}}, "required": ["nombre_torneo"]}}},
    {"type": "function", "function": {"name": "ver_cuadro_eliminatorias", "description": "Muestra el cuadro de eliminatorias con enfrentamientos y resultados.", "parameters": {"type": "object", "properties": {"nombre_torneo": {"type": "string"}}, "required": ["nombre_torneo"]}}},
]

FUNCIONES_MAPA = {
    "ayuda_asistente": ayuda_asistente,
    "buscar_en_internet": buscar_en_internet,
    "leer_pagina_web": leer_pagina_web,
    "abrir_aplicacion": abrir_aplicacion,
    "registrar_jugador": registrar_jugador,
    "crear_equipo": crear_equipo,
    "asociar_jugador_a_equipo": asociar_jugador_a_equipo,
    "crear_torneo": crear_torneo,
    "inscribir_equipo_en_torneo": inscribir_equipo_en_torneo,
    "listar_todo_lo_guardado": listar_todo_lo_guardado,
    "crear_grupo": crear_grupo,
    "añadir_equipo_a_grupo": añadir_equipo_a_grupo,
    "programar_partido": programar_partido,
    "registrar_resultado": registrar_resultado,
    "ver_clasificacion": ver_clasificacion,
    "ver_partidos": ver_partidos,
    "actualizar_stats_jugador": actualizar_stats_jugador,
    "ver_stats_jugadores": ver_stats_jugadores,
    "realizar_sorteo_grupos": realizar_sorteo_grupos,
    "realizar_sorteo_eliminatorias": realizar_sorteo_eliminatorias,
    "ver_cuadro_eliminatorias": ver_cuadro_eliminatorias,
}
