try:
    import mysql.connector
except ImportError:  # pragma: no cover - optional dependency
    mysql = None
else:
    mysql = mysql.connector

from .config import DB_CONFIG


def _db():
    if mysql is None:
        raise RuntimeError("mysql-connector-python is not installed")
    return mysql.connect(**DB_CONFIG,consume_results = True)


def obtener_nombre_usuario():
    try:
        conn = _db()
        cur = conn.cursor()
        cur.execute("SELECT valor FROM usuario WHERE clave = 'nombre_usuario'")
        res = cur.fetchone()
        cur.close()
        conn.close()
        return res[0] if res else "Usuario"
    except Exception:
        return "Usuario"


def obtener_nombre_asistente():
    try:
        conn = _db()
        cur = conn.cursor()
        cur.execute("SELECT valor FROM usuario WHERE clave = 'nombre_asistente'")
        res = cur.fetchone()
        cur.close()
        conn.close()
        return res[0] if res else "Asistente"
    except Exception:
        return "Asistente"
