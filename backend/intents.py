import re

from .apps import abrir_aplicacion
from .management import (
    asociar_jugador_a_equipo,
    crear_equipo,
    crear_torneo,
    inscribir_equipo_en_torneo,
    inscribir_jugador_en_torneo,
    inscribir_multiples_equipos_en_torneo,
    inscribir_y_sortear,
    registrar_jugador,
)
from .sports import (
    actualizar_partido_completo,
    actualizar_stats_jugador,
    añadir_equipo_a_grupo,
    crear_grupo,
    programar_partido,
    realizar_sorteo_eliminatorias,
    realizar_sorteo_grupos,
    registrar_resultado,
    ver_clasificacion,
    ver_clasificacion_grupos,
    ver_cuadro_eliminatorias,
    ver_grupos_y_partidos,
    ver_partidos,
    ver_stats_jugadores,
    ver_jugadores_equipo,
    ver_ranking_equipos,
    ver_ranking_jugadores,
    avanzar_eliminatorias,
    registrar_ganador_penaltis
)
from .sharing import (
    iniciar_servidor_compartir,
    detener_servidor_compartir,
    estado_compartir,
)
from .web import buscar_en_internet, leer_pagina_web
from .help import ayuda_asistente


# ── Constants ──────────────────────────────────────────────────────────────────

PALABRAS_ACCION = [
    "crea", "crear", "registra", "registrar", "añade", "añadir", "agrega",
    "programa", "programar", "inscribe", "inscribir", "actualiza", "actualizar",
    "muestra", "mostrar", "ver", "dame", "dime", "lista", "abre", "abrir",
    "realiza", "realizar", "haz", "genera", "generar", "sortea", "sortear",
]

PALABRAS_ACTUALES = [
    "actual", "ahora", "hoy", "este año", "2024", "2025", "2026",
    "último", "ultima", "reciente", "clasificación", "resultado",
    "goleador", "temporada", "noticias", "precio", "estreno",
]


# ── Helpers ────────────────────────────────────────────────────────────────────

def _r(tipo, texto, herramienta=None):
    """Shorthand response builder."""
    return {"tipo": tipo, "texto": texto, "herramienta": herramienta, "terminado": False}


def _necesita_busqueda(texto: str) -> bool:
    texto_lower = texto.lower()
    if any(texto_lower.startswith(p) or f" {p}" in texto_lower for p in PALABRAS_ACCION):
        return False
    return any(p in texto_lower for p in PALABRAS_ACTUALES)


def _extraer_entre_comillas(texto):
    match = re.search(r'["""](.+?)["""]', texto)
    return match.group(1) if match else None


def _extraer_fecha(texto):
    match = re.search(r'(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})', texto)
    if match:
        f = match.group(1)
        if "/" in f:
            d, m, a = f.split("/")
            return f"{a}-{m}-{d}"
        return f
    return None


def _extraer_resultado(texto):
    match = re.search(r'(\d+)\s*[-–]\s*(\d+)', texto)
    return (int(match.group(1)), int(match.group(2))) if match else None


def _extraer_nombres_con_comillas(texto):
    return re.findall(r'["""](.+?)["""]', texto)


def _extraer_torneo(texto):
    """Extract tournament name from text, using quotes first then pattern."""
    comillas = _extraer_nombres_con_comillas(texto)
    if comillas:
        return comillas[-1]
    m = re.search(
        r'(?:de|del|of|in|para|for|en|al torneo|del torneo|of the tournament)\s+'
        r'["\']?([^"\']+?)["\']?(?:\s+(?:except|excepto|menos|sin|y\b|and\b|grupo|group)|[,.]|\s*$)',
        texto, re.IGNORECASE
    )
    return m.group(1).strip() if m else None


def _extraer_equipo_y_torneo(texto):
    comillas = _extraer_nombres_con_comillas(texto)
    if len(comillas) >= 2:
        return comillas[0].strip(), comillas[1].strip()
    texto_limpio = re.sub(
        r'^(?:registra|registrar|añade|añadir|agrega|agregar|add|inscribe|inscribir'
        r'|apunta|assign|register|mete|meter|pon|poner)'
        r'\s+(?:el|un|al|a|the|al equipo|el equipo|un equipo|a)?\s*(?:equipo|team)?\s+',
        '', texto, flags=re.IGNORECASE
    ).strip()
    m = re.search(
        r'^(.+?)\s+(?:en el torneo|en|in the tournament|in|al torneo|al)\s+(.+)$',
        texto_limpio, re.IGNORECASE
    )
    if m:
        return m.group(1).strip().strip("\"'.,"), m.group(2).strip().strip("\"'.,")
    return None, None


def _extraer_jugador_y_torneo(texto):
    comillas = _extraer_nombres_con_comillas(texto)
    if len(comillas) >= 2:
        return comillas[0].strip(), comillas[1].strip()
    texto_limpio = re.sub(
        r'^(?:registra|registrar|añade|añadir|agrega|add|inscribe|inscribir|apunta|assign|register)'
        r'\s+(?:al|un|a|the)?\s*(?:jugador|player)?\s+',
        '', texto, flags=re.IGNORECASE
    ).strip()
    m = re.search(r'^(.+?)\s+(?:en|in|al torneo|in the tournament)\s+(.+)$', texto_limpio, re.IGNORECASE)
    if m:
        return m.group(1).strip().strip("\"'.,"), m.group(2).strip().strip("\"'.,")
    return None, None


def _extraer_exclusiones(texto):
    """Extract a list of excluded team names from phrases like 'except X and Y'."""
    m = re.search(
        r'(?:except|excepto|menos|sin|excluding|excluyendo)\s+(.+?)'
        r'(?:\s+(?:en|in|to|al|y\b|and\b)\s+|\s*$)',
        texto, re.IGNORECASE
    )
    if not m:
        return []
    partes = re.split(r'\s*(?:,|and\b|y\b)\s*', m.group(1), flags=re.IGNORECASE)
    return [p.strip().strip("\"'.,") for p in partes if p.strip()]


# ── Intent handlers ────────────────────────────────────────────────────────────
# Each handler receives (texto_usuario, t) where t = texto_usuario.lower()
# and returns a response dict or None if it cannot handle the input.

def _handle_crear_torneo(texto, t):
    nombre = _extraer_entre_comillas(texto)
    if not nombre:
        m = re.search(r'(?:llamado|called|named)\s+["\']?([A-Za-z0-9 ]+?)(?:["\']|con|with|$)', texto, re.IGNORECASE)
        nombre = m.group(1).strip() if m else None
    if not nombre:
        return _r("respuesta", "¿Cómo quieres llamar al torneo?")
    return _r("herramienta", crear_torneo(nombre, _extraer_fecha(texto)), "crear_torneo")


def _handle_crear_equipo(texto, t):
    nombre = _extraer_entre_comillas(texto)
    if not nombre:
        m = re.search(r'(?:equipo|team)\s+["\']?([A-Za-z0-9 ]+?)(?:["\']|$)', texto, re.IGNORECASE)
        nombre = m.group(1).strip() if m else None
    if not nombre:
        return _r("respuesta", "¿Cómo quieres llamar al equipo?")
    return _r("herramienta", crear_equipo(nombre), "crear_equipo")


def _handle_inscribir_todos_y_sortear(texto, t):
    nombre_torneo = _extraer_torneo(texto)
    if not nombre_torneo:
        return _r("respuesta", "¿A qué torneo quieres añadir y sortear los equipos?")
    return _r("herramienta", inscribir_y_sortear(nombre_torneo, _extraer_exclusiones(texto)), "inscribir_y_sortear")


def _handle_inscribir_todos(texto, t):
    nombre_torneo = _extraer_torneo(texto)
    if not nombre_torneo:
        return _r("respuesta", "¿A qué torneo quieres añadir todos los equipos?")
    return _r("herramienta", inscribir_multiples_equipos_en_torneo(nombre_torneo, _extraer_exclusiones(texto)), "inscribir_multiples_equipos_en_torneo")


def _handle_inscribir_equipo(texto, t):
    nombre_equipo, nombre_torneo = _extraer_equipo_y_torneo(texto)
    if nombre_equipo and nombre_torneo:
        return _r("herramienta", inscribir_equipo_en_torneo(nombre_equipo, nombre_torneo), "inscribir_equipo_en_torneo")
    return None


def _handle_inscribir_jugador(texto, t):
    nombre_jugador, nombre_torneo = _extraer_jugador_y_torneo(texto)
    if nombre_jugador and nombre_torneo:
        return _r("herramienta", inscribir_jugador_en_torneo(nombre_jugador, nombre_torneo), "inscribir_jugador_en_torneo")
    return None


def _handle_registrar_jugador(texto, t):
    nombre = _extraer_entre_comillas(texto)
    if not nombre:
        nombre = re.sub(r'^(?:registra|añade|agrega|inscribe)\s+(?:al|un|a)?\s*jugador\s+', '', texto, flags=re.IGNORECASE).strip()
        nombre = re.split(r'\s+(?:en|al|a)\s+(?:el\s+torneo\s+)?', nombre, maxsplit=1)[0].strip().strip("\"'.,")
    if not nombre:
        return None
    m_edad = re.search(r'(\d+)\s*años', texto, re.IGNORECASE)
    m_pos  = re.search(r'(?:posicion|posición|juega de|es)\s+([A-Za-z]+)', texto, re.IGNORECASE)
    edad    = int(m_edad.group(1)) if m_edad else None
    posicion = m_pos.group(1).strip() if m_pos else None
    # If a tournament is also mentioned, inscribe instead of just registering
    if "torneo" in t:
        nombre_jugador, nombre_torneo = _extraer_jugador_y_torneo(texto)
        if nombre_jugador and nombre_torneo:
            return _r("herramienta", inscribir_jugador_en_torneo(nombre_jugador, nombre_torneo), "inscribir_jugador_en_torneo")
        m_torneo = re.search(r'(?:en|in|al torneo|del torneo)\s+["\']?([^"\']+?)(?:["\']|\s|$)', texto, re.IGNORECASE)
        if m_torneo:
            return _r("herramienta", inscribir_jugador_en_torneo(nombre, m_torneo.group(1).strip()), "inscribir_jugador_en_torneo")
    return _r("herramienta", registrar_jugador(nombre, edad, posicion), "registrar_jugador")


def _handle_crear_grupo(texto, t):
    comillas = _extraer_nombres_con_comillas(texto)
    m_grupo  = re.search(r'grupo\s+([A-Za-z0-9]+)', texto, re.IGNORECASE)
    nombre_grupo  = comillas[0] if comillas else (f"Grupo {m_grupo.group(1)}" if m_grupo else None)
    m_torneo = re.search(r'(?:en|in|del torneo|of tournament)\s+["\']?([^"\']+?)["\']?\s*$', texto, re.IGNORECASE)
    nombre_torneo = comillas[1] if len(comillas) > 1 else (m_torneo.group(1).strip() if m_torneo else None)
    if not nombre_grupo or not nombre_torneo:
        return _r("respuesta", "Necesito el nombre del grupo y del torneo.")
    return _r("herramienta", crear_grupo(nombre_torneo, nombre_grupo), "crear_grupo")


def _handle_añadir_equipo_a_grupo(texto, t):
    comillas = _extraer_nombres_con_comillas(texto)
    m = re.search(
        r'(?:añade|agrega|add)\s+(?:a\s+|al equipo\s+)?["\']?([^"\']+?)["\']?'
        r'\s+(?:al|to|a)\s+(?:grupo\s+)?([A-Za-z0-9]+)',
        texto, re.IGNORECASE
    )
    m_torneo = re.search(r'(?:de|del torneo|of|in)\s+["\']?([^"\']+?)["\']?\s*$', texto, re.IGNORECASE)
    if not m or not m_torneo:
        return None
    nombre_equipo = comillas[0] if comillas else m.group(1).strip()
    nombre_grupo  = f"Grupo {m.group(2)}" if not m.group(2).lower().startswith("grupo") else m.group(2)
    nombre_torneo = comillas[1] if len(comillas) > 1 else m_torneo.group(1).strip()
    return _r("herramienta", añadir_equipo_a_grupo(nombre_equipo, nombre_grupo, nombre_torneo), "añadir_equipo_a_grupo")


def _handle_programar_partido(texto, t):
    m = re.search(
        r'(?:entre|between)\s+["\']?(.+?)["\']?\s+(?:vs?\.?|contra|and)\s+'
        r'["\']?(.+?)["\']?\s+(?:en|in)\s+["\']?(.+?)["\']?(?:\s|$)',
        texto, re.IGNORECASE
    )
    if not m:
        return None
    m_fase = re.search(r'(?:fase|phase|ronda|round)\s*:?\s*([^\.,]+)', texto, re.IGNORECASE)
    fase = m_fase.group(1).strip() if m_fase else "Fase de grupos"
    return _r("herramienta", programar_partido(m.group(3).strip(), m.group(1).strip(), m.group(2).strip(), _extraer_fecha(texto), fase), "programar_partido")


def _handle_actualizar_partido(texto, t):
    # Extract tournament
    comillas = _extraer_nombres_con_comillas(texto)
    m_torneo = re.search(
        r'(?:en el torneo|del torneo|en|in|of|for|de)\s+["\']?([^"\']+?)["\']?'
        r'(?:\s*[,.]|\s+(?:resultado|result|gol|goal|fase|phase|con\b)|$)',
        texto, re.IGNORECASE
    )
    nombre_torneo = comillas[0] if comillas else (m_torneo.group(1).strip() if m_torneo else None)

    # Extract teams
    texto_sin_verbo = re.sub(
        r'^(?:actualiza|actualizar|update|registra|anota)\s+'
        r'(?:el\s+|la\s+)?(?:partido|match|resultado|el\s+resultado)?\s*',
        '', texto, flags=re.IGNORECASE
    ).strip()
    m_equipos = re.search(
        r'^["\']?([A-Za-záéíóúÁÉÍÓÚñÑ][A-Za-záéíóúÁÉÍÓÚñÑ\s]*?)["\']?'
        r'\s+(?:vs?\.?|contra|versus)\s+'
        r'["\']?([A-Za-záéíóúÁÉÍÓÚñÑ][A-Za-záéíóúÁÉÍÓÚñÑ\s]*?)["\']?'
        r'(?:\s+(?:de|del|en|in|of)|[,.]|$)',
        texto_sin_verbo, re.IGNORECASE
    )
    nombre_local     = m_equipos.group(1).strip() if m_equipos else None
    nombre_visitante = m_equipos.group(2).strip() if m_equipos else None

    # Extract score
    marcador        = _extraer_resultado(texto)
    goles_local     = marcador[0] if marcador else None
    goles_visitante = marcador[1] if marcador else None

    # Extract phase
    m_fase = re.search(
        r'(?:de la fase|de la ronda|fase|ronda|phase|round)\s+(?:de\s+)?'
        r'([^\.,]+?)(?:\s*[,.]|\s+(?:del torneo|de|resultado|gol|con\b)|$)',
        texto, re.IGNORECASE
    )
    fase = m_fase.group(1).strip() if m_fase else None

    # Extract goalscorers
    goleadores = []
    m_goles = re.search(
        r'(?:goles?\s+de|gol\s+de|goals?\s+(?:by|scored\s+by|de))\s+(.+?)'
        r'(?=\s*[,.]?\s*(?:asistencia|assist|tarjeta|con\s+asistencia|$))',
        texto, re.IGNORECASE
    )
    if m_goles:
        partes = re.split(r'\s*(?:,\s*(?:gol\s+de\s+)?|y\b\s*(?:gol\s+de\s+)?|and\b\s*)\s*', m_goles.group(1).strip(), flags=re.IGNORECASE)
        goleadores = [p.strip().strip("\"'.,") for p in partes if p.strip()]

    # Extract assisters
    asistentes = []
    m_asist = re.search(
        r'(?:asistencias?\s+de|asistido\s+por|assists?\s+(?:by|de))\s+(.+?)'
        r'(?=\s*[,.]?\s*(?:gol|goal|tarjeta|minuto|$))',
        texto, re.IGNORECASE
    )
    if m_asist:
        partes = re.split(r'\s*(?:,|y\b|and\b)\s*', m_asist.group(1).strip(), flags=re.IGNORECASE)
        asistentes = [p.strip().strip("\"'.,") for p in partes if p.strip()]

    # Validate
    if not nombre_local or not nombre_visitante:
        return _r("respuesta", "No pude identificar los equipos. Usa el formato: 'Actualiza el partido Brasil vs Francia...'")
    if goles_local is None or goles_visitante is None:
        return _r("respuesta", f"¿Cuál fue el resultado de {nombre_local} vs {nombre_visitante}? Dímelo en formato 2-0.")
    if not nombre_torneo:
        return _r("respuesta", "¿En qué torneo se jugó ese partido?")

    return _r("herramienta", actualizar_partido_completo(
        nombre_torneo, nombre_local, nombre_visitante,
        goles_local, goles_visitante, goleadores, asistentes, fase
    ), "actualizar_partido_completo")


def _handle_registrar_resultado(texto, t):
    m = re.search(
        r'["\']?(.+?)["\']?\s+(\d+)\s*[-–]\s*(\d+)\s+["\']?(.+?)["\']?\s+(?:en|in)\s+["\']?(.+?)["\']?(?:\s|$)',
        texto, re.IGNORECASE
    )
    if not m:
        return None
    return _r("herramienta", registrar_resultado(m.group(5).strip(), m.group(1).strip(), m.group(4).strip(), int(m.group(2)), int(m.group(3))), "registrar_resultado")


def _handle_clasificacion_todos_grupos(texto, t):
    nombre_torneo = _extraer_torneo(texto)
    if not nombre_torneo:
        return _r("respuesta", "¿De qué torneo quieres ver la clasificación de grupos?")
    return _r("herramienta", ver_clasificacion_grupos(nombre_torneo), "ver_clasificacion_grupos")


def _handle_clasificacion_grupo(texto, t):
    nombre_torneo = _extraer_torneo(texto)
    m_grupo = re.search(r'grupo\s+([A-Za-z0-9]+)', texto, re.IGNORECASE)
    nombre_grupo = f"Grupo {m_grupo.group(1).upper()}" if m_grupo else None
    if not nombre_torneo:
        return _r("respuesta", "¿De qué torneo quieres ver la clasificación?")
    if nombre_grupo:
        return _r("herramienta", ver_clasificacion(nombre_torneo, nombre_grupo), "ver_clasificacion")
    return _r("herramienta", ver_clasificacion_grupos(nombre_torneo), "ver_clasificacion_grupos")


def _handle_grupos_y_partidos(texto, t):
    nombre_torneo = _extraer_torneo(texto)
    if not nombre_torneo:
        return _r("respuesta", "¿De qué torneo quieres ver los grupos y partidos?")
    return _r("herramienta", ver_grupos_y_partidos(nombre_torneo), "ver_grupos_y_partidos")


def _handle_ver_partidos(texto, t):
    nombre_torneo = _extraer_torneo(texto)
    if not nombre_torneo:
        return _r("respuesta", "¿De qué torneo quieres ver los partidos?")
    estado = ("jugado"    if any(f in t for f in ["jugado", "played", "terminado"]) else
              "programado" if any(f in t for f in ["programado", "pendiente", "scheduled", "por jugar"]) else None)
    m_fase = re.search(r'(?:de la fase|fase|ronda|phase|round)\s+(?:de\s+)?([^\.,]+?)(?:\s+de|\s+del|\s*$)', texto, re.IGNORECASE)
    fase = m_fase.group(1).strip() if m_fase else None
    return _r("herramienta", ver_partidos(nombre_torneo, estado, fase), "ver_partidos")


def _handle_stats_jugadores(texto, t):
    nombre_torneo = _extraer_torneo(texto)
    if not nombre_torneo:
        return None
    return _r("herramienta", ver_stats_jugadores(nombre_torneo), "ver_stats_jugadores")


def _handle_actualizar_stats_jugador(texto, t):
    comillas = _extraer_nombres_con_comillas(texto)
    m_jugador = re.search(r'(?:de|of|para|for|jugador)\s+["\']?([^"\']+?)["\']?\s+(?:en|in)', texto, re.IGNORECASE)
    m_torneo  = re.search(r'(?:en|in)\s+["\']?([^"\']+?)["\']?(?:\s|$)', texto, re.IGNORECASE)
    nombre_jugador = comillas[0] if comillas else (m_jugador.group(1).strip() if m_jugador else None)
    nombre_torneo  = comillas[1] if len(comillas) > 1 else (m_torneo.group(1).strip() if m_torneo else None)
    if not nombre_jugador or not nombre_torneo:
        return None
    mg  = re.search(r'(\d+)\s*gol',                          texto, re.IGNORECASE)
    ma  = re.search(r'(\d+)\s*asistencia',                   texto, re.IGNORECASE)
    mta = re.search(r'(\d+)\s*(?:tarjeta\s*)?amarilla',      texto, re.IGNORECASE)
    mtr = re.search(r'(\d+)\s*(?:tarjeta\s*)?roja',          texto, re.IGNORECASE)
    mp  = re.search(r'(\d+)\s*partido',                      texto, re.IGNORECASE)
    return _r("herramienta", actualizar_stats_jugador(
        nombre_jugador, nombre_torneo,
        int(mg.group(1))  if mg  else 0,
        int(ma.group(1))  if ma  else 0,
        int(mta.group(1)) if mta else 0,
        int(mtr.group(1)) if mtr else 0,
        int(mp.group(1))  if mp  else 0,
    ), "actualizar_stats_jugador")


def _handle_sorteo_grupos(texto, t):
    nombre_torneo = _extraer_torneo(texto)
    if not nombre_torneo:
        return _r("respuesta", "¿De qué torneo quieres hacer el sorteo de grupos?")
    return _r("herramienta", realizar_sorteo_grupos(nombre_torneo), "realizar_sorteo_grupos")


def _handle_sorteo_eliminatorias(texto, t):
    nombre_torneo = _extraer_torneo(texto)
    if not nombre_torneo:
        return None
    m_cpg = re.search(r'(\d+)\s*(?:clasificados|clasifican|qualify)', texto, re.IGNORECASE)
    cpg = int(m_cpg.group(1)) if m_cpg else None
    return _r("herramienta", realizar_sorteo_eliminatorias(nombre_torneo, cpg), "realizar_sorteo_eliminatorias")


def _handle_avanzar_eliminatorias(texto, t):
    nombre_torneo = _extraer_torneo(texto)
    if not nombre_torneo:
        return _r("respuesta", "¿De qué torneo quieres generar la siguiente ronda?")
    return _r("herramienta", avanzar_eliminatorias(nombre_torneo), "avanzar_eliminatorias")

def _handle_ganador_penaltis(texto, t):
    nombre_torneo = _extraer_torneo(texto)
    comillas = _extraer_nombres_con_comillas(texto)
    m_ganador = re.search(
        r'(?:ganador|winner|gano|ganó|avanza|advances)\s+(?:fue|is|por penaltis)?\s*'
        r'["\']?([A-Za-záéíóúÁÉÍÓÚñÑ][A-Za-záéíóúÁÉÍÓÚñÑ\s]+?)["\']?'
        r'(?:\s+(?:por|by|en|in)|[,.]|$)',
        texto, re.IGNORECASE
    )
    nombre_ganador = comillas[0] if comillas else (m_ganador.group(1).strip() if m_ganador else None)
    if not nombre_ganador:
        return _r("respuesta", "¿Qué equipo ganó por penaltis?")
    if not nombre_torneo:
        return _r("respuesta", "¿En qué torneo?")
    return _r("herramienta", registrar_ganador_penaltis(nombre_torneo, nombre_ganador), "registrar_ganador_penaltis")

def _handle_ver_cuadro(texto, t):
    nombre_torneo = _extraer_torneo(texto)
    if not nombre_torneo:
        return None
    return _r("herramienta", ver_cuadro_eliminatorias(nombre_torneo), "ver_cuadro_eliminatorias")


def _handle_ver_jugadores_equipo(texto, t):
    comillas = _extraer_nombres_con_comillas(texto)
    m_equipo = re.search(
        r'(?:jugadores\s+de|plantilla\s+de|squad\s+of|players\s+of|players\s+from)\s+'
        r'["\']?([^"\']+?)["\']?(?:\s+(?:en|in|del torneo|con stats)|[,.]|$)',
        texto, re.IGNORECASE
    )
    nombre_equipo = comillas[0] if comillas else (m_equipo.group(1).strip() if m_equipo else None)
    if not nombre_equipo:
        return _r("respuesta", "¿De qué equipo quieres ver los jugadores?")

    # Optional tournament for stats
    nombre_torneo = None
    if any(f in t for f in ["en el torneo", "en ", "in ", "con stats", "with stats"]):
        m_torneo = re.search(
            r'(?:en el torneo|en|in|del torneo|with stats from|con stats de)\s+'
            r'["\']?([^"\']+?)["\']?(?:\s|$)',
            texto, re.IGNORECASE
        )
        nombre_torneo = comillas[1] if len(comillas) > 1 else (m_torneo.group(1).strip() if m_torneo else None)

    return _r("herramienta", ver_jugadores_equipo(nombre_equipo, nombre_torneo), "ver_jugadores_equipo")


def _handle_ranking_jugadores(texto, t):
    nombre_torneo = _extraer_torneo(texto)
    if not nombre_torneo:
        return _r("respuesta", "¿De qué torneo quieres ver el ranking de jugadores?")
    m_top = re.search(r'top\s*(\d+)', texto, re.IGNORECASE)
    top = int(m_top.group(1)) if m_top else 10
    return _r("herramienta", ver_ranking_jugadores(nombre_torneo, top), "ver_ranking_jugadores")


def _handle_ranking_equipos(texto, t):
    nombre_torneo = _extraer_torneo(texto)
    if not nombre_torneo:
        return _r("respuesta", "¿De qué torneo quieres ver el ranking de equipos?")
    m_top = re.search(r'top\s*(\d+)', texto, re.IGNORECASE)
    top = int(m_top.group(1)) if m_top else 10
    return _r("herramienta", ver_ranking_equipos(nombre_torneo, top), "ver_ranking_equipos")


def _handle_iniciar_compartir(texto, t):
    # Check if user specified a folder
    m = re.search(
        r'(?:carpeta|folder|directorio|directory|desde|from)\s+["\']?([^"\']+?)["\']?(?:\s|$)',
        texto, re.IGNORECASE
    )
    carpeta = m.group(1).strip() if m else None
    return _r("herramienta", iniciar_servidor_compartir(carpeta), "iniciar_servidor_compartir")


def _handle_detener_compartir(texto, t):
    return _r("herramienta", detener_servidor_compartir(), "detener_servidor_compartir")


def _handle_estado_compartir(texto, t):
    return _r("herramienta", estado_compartir(), "estado_compartir")


# ── Intent registry ────────────────────────────────────────────────────────────
# Each entry: {"triggers": [...], "handler": fn}
# Triggers are checked against t = texto.lower()
# Order matters — more specific triggers must come before general ones.

INTENT_REGISTRY = [

    # ── Tournaments ────────────────────────────────────────────────────────
    {
        "triggers": ["crea el torneo", "crea un torneo", "crear torneo", "nuevo torneo"],
        "handler":  _handle_crear_torneo,
    },

    # ── Teams ──────────────────────────────────────────────────────────────
    {
        "triggers": ["crea el equipo", "crea un equipo", "crear equipo", "nuevo equipo"],
        "handler":  _handle_crear_equipo,
    },

    # ── Add all teams + draw groups (must be before add-all and draw separately)
    {
        "triggers": ["todos los equipos", "all teams", "all the teams"],
        "extra_check": lambda t: any(f in t for f in ["sorteo", "grupos", "groups", "draft", "distribu", "reparte", "divide"]),
        "handler":  _handle_inscribir_todos_y_sortear,
    },

    # ── Add all teams (no draft)
    {
        "triggers": ["todos los equipos", "all teams", "all the teams", "todos los equipos de la base", "all teams from"],
        "handler":  _handle_inscribir_todos,
    },

    # ── Add single team to tournament (must be before player inscription)
    {
        "triggers": ["inscribe", "inscribir", "apunta", "mete", "meter", "pon ", "poner", "añade", "añadir", "agrega", "agregar", "registra", "registrar"],
        "extra_check": lambda t: (
            any(f in t for f in [" en ", " al ", " in ", " to "]) and
            not any(f in t for f in ["jugador", "player", "grupo", "group", "partido", "resultado", "gol", "stats", "todos", "all"])
        ),
        "handler": _handle_inscribir_equipo,
    },

    # ── Add player to tournament
    {
        "triggers": ["inscribe", "inscribir", "apunta", "mete", "meter", "añade", "añadir", "agrega", "agregar", "registra", "registrar"],
        "extra_check": lambda t: (
            any(f in t for f in [" en ", " al ", " in ", " to "]) and
            any(f in t for f in ["jugador", "player"])
        ),
        "handler": _handle_inscribir_jugador,
    },

    # ── Register new player
    {
        "triggers": ["registra al jugador", "registra un jugador", "registra jugador",
                     "añade al jugador", "añade un jugador", "agrega al jugador",
                     "agrega un jugador", "inscribe al jugador", "inscribe un jugador",
                     "nuevo jugador"],
        "handler": _handle_registrar_jugador,
    },

    # ── Groups ─────────────────────────────────────────────────────────────
    {
        "triggers": ["crea el grupo", "crea un grupo", "crear grupo", "nuevo grupo"],
        "handler":  _handle_crear_grupo,
    },
    {
        "triggers": ["añade", "agrega", "add"],
        "extra_check": lambda t: "grupo" in t,
        "handler": _handle_añadir_equipo_a_grupo,
    },

    # ── Matches ────────────────────────────────────────────────────────────
    {
        "triggers": ["programa el partido", "programa un partido", "programar partido", "partido entre"],
        "handler":  _handle_programar_partido,
    },
    {
        "triggers": ["actualiza el partido", "actualizar el partido", "update the match",
                     "actualiza el resultado", "update match", "registra el partido",
                     "anota el resultado"],
        "handler":  _handle_actualizar_partido,
    },
    {
        "triggers": ["registra el resultado", "registra resultado", "el resultado fue",
                     "ganó", "gano", "empató", "empato", "termino", "terminó"],
        "handler":  _handle_registrar_resultado,
    },

    # ── Views — standings (all groups before single group) ─────────────────
    {
        "triggers": ["clasificacion", "clasificación", "tabla de posiciones", "standings",
                     "clasificacion de grupos", "group standings", "todas las tablas",
                     "all standings", "todos los grupos", "clasificacion general",
                     "general standings"],
        "extra_check": lambda t: (
            any(f in t for f in ["todos", "todas", "all", "general", "completa", "entera", "grupos", "groups"]) and
            not re.search(r'grupo\s+[a-zA-Z]\b', t)
        ),
        "handler": _handle_clasificacion_todos_grupos,
    },
    {
        "triggers": ["clasificacion", "clasificación", "tabla de posiciones", "standings",
                     "tabla del grupo", "group standings", "posiciones del grupo",
                     "clasificacion del grupo", "ver clasificacion"],
        "handler":  _handle_clasificacion_grupo,
    },

    # ── Views — groups and matches ─────────────────────────────────────────
    {
        "triggers": ["grupos y partidos", "groups and matches", "grupos y sus partidos",
                     "grupos con sus partidos", "dime los grupos", "muestra los grupos",
                     "show the groups", "show groups", "ver grupos", "grupos del torneo",
                     "qué grupos hay", "que grupos hay", "cuáles son los grupos",
                     "cuales son los grupos"],
        "handler":  _handle_grupos_y_partidos,
    },

    # ── Views — matches ────────────────────────────────────────────────────
    {
        "triggers": ["ver partidos", "muestra los partidos", "partidos del", "fixture",
                     "calendario de partidos", "dime los partidos", "cuales son los partidos",
                     "qué partidos", "que partidos", "partidos programados", "partidos pendientes",
                     "partidos jugados", "show matches", "show the matches", "what matches",
                     "scheduled matches", "list matches", "matches for", "partidos de",
                     "enfrentamientos", "partidos del torneo"],
        "handler":  _handle_ver_partidos,
    },

    {
        "triggers": ["jugadores de", "plantilla de", "squad of", "players of",
                     "players from", "jugadores del equipo", "ver jugadores",
                     "muestra los jugadores", "dime los jugadores", "show players",
                     "quienes juegan en", "quiénes juegan en"],
        "handler": _handle_ver_jugadores_equipo,
    },
    {
        "triggers": ["ranking de jugadores", "ranking de goleadores", "ranking de asistentes",
                     "top goleadores", "top asistentes", "top scorers", "top assisters",
                     "mejor goleador", "mejores goleadores", "tabla de goleadores",
                     "tabla de asistentes", "goleadores del torneo", "asistentes del torneo",
                     "quién ha marcado", "quien ha marcado", "quién lleva más goles",
                     "quien lleva mas goles", "máximo goleador", "maximo goleador",
                     "top de goleadores", "top de asistentes", "scorers", "assisters",
                     "who scored", "most goals scored", "most assists"],
        "handler": _handle_ranking_jugadores,
    },
    {
        "triggers": ["ranking de equipos", "top equipos", "equipos con mas goles",
                     "equipos con más goles", "menos goles encajados", "mejor defensa",
                     "mejor ataque", "team rankings", "most goals", "fewest goals conceded",
                     "que equipo ha marcado", "qué equipo ha marcado", "equipo con más goles",
                     "equipo con mas goles", "equipos más goleadores", "equipos mas goleadores",
                     "mejor equipo", "peor defensa", "team stats", "estadisticas de equipos",
                     "estadísticas de equipos", "ranking equipos"],
        "handler": _handle_ranking_equipos,
    },

    # ── Views — player stats (general) ────────────────────────────────────
    {
        "triggers": ["stats de jugadores", "estadisticas de jugadores",
                     "estadísticas de jugadores", "goleadores", "ver stats",
                     "stats del torneo", "estadisticas del torneo", "estadísticas del torneo",
                     "stats de", "muestra las stats", "show stats", "player stats",
                     "estadisticas generales", "estadísticas generales",
                     "resumen estadisticas", "resumen estadísticas",
                     "dime las stats", "dime las estadisticas", "dime las estadísticas"],
        "handler":  _handle_stats_jugadores,
    },

    # ── Update player stats manually ───────────────────────────────────────
    {
        "triggers": ["actualiza las stats", "actualiza stats", "añade goles",
                     "registra goles", "añade asistencias"],
        "handler":  _handle_actualizar_stats_jugador,
    },

    # ── File sharing ───────────────────────────────────────────────────────
    {
        "triggers": ["compartir archivos", "compartir ficheros", "iniciar compartir",
                     "share files", "start sharing", "activar compartir",
                     "servidor de archivos", "file server", "enviar archivos",
                     "recibir archivos", "compartir carpeta"],
        "handler": _handle_iniciar_compartir,
    },
    {
        "triggers": ["detener compartir", "parar compartir", "stop sharing",
                     "apagar servidor de archivos", "desactivar compartir"],
        "handler": _handle_detener_compartir,
    },
    {
        "triggers": ["estado compartir", "compartir activo", "sharing status",
                     "está compartiendo", "esta compartiendo", "is sharing"],
        "handler": _handle_estado_compartir,
    },

    # ── Draws ──────────────────────────────────────────────────────────────
    {
        "triggers": ["sorteo de grupos", "realiza el sorteo", "haz el sorteo",
                     "sortear grupos", "realizar sorteo", "draw de grupos",
                     "draft", "distribuye", "distribúyelos", "reparte",
                     "divide los equipos", "organiza los grupos", "crea los grupos"],
        "handler":  _handle_sorteo_grupos,
    },
    {
        "triggers": ["sorteo de eliminatorias", "cuadro de eliminatorias",
                     "genera las eliminatorias", "crea las eliminatorias",
                     "ronda eliminatoria", "knockout draw", "fase eliminatoria"],
        "handler":  _handle_sorteo_eliminatorias,
    },
    {
        "triggers": ["ver cuadro", "muestra el cuadro", "ver eliminatorias",
                     "muestra las eliminatorias", "bracket"],
        "handler":  _handle_ver_cuadro,
    },
    {
        "triggers": ["siguiente ronda", "next round", "genera la siguiente",
                     "avanzar eliminatorias", "avanzar ronda", "generar siguiente ronda",
                     "siguiente fase", "próxima ronda", "proxima ronda",
                     "crear siguiente ronda", "generate next round"],
        "handler": _handle_avanzar_eliminatorias,
    },
    {
        "triggers": ["ganador por penaltis", "gano por penaltis", "ganó por penaltis",
                     "winner on penalties", "won on penalties", "avanza por penaltis",
                     "penaltis", "penalties"],
        "handler": _handle_ganador_penaltis,
    },
]


# ── Dispatcher ─────────────────────────────────────────────────────────────────

def intentar_accion_deportiva(session, texto_usuario):
    t = texto_usuario.lower()

    for intent in INTENT_REGISTRY:
        # Check triggers
        if not any(trigger in t for trigger in intent["triggers"]):
            continue
        # Check optional extra condition
        if "extra_check" in intent and not intent["extra_check"](t):
            continue
        # Run handler
        resultado = intent["handler"](texto_usuario, t)
        if resultado is not None:
            return resultado

    return None