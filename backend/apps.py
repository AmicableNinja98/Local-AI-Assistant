import glob
import os
import shutil

from .db import _db


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
        conn = _db()
        cur = conn.cursor()
        cur.execute("SELECT ruta FROM aplicaciones WHERE LOWER(nombre) = %s", (nombre.lower(),))
        res = cur.fetchone()
        cur.close()
        conn.close()
        return res[0] if res else None
    except Exception:
        return None


def guardar_ruta_app(nombre: str, ruta: str) -> str:
    try:
        conn = _db()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO aplicaciones (nombre, ruta) VALUES (%s, %s) ON DUPLICATE KEY UPDATE ruta = VALUES(ruta)",
            (nombre.lower(), ruta),
        )
        conn.commit()
        cur.close()
        conn.close()
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
