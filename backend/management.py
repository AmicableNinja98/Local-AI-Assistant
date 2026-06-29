from .db import _db


def registrar_jugador(nombre, edad=None, posicion=None):
    try:
        conn = _db()
        cur = conn.cursor()
        cur.execute("INSERT INTO jugadores (nombre, edad, posicion) VALUES (%s, %s, %s)", (nombre, edad, posicion))
        conn.commit()
        cur.close()
        conn.close()
        return f"Jugador '{nombre}' registrado correctamente."
    except Exception as e:
        return f"Error al registrar jugador: {e}"


def crear_equipo(nombre):
    try:
        conn = _db()
        cur = conn.cursor()
        cur.execute("INSERT INTO equipos (nombre) VALUES (%s)", (nombre,))
        conn.commit()
        cur.close()
        conn.close()
        return f"Equipo '{nombre}' creado correctamente."
    except Exception as e:
        return f"Error al crear equipo: {e}"


def asociar_jugador_a_equipo(nombre_jugador, nombre_equipo):
    try:
        conn = _db()
        cur = conn.cursor()
        cur.execute("SELECT id FROM jugadores WHERE nombre LIKE %s", (f"%{nombre_jugador}%",))
        j = cur.fetchone()
        cur.execute("SELECT id FROM equipos WHERE nombre LIKE %s", (f"%{nombre_equipo}%",))
        e = cur.fetchone()
        if not j:
            return f"No encontré al jugador '{nombre_jugador}'."
        if not e:
            return f"No encontré al equipo '{nombre_equipo}'."
        cur.execute("INSERT INTO equipo_jugadores (equipo_id, jugador_id) VALUES (%s, %s)", (e[0], j[0]))
        conn.commit()
        cur.close()
        conn.close()
        return f"{nombre_jugador} asignado al equipo {nombre_equipo}."
    except Exception as ex:
        return f"Error: {ex}"


def crear_torneo(nombre, fecha_inicio=None):
    try:
        conn = _db()
        cur = conn.cursor()
        cur.execute("INSERT INTO torneos (nombre, fecha_inicio) VALUES (%s, %s)", (nombre, fecha_inicio))
        conn.commit()
        cur.close()
        conn.close()
        return f"Torneo '{nombre}' creado correctamente."
    except Exception as e:
        return f"Error al crear torneo: {e}"


def inscribir_equipo_en_torneo(nombre_equipo, nombre_torneo):
    try:
        conn = _db()
        cur = conn.cursor()
        cur.execute("SELECT id FROM equipos WHERE nombre LIKE %s", (f"%{nombre_equipo}%",))
        e = cur.fetchone()
        cur.execute("SELECT id FROM torneos WHERE nombre LIKE %s", (f"%{nombre_torneo}%",))
        t = cur.fetchone()
        if not e:
            return f"No existe el equipo '{nombre_equipo}'."
        if not t:
            return f"No existe el torneo '{nombre_torneo}'."
        cur.execute("INSERT INTO torneo_equipos (torneo_id, equipo_id) VALUES (%s, %s)", (t[0], e[0]))
        conn.commit()
        cur.close()
        conn.close()
        return f"Equipo '{nombre_equipo}' inscrito en '{nombre_torneo}'."
    except Exception as ex:
        return f"Error: {ex}"


def listar_todo_lo_guardado():
    try:
        conn = _db()
        cur = conn.cursor()
        cur.execute("SELECT nombre, posicion FROM jugadores")
        jugadores = cur.fetchall()
        cur.execute("SELECT nombre FROM equipos")
        equipos = cur.fetchall()
        cur.execute("SELECT nombre, estado FROM torneos")
        torneos = cur.fetchall()
        cur.close()
        conn.close()
        res = "--- REGISTROS ACTUALES ---\n"
        res += f"Jugadores: {', '.join([j[0] for j in jugadores]) if jugadores else 'Ninguno'}\n"
        res += f"Equipos: {', '.join([e[0] for e in equipos]) if equipos else 'Ninguno'}\n"
        res += f"Torneos: {', '.join([f'{t[0]} ({t[1]})' for t in torneos]) if torneos else 'Ninguno'}\n"
        return res
    except Exception as e:
        return f"Error: {e}"
