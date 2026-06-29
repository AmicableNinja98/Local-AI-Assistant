import re

from .apps import abrir_aplicacion
from .management import (
    asociar_jugador_a_equipo,
    crear_equipo,
    crear_torneo,
    inscribir_equipo_en_torneo,
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
from .help import ayuda_asistente


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


def _necesita_busqueda(texto: str) -> bool:
    texto_lower = texto.lower()
    if any(texto_lower.startswith(p) or f" {p}" in texto_lower for p in PALABRAS_ACCION):
        return False
    return any(p in texto_lower for p in PALABRAS_ACTUALES)


def _extraer_entre_comillas(texto):
    match = re.search(r'["“”](.+?)["“”]', texto)
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


def intentar_accion_deportiva(session, texto_usuario):
    t = texto_usuario.lower()

    if any(f in t for f in ["crea el torneo", "crea un torneo", "crear torneo", "nuevo torneo"]):
        nombre = _extraer_entre_comillas(texto_usuario)
        if not nombre:
            m = re.search(r'(?:llamado|called|named)\s+["\']?([A-Za-z0-9 ]+?)(?:["\']|con|with|$)', texto_usuario, re.IGNORECASE)
            nombre = m.group(1).strip() if m else None
        if not nombre:
            return {"tipo": "respuesta", "texto": "¿Cómo quieres llamar al torneo?", "herramienta": None, "terminado": False}
        fecha = _extraer_fecha(texto_usuario)
        return {"tipo": "herramienta", "texto": crear_torneo(nombre, fecha), "herramienta": "crear_torneo", "terminado": False}

    if any(f in t for f in ["crea el equipo", "crea un equipo", "crear equipo", "nuevo equipo"]):
        nombre = _extraer_entre_comillas(texto_usuario)
        if not nombre:
            m = re.search(r'(?:equipo|team)\s+["\']?([A-Za-z0-9 ]+?)(?:["\']|$)', texto_usuario, re.IGNORECASE)
            nombre = m.group(1).strip() if m else None
        if not nombre:
            return {"tipo": "respuesta", "texto": "¿Cómo quieres llamar al equipo?", "herramienta": None, "terminado": False}
        return {"tipo": "herramienta", "texto": crear_equipo(nombre), "herramienta": "crear_equipo", "terminado": False}

    if any(f in t for f in ["inscribe", "inscribir", "apunta"]) and ("torneo" in t or "en" in t):
        comillas = re.findall(r'["“”](.+?)["“”]', texto_usuario)
        if len(comillas) >= 2:
            return {"tipo": "herramienta", "texto": inscribir_equipo_en_torneo(comillas[0], comillas[1]), "herramienta": "inscribir_equipo_en_torneo", "terminado": False}
        m = re.search(r'(?:inscribe|inscribir|apunta)\s+(?:al?\s+)?["\']?(.+?)["\']?\s+en\s+["\']?(.+?)["\']?(?:\s|$)', texto_usuario, re.IGNORECASE)
        if m:
            return {"tipo": "herramienta", "texto": inscribir_equipo_en_torneo(m.group(1).strip(), m.group(2).strip()), "herramienta": "inscribir_equipo_en_torneo", "terminado": False}

    if any(f in t for f in ["crea el grupo", "crea un grupo", "crear grupo", "nuevo grupo"]):
        comillas = re.findall(r'["“”](.+?)["“”]', texto_usuario)
        m_grupo = re.search(r'grupo\s+([A-Za-z0-9]+)', texto_usuario, re.IGNORECASE)
        nombre_grupo = comillas[0] if comillas else (f"Grupo {m_grupo.group(1)}" if m_grupo else None)
        m_torneo = re.search(r'(?:en|in|del torneo|of tournament)\s+["\']?([^"\']+?)["\']?\s*$', texto_usuario, re.IGNORECASE)
        nombre_torneo = comillas[1] if len(comillas) > 1 else (m_torneo.group(1).strip() if m_torneo else None)
        if not nombre_grupo or not nombre_torneo:
            return {"tipo": "respuesta", "texto": "Necesito el nombre del grupo y del torneo.", "herramienta": None, "terminado": False}
        return {"tipo": "herramienta", "texto": crear_grupo(nombre_torneo, nombre_grupo), "herramienta": "crear_grupo", "terminado": False}

    if any(f in t for f in ["añade", "agrega", "add"]) and "grupo" in t:
        comillas = re.findall(r'["“”](.+?)["“”]', texto_usuario)
        m = re.search(r'(?:añade|agrega|add)\s+(?:a\s+|al equipo\s+)?["\']?([^"\']+?)["\']?\s+(?:al|to|a)\s+(?:grupo\s+)?([A-Za-z0-9]+)', texto_usuario, re.IGNORECASE)
        m_torneo = re.search(r'(?:de|del torneo|of|in)\s+["\']?([^"\']+?)["\']?\s*$', texto_usuario, re.IGNORECASE)
        if m and m_torneo:
            nombre_equipo = comillas[0] if comillas else m.group(1).strip()
            nombre_grupo = f"Grupo {m.group(2)}" if not m.group(2).lower().startswith("grupo") else m.group(2)
            nombre_torneo = comillas[1] if len(comillas) > 1 else m_torneo.group(1).strip()
            return {"tipo": "herramienta", "texto": añadir_equipo_a_grupo(nombre_equipo, nombre_grupo, nombre_torneo), "herramienta": "añadir_equipo_a_grupo", "terminado": False}

    if any(f in t for f in ["registra al jugador", "registra jugador", "añade al jugador", "nuevo jugador"]):
        nombre = _extraer_entre_comillas(texto_usuario)
        if not nombre:
            m = re.search(r'jugador\s+["\']?([A-Za-z\s]+?)(?:["\']|de\s+\d|,|$)', texto_usuario, re.IGNORECASE)
            nombre = m.group(1).strip() if m else None
        m_edad = re.search(r'(\d+)\s*años', texto_usuario, re.IGNORECASE)
        m_pos = re.search(r'(?:posicion|posición|juega de|es)\s+([A-Za-z]+)', texto_usuario, re.IGNORECASE)
        edad = int(m_edad.group(1)) if m_edad else None
        posicion = m_pos.group(1).strip() if m_pos else None
        if nombre:
            return {"tipo": "herramienta", "texto": registrar_jugador(nombre, edad, posicion), "herramienta": "registrar_jugador", "terminado": False}

    if any(f in t for f in ["programa el partido", "programa un partido", "programar partido", "partido entre"]):
        m = re.search(r'(?:entre|between)\s+["\']?(.+?)["\']?\s+(?:vs?\.?|contra|and)\s+["\']?(.+?)["\']?\s+(?:en|in)\s+["\']?(.+?)["\']?(?:\s|$)', texto_usuario, re.IGNORECASE)
        if m:
            fecha = _extraer_fecha(texto_usuario)
            m_fase = re.search(r'(?:fase|phase|ronda|round)\s*:??\s*([^\.,]+)', texto_usuario, re.IGNORECASE)
            fase = m_fase.group(1).strip() if m_fase else "Fase de grupos"
            resultado = programar_partido(m.group(3).strip(), m.group(1).strip(), m.group(2).strip(), fecha, fase)
            return {"tipo": "herramienta", "texto": resultado, "herramienta": "programar_partido", "terminado": False}

    if any(f in t for f in ["registra el resultado", "registra resultado", "el resultado fue", "ganó", "gano", "empató", "empato", "termino", "terminó"]):
        m = re.search(r'["\']?(.+?)["\']?\s+(\d+)\s*[-–]\s*(\d+)\s+["\']?(.+?)["\']?\s+(?:en|in)\s+["\']?(.+?)["\']?(?:\s|$)', texto_usuario, re.IGNORECASE)
        if m:
            resultado = registrar_resultado(m.group(5).strip(), m.group(1).strip(), m.group(4).strip(), int(m.group(2)), int(m.group(3)))
            return {"tipo": "herramienta", "texto": resultado, "herramienta": "registrar_resultado", "terminado": False}

    if any(f in t for f in ["clasificacion", "clasificación", "tabla de posiciones", "standings", "ver clasificacion"]):
        comillas = re.findall(r'["“”](.+?)["“”]', texto_usuario)
        m_torneo = re.search(r'(?:de|del|of|in)\s+["\']?([^"\']+?)(?:["\']|grupo|group|$)', texto_usuario, re.IGNORECASE)
        nombre_torneo = comillas[0] if comillas else (m_torneo.group(1).strip() if m_torneo else None)
        m_grupo = re.search(r'grupo\s+([A-Za-z0-9]+)', texto_usuario, re.IGNORECASE)
        nombre_grupo = f"Grupo {m_grupo.group(1)}" if m_grupo else None
        if nombre_torneo:
            return {"tipo": "herramienta", "texto": ver_clasificacion(nombre_torneo, nombre_grupo), "herramienta": "ver_clasificacion", "terminado": False}

    if any(f in t for f in ["ver partidos", "muestra los partidos", "partidos del", "fixture", "calendario de partidos"]):
        comillas = re.findall(r'["“”](.+?)["“”]', texto_usuario)
        m_torneo = re.search(r'(?:de|del|of|in)\s+["\']?([^"\']+?)["\']?(?:\s|$)', texto_usuario, re.IGNORECASE)
        nombre_torneo = comillas[0] if comillas else (m_torneo.group(1).strip() if m_torneo else None)
        estado = "jugado" if "jugado" in t else ("programado" if "programado" in t else None)
        if nombre_torneo:
            return {"tipo": "herramienta", "texto": ver_partidos(nombre_torneo, estado), "herramienta": "ver_partidos", "terminado": False}

    if any(f in t for f in ["stats de jugadores", "estadisticas de jugadores", "estadísticas de jugadores", "goleadores", "ver stats"]):
        comillas = re.findall(r'["“”](.+?)["“”]', texto_usuario)
        m_torneo = re.search(r'(?:de|del|of|in)\s+["\']?([^"\']+?)["\']?(?:\s|$)', texto_usuario, re.IGNORECASE)
        nombre_torneo = comillas[0] if comillas else (m_torneo.group(1).strip() if m_torneo else None)
        if nombre_torneo:
            return {"tipo": "herramienta", "texto": ver_stats_jugadores(nombre_torneo), "herramienta": "ver_stats_jugadores", "terminado": False}

    if any(f in t for f in ["actualiza las stats", "actualiza stats", "añade goles", "registra goles", "añade asistencias"]):
        comillas = re.findall(r'["“”](.+?)["“”]', texto_usuario)
        m_jugador = re.search(r'(?:de|of|para|for|jugador)\s+["\']?([^"\']+?)["\']?\s+(?:en|in)', texto_usuario, re.IGNORECASE)
        m_torneo = re.search(r'(?:en|in)\s+["\']?([^"\']+?)["\']?(?:\s|$)', texto_usuario, re.IGNORECASE)
        nombre_jugador = comillas[0] if comillas else (m_jugador.group(1).strip() if m_jugador else None)
        nombre_torneo = comillas[1] if len(comillas) > 1 else (m_torneo.group(1).strip() if m_torneo else None)
        mg = re.search(r'(\d+)\s*gol', texto_usuario, re.IGNORECASE)
        ma = re.search(r'(\d+)\s*asistencia', texto_usuario, re.IGNORECASE)
        mta = re.search(r'(\d+)\s*(?:tarjeta\s*)?amarilla', texto_usuario, re.IGNORECASE)
        mtr = re.search(r'(\d+)\s*(?:tarjeta\s*)?roja', texto_usuario, re.IGNORECASE)
        mp = re.search(r'(\d+)\s*partido', texto_usuario, re.IGNORECASE)
        if nombre_jugador and nombre_torneo:
            resultado = actualizar_stats_jugador(
                nombre_jugador, nombre_torneo,
                int(mg.group(1)) if mg else 0,
                int(ma.group(1)) if ma else 0,
                int(mta.group(1)) if mta else 0,
                int(mtr.group(1)) if mtr else 0,
                int(mp.group(1)) if mp else 0,
            )
            return {"tipo": "herramienta", "texto": resultado, "herramienta": "actualizar_stats_jugador", "terminado": False}

    if any(f in t for f in ["sorteo de grupos", "realiza el sorteo", "haz el sorteo", "sortear grupos", "realizar sorteo", "draw de grupos"]):
        comillas = re.findall(r'["“”](.+?)["“”]', texto_usuario)
        m_torneo = re.search(r'(?:de|del|of|in|para)\s+["\']?([^"\']+?)["\']?(?:\s|$)', texto_usuario, re.IGNORECASE)
        nombre_torneo = comillas[0] if comillas else (m_torneo.group(1).strip() if m_torneo else None)
        if nombre_torneo:
            return {"tipo": "herramienta", "texto": realizar_sorteo_grupos(nombre_torneo), "herramienta": "realizar_sorteo_grupos", "terminado": False}

    if any(f in t for f in ["sorteo de eliminatorias", "cuadro de eliminatorias", "genera las eliminatorias", "crea las eliminatorias", "ronda eliminatoria", "knockout draw", "fase eliminatoria"]):
        comillas = re.findall(r'["“”](.+?)["“”]', texto_usuario)
        m_torneo = re.search(r'(?:de|del|of|in|para)\s+["\']?([^"\']+?)["\']?(?:\s|$)', texto_usuario, re.IGNORECASE)
        nombre_torneo = comillas[0] if comillas else (m_torneo.group(1).strip() if m_torneo else None)
        m_cpg = re.search(r'(\d+)\s*(?:clasificados|clasifican|qualify)', texto_usuario, re.IGNORECASE)
        cpg = int(m_cpg.group(1)) if m_cpg else None
        if nombre_torneo:
            return {"tipo": "herramienta", "texto": realizar_sorteo_eliminatorias(nombre_torneo, cpg), "herramienta": "realizar_sorteo_eliminatorias", "terminado": False}

    if any(f in t for f in ["ver cuadro", "muestra el cuadro", "ver eliminatorias", "muestra las eliminatorias", "bracket"]):
        comillas = re.findall(r'["“”](.+?)["“”]', texto_usuario)
        m_torneo = re.search(r'(?:de|del|of|in)\s+["\']?([^"\']+?)["\']?(?:\s|$)', texto_usuario, re.IGNORECASE)
        nombre_torneo = comillas[0] if comillas else (m_torneo.group(1).strip() if m_torneo else None)
        if nombre_torneo:
            return {"tipo": "herramienta", "texto": ver_cuadro_eliminatorias(nombre_torneo), "herramienta": "ver_cuadro_eliminatorias", "terminado": False}

    return None
