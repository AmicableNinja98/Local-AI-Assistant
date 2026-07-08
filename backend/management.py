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
        cur.execute("SELECT id, nombre FROM equipos WHERE LOWER(nombre) LIKE LOWER(%s) LIMIT 1", (f"%{nombre_equipo}%",))
        e = cur.fetchone()
        cur.execute("SELECT id FROM torneos WHERE LOWER(nombre) LIKE LOWER(%s) LIMIT 1", (f"%{nombre_torneo}%",))
        t = cur.fetchone()
        if not e:
            cur.close(); conn.close()
            return f"No existe el equipo '{nombre_equipo}'."
        if not t:
            cur.close(); conn.close()
            return f"No existe el torneo '{nombre_torneo}'."

        equipo_id  = e[0]
        equipo_nombre = e[1]
        torneo_id  = t[0]

        # Inscribe the team
        cur.execute("INSERT IGNORE INTO torneo_equipos (torneo_id, equipo_id) VALUES (%s, %s)", (torneo_id, equipo_id))
        cur.execute("INSERT IGNORE INTO estadisticas_equipo_torneo (torneo_id, equipo_id) VALUES (%s, %s)", (torneo_id, equipo_id))

        # Auto-inscribe all players belonging to this team
        cur.execute("SELECT jugador_id FROM equipo_jugadores WHERE equipo_id = %s", (equipo_id,))
        jugadores = cur.fetchall()
        for (jugador_id,) in jugadores:
            cur.execute("""
                INSERT IGNORE INTO estadisticas_jugador_torneo
                    (torneo_id, jugador_id, equipo_id)
                VALUES (%s, %s, %s)
            """, (torneo_id, jugador_id, equipo_id))

        conn.commit()
        cur.close(); conn.close()

        if jugadores:
            return (f"Equipo '{equipo_nombre}' inscrito en '{nombre_torneo}' "
                    f"junto con sus {len(jugadores)} jugador(es).")
        return f"Equipo '{equipo_nombre}' inscrito en '{nombre_torneo}' (sin jugadores asignados aún)."

    except Exception as ex:
        return f"Error: {ex}"


def inscribir_multiples_equipos_en_torneo(nombre_torneo, excluir=None):
    """
    Inscribes all teams in the database into a tournament.
    excluir: list of team name strings to skip (optional).
    """
    try:
        excluir = [e.lower().strip() for e in excluir] if excluir else []

        conn = _db()
        cur = conn.cursor()

        cur.execute("SELECT id FROM torneos WHERE LOWER(nombre) LIKE LOWER(%s) LIMIT 1", (f"%{nombre_torneo}%",))
        t = cur.fetchone()
        if not t:
            cur.close(); conn.close()
            return f"No existe el torneo '{nombre_torneo}'."
        torneo_id = t[0]

        cur.execute("SELECT id, nombre FROM equipos")
        todos = cur.fetchall()
        if not todos:
            cur.close(); conn.close()
            return "No hay equipos registrados en la base de datos."

        inscritos = []
        omitidos  = []

        for equipo_id, equipo_nombre in todos:
            # Check exclusion list with partial matching
            if any(ex in equipo_nombre.lower() for ex in excluir):
                omitidos.append(equipo_nombre)
                continue

            cur.execute("INSERT IGNORE INTO torneo_equipos (torneo_id, equipo_id) VALUES (%s, %s)", (torneo_id, equipo_id))
            cur.execute("INSERT IGNORE INTO estadisticas_equipo_torneo (torneo_id, equipo_id) VALUES (%s, %s)", (torneo_id, equipo_id))

            # Auto-inscribe players of this team
            cur.execute("SELECT jugador_id FROM equipo_jugadores WHERE equipo_id = %s", (equipo_id,))
            jugadores = cur.fetchall()
            for (jugador_id,) in jugadores:
                cur.execute("""
                    INSERT IGNORE INTO estadisticas_jugador_torneo (torneo_id, jugador_id, equipo_id)
                    VALUES (%s, %s, %s)
                """, (torneo_id, jugador_id, equipo_id))

            inscritos.append(equipo_nombre)

        conn.commit()
        cur.close(); conn.close()

        lineas = [f"✅ {len(inscritos)} equipo(s) inscritos en '{nombre_torneo}':"]
        for nombre in inscritos:
            lineas.append(f"   • {nombre}")
        if omitidos:
            lineas.append(f"\n⏭️  Omitidos ({len(omitidos)}): {', '.join(omitidos)}")
        return "\n".join(lineas)

    except Exception as ex:
        return f"Error: {ex}"


def inscribir_jugador_en_torneo(nombre_jugador, nombre_torneo):
    try:
        conn = _db()
        cur = conn.cursor()
        cur.execute("SELECT id FROM jugadores WHERE LOWER(nombre) LIKE LOWER(%s) LIMIT 1", (f"%{nombre_jugador}%",))
        j = cur.fetchone()
        cur.execute("SELECT id FROM torneos WHERE LOWER(nombre) LIKE LOWER(%s) LIMIT 1", (f"%{nombre_torneo}%",))
        t = cur.fetchone()
        if not j:
            cur.close(); conn.close()
            return f"No existe el jugador '{nombre_jugador}'."
        if not t:
            cur.close(); conn.close()
            return f"No existe el torneo '{nombre_torneo}'."

        equipo_id = None
        cur.execute("SELECT equipo_id FROM equipo_jugadores WHERE jugador_id = %s LIMIT 1", (j[0],))
        eq = cur.fetchone()
        if eq:
            equipo_id = eq[0]
            cur.execute("INSERT IGNORE INTO torneo_equipos (torneo_id, equipo_id) VALUES (%s, %s)", (t[0], equipo_id))
            cur.execute("INSERT IGNORE INTO estadisticas_equipo_torneo (torneo_id, equipo_id) VALUES (%s, %s)", (t[0], equipo_id))

        cur.execute("INSERT IGNORE INTO estadisticas_jugador_torneo (torneo_id, jugador_id, equipo_id) VALUES (%s, %s, %s)", (t[0], j[0], equipo_id))
        conn.commit()
        cur.close(); conn.close()
        return f"Jugador '{nombre_jugador}' registrado en '{nombre_torneo}'."
    except Exception as ex:
        return f"Error: {ex}"


def inscribir_y_sortear(nombre_torneo, excluir=None):
    """Inscribes all teams then immediately drafts them into groups."""
    from .sports import realizar_sorteo_grupos

    resultado_inscripcion = inscribir_multiples_equipos_en_torneo(nombre_torneo, excluir)
    if resultado_inscripcion.startswith("No existe") or resultado_inscripcion.startswith("Error"):
        return resultado_inscripcion

    resultado_sorteo = realizar_sorteo_grupos(nombre_torneo)
    return f"{resultado_inscripcion}\n\n{resultado_sorteo}"


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
