import random

from .db import _db


def _obtener_id_torneo(nombre: str):
    conn = _db()
    cur = conn.cursor()
    cur.execute("SELECT id FROM torneos WHERE nombre LIKE %s", (f"%{nombre}%",))
    res = cur.fetchone()
    cur.close()
    conn.close()
    return res[0] if res else None


def _obtener_id_equipo(nombre: str):
    conn = _db()
    cur = conn.cursor()
    cur.execute("SELECT id FROM equipos WHERE nombre LIKE %s", (f"%{nombre}%",))
    res = cur.fetchone()
    cur.close()
    conn.close()
    return res[0] if res else None


def _obtener_id_jugador(nombre: str):
    conn = _db()
    cur = conn.cursor()
    cur.execute("SELECT id FROM jugadores WHERE nombre LIKE %s", (f"%{nombre}%",))
    res = cur.fetchone()
    cur.close()
    conn.close()
    return res[0] if res else None


def _obtener_id_grupo(nombre_torneo: str, nombre_grupo: str):
    conn = _db()
    cur = conn.cursor()
    cur.execute("""
        SELECT g.id FROM grupos g
        JOIN torneos t ON g.torneo_id = t.id
        WHERE t.nombre LIKE %s AND g.nombre LIKE %s
    """, (f"%{nombre_torneo}%", f"%{nombre_grupo}%"))
    res = cur.fetchone()
    cur.close()
    conn.close()
    return res[0] if res else None


def _asegurar_estadisticas_equipo(conn, torneo_id, equipo_id):
    cur = conn.cursor(buffered=True)
    cur.execute("""
        INSERT IGNORE INTO estadisticas_equipo_torneo (torneo_id, equipo_id)
        VALUES (%s, %s)
    """, (torneo_id, equipo_id))
    conn.commit()
    cur.close()


def crear_grupo(nombre_torneo: str, nombre_grupo: str) -> str:
    try:
        t_id = _obtener_id_torneo(nombre_torneo)
        if not t_id:
            return f"No encontré el torneo '{nombre_torneo}'."
        conn = _db()
        cur = conn.cursor()
        cur.execute("INSERT IGNORE INTO grupos (torneo_id, nombre) VALUES (%s, %s)", (t_id, nombre_grupo))
        conn.commit()
        cur.close()
        conn.close()
        return f"Grupo '{nombre_grupo}' creado en el torneo '{nombre_torneo}'."
    except Exception as e:
        return f"Error al crear grupo: {e}"


def añadir_equipo_a_grupo(nombre_equipo: str, nombre_grupo: str, nombre_torneo: str) -> str:
    try:
        e_id = _obtener_id_equipo(nombre_equipo)
        g_id = _obtener_id_grupo(nombre_torneo, nombre_grupo)
        t_id = _obtener_id_torneo(nombre_torneo)
        if not e_id:
            return f"No encontré el equipo '{nombre_equipo}'."
        if not g_id:
            return f"No encontré el grupo '{nombre_grupo}' en '{nombre_torneo}'."
        conn = _db()
        cur = conn.cursor()
        cur.execute("INSERT IGNORE INTO grupo_equipos (grupo_id, equipo_id) VALUES (%s, %s)", (g_id, e_id))
        _asegurar_estadisticas_equipo(conn, t_id, e_id)
        conn.commit()
        cur.close()
        conn.close()
        return f"'{nombre_equipo}' añadido al {nombre_grupo} del torneo '{nombre_torneo}'."
    except Exception as e:
        return f"Error: {e}"


def programar_partido(nombre_torneo: str, nombre_local: str, nombre_visitante: str,
                      fecha: str = None, fase: str = "Fase de grupos",
                      nombre_grupo: str = None) -> str:
    try:
        t_id = _obtener_id_torneo(nombre_torneo)
        l_id = _obtener_id_equipo(nombre_local)
        v_id = _obtener_id_equipo(nombre_visitante)
        if not t_id:
            return f"No encontré el torneo '{nombre_torneo}'."
        if not l_id:
            return f"No encontré el equipo '{nombre_local}'."
        if not v_id:
            return f"No encontré el equipo '{nombre_visitante}'."
        g_id = _obtener_id_grupo(nombre_torneo, nombre_grupo) if nombre_grupo else None
        conn = _db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO partidos (torneo_id, equipo_local_id, equipo_visitante_id,
                                  fecha, fase, grupo_id, estado)
            VALUES (%s, %s, %s, %s, %s, %s, 'programado')
        """, (t_id, l_id, v_id, fecha, fase, g_id))
        conn.commit()
        cur.close()
        conn.close()
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
        if not t_id:
            return f"No encontré el torneo '{nombre_torneo}'."
        if not l_id:
            return f"No encontré el equipo '{nombre_local}'."
        if not v_id:
            return f"No encontré el equipo '{nombre_visitante}'."

        conn = _db()
        cur = conn.cursor()
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

        conn.commit()
        cur.close()
        conn.close()

        resultado_str = (f"Victoria {nombre_local}" if goles_local > goles_visitante
                         else f"Victoria {nombre_visitante}" if goles_visitante > goles_local
                         else "Empate")
        return (f"Resultado registrado: {nombre_local} {goles_local} - {goles_visitante} {nombre_visitante}. "
                f"{resultado_str}. Estadísticas actualizadas.")
    except Exception as e:
        return f"Error al registrar resultado: {e}"


def actualizar_partido_completo(nombre_torneo: str, nombre_local: str,
                                 nombre_visitante: str, goles_local: int,
                                 goles_visitante: int, goleadores: list = None,
                                 asistentes: list = None, fase: str = None) -> str:
    try:
        t_id = _obtener_id_torneo(nombre_torneo)
        l_id = _obtener_id_equipo(nombre_local)
        v_id = _obtener_id_equipo(nombre_visitante)

        if not t_id: return f"⚠️  No encontré el torneo '{nombre_torneo}'."
        if not l_id: return f"⚠️  No encontré el equipo '{nombre_local}'."
        if not v_id: return f"⚠️  No encontré el equipo '{nombre_visitante}'."

        conn = _db()

        # ── VALIDATION 1: Check the match exists ───────────────────────────
        cur = conn.cursor(buffered=True)
        query = """
            SELECT id, estado FROM partidos
            WHERE torneo_id = %s
              AND equipo_local_id = %s
              AND equipo_visitante_id = %s
        """
        params = [t_id, l_id, v_id]
        if fase:
            query += " AND fase LIKE %s"
            params.append(f"%{fase}%")
        # Prioritise unplayed matches — if both exist, update the pending one
        query += " ORDER BY CASE WHEN estado = 'programado' THEN 0 ELSE 1 END, id DESC LIMIT 1"

        cur.execute(query, params)
        partido = cur.fetchone()
        cur.close()

        if not partido:
            conn.close()
            fase_str = f" en la fase '{fase}'" if fase else ""
            return (
                f"⚠️  No encontré el partido {nombre_local} vs {nombre_visitante}"
                f"{fase_str} en '{nombre_torneo}'.\n"
                f"Comprueba que los nombres de los equipos y la fase sean correctos.\n"
                f"Puedes ver los partidos programados con: 'Ver partidos de {nombre_torneo}'"
            )

        partido_id = partido[0]

        # ── VALIDATION 2: Resolve all player names before touching anything ─
        goleadores   = goleadores  or []
        asistentes   = asistentes  or []
        no_encontrados = []

        goleadores_ids  = []   # list of (nombre, j_id, eq_id)
        asistentes_ids  = []

        for nombre in goleadores:
            j_id = _obtener_id_jugador(nombre)
            if not j_id:
                no_encontrados.append(nombre)
                continue
            cur = conn.cursor(buffered=True)
            cur.execute(
                "SELECT equipo_id FROM equipo_jugadores WHERE jugador_id = %s LIMIT 1",
                (j_id,)
            )
            eq = cur.fetchone()
            cur.close()
            goleadores_ids.append((nombre, j_id, eq[0] if eq else None))

        for nombre in asistentes:
            j_id = _obtener_id_jugador(nombre)
            if not j_id:
                no_encontrados.append(nombre)
                continue
            cur = conn.cursor(buffered=True)
            cur.execute(
                "SELECT equipo_id FROM equipo_jugadores WHERE jugador_id = %s LIMIT 1",
                (j_id,)
            )
            eq = cur.fetchone()
            cur.close()
            asistentes_ids.append((nombre, j_id, eq[0] if eq else None))

        if no_encontrados:
            conn.close()
            return (
                f"⚠️  No se actualizó el partido porque no encontré "
                f"{'este jugador' if len(no_encontrados) == 1 else 'estos jugadores'} "
                f"en la base de datos:\n"
                + "\n".join(f"   • {n}" for n in no_encontrados)
                + "\n\nComprueba los nombres e inténtalo de nuevo."
            )

        # ── ALL VALIDATIONS PASSED — now update everything ─────────────────

        # Update match result
        cur = conn.cursor(buffered=True)
        cur.execute("""
            UPDATE partidos
            SET goles_local = %s, goles_visitante = %s, estado = 'jugado'
            WHERE id = %s
        """, (goles_local, goles_visitante, partido_id))
        conn.commit()
        cur.close()

        # Update team stats
        _asegurar_estadisticas_equipo(conn, t_id, l_id)
        _asegurar_estadisticas_equipo(conn, t_id, v_id)

        if goles_local > goles_visitante:
            pts_l, pts_v = 3, 0
            win_l, win_v = "victorias", "derrotas"
        elif goles_local < goles_visitante:
            pts_l, pts_v = 0, 3
            win_l, win_v = "derrotas", "victorias"
        else:
            pts_l, pts_v = 1, 1
            win_l, win_v = "empates", "empates"

        cur = conn.cursor(buffered=True)
        cur.execute(f"UPDATE estadisticas_equipo_torneo SET {win_l} = {win_l} + 1 WHERE torneo_id=%s AND equipo_id=%s", (t_id, l_id))
        cur.execute(f"UPDATE estadisticas_equipo_torneo SET {win_v} = {win_v} + 1 WHERE torneo_id=%s AND equipo_id=%s", (t_id, v_id))
        cur.execute("""
            UPDATE estadisticas_equipo_torneo
            SET partidos_jugados = partidos_jugados + 1,
                goles_favor  = goles_favor  + %s,
                goles_contra = goles_contra + %s,
                puntos       = puntos       + %s
            WHERE torneo_id = %s AND equipo_id = %s
        """, (goles_local, goles_visitante, pts_l, t_id, l_id))
        cur.execute("""
            UPDATE estadisticas_equipo_torneo
            SET partidos_jugados = partidos_jugados + 1,
                goles_favor  = goles_favor  + %s,
                goles_contra = goles_contra + %s,
                puntos       = puntos       + %s
            WHERE torneo_id = %s AND equipo_id = %s
        """, (goles_visitante, goles_local, pts_v, t_id, v_id))
        conn.commit()
        cur.close()

        # Increment partidos_jugados for ALL players of both teams
        for equipo_id in [l_id, v_id]:
            cur = conn.cursor(buffered=True)
            cur.execute(
                "SELECT jugador_id FROM equipo_jugadores WHERE equipo_id = %s",
                (equipo_id,)
            )
            jugadores_equipo = cur.fetchall()
            cur.close()

            for (jugador_id,) in jugadores_equipo:
                cur = conn.cursor(buffered=True)
                cur.execute("""
                    INSERT INTO estadisticas_jugador_torneo
                        (torneo_id, jugador_id, equipo_id, partidos_jugados)
                    VALUES (%s, %s, %s, 1)
                    ON DUPLICATE KEY UPDATE
                        partidos_jugados = partidos_jugados + 1
                """, (t_id, jugador_id, equipo_id))
                cur.close()
            conn.commit()

        # Update goals for each goalscorer
        jugadores_actualizados = []
        for nombre, j_id, eq_id in goleadores_ids:
            cur = conn.cursor(buffered=True)
            cur.execute("""
                INSERT INTO estadisticas_jugador_torneo
                    (torneo_id, jugador_id, equipo_id, goles)
                VALUES (%s, %s, %s, 1)
                ON DUPLICATE KEY UPDATE
                    goles = goles + 1
            """, (t_id, j_id, eq_id))
            conn.commit()
            cur.close()
            jugadores_actualizados.append(f"⚽ {nombre}")

        # Update assists for each assister
        for nombre, j_id, eq_id in asistentes_ids:
            cur = conn.cursor(buffered=True)
            cur.execute("""
                INSERT INTO estadisticas_jugador_torneo
                    (torneo_id, jugador_id, equipo_id, asistencias)
                VALUES (%s, %s, %s, 1)
                ON DUPLICATE KEY UPDATE
                    asistencias = asistencias + 1
            """, (t_id, j_id, eq_id))
            conn.commit()
            cur.close()
            jugadores_actualizados.append(f"🅰️  {nombre}")

        conn.close()

        # Build response
        resultado_str = ("Victoria " + nombre_local     if goles_local > goles_visitante else
                         "Victoria " + nombre_visitante if goles_visitante > goles_local  else
                         "Empate")

        lineas = [
            f"✅ Partido actualizado: {nombre_local} {goles_local} - {goles_visitante} {nombre_visitante}",
            f"   {resultado_str}",
        ]
        if jugadores_actualizados:
            lineas.append("📊 Stats de jugadores actualizadas:")
            for j in jugadores_actualizados:
                lineas.append(f"   {j}")
        return "\n".join(lineas)

    except Exception as e:
        return f"Error: {e}"


def ver_clasificacion(nombre_torneo: str, nombre_grupo: str = None) -> str:
    try:
        t_id = _obtener_id_torneo(nombre_torneo)
        if not t_id:
            return f"No encontré el torneo '{nombre_torneo}'."
        conn = _db()
        cur = conn.cursor()

        if nombre_grupo:
            g_id = _obtener_id_grupo(nombre_torneo, nombre_grupo)
            if not g_id:
                return f"No encontré el grupo '{nombre_grupo}'."
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

        filas = cur.fetchall()
        cur.close()
        conn.close()
        if not filas:
            return "No hay estadísticas registradas aún."

        sep = "─" * 72
        cabecera = f"{'Equipo':<20} {'PJ':>3} {'V':>3} {'E':>3} {'D':>3} {'GF':>4} {'GC':>4} {'DG':>4} {'Pts':>4}"
        lineas = [titulo, sep, cabecera, sep]
        for pos, f in enumerate(filas, 1):
            lineas.append(f"{pos}. {f[0]:<18} {f[1]:>3} {f[2]:>3} {f[3]:>3} {f[4]:>3} {f[5]:>4} {f[6]:>4} {f[7]:>4} {f[8]:>4}")
        lineas.append(sep)
        return "\n".join(lineas)
    except Exception as e:
        return f"Error: {e}"


def ver_clasificacion_grupos(nombre_torneo: str) -> str:    
    """Shows standings for every group in the tournament, one table per group."""
    try:
        t_id = _obtener_id_torneo(nombre_torneo)
        if not t_id:
            return f"No encontré el torneo '{nombre_torneo}'."

        conn = _db()
        cur = conn.cursor(buffered=True)
        cur.execute("""
            SELECT id, nombre FROM grupos
            WHERE torneo_id = %s ORDER BY nombre
        """, (t_id,))
        grupos = cur.fetchall()
        cur.close()
        conn.close()

        if not grupos:
            return f"No hay grupos creados en '{nombre_torneo}'. Realiza primero el sorteo de grupos."

        lineas = [f"📊 Clasificación por grupos — {nombre_torneo}", "═" * 72]

        for g_id, g_nombre in grupos:
            resultado = ver_clasificacion(nombre_torneo, g_nombre)
            lineas.append(f"\n{resultado}")

        return "\n".join(lineas)

    except Exception as e:
        return f"Error: {e}"


def ver_partidos(nombre_torneo: str, estado: str = None, fase: str = None) -> str:
    try:
        t_id = _obtener_id_torneo(nombre_torneo)
        if not t_id:
            return f"No encontré el torneo '{nombre_torneo}'."
        conn = _db()
        cur = conn.cursor()

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
            query += " AND p.estado = %s"
            params.append(estado)
        if fase:
            query += " AND p.fase LIKE %s"
            params.append(f"%{fase}%")
        query += " ORDER BY p.fecha ASC, p.id ASC"

        cur.execute(query, params)
        filas = cur.fetchall()
        cur.close()
        conn.close()
        if not filas:
            return "No hay partidos registrados con ese filtro."

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


def actualizar_stats_jugador(nombre_jugador: str, nombre_torneo: str,
                              goles: int = 0, asistencias: int = 0,
                              tarjetas_amarillas: int = 0, tarjetas_rojas: int = 0,
                              partidos_jugados: int = 0) -> str:
    try:
        j_id = _obtener_id_jugador(nombre_jugador)
        t_id = _obtener_id_torneo(nombre_torneo)
        if not j_id:
            return f"No encontré al jugador '{nombre_jugador}'."
        if not t_id:
            return f"No encontré el torneo '{nombre_torneo}'."

        conn = _db()
        cur = conn.cursor()
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
        conn.commit()
        cur.close()
        conn.close()

        cambios = []
        if goles:
            cambios.append(f"{goles} gol(es)")
        if asistencias:
            cambios.append(f"{asistencias} asistencia(s)")
        if tarjetas_amarillas:
            cambios.append(f"{tarjetas_amarillas} tarjeta(s) amarilla(s)")
        if tarjetas_rojas:
            cambios.append(f"{tarjetas_rojas} tarjeta(s) roja(s)")
        if partidos_jugados:
            cambios.append(f"{partidos_jugados} partido(s) jugado(s)")
        return f"Stats de '{nombre_jugador}' actualizadas en '{nombre_torneo}': {', '.join(cambios)}."
    except Exception as e:
        return f"Error: {e}"


def ver_stats_jugadores(nombre_torneo: str, top: int = 10) -> str:
    try:
        t_id = _obtener_id_torneo(nombre_torneo)
        if not t_id:
            return f"No encontré el torneo '{nombre_torneo}'."
        conn = _db()
        cur = conn.cursor()
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
        filas = cur.fetchall()
        cur.close()
        conn.close()
        if not filas:
            return "No hay estadísticas de jugadores registradas."

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


def _calcular_formato(num_equipos: int) -> dict:
    formatos = {
        4: (1, 4, 2),
        6: (2, 3, 2),
        8: (2, 4, 2),
        12: (3, 4, 2),
        16: (4, 4, 2),
        24: (6, 4, 2),
        32: (8, 4, 2),
        48: (12, 4, 2),
    }
    if num_equipos in formatos:
        ng, epg, cpg = formatos[num_equipos]
        return {"num_grupos": ng, "equipos_por_grupo": epg, "clasificados": cpg, "valido": True}
    for epg in [4, 3]:
        if num_equipos % epg == 0:
            ng = num_equipos // epg
            cpg = 2 if ng >= 2 else num_equipos // 2
            return {"num_grupos": ng, "equipos_por_grupo": epg, "clasificados": cpg, "valido": True}
    return {"valido": False, "mensaje": f"No se puede hacer un sorteo equilibrado con {num_equipos} equipos. Prueba con 4, 6, 8, 12, 16, 24, 32 o 48 equipos."}


def _nombre_ronda(num_equipos: int) -> str:
    nombres = {
        2: "Final",
        4: "Semifinales",
        8: "Cuartos de final",
        16: "Octavos de final",
        32: "Dieciseisavos de final",
    }
    return nombres.get(num_equipos, f"Ronda de {num_equipos}")


def realizar_sorteo_grupos(nombre_torneo: str, semilla: int = None) -> str:
    try:
        t_id = _obtener_id_torneo(nombre_torneo)
        if not t_id:
            return f"No encontré el torneo '{nombre_torneo}'."

        conn = _db()
        cur = conn.cursor()
        cur.execute("""
            SELECT e.id, e.nombre FROM equipos e
            JOIN torneo_equipos te ON te.equipo_id = e.id
            WHERE te.torneo_id = %s
        """, (t_id,))
        equipos = cur.fetchall()

        if not equipos:
            cur.close()
            conn.close()
            return f"No hay equipos inscritos en '{nombre_torneo}'. Inscribe equipos primero."

        num_equipos = len(equipos)
        formato = _calcular_formato(num_equipos)

        if not formato["valido"]:
            cur.close()
            conn.close()
            return formato["mensaje"]

        if semilla:
            random.seed(semilla)
        equipos_mezclados = list(equipos)
        random.shuffle(equipos_mezclados)

        cur.execute("DELETE FROM grupos WHERE torneo_id = %s", (t_id,))
        conn.commit()

        ng = formato["num_grupos"]
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

            equipos_grupo = equipos_mezclados[i * epg:(i + 1) * epg]
            lineas.append(f"\n  {nombre_grupo}:")
            for e_id, e_nombre in equipos_grupo:
                cur.execute("INSERT IGNORE INTO grupo_equipos (grupo_id, equipo_id) VALUES (%s, %s)", (g_id, e_id))
                _asegurar_estadisticas_equipo(conn, t_id, e_id)
                lineas.append(f"    • {e_nombre}")

            for j in range(len(equipos_grupo)):
                for k in range(j + 1, len(equipos_grupo)):
                    local_id = equipos_grupo[j][0]
                    visita_id = equipos_grupo[k][0]
                    cur.execute("""
                        INSERT INTO partidos
                            (torneo_id, equipo_local_id, equipo_visitante_id, fase, grupo_id, estado)
                        VALUES (%s, %s, %s, 'Fase de grupos', %s, 'programado')
                    """, (t_id, local_id, visita_id, g_id))

        conn.commit()
        cur.close()
        conn.close()
        lineas.append("\n" + "─" * 40)
        lineas.append("✅ Grupos creados y partidos de fase de grupos generados automáticamente.")
        lineas.append(f"   Usa 'ver partidos {nombre_torneo}' para ver el calendario.")
        return "\n".join(lineas)

    except Exception as e:
        return f"Error al realizar el sorteo: {e}"


def ver_grupos_y_partidos(nombre_torneo: str) -> str:
    try:
        t_id = _obtener_id_torneo(nombre_torneo)
        if not t_id:
            return f"No encontré el torneo '{nombre_torneo}'."

        conn = _db()
        cur = conn.cursor()

        # Get all groups for this tournament
        cur.execute("""
            SELECT id, nombre FROM grupos
            WHERE torneo_id = %s ORDER BY nombre
        """, (t_id,))
        grupos = cur.fetchall()

        if not grupos:
            cur.close(); conn.close()
            return f"No hay grupos creados en '{nombre_torneo}'. Realiza primero el sorteo de grupos."

        lineas = [f"📋 Grupos y partidos — {nombre_torneo}", "═" * 50]

        for g_id, g_nombre in grupos:
            lineas.append(f"\n  {g_nombre}")
            lineas.append("  " + "─" * 40)

            # Teams in this group
            cur.execute("""
                SELECT e.nombre
                FROM equipos e
                JOIN grupo_equipos ge ON ge.equipo_id = e.id
                WHERE ge.grupo_id = %s
                ORDER BY e.nombre
            """, (g_id,))
            equipos = cur.fetchall()
            lineas.append("  🏳️  Equipos:")
            for (eq_nombre,) in equipos:
                lineas.append(f"       • {eq_nombre}")

            # Matches in this group
            cur.execute("""
                SELECT el.nombre, p.goles_local, p.goles_visitante,
                       ev.nombre, p.fecha, p.estado
                FROM partidos p
                JOIN equipos el ON p.equipo_local_id = el.id
                JOIN equipos ev ON p.equipo_visitante_id = ev.id
                WHERE p.grupo_id = %s AND p.torneo_id = %s
                ORDER BY p.fecha ASC, p.id ASC
            """, (g_id, t_id))
            partidos = cur.fetchall()

            lineas.append("  ⚽ Partidos:")
            if not partidos:
                lineas.append("       (Sin partidos programados)")
            else:
                for local, gl, gv, visitante, fecha, estado in partidos:
                    fecha_str = f" [{fecha}]" if fecha else ""
                    if estado == "jugado":
                        lineas.append(f"       {local} {gl} - {gv} {visitante}{fecha_str} ✅")
                    else:
                        lineas.append(f"       {local} vs {visitante}{fecha_str} 🕐")

        cur.close(); conn.close()
        lineas.append("\n" + "═" * 50)
        return "\n".join(lineas)

    except Exception as e:
        return f"Error: {e}"


def realizar_sorteo_eliminatorias(nombre_torneo: str, clasificados_por_grupo: int = None) -> str:
    try:
        t_id = _obtener_id_torneo(nombre_torneo)
        if not t_id:
            return f"No encontré el torneo '{nombre_torneo}'."

        conn = _db()
        cur = conn.cursor()
        cur.execute("SELECT id, nombre FROM grupos WHERE torneo_id = %s ORDER BY nombre", (t_id,))
        grupos = cur.fetchall()

        if not grupos:
            cur.close()
            conn.close()
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
                    "posicion": pos, "equipo_id": e_id, "nombre": e_nombre,
                })

        total = len(clasificados)
        if total < 2:
            cur.close()
            conn.close()
            return "No hay suficientes equipos clasificados. Registra los resultados de la fase de grupos primero."

        if total & (total - 1) != 0:
            cur.close()
            conn.close()
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

        conn.commit()
        cur.close()
        conn.close()
        lineas.append("─" * 50)
        lineas.append("✅ Cuadro de eliminatorias generado y partidos programados.")
        return "\n".join(lineas)

    except Exception as e:
        return f"Error al realizar el sorteo de eliminatorias: {e}"


def avanzar_eliminatorias(nombre_torneo: str) -> str:
    """
    Checks the current KO round, extracts winners, and generates the next round.
    Call this after all matches in the current round are played.
    """
    try:
        t_id = _obtener_id_torneo(nombre_torneo)
        if not t_id:
            return f"No encontré el torneo '{nombre_torneo}'."

        conn = _db()

        # ── Get the most recent round ──────────────────────────────────────
        cur = conn.cursor(buffered=True)
        cur.execute("""
            SELECT ronda FROM eliminatorias
            WHERE torneo_id = %s
            ORDER BY partido_id DESC LIMIT 1
        """, (t_id,))
        row = cur.fetchone()
        cur.close()

        if not row:
            conn.close()
            return "No hay cuadro de eliminatorias generado aún."

        ronda_actual = row[0]

        # ── Get all matches of the current round ordered by bracket position
        cur = conn.cursor(buffered=True)
        cur.execute("""
            SELECT el.orden, el.equipo1_id, el.equipo2_id, el.partido_id,
                   p.goles_local, p.goles_visitante, p.estado
            FROM eliminatorias el
            LEFT JOIN partidos p ON el.partido_id = p.id
            WHERE el.torneo_id = %s AND el.ronda = %s
            ORDER BY el.orden ASC
        """, (t_id, ronda_actual))
        partidos_ronda = cur.fetchall()
        cur.close()

        if not partidos_ronda:
            conn.close()
            return f"No encontré partidos para la ronda '{ronda_actual}'."

        # ── Check all matches are played ───────────────────────────────────
        pendientes = [p for p in partidos_ronda if p[6] != "jugado"]
        if pendientes:
            conn.close()
            return (
                f"⚠️  Aún hay {len(pendientes)} partido(s) pendiente(s) en {ronda_actual}.\n"
                "Registra todos los resultados antes de generar la siguiente ronda."
            )

        # ── Extract winners — no draws allowed in KO ───────────────────────
        ganadores = []
        for orden, eq1_id, eq2_id, partido_id, gl, gv, estado in partidos_ronda:
            if gl is None or gv is None:
                conn.close()
                return f"⚠️  El partido {orden + 1} no tiene resultado registrado."
            if gl == gv:
                # Draw — cannot advance automatically
                cur = conn.cursor(buffered=True)
                cur.execute("SELECT nombre FROM equipos WHERE id = %s", (eq1_id,))
                n1 = cur.fetchone()[0]
                cur.close()
                cur = conn.cursor(buffered=True)
                cur.execute("SELECT nombre FROM equipos WHERE id = %s", (eq2_id,))
                n2 = cur.fetchone()[0]
                cur.close()
                conn.close()
                return (
                    f"⚠️  El partido {n1} vs {n2} terminó en empate ({gl}-{gv}).\n"
                    "En eliminatorias no puede haber empate. Especifica el ganador "
                    "por penaltis con: 'El ganador por penaltis fue [equipo]'"
                )
            ganador_id = eq1_id if gl > gv else eq2_id
            ganadores.append(ganador_id)

        # ── If only 1 match was the final, declare champion ────────────────
        if len(ganadores) == 1:
            cur = conn.cursor(buffered=True)
            cur.execute("SELECT nombre FROM equipos WHERE id = %s", (ganadores[0],))
            campeon = cur.fetchone()[0]
            cur.close()
            conn.close()
            return (
                f"🏆 ¡{campeon} es el CAMPEÓN de '{nombre_torneo}'!\n"
                "El torneo ha finalizado."
            )

        # ── Build next round ───────────────────────────────────────────────
        nueva_ronda = _nombre_ronda(len(ganadores))
        lineas = [
            f"✅ {ronda_actual} completada.",
            f"🎯 Generando {nueva_ronda} — {len(ganadores)} equipos",
            "─" * 50
        ]

        # Pair winners: 1st vs 2nd, 3rd vs 4th, etc.
        for i in range(0, len(ganadores), 2):
            eq1_id = ganadores[i]
            eq2_id = ganadores[i + 1]

            cur = conn.cursor(buffered=True)
            cur.execute("SELECT nombre FROM equipos WHERE id = %s", (eq1_id,))
            n1 = cur.fetchone()[0]
            cur.close()

            cur = conn.cursor(buffered=True)
            cur.execute("SELECT nombre FROM equipos WHERE id = %s", (eq2_id,))
            n2 = cur.fetchone()[0]
            cur.close()

            # Create match
            cur = conn.cursor(buffered=True)
            cur.execute("""
                INSERT INTO partidos
                    (torneo_id, equipo_local_id, equipo_visitante_id, fase, estado)
                VALUES (%s, %s, %s, %s, 'programado')
            """, (t_id, eq1_id, eq2_id, nueva_ronda))
            conn.commit()
            partido_id = cur.lastrowid
            cur.close()

            # Register in bracket
            orden = i // 2
            cur = conn.cursor(buffered=True)
            cur.execute("""
                INSERT INTO eliminatorias
                    (torneo_id, ronda, orden, equipo1_id, equipo2_id, partido_id)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (t_id, nueva_ronda, orden, eq1_id, eq2_id, partido_id))
            conn.commit()
            cur.close()

            lineas.append(f"  Partido {orden + 1}: {n1} vs {n2}")

        conn.close()
        lineas.append("─" * 50)
        lineas.append(f"✅ {nueva_ronda} generada. Registra los resultados para continuar.")
        return "\n".join(lineas)

    except Exception as e:
        return f"Error: {e}"


def ver_cuadro_eliminatorias(nombre_torneo: str) -> str:
    try:
        t_id = _obtener_id_torneo(nombre_torneo)
        if not t_id:
            return f"No encontré el torneo '{nombre_torneo}'."
        conn = _db()
        cur = conn.cursor()
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
        filas = cur.fetchall()
        cur.close()
        conn.close()
        if not filas:
            return "No hay cuadro de eliminatorias generado aún."

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


def ver_jugadores_equipo(nombre_equipo: str, nombre_torneo: str = None) -> str:
    """Shows all players of a team with their stats, optionally filtered by tournament."""
    try:
        e_id = _obtener_id_equipo(nombre_equipo)
        if not e_id:
            return f"No encontré el equipo '{nombre_equipo}'."

        conn = _db()
        cur = conn.cursor(buffered=True)

        # Get all players of the team
        cur.execute("""
            SELECT j.id, j.nombre, j.edad, j.posicion
            FROM jugadores j
            JOIN equipo_jugadores ej ON ej.jugador_id = j.id
            WHERE ej.equipo_id = %s
            ORDER BY j.nombre
        """, (e_id,))
        jugadores = cur.fetchall()
        cur.close()

        if not jugadores:
            conn.close()
            return f"El equipo '{nombre_equipo}' no tiene jugadores registrados."

        # If tournament specified, fetch stats per player
        t_id = _obtener_id_torneo(nombre_torneo) if nombre_torneo else None

        sep = "─" * 72
        if t_id:
            cabecera = f"{'Jugador':<22} {'Edad':>4} {'Pos':<12} {'PJ':>3} {'G':>3} {'A':>3} {'TA':>3} {'TR':>3}"
            titulo   = f"👥 Plantilla — {nombre_equipo} ({nombre_torneo})"
        else:
            cabecera = f"{'Jugador':<22} {'Edad':>4} {'Posición':<12}"
            titulo   = f"👥 Plantilla — {nombre_equipo}"

        lineas = [titulo, sep, cabecera, sep]

        for j_id, j_nombre, j_edad, j_pos in jugadores:
            edad_str = str(j_edad) if j_edad else "—"
            pos_str  = j_pos or "—"

            if t_id:
                cur = conn.cursor(buffered=True)
                cur.execute("""
                    SELECT partidos_jugados, goles, asistencias,
                           tarjetas_amarillas, tarjetas_rojas
                    FROM estadisticas_jugador_torneo
                    WHERE torneo_id = %s AND jugador_id = %s
                """, (t_id, j_id))
                stats = cur.fetchone()
                cur.close()
                if stats:
                    pj, g, a, ta, tr = stats
                else:
                    pj, g, a, ta, tr = 0, 0, 0, 0, 0
                lineas.append(f"  {j_nombre:<22} {edad_str:>4} {pos_str:<12} {pj:>3} {g:>3} {a:>3} {ta:>3} {tr:>3}")
            else:
                lineas.append(f"  {j_nombre:<22} {edad_str:>4} {pos_str:<12}")

        lineas.append(sep)
        conn.close()
        return "\n".join(lineas)

    except Exception as e:
        return f"Error: {e}"


def ver_ranking_jugadores(nombre_torneo: str, top: int = 10) -> str:
    """Shows top scorers and top assisters for a tournament."""
    try:
        t_id = _obtener_id_torneo(nombre_torneo)
        if not t_id:
            return f"No encontré el torneo '{nombre_torneo}'."

        conn = _db()

        # Top scorers
        cur = conn.cursor(buffered=True)
        cur.execute("""
            SELECT j.nombre, e.nombre, ej.goles, ej.asistencias,
                   ej.partidos_jugados, ej.tarjetas_amarillas, ej.tarjetas_rojas
            FROM estadisticas_jugador_torneo ej
            JOIN jugadores j ON ej.jugador_id = j.id
            LEFT JOIN equipos e ON ej.equipo_id = e.id
            WHERE ej.torneo_id = %s AND ej.goles > 0
            ORDER BY ej.goles DESC, ej.asistencias DESC
            LIMIT %s
        """, (t_id, top))
        goleadores = cur.fetchall()
        cur.close()

        # Top assisters
        cur = conn.cursor(buffered=True)
        cur.execute("""
            SELECT j.nombre, e.nombre, ej.asistencias, ej.goles,
                   ej.partidos_jugados
            FROM estadisticas_jugador_torneo ej
            JOIN jugadores j ON ej.jugador_id = j.id
            LEFT JOIN equipos e ON ej.equipo_id = e.id
            WHERE ej.torneo_id = %s AND ej.asistencias > 0
            ORDER BY ej.asistencias DESC, ej.goles DESC
            LIMIT %s
        """, (t_id, top))
        asistentes = cur.fetchall()
        cur.close()
        conn.close()

        sep = "─" * 60
        lineas = [f"🏅 Rankings de jugadores — {nombre_torneo}", "═" * 60]

        # Scorers table
        lineas.append(f"\n  ⚽ Top {top} Goleadores")
        lineas.append(sep)
        lineas.append(f"  {'#':<3} {'Jugador':<22} {'Equipo':<15} {'G':>3} {'A':>3} {'PJ':>3}")
        lineas.append(sep)
        if goleadores:
            for pos, (nombre, equipo, g, a, pj, ta, tr) in enumerate(goleadores, 1):
                equipo_str = equipo or "—"
                lineas.append(f"  {pos:<3} {nombre:<22} {equipo_str:<15} {g:>3} {a:>3} {pj:>3}")
        else:
            lineas.append("  Sin datos de goles registrados aún.")
        lineas.append(sep)

        # Assisters table
        lineas.append(f"\n  🅰️  Top {top} Asistentes")
        lineas.append(sep)
        lineas.append(f"  {'#':<3} {'Jugador':<22} {'Equipo':<15} {'A':>3} {'G':>3} {'PJ':>3}")
        lineas.append(sep)
        if asistentes:
            for pos, (nombre, equipo, a, g, pj) in enumerate(asistentes, 1):
                equipo_str = equipo or "—"
                lineas.append(f"  {pos:<3} {nombre:<22} {equipo_str:<15} {a:>3} {g:>3} {pj:>3}")
        else:
            lineas.append("  Sin datos de asistencias registrados aún.")
        lineas.append(sep)

        return "\n".join(lineas)

    except Exception as e:
        return f"Error: {e}"


def ver_ranking_equipos(nombre_torneo: str, top: int = 10) -> str:
    """Shows team rankings: most goals scored and fewest conceded."""
    try:
        t_id = _obtener_id_torneo(nombre_torneo)
        if not t_id:
            return f"No encontré el torneo '{nombre_torneo}'."

        conn = _db()

        # Most goals scored
        cur = conn.cursor(buffered=True)
        cur.execute("""
            SELECT e.nombre, et.goles_favor, et.goles_contra,
                   (et.goles_favor - et.goles_contra) AS dg,
                   et.partidos_jugados, et.puntos
            FROM estadisticas_equipo_torneo et
            JOIN equipos e ON et.equipo_id = e.id
            WHERE et.torneo_id = %s AND et.partidos_jugados > 0
            ORDER BY et.goles_favor DESC, dg DESC
            LIMIT %s
        """, (t_id, top))
        mas_goles = cur.fetchall()
        cur.close()

        # Fewest goals conceded
        cur = conn.cursor(buffered=True)
        cur.execute("""
            SELECT e.nombre, et.goles_contra, et.goles_favor,
                   (et.goles_favor - et.goles_contra) AS dg,
                   et.partidos_jugados, et.puntos
            FROM estadisticas_equipo_torneo et
            JOIN equipos e ON et.equipo_id = e.id
            WHERE et.torneo_id = %s AND et.partidos_jugados > 0
            ORDER BY et.goles_contra ASC, dg DESC
            LIMIT %s
        """, (t_id, top))
        menos_goles = cur.fetchall()
        cur.close()
        conn.close()

        sep = "─" * 62
        lineas = [f"🏆 Rankings de equipos — {nombre_torneo}", "═" * 62]

        # Most goals scored
        lineas.append(f"\n  ⚽ Top {top} — Más goles marcados")
        lineas.append(sep)
        lineas.append(f"  {'#':<3} {'Equipo':<22} {'GF':>4} {'GC':>4} {'DG':>4} {'PJ':>3} {'Pts':>4}")
        lineas.append(sep)
        if mas_goles:
            for pos, (nombre, gf, gc, dg, pj, pts) in enumerate(mas_goles, 1):
                lineas.append(f"  {pos:<3} {nombre:<22} {gf:>4} {gc:>4} {dg:>4} {pj:>3} {pts:>4}")
        else:
            lineas.append("  Sin datos registrados aún.")
        lineas.append(sep)

        # Fewest goals conceded
        lineas.append(f"\n  🛡️  Top {top} — Menos goles encajados")
        lineas.append(sep)
        lineas.append(f"  {'#':<3} {'Equipo':<22} {'GC':>4} {'GF':>4} {'DG':>4} {'PJ':>3} {'Pts':>4}")
        lineas.append(sep)
        if menos_goles:
            for pos, (nombre, gc, gf, dg, pj, pts) in enumerate(menos_goles, 1):
                lineas.append(f"  {pos:<3} {nombre:<22} {gc:>4} {gf:>4} {dg:>4} {pj:>3} {pts:>4}")
        else:
            lineas.append("  Sin datos registrados aún.")
        lineas.append(sep)

        return "\n".join(lineas)

    except Exception as e:
        return f"Error: {e}"
    

def registrar_ganador_penaltis(nombre_torneo: str, nombre_ganador: str) -> str:
    try:
        t_id = _obtener_id_torneo(nombre_torneo)
        e_id = _obtener_id_equipo(nombre_ganador)
        if not t_id: return f"No encontré el torneo '{nombre_torneo}'."
        if not e_id: return f"No encontré el equipo '{nombre_ganador}'."

        conn = _db()
        cur = conn.cursor(buffered=True)

        # Find the most recent KO drawn match
        cur.execute("""
            SELECT p.id, p.equipo_local_id, p.equipo_visitante_id,
                   p.goles_local, p.goles_visitante
            FROM partidos p
            JOIN eliminatorias el ON el.partido_id = p.id
            WHERE p.torneo_id = %s
              AND p.goles_local = p.goles_visitante
              AND p.estado = 'jugado'
            ORDER BY p.id DESC LIMIT 1
        """, (t_id,))
        partido = cur.fetchone()
        cur.close()

        if not partido:
            conn.close()
            return "No encontré ningún partido empatado reciente en eliminatorias."

        p_id, local_id, visita_id, gl, gv = partido

        if e_id == local_id:
            nuevo_gl, nuevo_gv = gl + 1, gv
        else:
            nuevo_gl, nuevo_gv = gl, gv + 1

        cur = conn.cursor(buffered=True)
        cur.execute("""
            UPDATE partidos
            SET goles_local = %s, goles_visitante = %s
            WHERE id = %s
        """, (nuevo_gl, nuevo_gv, p_id))
        conn.commit()
        cur.close()
        conn.close()

        return (
            f"✅ '{nombre_ganador}' avanza por penaltis.\n"
            f"Ahora puedes generar la siguiente ronda con: "
            f"'Genera la siguiente ronda de {nombre_torneo}'"
        )

    except Exception as e:
        return f"Error: {e}"