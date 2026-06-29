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
    cur = conn.cursor()
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
