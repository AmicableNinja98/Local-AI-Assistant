import re

from .apps import abrir_aplicacion
from .management import (
    asociar_jugador_a_equipo,
    crear_equipo,
    crear_torneo,
    inscribir_equipo_en_torneo,
    inscribir_jugador_en_torneo,
    inscribir_multiples_equipos_en_torneo,
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


def _extraer_nombres_con_comillas(texto):
    return re.findall(r'["“”](.+?)["“”]', texto)


def _extraer_equipo_y_torneo(texto):
    comillas = _extraer_nombres_con_comillas(texto)
    if len(comillas) >= 2:
        return comillas[0].strip(), comillas[1].strip()

    # Strip leading verb and optional keywords
    texto_limpio = re.sub(
        r'^(?:registra|registrar|añade|añadir|agrega|agregar|add|inscribe|inscribir'
        r'|apunta|assign|register|mete|meter|pon|poner)'
        r'\s+(?:el|un|al|a|the|al equipo|el equipo|un equipo|a)?\s*(?:equipo|team)?\s+',
        '', texto, flags=re.IGNORECASE
    ).strip()

    # Split on "en / in / al torneo / in the tournament"
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
    
    # ── Inscribir todos los equipos en torneo ───────────────────────────────
    # Catches: "add all teams to World Cup Test"
    #          "inscribe todos los equipos en World Cup Test"
    #          "add all teams except Mexico and Canada to World Cup Test"
    if any(f in t for f in ["todos los equipos", "all teams", "all the teams",
                              "todos los equipos de la base", "all teams from"]):

        # Extract tournament name
        comillas = _extraer_nombres_con_comillas(texto_usuario)
        m_torneo = re.search(
            r'(?:en|in|to|al torneo|to the tournament)\s+["\']?([^"\']+?)["\']?'
            r'(?:\s+except|\s+excepto|\s+menos|\s*$)',
            texto_usuario, re.IGNORECASE
        )
        nombre_torneo = comillas[-1] if comillas else (m_torneo.group(1).strip() if m_torneo else None)

        if not nombre_torneo:
            return {"tipo": "respuesta",
                    "texto": "¿A qué torneo quieres añadir todos los equipos?",
                    "herramienta": None, "terminado": False}

        # Extract exclusions after "except / excepto / menos"
        excluir = []
        m_excluir = re.search(
            r'(?:except|excepto|menos|excluding|excluyendo)\s+(.+?)(?:\s+(?:en|in|to|al)\s+|$)',
            texto_usuario, re.IGNORECASE
        )
        if m_excluir:
            raw = m_excluir.group(1)
            # Split on "and", "y", "," to get individual names
            partes = re.split(r'\s*(?:,|and|y)\s*', raw, flags=re.IGNORECASE)
            excluir = [p.strip().strip("\"'.,") for p in partes if p.strip()]

        return {"tipo": "herramienta",
                "texto": inscribir_multiples_equipos_en_torneo(nombre_torneo, excluir),
                "herramienta": "inscribir_multiples_equipos_en_torneo", "terminado": False}

    # ── Inscribir equipo en torneo ──────────────────────────────────────────
    # Catches: "Inscribe Japon en World Cup Test"
    #          "Añade España al torneo Liga 2026"
    #          "Registra el equipo Brasil en World Cup"
    if any(f in t for f in ["inscribe", "inscribir", "apunta", "mete", "meter",
                             "pon ", "poner", "añade", "añadir", "agrega", "agregar",
                             "registra", "registrar"]) \
       and any(f in t for f in [" en ", " al ", " in ", " to "]) \
       and not any(f in t for f in ["jugador", "player", "grupo", "group",
                                    "partido", "resultado", "gol", "stats","todos","all"]):

        nombre_equipo, nombre_torneo = _extraer_equipo_y_torneo(texto_usuario)
        if nombre_equipo and nombre_torneo:
            return {"tipo": "herramienta",
                    "texto": inscribir_equipo_en_torneo(nombre_equipo, nombre_torneo),
                    "herramienta": "inscribir_equipo_en_torneo", "terminado": False}

    # ── Inscribir jugador en torneo ─────────────────────────────────────────
    if any(f in t for f in ["inscribe", "inscribir", "apunta", "mete", "meter",
                             "añade", "añadir", "agrega", "agregar",
                             "registra", "registrar"]) \
       and any(f in t for f in [" en ", " al ", " in ", " to "]) \
       and any(f in t for f in ["jugador", "player"]):

        nombre_jugador, nombre_torneo = _extraer_jugador_y_torneo(texto_usuario)
        if nombre_jugador and nombre_torneo:
            return {"tipo": "herramienta",
                    "texto": inscribir_jugador_en_torneo(nombre_jugador, nombre_torneo),
                    "herramienta": "inscribir_jugador_en_torneo", "terminado": False}

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

    if any(f in t for f in ["registra al jugador", "registra un jugador", "registra jugador", "añade al jugador", "añade un jugador", "agrega al jugador", "agrega un jugador", "inscribe al jugador", "inscribe un jugador", "nuevo jugador"]):
        nombre = _extraer_entre_comillas(texto_usuario)
        if not nombre:
            nombre = re.sub(r'^(?:registra|añade|agrega|inscribe)\s+(?:al|un|a)?\s*jugador\s+', '', texto_usuario, flags=re.IGNORECASE).strip()
            nombre = re.split(r'\s+(?:en|al|a)\s+(?:el\s+torneo\s+)?', nombre, maxsplit=1)[0].strip().strip("\"'.,")
        m_edad = re.search(r'(\d+)\s*años', texto_usuario, re.IGNORECASE)
        m_pos = re.search(r'(?:posicion|posición|juega de|es)\s+([A-Za-z]+)', texto_usuario, re.IGNORECASE)
        edad = int(m_edad.group(1)) if m_edad else None
        posicion = m_pos.group(1).strip() if m_pos else None
        if nombre:
            if "torneo" in t:
                nombre_jugador, nombre_torneo = _extraer_jugador_y_torneo(texto_usuario)
                if nombre_jugador and nombre_torneo:
                    return {"tipo": "herramienta", "texto": inscribir_jugador_en_torneo(nombre_jugador, nombre_torneo), "herramienta": "inscribir_jugador_en_torneo", "terminado": False}
                m_torneo = re.search(r'(?:en|in|al torneo|al torneo de|del torneo|del torneo de)\s+["\']?([^"\']+?)(?:["\']|\s|$)', texto_usuario, re.IGNORECASE)
                nombre_torneo = m_torneo.group(1).strip() if m_torneo else None
                if nombre_torneo:
                    return {"tipo": "herramienta", "texto": inscribir_jugador_en_torneo(nombre, nombre_torneo), "herramienta": "inscribir_jugador_en_torneo", "terminado": False}
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
