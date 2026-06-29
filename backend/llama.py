import subprocess
import time

try:
    import psutil
except ImportError:  # pragma: no cover - optional dependency
    psutil = None

from .config import GPU_LAYERS, RUTA_LLAMA, RUTA_MODELO


def iniciar_servidor():
    print("🔧 Iniciando servidor llama.cpp...")
    try:
        proceso = subprocess.Popen(
            [RUTA_LLAMA, "-m", RUTA_MODELO, "-c", "8192",
             "-ngl", str(GPU_LAYERS), "--port", "8080"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(f"No se encontró llama-server.exe en:\n{RUTA_LLAMA}\nVerifica la ruta en el .env") from exc
    print("⏳ Cargando modelo", end="", flush=True)
    for _ in range(10):
        time.sleep(1)
        print(".", end="", flush=True)
    print(" ¡Listo!\n")
    return proceso


def cerrar_servidor(proceso):
    if proceso and proceso.poll() is None and psutil is not None:
        try:
            padre = psutil.Process(proceso.pid)
            for hijo in padre.children(recursive=True):
                hijo.kill()
            padre.kill()
        except Exception:
            pass
