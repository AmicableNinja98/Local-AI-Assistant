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
import random
import math

# ── Configuración ──────────────────────────────────────────────────────────────

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

RUTA_LLAMA  = os.getenv("RUTA_LLAMA")
RUTA_MODELO = os.getenv("RUTA_MODELO")
GPU_LAYERS  = int(os.getenv("GPU_LAYERS", 24))

DB_CONFIG = {
    "host":     os.getenv("DB_HOST",     "localhost"),
    "user":     os.getenv("DB_USER",     "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME",     "asistente_ia")
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

# ── Herramientas generales ─────────────────────────────────────────────────────

def ayuda_asistente():
    return """
====================================================================
📋 FUNCIONES DISPONIBLES
====================================================================
1. 💬 Conversación libre en español o inglés.
2. 🔍 Búsqueda web automática para información reciente.
   También puedes forzarla con '/buscar [consulta]'.
3. 👤 Recuerdo tu nombre gracias a MariaDB.
4. 🖥️  Abrir aplicaciones: 'Abre Steam', 'Abre Discord', etc.
   Si no conozco la ruta te la pediré y la recordaré para siempre.
5. ⚽ GESTIÓN DEPORTIVA:
   · Torneos: crear, inscribir equipos
   · Sorteo: 'Realiza el sorteo de grupos de [torneo]'
             Adapta automáticamente según el nº de equipos
             Formatos: 4, 6, 8, 12, 16, 24, 32, 48 equipos
   · Grupos: crear grupos (A, B...), añadir equipos a grupos
   · Partidos: programar fixtures, registrar resultados
   · Tabla: ver clasificación general o por grupo
   · Eliminatorias: 'Genera las eliminatorias de [torneo]'
                    Cruces automáticos (1ºA vs 2ºB...)
   · Jugadores: registrar goles, asistencias, tarjetas
   · Stats: ver tabla de goleadores y estadísticas
6. ❓ Ayuda: escribe '/ayuda' o pregúntame qué puedo hacer.
====================================================================
Ejemplo de flujo Copa del Mundo:
  'Crea el torneo "World Cup 2026"'
  'Crea el equipo España'
  'Inscribe España en "World Cup 2026"'
  'Realiza el sorteo de grupos de "World Cup 2026"'
  'Registra el resultado: España 2 - Alemania 1 en "World Cup 2026"'
  'Muestra la clasificación del Grupo A de "World Cup 2026"'
  'Genera las eliminatorias de "World Cup 2026"'
  'Ver cuadro de "World Cup 2026"'
===================================================================="""

# ── Funciones de base de datos general ────────────────────────────────────────

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
        return f"Torneo '{nombre}' creado correctamente."
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

# ── Web ────────────────────────────────────────────────────────────────────────

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
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        texto = soup.get_text(separator="\n")
        lineas = [l.strip() for l in texto.splitlines() if l.strip()]
        contenido = "\n".join(lineas)
        if len(contenido) < 200:
            return f"PAGINA_JS_DETECTADA:{url}"
        return contenido[:1500] + ("..." if len(contenido) > 1500 else "")
    except Exception as e:
        return f"No se pudo leer la página: {e}"

# ── Aplicaciones ───────────────────────────────────────────────────────────────

def _buscar_app_en_sistema(nombre: str) -> str | None:
    nombre_lower = nombre.lower()
    en_path = shutil.which(nombre_lower) or shutil.which(nombre_lower + ".exe")
    if en_path:
        return en_path
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
    try:
        conn = _db(); cur = conn.cursor()
        cur.execute("SELECT ruta FROM aplicaciones WHERE LOWER(nombre) = %s", (nombre.lower(),))
        res = cur.fetchone(); cur.close(); conn.close()
        return res[0] if res else None
    except Exception:
        return None

def guardar_ruta_app(nombre: str, ruta: str) -> str:
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
    ruta = obtener_ruta_app(nombre)
    if not ruta:
        ruta_auto = _buscar_app_en_sistema(nombre)
        if ruta_auto:
            guardar_ruta_app(nombre, ruta_auto)
            ruta = ruta_auto
    if ruta:
        try:
            os.startfile(ruta)
            return {"estado": "abierta", "mensaje": f"'{nombre}' abierta correctamente.", "app": nombre}
        except Exception as e:
            return {"estado": "error", "mensaje": f"Se encontró '{nombre}' pero no se pudo abrir: {e}", "app": nombre}
    return {"estado": "no_encontrada", "mensaje": f"No encontré '{nombre}' en la base de datos ni en el sistema.", "app": nombre}

# ── Helpers deportivos ─────────────────────────────────────────────────────────

def _obtener_id_torneo(nombre: str):
    conn = _db(); cur = conn.cursor()
    cur.execute("SELECT id FROM torneos WHERE nombre LIKE %s", (f"%{nombre}%",))
    res = cur.fetchone(); cur.close(); conn.close()
    return res[0] if res else None

def _obtener_id_equipo(nombre: str):
    conn = _db(); cur = conn.cursor()
    cur.execute("SELECT id FROM equipos WHERE nombre LIKE %s", (f"%{nombre}%",))
    res = cur.fetchone(); cur.close(); conn.close()
    return res[0] if res else None

def _obtener_id_jugador(nombre: str):
    conn = _db(); cur = conn.cursor()
    cur.execute("SELECT id FROM jugadores WHERE nombre LIKE %s", (f"%{nombre}%",))
    res = cur.fetchone(); cur.close(); conn.close()
    return res[0] if res else None

def _obtener_id_grupo(nombre_torneo: str, nombre_grupo: str):
    conn = _db(); cur = conn.cursor()
    cur.execute("""
        SELECT g.id FROM grupos g
        JOIN torneos t ON g.torneo_id = t.id
        WHERE t.nombre LIKE %s AND g.nombre LIKE %s
    """, (f"%{nombre_torneo}%", f"%{nombre_grupo}%"))
    res = cur.fetchone(); cur.close(); conn.close()
    return res[0] if res else None

def _asegurar_estadisticas_equipo(conn, torneo_id, equipo_id):
    cur = conn.cursor()
    cur.execute("""
        INSERT IGNORE INTO estadisticas_equipo_torneo (torneo_id, equipo_id)
        VALUES (%s, %s)
    """, (torneo_id, equipo_id))
    conn.commit(); cur.close()

# ── Grupos ─────────────────────────────────────────────────────────────────────

def crear_grupo(nombre_torneo: str, nombre_grupo: str) -> str:
    try:
        t_id = _obtener_id_torneo(nombre_torneo)
        if not t_id: return f"No encontré el torneo '{nombre_torneo}'."
        conn = _db(); cur = conn.cursor()
        cur.execute("INSERT IGNORE INTO grupos (torneo_id, nombre) VALUES (%s, %s)", (t_id, nombre_grupo))
        conn.commit(); cur.close(); conn.close()
        return f"Grupo '{nombre_grupo}' creado en el torneo '{nombre_torneo}'."
    except Exception as e:
        return f"Error al crear grupo: {e}"

def añadir_equipo_a_grupo(nombre_equipo: str, nombre_grupo: str, nombre_torneo: str) -> str:
    try:
        e_id = _obtener_id_equipo(nombre_equipo)
        g_id = _obtener_id_grupo(nombre_torneo, nombre_grupo)
        t_id = _obtener_id_torneo(nombre_torneo)
        if not e_id: return f"No encontré el equipo '{nombre_equipo}'."
        if not g_id: return f"No encontré el grupo '{nombre_grupo}' en '{nombre_torneo}'."
        conn = _db(); cur = conn.cursor()
        cur.execute("INSERT IGNORE INTO grupo_equipos (grupo_id, equipo_id) VALUES (%s, %s)", (g_id, e_id))
        _asegurar_estadisticas_equipo(conn, t_id, e_id)
        conn.commit(); cur.close(); conn.close()
        return f"'{nombre_equipo}' añadido al {nombre_grupo} del torneo '{nombre_torneo}'."
    except Exception as e:
        return f"Error: {e}"

# ── Partidos ───────────────────────────────────────────────────────────────────

def programar_partido(nombre_torneo: str, nombre_local: str, nombre_visitante: str,
                      fecha: str = None, fase: str = "Fase de grupos",
                      nombre_grupo: str = None) -> str:
    try:
        t_id = _obtener_id_torneo(nombre_torneo)
        l_id = _obtener_id_equipo(nombre_local)
        v_id = _obtener_id_equipo(nombre_visitante)
        if not t_id: return f"No encontré el torneo '{nombre_torneo}'."
        if not l_id: return f"No encontré el equipo '{nombre_local}'."
        if not v_id: return f"No encontré el equipo '{nombre_visitante}'."
        g_id = _obtener_id_grupo(nombre_torneo, nombre_grupo) if nombre_grupo else None
        conn = _db(); cur = conn.cursor()
        cur.execute("""
            INSERT INTO partidos (torneo_id, equipo_local_id, equipo_visitante_id,
                                  fecha, fase, grupo_id, estado)
            VALUES (%s, %s, %s, %s, %s, %s, 'programado')
        """, (t_id, l_id, v_id, fecha, fase, g_id))
        conn.commit(); cur.close(); conn.close()
        fecha_str = f" el {fecha}" if fecha else ""
        return f"Partido programado: {nombre_local} vs {nombre_visitante}{fecha_str} ({fase})."
    except Exception as e:
        return f"Error al programar partido: {e}"

def registrar_resultado(nombre_torneo: str, nombre_local: str, nombre_visitante: str,
                        goles_local: int, goles_visitante: int) -> str:
    try:
        t_id = _obtener_id_torneo(nombre_torneo)
        l_id = _obtener_id_equipo(nombre_local)
        v_id = _obtener_id_equipo(nombre_visitante)
        if not t_id: return f"No encontré el torneo '{nombre_torneo}'."
        if not l_id: return f"No encontré el equipo '{nombre_local}'."
        if not v_id: return f"No encontré el equipo '{nombre_visitante}'."

        conn = _db(); cur = conn.cursor()
        cur.execute("""
            SELECT id FROM partidos
            WHERE torneo_id = %s AND equipo_local_id = %s AND equipo_visitante_id = %s
            ORDER BY id DESC LIMIT 1
        """, (t_id, l_id, v_id))
        partido = cur.fetchone()

        if partido:
            cur.execute("""
                UPDATE partidos SET goles_local = %s, goles_visitante = %s, estado = 'jugado'
                WHERE id = %s
            """, (goles_local, goles_visitante, partido[0]))
        else:
            cur.execute("""
                INSERT INTO partidos (torneo_id, equipo_local_id, equipo_visitante_id,
                                      goles_local, goles_visitante, estado)
                VALUES (%s, %s, %s, %s, %s, 'jugado')
            """, (t_id, l_id, v_id, goles_local, goles_visitante))
        conn.commit()

        _asegurar_estadisticas_equipo(conn, t_id, l_id)
        _asegurar_estadisticas_equipo(conn, t_id, v_id)

        if goles_local > goles_visitante:
            pts_l, pts_v = 3, 0
            cur.execute("UPDATE estadisticas_equipo_torneo SET victorias = victorias + 1 WHERE torneo_id=%s AND equipo_id=%s", (t_id, l_id))
            cur.execute("UPDATE estadisticas_equipo_torneo SET derrotas  = derrotas  + 1 WHERE torneo_id=%s AND equipo_id=%s", (t_id, v_id))
        elif goles_local < goles_visitante:
            pts_l, pts_v = 0, 3
            cur.execute("UPDATE estadisticas_equipo_torneo SET derrotas  = derrotas  + 1 WHERE torneo_id=%s AND equipo_id=%s", (t_id, l_id))
            cur.execute("UPDATE estadisticas_equipo_torneo SET victorias = victorias + 1 WHERE torneo_id=%s AND equipo_id=%s", (t_id, v_id))
        else:
            pts_l, pts_v = 1, 1
            cur.execute("UPDATE estadisticas_equipo_torneo SET empates = empates + 1 WHERE torneo_id=%s AND equipo_id=%s", (t_id, l_id))
            cur.execute("UPDATE estadisticas_equipo_torneo SET empates = empates + 1 WHERE torneo_id=%s AND equipo_id=%s", (t_id, v_id))

        cur.execute("""
            UPDATE estadisticas_equipo_torneo
            SET partidos_jugados = partidos_jugados + 1,
                goles_favor   = goles_favor   + %s,
                goles_contra  = goles_contra  + %s,
                puntos        = puntos        + %s
            WHERE torneo_id = %s AND equipo_id = %s
        """, (goles_local, goles_visitante, pts_l, t_id, l_id))

        cur.execute("""
            UPDATE estadisticas_equipo_torneo
            SET partidos_jugados = partidos_jugados + 1,
                goles_favor   = goles_favor   + %s,
                goles_contra  = goles_contra  + %s,
                puntos        = puntos        + %s
            WHERE torneo_id = %s AND equipo_id = %s
        """, (goles_visitante, goles_local, pts_v, t_id, v_id))

        conn.commit(); cur.close(); conn.close()

        resultado_str = (f"Victoria {nombre_local}" if goles_local > goles_visitante
                         else f"Victoria {nombre_visitante}" if goles_visitante > goles_local
                         else "Empate")
        return (f"Resultado registrado: {nombre_local} {goles_local} - {goles_visitante} {nombre_visitante}. "
                f"{resultado_str}. Estadísticas actualizadas.")
    except Exception as e:
        return f"Error al registrar resultado: {e}"

# ── Clasificaciones ────────────────────────────────────────────────────────────

def ver_clasificacion(nombre_torneo: str, nombre_grupo: str = None) -> str:
    try:
        t_id = _obtener_id_torneo(nombre_torneo)
        if not t_id: return f"No encontré el torneo '{nombre_torneo}'."
        conn = _db(); cur = conn.cursor()

        if nombre_grupo:
            g_id = _obtener_id_grupo(nombre_torneo, nombre_grupo)
            if not g_id: return f"No encontré el grupo '{nombre_grupo}'."
            cur.execute("""
                SELECT e.nombre, et.partidos_jugados, et.victorias, et.empates,
                       et.derrotas, et.goles_favor, et.goles_contra,
                       (et.goles_favor - et.goles_contra) AS diferencia, et.puntos
                FROM estadisticas_equipo_torneo et
                JOIN equipos e ON et.equipo_id = e.id
                JOIN grupo_equipos ge ON ge.equipo_id = et.equipo_id AND ge.grupo_id = %s
                WHERE et.torneo_id = %s
                ORDER BY et.puntos DESC, diferencia DESC, et.goles_favor DESC
            """, (g_id, t_id))
            titulo = f"Clasificación — {nombre_grupo} ({nombre_torneo})"
        else:
            cur.execute("""
                SELECT e.nombre, et.partidos_jugados, et.victorias, et.empates,
                       et.derrotas, et.goles_favor, et.goles_contra,
                       (et.goles_favor - et.goles_contra) AS diferencia, et.puntos
                FROM estadisticas_equipo_torneo et
                JOIN equipos e ON et.equipo_id = e.id
                WHERE et.torneo_id = %s
                ORDER BY et.puntos DESC, diferencia DESC, et.goles_favor DESC
            """, (t_id,))
            titulo = f"Clasificación general — {nombre_torneo}"

        filas = cur.fetchall(); cur.close(); conn.close()
        if not filas: return "No hay estadísticas registradas aún."

        sep = "─" * 72
        cabecera = f"{'Equipo':<20} {'PJ':>3} {'V':>3} {'E':>3} {'D':>3} {'GF':>4} {'GC':>4} {'DG':>4} {'Pts':>4}"
        lineas = [titulo, sep, cabecera, sep]
        for pos, f in enumerate(filas, 1):
            lineas.append(f"{pos}. {f[0]:<18} {f[1]:>3} {f[2]:>3} {f[3]:>3} {f[4]:>3} {f[5]:>4} {f[6]:>4} {f[7]:>4} {f[8]:>4}")
        lineas.append(sep)
        return "\n".join(lineas)
    except Exception as e:
        return f"Error: {e}"

def ver_partidos(nombre_torneo: str, estado: str = None, fase: str = None) -> str:
    try:
        t_id = _obtener_id_torneo(nombre_torneo)
        if not t_id: return f"No encontré el torneo '{nombre_torneo}'."
        conn = _db(); cur = conn.cursor()

        query = """
            SELECT el.nombre, p.goles_local, p.goles_visitante, ev.nombre,
                   p.fecha, p.fase, p.estado
            FROM partidos p
            JOIN equipos el ON p.equipo_local_id = el.id
            JOIN equipos ev ON p.equipo_visitante_id = ev.id
            WHERE p.torneo_id = %s
        """
        params = [t_id]
        if estado:
            query += " AND p.estado = %s"; params.append(estado)
        if fase:
            query += " AND p.fase LIKE %s"; params.append(f"%{fase}%")
        query += " ORDER BY p.fecha ASC, p.id ASC"

        cur.execute(query, params); filas = cur.fetchall()
        cur.close(); conn.close()
        if not filas: return "No hay partidos registrados con ese filtro."

        filtro = f" [{estado or ''}{' · ' if estado and fase else ''}{fase or ''}]" if estado or fase else ""
        lineas = [f"Partidos — {nombre_torneo}{filtro}", "─" * 60]
        for f in filas:
            if f[6] == "jugado":
                lineas.append(f"  {f[0]} {f[1]} - {f[2]} {f[3]}  ({f[5]})")
            else:
                fecha_str = f" — {f[4]}" if f[4] else ""
                lineas.append(f"  {f[0]} vs {f[3]}{fecha_str}  ({f[5]}) [Pendiente]")
        lineas.append("─" * 60)
        return "\n".join(lineas)
    except Exception as e:
        return f"Error: {e}"

# ── Estadísticas de jugadores ──────────────────────────────────────────────────

def actualizar_stats_jugador(nombre_jugador: str, nombre_torneo: str,
                              goles: int = 0, asistencias: int = 0,
                              tarjetas_amarillas: int = 0, tarjetas_rojas: int = 0,
                              partidos_jugados: int = 0) -> str:
    try:
        j_id = _obtener_id_jugador(nombre_jugador)
        t_id = _obtener_id_torneo(nombre_torneo)
        if not j_id: return f"No encontré al jugador '{nombre_jugador}'."
        if not t_id: return f"No encontré el torneo '{nombre_torneo}'."

        conn = _db(); cur = conn.cursor()
        cur.execute("SELECT equipo_id FROM equipo_jugadores WHERE jugador_id = %s LIMIT 1", (j_id,))
        eq = cur.fetchone()
        e_id = eq[0] if eq else None

        cur.execute("""
            INSERT INTO estadisticas_jugador_torneo
                (torneo_id, jugador_id, equipo_id, goles, asistencias,
                 tarjetas_amarillas, tarjetas_rojas, partidos_jugados)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                goles              = goles              + VALUES(goles),
                asistencias        = asistencias        + VALUES(asistencias),
                tarjetas_amarillas = tarjetas_amarillas + VALUES(tarjetas_amarillas),
                tarjetas_rojas     = tarjetas_rojas     + VALUES(tarjetas_rojas),
                partidos_jugados   = partidos_jugados   + VALUES(partidos_jugados)
        """, (t_id, j_id, e_id, goles, asistencias, tarjetas_amarillas, tarjetas_rojas, partidos_jugados))
        conn.commit(); cur.close(); conn.close()

        cambios = []
        if goles:              cambios.append(f"{goles} gol(es)")
        if asistencias:        cambios.append(f"{asistencias} asistencia(s)")
        if tarjetas_amarillas: cambios.append(f"{tarjetas_amarillas} tarjeta(s) amarilla(s)")
        if tarjetas_rojas:     cambios.append(f"{tarjetas_rojas} tarjeta(s) roja(s)")
        if partidos_jugados:   cambios.append(f"{partidos_jugados} partido(s) jugado(s)")
        return f"Stats de '{nombre_jugador}' actualizadas en '{nombre_torneo}': {', '.join(cambios)}."
    except Exception as e:
        return f"Error: {e}"

def ver_stats_jugadores(nombre_torneo: str, top: int = 10) -> str:
    try:
        t_id = _obtener_id_torneo(nombre_torneo)
        if not t_id: return f"No encontré el torneo '{nombre_torneo}'."
        conn = _db(); cur = conn.cursor()
        cur.execute("""
            SELECT j.nombre, e.nombre, ej.partidos_jugados, ej.goles,
                   ej.asistencias, ej.tarjetas_amarillas, ej.tarjetas_rojas
            FROM estadisticas_jugador_torneo ej
            JOIN jugadores j ON ej.jugador_id = j.id
            LEFT JOIN equipos e ON ej.equipo_id = e.id
            WHERE ej.torneo_id = %s
            ORDER BY ej.goles DESC, ej.asistencias DESC
            LIMIT %s
        """, (t_id, top))
        filas = cur.fetchall(); cur.close(); conn.close()
        if not filas: return "No hay estadísticas de jugadores registradas."

        sep = "─" * 72
        cabecera = f"{'Jugador':<20} {'Equipo':<15} {'PJ':>3} {'G':>3} {'A':>3} {'TA':>3} {'TR':>3}"
        lineas = [f"Estadísticas de jugadores — {nombre_torneo}", sep, cabecera, sep]
        for pos, f in enumerate(filas, 1):
            equipo = f[1] or "—"
            lineas.append(f"{pos}. {f[0]:<18} {equipo:<15} {f[2]:>3} {f[3]:>3} {f[4]:>3} {f[5]:>3} {f[6]:>3}")
        lineas.append(sep)
        return "\n".join(lineas)
    except Exception as e:
        return f"Error: {e}"

# ── Sorteo de grupos ───────────────────────────────────────────────────────────

def _calcular_formato(num_equipos: int) -> dict:
    formatos = {
        4:  (1, 4,  2),
        6:  (2, 3,  2),
        8:  (2, 4,  2),
        12: (3, 4,  2),
        16: (4, 4,  2),
        24: (6, 4,  2),
        32: (8, 4,  2),
        48: (12, 4, 2),
    }
    if num_equipos in formatos:
        ng, epg, cpg = formatos[num_equipos]
        return {"num_grupos": ng, "equipos_por_grupo": epg, "clasificados": cpg, "valido": True}
    for epg in [4, 3]:
        if num_equipos % epg == 0:
            ng  = num_equipos // epg
            cpg = 2 if ng >= 2 else num_equipos // 2
            return {"num_grupos": ng, "equipos_por_grupo": epg, "clasificados": cpg, "valido": True}
    return {"valido": False, "mensaje": f"No se puede hacer un sorteo equilibrado con {num_equipos} equipos. "
                                         "Prueba con 4, 6, 8, 12, 16, 24, 32 o 48 equipos."}

def _nombre_ronda(num_equipos: int) -> str:
    nombres = {
        2:  "Final",
        4:  "Semifinales",
        8:  "Cuartos de final",
        16: "Octavos de final",
        32: "Dieciseisavos de final",
    }
    return nombres.get(num_equipos, f"Ronda de {num_equipos}")

def realizar_sorteo_grupos(nombre_torneo: str, semilla: int = None) -> str:
    try:
        t_id = _obtener_id_torneo(nombre_torneo)
        if not t_id:
            return f"No encontré el torneo '{nombre_torneo}'."

        conn = _db(); cur = conn.cursor()
        cur.execute("""
            SELECT e.id, e.nombre FROM equipos e
            JOIN torneo_equipos te ON te.equipo_id = e.id
            WHERE te.torneo_id = %s
        """, (t_id,))
        equipos = cur.fetchall()

        if not equipos:
            cur.close(); conn.close()
            return f"No hay equipos inscritos en '{nombre_torneo}'. Inscribe equipos primero."

        num_equipos = len(equipos)
        formato = _calcular_formato(num_equipos)

        if not formato["valido"]:
            cur.close(); conn.close()
            return formato["mensaje"]

        if semilla:
            random.seed(semilla)
        equipos_mezclados = list(equipos)
        random.shuffle(equipos_mezclados)

        cur.execute("DELETE FROM grupos WHERE torneo_id = %s", (t_id,))
        conn.commit()

        ng  = formato["num_grupos"]
        epg = formato["equipos_por_grupo"]
        letras = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        lineas = [f"🎲 Sorteo de grupos — {nombre_torneo}",
                  f"   {num_equipos} equipos → {ng} grupos de {epg}",
                  "─" * 40]

        for i in range(ng):
            nombre_grupo = f"Grupo {letras[i]}"
            cur.execute("INSERT INTO grupos (torneo_id, nombre) VALUES (%s, %s)", (t_id, nombre_grupo))
            conn.commit()
            g_id = cur.lastrowid

            equipos_grupo = equipos_mezclados[i * epg : (i + 1) * epg]
            lineas.append(f"\n  {nombre_grupo}:")
            for e_id, e_nombre in equipos_grupo:
                cur.execute("INSERT IGNORE INTO grupo_equipos (grupo_id, equipo_id) VALUES (%s, %s)", (g_id, e_id))
                _asegurar_estadisticas_equipo(conn, t_id, e_id)
                lineas.append(f"    • {e_nombre}")

            # Auto-generate group stage fixtures
            for j in range(len(equipos_grupo)):
                for k in range(j + 1, len(equipos_grupo)):
                    local_id   = equipos_grupo[j][0]
                    visita_id  = equipos_grupo[k][0]
                    cur.execute("""
                        INSERT INTO partidos
                            (torneo_id, equipo_local_id, equipo_visitante_id, fase, grupo_id, estado)
                        VALUES (%s, %s, %s, 'Fase de grupos', %s, 'programado')
                    """, (t_id, local_id, visita_id, g_id))

        conn.commit(); cur.close(); conn.close()
        lineas.append("\n" + "─" * 40)
        lineas.append("✅ Grupos creados y partidos de fase de grupos generados automáticamente.")
        lineas.append(f"   Usa 'ver partidos {nombre_torneo}' para ver el calendario.")
        return "\n".join(lineas)

    except Exception as e:
        return f"Error al realizar el sorteo: {e}"

# ── Sorteo de eliminatorias ────────────────────────────────────────────────────

def realizar_sorteo_eliminatorias(nombre_torneo: str, clasificados_por_grupo: int = None) -> str:
    try:
        t_id = _obtener_id_torneo(nombre_torneo)
        if not t_id:
            return f"No encontré el torneo '{nombre_torneo}'."

        conn = _db(); cur = conn.cursor()
        cur.execute("SELECT id, nombre FROM grupos WHERE torneo_id = %s ORDER BY nombre", (t_id,))
        grupos = cur.fetchall()

        if not grupos:
            cur.close(); conn.close()
            return "No hay grupos definidos. Realiza primero el sorteo de grupos."

        if clasificados_por_grupo is None:
            cur.execute("SELECT COUNT(*) FROM torneo_equipos WHERE torneo_id = %s", (t_id,))
            num_equipos = cur.fetchone()[0]
            formato = _calcular_formato(num_equipos)
            clasificados_por_grupo = formato.get("clasificados", 2)

        clasificados = []
        for gi, (g_id, g_nombre) in enumerate(grupos):
            cur.execute("""
                SELECT et.equipo_id, e.nombre,
                       et.puntos,
                       (et.goles_favor - et.goles_contra) AS dg,
                       et.goles_favor
                FROM estadisticas_equipo_torneo et
                JOIN equipos e ON et.equipo_id = e.id
                JOIN grupo_equipos ge ON ge.equipo_id = et.equipo_id AND ge.grupo_id = %s
                WHERE et.torneo_id = %s
                ORDER BY et.puntos DESC, dg DESC, et.goles_favor DESC
                LIMIT %s
            """, (g_id, t_id, clasificados_por_grupo))
            for pos, (e_id, e_nombre, pts, dg, gf) in enumerate(cur.fetchall()):
                clasificados.append({
                    "grupo_idx": gi, "grupo_nombre": g_nombre,
                    "posicion": pos, "equipo_id": e_id, "nombre": e_nombre
                })

        total = len(clasificados)
        if total < 2:
            cur.close(); conn.close()
            return "No hay suficientes equipos clasificados. Registra los resultados de la fase de grupos primero."

        if total & (total - 1) != 0:
            cur.close(); conn.close()
            return (f"Hay {total} equipos clasificados pero se necesita una potencia de 2 (2, 4, 8, 16...). "
                    f"Ajusta los clasificados por grupo.")

        cur.execute("DELETE FROM eliminatorias WHERE torneo_id = %s", (t_id,))
        conn.commit()

        primeros = [c for c in clasificados if c["posicion"] == 0]
        segundos = [c for c in clasificados if c["posicion"] == 1]
        ng = len(grupos)
        enfrentamientos = []
        for i in range(ng // 2):
            e1 = primeros[i]
            e2 = segundos[ng // 2 + i] if ng // 2 + i < len(segundos) else segundos[i]
            enfrentamientos.append((e1, e2))
        for i in range(ng // 2, ng):
            e1 = primeros[i]
            e2 = segundos[i - ng // 2]
            enfrentamientos.append((e1, e2))

        ronda_nombre = _nombre_ronda(total)
        lineas = [f"🏆 Sorteo de eliminatorias — {nombre_torneo}",
                  f"   {total} equipos clasificados → {ronda_nombre}",
                  "─" * 50]

        for orden, (eq1, eq2) in enumerate(enfrentamientos):
            cur.execute("""
                INSERT INTO partidos
                    (torneo_id, equipo_local_id, equipo_visitante_id, fase, estado)
                VALUES (%s, %s, %s, %s, 'programado')
            """, (t_id, eq1["equipo_id"], eq2["equipo_id"], ronda_nombre))
            conn.commit()
            partido_id = cur.lastrowid

            cur.execute("""
                INSERT INTO eliminatorias (torneo_id, ronda, orden, equipo1_id, equipo2_id, partido_id)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (t_id, ronda_nombre, orden, eq1["equipo_id"], eq2["equipo_id"], partido_id))

            lineas.append(
                f"  Partido {orden + 1}: {eq1['nombre']} ({eq1['grupo_nombre']} 1º)"
                f" vs {eq2['nombre']} ({eq2['grupo_nombre']} 2º)"
            )

        conn.commit(); cur.close(); conn.close()
        lineas.append("─" * 50)
        lineas.append("✅ Cuadro de eliminatorias generado y partidos programados.")
        return "\n".join(lineas)

    except Exception as e:
        return f"Error al realizar el sorteo de eliminatorias: {e}"

def ver_cuadro_eliminatorias(nombre_torneo: str) -> str:
    try:
        t_id = _obtener_id_torneo(nombre_torneo)
        if not t_id: return f"No encontré el torneo '{nombre_torneo}'."
        conn = _db(); cur = conn.cursor()
        cur.execute("""
            SELECT el.ronda, el.orden,
                   e1.nombre, p.goles_local,
                   e2.nombre, p.goles_visitante, p.estado
            FROM eliminatorias el
            JOIN equipos e1 ON el.equipo1_id = e1.id
            JOIN equipos e2 ON el.equipo2_id = e2.id
            LEFT JOIN partidos p ON el.partido_id = p.id
            WHERE el.torneo_id = %s
            ORDER BY el.ronda, el.orden
        """, (t_id,))
        filas = cur.fetchall(); cur.close(); conn.close()
        if not filas: return "No hay cuadro de eliminatorias generado aún."

        lineas = [f"🏆 Cuadro de eliminatorias — {nombre_torneo}", "─" * 50]
        ronda_actual = None
        for f in filas:
            ronda, orden, eq1, gl, eq2, gv, estado = f
            if ronda != ronda_actual:
                ronda_actual = ronda
                lineas.append(f"\n  {ronda}:")
            if estado == "jugado":
                lineas.append(f"    {eq1} {gl} - {gv} {eq2}")
            else:
                lineas.append(f"    {eq1} vs {eq2}  [Pendiente]")
        lineas.append("\n" + "─" * 50)
        return "\n".join(lineas)
    except Exception as e:
        return f"Error: {e}"

# ── TOOLS ──────────────────────────────────────────────────────────────────────

TOOLS = [
    {"type": "function", "function": {"name": "ayuda_asistente", "description": "Muestra las capacidades del asistente.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "buscar_en_internet",
        "description": "Busca información actualizada en internet. Úsala SIEMPRE que el usuario pregunte sobre eventos, noticias, personas, precios, resultados deportivos, o cualquier cosa que pueda haber cambiado después de 2022.",
        "parameters": {"type": "object", "properties": {"consulta": {"type": "string"}}, "required": ["consulta"]}
    }},
    {"type": "function", "function": {
        "name": "leer_pagina_web",
        "description": "Lee el contenido completo de una URL específica.",
        "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}
    }},
    {"type": "function", "function": {
        "name": "abrir_aplicacion",
        "description": "Abre una aplicación instalada en el PC del usuario.",
        "parameters": {"type": "object", "properties": {"nombre": {"type": "string"}}, "required": ["nombre"]}
    }},
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
    "ayuda_asistente":           ayuda_asistente,
    "buscar_en_internet":        buscar_en_internet,
    "leer_pagina_web":           leer_pagina_web,
    "abrir_aplicacion":          abrir_aplicacion,
    "registrar_jugador":         registrar_jugador,
    "crear_equipo":              crear_equipo,
    "asociar_jugador_a_equipo":  asociar_jugador_a_equipo,
    "crear_torneo":              crear_torneo,
    "inscribir_equipo_en_torneo": inscribir_equipo_en_torneo,
    "listar_todo_lo_guardado":   listar_todo_lo_guardado,
    "crear_grupo":               crear_grupo,
    "añadir_equipo_a_grupo":     añadir_equipo_a_grupo,
    "programar_partido":         programar_partido,
    "registrar_resultado":       registrar_resultado,
    "ver_clasificacion":         ver_clasificacion,
    "ver_partidos":              ver_partidos,
    "actualizar_stats_jugador":  actualizar_stats_jugador,
    "ver_stats_jugadores":       ver_stats_jugadores,
    "realizar_sorteo_grupos":        realizar_sorteo_grupos,
    "realizar_sorteo_eliminatorias": realizar_sorteo_eliminatorias,
    "ver_cuadro_eliminatorias":      ver_cuadro_eliminatorias,
}

# ── Servidor llama.cpp ─────────────────────────────────────────────────────────

def iniciar_servidor():
    print("🔧 Iniciando servidor llama.cpp...")
    try:
        proceso = subprocess.Popen(
            [RUTA_LLAMA, "-m", RUTA_MODELO, "-c", "8192",
             "-ngl", str(GPU_LAYERS), "--port", "8080"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except FileNotFoundError:
        raise RuntimeError(f"No se encontró llama-server.exe en:\n{RUTA_LLAMA}\nVerifica la ruta en el .env")
    print("⏳ Cargando modelo", end="", flush=True)
    for _ in range(10):
        time.sleep(1)
        print(".", end="", flush=True)
    print(" ¡Listo!\n")
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

# ── Detección de intención ─────────────────────────────────────────────────────

PALABRAS_ACCION = [
    "crea", "crear", "registra", "registrar", "añade", "añadir", "agrega",
    "programa", "programar", "inscribe", "inscribir", "actualiza", "actualizar",
    "muestra", "mostrar", "ver", "dame", "dime", "lista", "abre", "abrir",
    "realiza", "realizar", "haz", "genera", "generar", "sortea", "sortear"
]

PALABRAS_ACTUALES = [
    "actual", "ahora", "hoy", "este año", "2024", "2025", "2026",
    "último", "ultima", "reciente", "clasificación", "resultado",
    "goleador", "temporada", "noticias", "precio", "estreno"
]

def _necesita_busqueda(texto: str) -> bool:
    texto_lower = texto.lower()
    if any(texto_lower.startswith(p) or f" {p}" in texto_lower for p in PALABRAS_ACCION):
        return False
    return any(p in texto_lower for p in PALABRAS_ACTUALES)

# ── Parsing directo de comandos deportivos ─────────────────────────────────────

def _extraer_entre_comillas(texto):
    match = re.search(r'["\u201c\u201d](.+?)["\u201c\u201d]', texto)
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
    match = re.search(r'(\d+)\s*[-\u2013]\s*(\d+)', texto)
    return (int(match.group(1)), int(match.group(2))) if match else None

def _intentar_accion_deportiva(session, texto_usuario):
    t = texto_usuario.lower()

    # ── Crear torneo ────────────────────────────────────────────────────────────
    if any(f in t for f in ["crea el torneo", "crea un torneo", "crear torneo", "nuevo torneo"]):
        nombre = _extraer_entre_comillas(texto_usuario)
        if not nombre:
            m = re.search(r'(?:llamado|called|named)\s+["\']?([A-Za-z0-9 ]+?)(?:["\']|con|with|$)', texto_usuario, re.IGNORECASE)
            nombre = m.group(1).strip() if m else None
        if not nombre:
            return {"tipo": "respuesta", "texto": "¿Cómo quieres llamar al torneo?", "herramienta": None, "terminado": False}
        fecha = _extraer_fecha(texto_usuario)
        return {"tipo": "herramienta", "texto": crear_torneo(nombre, fecha), "herramienta": "crear_torneo", "terminado": False}

    # ── Crear equipo ────────────────────────────────────────────────────────────
    if any(f in t for f in ["crea el equipo", "crea un equipo", "crear equipo", "nuevo equipo"]):
        nombre = _extraer_entre_comillas(texto_usuario)
        if not nombre:
            m = re.search(r'(?:equipo|team)\s+["\']?([A-Za-z0-9 ]+?)(?:["\']|$)', texto_usuario, re.IGNORECASE)
            nombre = m.group(1).strip() if m else None
        if not nombre:
            return {"tipo": "respuesta", "texto": "¿Cómo quieres llamar al equipo?", "herramienta": None, "terminado": False}
        return {"tipo": "herramienta", "texto": crear_equipo(nombre), "herramienta": "crear_equipo", "terminado": False}

    # ── Inscribir equipo en torneo ──────────────────────────────────────────────
    if any(f in t for f in ["inscribe", "inscribir", "apunta"]) and ("torneo" in t or "en" in t):
        comillas = re.findall(r'["\u201c\u201d](.+?)["\u201c\u201d]', texto_usuario)
        if len(comillas) >= 2:
            return {"tipo": "herramienta", "texto": inscribir_equipo_en_torneo(comillas[0], comillas[1]),
                    "herramienta": "inscribir_equipo_en_torneo", "terminado": False}
        m = re.search(r'(?:inscribe|inscribir|apunta)\s+(?:al?\s+)?["\']?(.+?)["\']?\s+en\s+["\']?(.+?)["\']?(?:\s|$)', texto_usuario, re.IGNORECASE)
        if m:
            return {"tipo": "herramienta", "texto": inscribir_equipo_en_torneo(m.group(1).strip(), m.group(2).strip()),
                    "herramienta": "inscribir_equipo_en_torneo", "terminado": False}

    # ── Crear grupo ─────────────────────────────────────────────────────────────
    if any(f in t for f in ["crea el grupo", "crea un grupo", "crear grupo", "nuevo grupo"]):
        comillas = re.findall(r'["\u201c\u201d](.+?)["\u201c\u201d]', texto_usuario)
        m_grupo = re.search(r'grupo\s+([A-Za-z0-9]+)', texto_usuario, re.IGNORECASE)
        nombre_grupo = comillas[0] if comillas else (f"Grupo {m_grupo.group(1)}" if m_grupo else None)
        m_torneo = re.search(r'(?:en|in|del torneo|of tournament)\s+["\']?([^"\']+?)["\']?\s*$', texto_usuario, re.IGNORECASE)
        nombre_torneo = comillas[1] if len(comillas) > 1 else (m_torneo.group(1).strip() if m_torneo else None)
        if not nombre_grupo or not nombre_torneo:
            return {"tipo": "respuesta", "texto": "Necesito el nombre del grupo y del torneo.", "herramienta": None, "terminado": False}
        return {"tipo": "herramienta", "texto": crear_grupo(nombre_torneo, nombre_grupo), "herramienta": "crear_grupo", "terminado": False}

    # ── Añadir equipo a grupo ───────────────────────────────────────────────────
    if any(f in t for f in ["añade", "agrega", "add"]) and "grupo" in t:
        comillas = re.findall(r'["\u201c\u201d](.+?)["\u201c\u201d]', texto_usuario)
        m = re.search(r'(?:añade|agrega|add)\s+(?:a\s+|al equipo\s+)?["\']?([^"\']+?)["\']?\s+(?:al|to|a)\s+(?:grupo\s+)?([A-Za-z0-9]+)', texto_usuario, re.IGNORECASE)
        m_torneo = re.search(r'(?:de|del torneo|of|in)\s+["\']?([^"\']+?)["\']?\s*$', texto_usuario, re.IGNORECASE)
        if m and m_torneo:
            nombre_equipo = comillas[0] if comillas else m.group(1).strip()
            nombre_grupo  = f"Grupo {m.group(2)}" if not m.group(2).lower().startswith("grupo") else m.group(2)
            nombre_torneo = comillas[1] if len(comillas) > 1 else m_torneo.group(1).strip()
            return {"tipo": "herramienta", "texto": añadir_equipo_a_grupo(nombre_equipo, nombre_grupo, nombre_torneo),
                    "herramienta": "añadir_equipo_a_grupo", "terminado": False}

    # ── Registrar jugador ───────────────────────────────────────────────────────
    if any(f in t for f in ["registra al jugador", "registra jugador", "añade al jugador", "nuevo jugador"]):
        nombre = _extraer_entre_comillas(texto_usuario)
        if not nombre:
            m = re.search(r'jugador\s+["\']?([A-Za-z\s]+?)(?:["\']|de\s+\d|,|$)', texto_usuario, re.IGNORECASE)
            nombre = m.group(1).strip() if m else None
        m_edad  = re.search(r'(\d+)\s*años', texto_usuario, re.IGNORECASE)
        m_pos   = re.search(r'(?:posicion|posición|juega de|es)\s+([A-Za-z]+)', texto_usuario, re.IGNORECASE)
        edad    = int(m_edad.group(1)) if m_edad else None
        posicion = m_pos.group(1).strip() if m_pos else None
        if nombre:
            return {"tipo": "herramienta", "texto": registrar_jugador(nombre, edad, posicion),
                    "herramienta": "registrar_jugador", "terminado": False}

    # ── Programar partido ───────────────────────────────────────────────────────
    if any(f in t for f in ["programa el partido", "programa un partido", "programar partido", "partido entre"]):
        m = re.search(r'(?:entre|between)\s+["\']?(.+?)["\']?\s+(?:vs?\.?|contra|and)\s+["\']?(.+?)["\']?\s+(?:en|in)\s+["\']?(.+?)["\']?(?:\s|$)', texto_usuario, re.IGNORECASE)
        if m:
            fecha = _extraer_fecha(texto_usuario)
            m_fase = re.search(r'(?:fase|phase|ronda|round)\s*:?\s*([^\.,]+)', texto_usuario, re.IGNORECASE)
            fase = m_fase.group(1).strip() if m_fase else "Fase de grupos"
            resultado = programar_partido(m.group(3).strip(), m.group(1).strip(), m.group(2).strip(), fecha, fase)
            return {"tipo": "herramienta", "texto": resultado, "herramienta": "programar_partido", "terminado": False}

    # ── Registrar resultado ─────────────────────────────────────────────────────
    if any(f in t for f in ["registra el resultado", "registra resultado", "el resultado fue",
                              "ganó", "gano", "empató", "empato", "termino", "terminó"]):
        m = re.search(r'["\']?(.+?)["\']?\s+(\d+)\s*[-\u2013]\s*(\d+)\s+["\']?(.+?)["\']?\s+(?:en|in)\s+["\']?(.+?)["\']?(?:\s|$)', texto_usuario, re.IGNORECASE)
        if m:
            resultado = registrar_resultado(m.group(5).strip(), m.group(1).strip(), m.group(4).strip(), int(m.group(2)), int(m.group(3)))
            return {"tipo": "herramienta", "texto": resultado, "herramienta": "registrar_resultado", "terminado": False}

    # ── Ver clasificación ───────────────────────────────────────────────────────
    if any(f in t for f in ["clasificacion", "clasificación", "tabla de posiciones", "standings", "ver clasificacion"]):
        comillas = re.findall(r'["\u201c\u201d](.+?)["\u201c\u201d]', texto_usuario)
        m_torneo = re.search(r'(?:de|del|of|in)\s+["\']?([^"\']+?)(?:["\']|grupo|group|$)', texto_usuario, re.IGNORECASE)
        nombre_torneo = comillas[0] if comillas else (m_torneo.group(1).strip() if m_torneo else None)
        m_grupo = re.search(r'grupo\s+([A-Za-z0-9]+)', texto_usuario, re.IGNORECASE)
        nombre_grupo = f"Grupo {m_grupo.group(1)}" if m_grupo else None
        if nombre_torneo:
            return {"tipo": "herramienta", "texto": ver_clasificacion(nombre_torneo, nombre_grupo),
                    "herramienta": "ver_clasificacion", "terminado": False}

    # ── Ver partidos ────────────────────────────────────────────────────────────
    if any(f in t for f in ["ver partidos", "muestra los partidos", "partidos del", "fixture", "calendario de partidos"]):
        comillas = re.findall(r'["\u201c\u201d](.+?)["\u201c\u201d]', texto_usuario)
        m_torneo = re.search(r'(?:de|del|of|in)\s+["\']?([^"\']+?)["\']?(?:\s|$)', texto_usuario, re.IGNORECASE)
        nombre_torneo = comillas[0] if comillas else (m_torneo.group(1).strip() if m_torneo else None)
        estado = "jugado" if "jugado" in t else ("programado" if "programado" in t else None)
        if nombre_torneo:
            return {"tipo": "herramienta", "texto": ver_partidos(nombre_torneo, estado),
                    "herramienta": "ver_partidos", "terminado": False}

    # ── Ver stats jugadores ─────────────────────────────────────────────────────
    if any(f in t for f in ["stats de jugadores", "estadisticas de jugadores", "estadísticas de jugadores", "goleadores", "ver stats"]):
        comillas = re.findall(r'["\u201c\u201d](.+?)["\u201c\u201d]', texto_usuario)
        m_torneo = re.search(r'(?:de|del|of|in)\s+["\']?([^"\']+?)["\']?(?:\s|$)', texto_usuario, re.IGNORECASE)
        nombre_torneo = comillas[0] if comillas else (m_torneo.group(1).strip() if m_torneo else None)
        if nombre_torneo:
            return {"tipo": "herramienta", "texto": ver_stats_jugadores(nombre_torneo),
                    "herramienta": "ver_stats_jugadores", "terminado": False}

    # ── Actualizar stats jugador ────────────────────────────────────────────────
    if any(f in t for f in ["actualiza las stats", "actualiza stats", "añade goles", "registra goles", "añade asistencias"]):
        comillas = re.findall(r'["\u201c\u201d](.+?)["\u201c\u201d]', texto_usuario)
        m_jugador = re.search(r'(?:de|of|para|for|jugador)\s+["\']?([^"\']+?)["\']?\s+(?:en|in)', texto_usuario, re.IGNORECASE)
        m_torneo  = re.search(r'(?:en|in)\s+["\']?([^"\']+?)["\']?(?:\s|$)', texto_usuario, re.IGNORECASE)
        nombre_jugador = comillas[0] if comillas else (m_jugador.group(1).strip() if m_jugador else None)
        nombre_torneo  = comillas[1] if len(comillas) > 1 else (m_torneo.group(1).strip() if m_torneo else None)
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
                int(mp.group(1)) if mp else 0
            )
            return {"tipo": "herramienta", "texto": resultado, "herramienta": "actualizar_stats_jugador", "terminado": False}

    # ── Sorteo de grupos ────────────────────────────────────────────────────────
    if any(f in t for f in ["sorteo de grupos", "realiza el sorteo", "haz el sorteo",
                              "sortear grupos", "realizar sorteo", "draw de grupos"]):
        comillas = re.findall(r'["\u201c\u201d](.+?)["\u201c\u201d]', texto_usuario)
        m_torneo = re.search(r'(?:de|del|of|in|para)\s+["\']?([^"\']+?)["\']?(?:\s|$)', texto_usuario, re.IGNORECASE)
        nombre_torneo = comillas[0] if comillas else (m_torneo.group(1).strip() if m_torneo else None)
        if nombre_torneo:
            return {"tipo": "herramienta", "texto": realizar_sorteo_grupos(nombre_torneo),
                    "herramienta": "realizar_sorteo_grupos", "terminado": False}

    # ── Sorteo de eliminatorias ─────────────────────────────────────────────────
    if any(f in t for f in ["sorteo de eliminatorias", "cuadro de eliminatorias", "genera las eliminatorias",
                              "crea las eliminatorias", "ronda eliminatoria", "knockout draw", "fase eliminatoria"]):
        comillas = re.findall(r'["\u201c\u201d](.+?)["\u201c\u201d]', texto_usuario)
        m_torneo = re.search(r'(?:de|del|of|in|para)\s+["\']?([^"\']+?)["\']?(?:\s|$)', texto_usuario, re.IGNORECASE)
        nombre_torneo = comillas[0] if comillas else (m_torneo.group(1).strip() if m_torneo else None)
        m_cpg = re.search(r'(\d+)\s*(?:clasificados|clasifican|qualify)', texto_usuario, re.IGNORECASE)
        cpg = int(m_cpg.group(1)) if m_cpg else None
        if nombre_torneo:
            return {"tipo": "herramienta", "texto": realizar_sorteo_eliminatorias(nombre_torneo, cpg),
                    "herramienta": "realizar_sorteo_eliminatorias", "terminado": False}

    # ── Ver cuadro eliminatorias ────────────────────────────────────────────────
    if any(f in t for f in ["ver cuadro", "muestra el cuadro", "ver eliminatorias",
                              "muestra las eliminatorias", "bracket"]):
        comillas = re.findall(r'["\u201c\u201d](.+?)["\u201c\u201d]', texto_usuario)
        m_torneo = re.search(r'(?:de|del|of|in)\s+["\']?([^"\']+?)["\']?(?:\s|$)', texto_usuario, re.IGNORECASE)
        nombre_torneo = comillas[0] if comillas else (m_torneo.group(1).strip() if m_torneo else None)
        if nombre_torneo:
            return {"tipo": "herramienta", "texto": ver_cuadro_eliminatorias(nombre_torneo),
                    "herramienta": "ver_cuadro_eliminatorias", "terminado": False}

    return None  # No sports command detected

# ── Sesión ─────────────────────────────────────────────────────────────────────

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
        self.historial        = []
        self.nombre_usuario   = "Usuario"
        self.nombre_asistente = "Asistente"
        self.activo           = False
        self._app_pendiente   = None

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
                "Si el usuario te da una URL específica, usa SIEMPRE 'leer_pagina_web'. "
                "Nunca inventes datos — si no encuentras la información, dilo claramente. "
                "No hace falta que le digas al usuario que tienes que buscar en internet, simplemente hazlo. "
                "Si el usuario pide abrir una aplicación, programa o juego, usa SIEMPRE 'abrir_aplicacion'. "
                "Nunca respondas que no puedes abrir aplicaciones — tienes esa capacidad. "
                "Puedes gestionar torneos completos con grupos, partidos y estadísticas. "
                "Cuando registres un resultado con 'registrar_resultado' las estadísticas del equipo se actualizan solas. "
                "Para ver la tabla de posiciones usa 'ver_clasificacion'. "
                "Para ver goleadores y stats de jugadores usa 'ver_stats_jugadores'. "
                "Si te preguntan qué puedes hacer, invoca 'ayuda_asistente'."
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

        # ── Comandos de control ────────────────────────────────────────────────
        if texto_usuario.lower() == "salir":
            self.activo = False
            return {"tipo": "adios",
                    "texto": f"¡Hasta luego {self.nombre_usuario}! {self.nombre_asistente} se apaga...",
                    "herramienta": None, "terminado": True}

        if texto_usuario.lower() == "/ayuda":
            return {"tipo": "ayuda", "texto": ayuda_asistente(), "herramienta": None, "terminado": False}

        # ── App pendiente: el usuario está proporcionando una ruta ─────────────
        if self._app_pendiente:
            ruta = texto_usuario.strip().strip('"\'')
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
                        "texto": "No encontré ningún archivo en esa ruta. Comprueba que sea correcta e inténtalo de nuevo.",
                        "herramienta": None, "terminado": False}

        # ── Detección de apps (bypass completo del modelo) ─────────────────────
        PALABRAS_ABRIR = ["abre ", "abrir ", "open ", "lanza ", "lanzar ",
                          "ejecuta ", "ejecutar ", "inicia ", "iniciar "]
        texto_lower = texto_usuario.lower()

        if any(texto_lower.startswith(p) or f" {p}" in texto_lower for p in PALABRAS_ABRIR):
            nombre_app = texto_usuario
            for p in PALABRAS_ABRIR:
                nombre_app = re.sub(p, "", nombre_app, flags=re.IGNORECASE).strip()
            for filler in ["la aplicación", "la aplicacion", "el programa", "el juego",
                           "la app", "por favor", "porfavor"]:
                nombre_app = re.sub(filler, "", nombre_app, flags=re.IGNORECASE).strip()

            # Check if the user also provided a path inline
            ruta_inline = None
            path_patterns = [
                r'(?:la ruta es|ruta:|path:|this is the path|the path is|su ruta es|está en|esta en)\s*["\']?([\w:\\\/\s\.\-\_]+\.exe)["\']?',
                r'["\']?((?:[A-Za-z]:\\|\/)[^\s"\']+\.exe)["\']?',
            ]
            for pattern in path_patterns:
                match = re.search(pattern, texto_usuario, re.IGNORECASE)
                if match:
                    ruta_inline = match.group(1).strip().strip('"\'')
                    nombre_app = texto_usuario[:match.start()].strip()
                    for p in PALABRAS_ABRIR:
                        nombre_app = re.sub(p, "", nombre_app, flags=re.IGNORECASE).strip()
                    for filler in ["la aplicación", "la aplicacion", "el programa", "el juego",
                                   "la app", "la ruta es", "ruta:", "path:", "this is the path",
                                   "the path is", "su ruta es", "está en", "esta en", ",",
                                   "por favor", "porfavor"]:
                        nombre_app = re.sub(filler, "", nombre_app, flags=re.IGNORECASE).strip()
                    nombre_app = nombre_app.strip(" .,")
                    break

            if nombre_app:
                if ruta_inline:
                    if os.path.exists(ruta_inline):
                        guardar_ruta_app(nombre_app, ruta_inline)
                        try:
                            os.startfile(ruta_inline)
                            return {"tipo": "herramienta",
                                    "texto": f"Ruta guardada y '{nombre_app}' abierta correctamente. "
                                             "La próxima vez la abriré automáticamente.",
                                    "herramienta": "abrir_aplicacion", "terminado": False}
                        except Exception as e:
                            return {"tipo": "error",
                                    "texto": f"Ruta guardada pero no se pudo abrir '{nombre_app}': {e}",
                                    "herramienta": None, "terminado": False}
                    else:
                        return {"tipo": "respuesta",
                                "texto": f"Guardé el nombre '{nombre_app}' pero no encontré ningún archivo en:\n{ruta_inline}\n"
                                         "Comprueba que la ruta sea correcta e inténtalo de nuevo.",
                                "herramienta": None, "terminado": False}

                resultado = abrir_aplicacion(nombre_app)
                if resultado["estado"] == "no_encontrada":
                    self._app_pendiente = resultado["app"]
                    return {"tipo": "respuesta",
                            "texto": f"No encontré '{resultado['app']}' automáticamente.\n"
                                     "¿Puedes decirme la ruta completa del ejecutable?\n"
                                     f"(Ej: C:\\Program Files\\App\\app.exe)\n"
                                     f"O dime directamente: 'Abre {resultado['app']}, la ruta es C:\\...\\app.exe'",
                            "herramienta": "abrir_aplicacion", "terminado": False}
                return {"tipo": "herramienta", "texto": resultado["mensaje"],
                        "herramienta": "abrir_aplicacion", "terminado": False}

        # ── Detección de comandos deportivos (bypass completo del modelo) ──────
        accion = _intentar_accion_deportiva(self, texto_usuario)
        if accion:
            return accion

        # ── Búsqueda web directa ───────────────────────────────────────────────
        if texto_usuario.startswith("/buscar "):
            query = texto_usuario[8:]
            datos = buscar_en_internet(query)
            contexto = (f"Pregunta: {query}\nContexto de internet:\n{datos}\n"
                        "Responde basándote estrictamente en estos datos sin inventar nada.")
            self.historial.append({"role": "user", "content": contexto})
        else:
            self.historial.append({"role": "user", "content": texto_usuario})

        # ── Detección de URLs ──────────────────────────────────────────────────
        urls = re.findall(r'https?://\S+', texto_usuario)
        if urls:
            url = urls[0]
            contenido = leer_pagina_web(url)
            pregunta_sin_url = texto_usuario.replace(url, "").strip()
            if contenido.startswith("PAGINA_JS_DETECTADA"):
                dominio   = url.split("/")[2]
                contenido = buscar_en_internet(f"site:{dominio} {pregunta_sin_url or 'informacion'}")
            self.historial.append({"role": "user", "content":
                f"Contenido real de {url}:\n{contenido}\n\n"
                f"Usando ÚNICAMENTE este contenido, responde: {pregunta_sin_url or texto_usuario}\n"
                "Sé específico con nombres, cifras y fechas. No inventes nada."
            })
            if len(self.historial) > 14:
                self.historial = [self.historial[0]] + self.historial[-12:]
            try:
                respuesta = client.chat.completions.create(model="local-model", messages=self.historial)
                respuesta_final = respuesta.choices[0].message.content
                self.historial.append({"role": "assistant", "content": respuesta_final})
                return {"tipo": "herramienta", "texto": respuesta_final,
                        "herramienta": "leer_pagina_web", "terminado": False}
            except Exception as e:
                return {"tipo": "error", "texto": f"Error: {e}", "herramienta": None, "terminado": False}

        # ── Llamada al modelo (fallback para todo lo demás) ────────────────────
        if len(self.historial) > 14:
            self.historial = [self.historial[0]] + self.historial[-12:]

        try:
            completion = client.chat.completions.create(
                model="local-model",
                messages=self.historial,
                tools=TOOLS,
                tool_choice="auto",
                temperature=0.4
            )
            mensaje_ia = completion.choices[0].message

            if mensaje_ia.tool_calls:
                tool_call   = mensaje_ia.tool_calls[0]
                nombre_func = tool_call.function.name
                argumentos  = json.loads(tool_call.function.arguments)
                funcion     = FUNCIONES_MAPA.get(nombre_func)
                resultado   = (funcion(**argumentos) if funcion else "Herramienta no encontrada.") \
                              if nombre_func != "abrir_aplicacion" else None

                if nombre_func == "ayuda_asistente":
                    self.historial.append({"role": "assistant", "content": "He mostrado el menú de ayuda."})
                    return {"tipo": "ayuda", "texto": ayuda_asistente(), "herramienta": nombre_func, "terminado": False}

                if nombre_func in ("buscar_en_internet", "leer_pagina_web"):
                    self.historial.append(mensaje_ia)
                    self.historial.append({"role": "tool", "tool_call_id": tool_call.id,
                                           "name": nombre_func, "content": resultado})
                    self.historial.append({"role": "user", "content":
                        "Usando ÚNICAMENTE la información obtenida anteriormente, "
                        "responde la pregunta original con datos concretos y específicos. "
                        "No uses frases como 'según mis fuentes' ni dejes campos vacíos con corchetes. "
                        "Si la información no está en los resultados, dilo claramente."
                    })
                    segunda = client.chat.completions.create(model="local-model", messages=self.historial)
                    respuesta_final = segunda.choices[0].message.content
                    self.historial.append({"role": "assistant", "content": respuesta_final})
                    return {"tipo": "herramienta", "texto": respuesta_final,
                            "herramienta": nombre_func, "terminado": False}

                if nombre_func == "abrir_aplicacion":
                    resultado = abrir_aplicacion(**argumentos)
                    if resultado["estado"] == "no_encontrada":
                        self._app_pendiente = resultado["app"]
                        self.historial.append({"role": "assistant", "content": resultado["mensaje"]})
                        return {"tipo": "respuesta",
                                "texto": f"No encontré '{resultado['app']}' automáticamente. "
                                         "¿Puedes decirme la ruta completa del ejecutable?\n"
                                         f"(Ej: C:\\Program Files\\App\\app.exe)",
                                "herramienta": nombre_func, "terminado": False}
                    self.historial.append({"role": "assistant", "content": resultado["mensaje"]})
                    return {"tipo": "herramienta", "texto": resultado["mensaje"],
                            "herramienta": nombre_func, "terminado": False}

                # Generic tool handler
                self.historial.append(mensaje_ia)
                self.historial.append({"role": "tool", "tool_call_id": tool_call.id,
                                       "name": nombre_func, "content": str(resultado)})
                segunda = client.chat.completions.create(model="local-model", messages=self.historial)
                respuesta_final = segunda.choices[0].message.content
                self.historial.append({"role": "assistant", "content": respuesta_final})
                return {"tipo": "herramienta", "texto": respuesta_final,
                        "herramienta": nombre_func, "terminado": False}

            # ── Respuesta de texto sin herramienta ─────────────────────────────
            respuesta = mensaje_ia.content
            modelo_finge_buscar = any(frase in respuesta.lower() for frase in [
                "buscar en internet", "buscar en la web", "consultando fuentes",
                "según mis fuentes", "luego de buscar", "he encontrado en internet"
            ])

            if modelo_finge_buscar or _necesita_busqueda(texto_usuario):
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
                return {"tipo": "herramienta", "texto": respuesta_final,
                        "herramienta": "buscar_en_internet", "terminado": False}

            self.historial.append({"role": "assistant", "content": respuesta})
            return {"tipo": "respuesta", "texto": respuesta, "herramienta": None, "terminado": False}

        except Exception as e:
            return {"tipo": "error", "texto": f"Error de comunicación con el modelo: {e}",
                    "herramienta": None, "terminado": False}

    def cerrar(self):
        self.activo = False
        cerrar_servidor(self.proceso_servidor)