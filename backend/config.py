import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency
    def load_dotenv(*_args, **_kwargs):
        return False

try:
    from openai import OpenAI as _OpenAI
except ImportError:  # pragma: no cover - optional dependency
    _OpenAI = None


load_dotenv(Path(__file__).resolve().parent.parent / ".env")

RUTA_LLAMA = os.getenv("RUTA_LLAMA")
RUTA_MODELO = os.getenv("RUTA_MODELO")
GPU_LAYERS = int(os.getenv("GPU_LAYERS", 24))

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "asistente_ia"),
}

if _OpenAI is None:
    client = None
else:
    client = _OpenAI(base_url="http://localhost:8080/v1", api_key="sk-no-key-required")
