import os
import threading
import socket
import urllib.parse
from pathlib import Path

from flask import Flask, request, send_file
from flask_cors import CORS
from waitress import serve

# ── Constants ──────────────────────────────────────────────────────────────────

PORT          = 8765
MAX_BODY      = 100 * 1024 * 1024 * 1024   # 100 GB
CHANNEL_TIMEOUT = 7200                       # 2 hours
CHUNK_SIZE    = 4 * 1024 * 1024             # 4 MB read chunks

# ── State ──────────────────────────────────────────────────────────────────────

_server_thread: threading.Thread | None = None
_running = False
_share_dir = str(Path.home() / "Compartido")
_upload_dir = str(Path.home() / "Compartido" / "Recibidos")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def _format_size(size: int) -> str:
    if size >= 1024 ** 3:
        return f"{size / 1024 ** 3:.1f} GB"
    if size >= 1024 ** 2:
        return f"{size / 1024 ** 2:.0f} MB"
    if size >= 1024:
        return f"{size / 1024:.0f} KB"
    return f"{size} B"


def _safe_filename(raw: str) -> str:
    """Decode URL-encoded filename and strip path separators."""
    name = urllib.parse.unquote(raw)
    return Path(name).name or "archivo_recibido"


def _unique_dest(directory: Path, filename: str) -> Path:
    """Return a path that does not already exist, adding a counter suffix if needed."""
    dest = directory / filename
    stem, suffix = Path(filename).stem, Path(filename).suffix
    counter = 1
    while dest.exists():
        dest = directory / f"{stem}_{counter}{suffix}"
        counter += 1
    return dest


# ── HTML helpers ────────────────────────────────────────────────────────────────

def _html_page(title: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    body        {{ font-family: sans-serif; max-width: 650px; margin: 40px auto; padding: 0 20px; }}
    h2, h3      {{ color: #333; }}
    table       {{ width: 100%; border-collapse: collapse; margin-bottom: 30px; }}
    td          {{ padding: 10px; border-bottom: 1px solid #eee; }}
    a           {{ color: #0077cc; text-decoration: none; }}
    a:hover     {{ text-decoration: underline; }}
    .card       {{ background: #f5f5f5; padding: 20px; border-radius: 8px; }}
    .btn        {{ background: #0077cc; color: white; border: none; padding: 10px 20px;
                   border-radius: 5px; cursor: pointer; font-size: 15px;
                   margin-top: 10px; display: inline-block; }}
    .btn:disabled {{ background: #aaa; cursor: not-allowed; }}
    .bar-outer  {{ background: #ddd; border-radius: 5px; height: 22px;
                   width: 100%; margin-top: 12px; display: none; }}
    .bar-inner  {{ background: #0077cc; height: 22px; border-radius: 5px;
                   width: 0%; transition: width 0.2s; }}
    #pct        {{ text-align: center; margin: 4px 0; font-size: 14px; color: #555; }}
    #msg        {{ font-weight: bold; margin-top: 8px; }}
  </style>
</head>
<body>{body}</body>
</html>"""


def _file_rows(share_dir: str) -> str:
    rows = []
    for f in sorted(Path(share_dir).iterdir()):
        if f.is_file():
            encoded = urllib.parse.quote(f.name)
            size    = _format_size(f.stat().st_size)
            rows.append(
                f'<tr>'
                f'<td><a href="/download/{encoded}">{f.name}</a></td>'
                f'<td style="color:#888;white-space:nowrap">{size}</td>'
                f'</tr>'
            )
    return "".join(rows) or (
        '<tr><td colspan="2" style="color:#888">No hay archivos compartidos aún.</td></tr>'
    )


def _upload_script() -> str:
    """JavaScript that sends the file as a raw stream with a progress bar."""
    return """
<script>
function enviar() {
  const file = document.getElementById('fileInput').files[0];
  if (!file) { alert('Selecciona un archivo primero.'); return; }

  const btn  = document.getElementById('btn');
  const barO = document.getElementById('barOuter');
  const barI = document.getElementById('barInner');
  const pct  = document.getElementById('pct');
  const msg  = document.getElementById('msg');

  btn.disabled = true;
  btn.textContent = 'Enviando...';
  barO.style.display = 'block';
  msg.textContent = '';
  msg.style.color = 'green';

  const xhr = new XMLHttpRequest();
  xhr.open('POST', '/upload', true);
  xhr.setRequestHeader('X-Filename',     encodeURIComponent(file.name));
  xhr.setRequestHeader('Content-Type',   'application/octet-stream');
  xhr.setRequestHeader('Content-Length', file.size);
  xhr.timeout = 0;

  xhr.upload.onprogress = function(e) {
    if (e.lengthComputable) {
      const p   = Math.round(e.loaded / e.total * 100);
      const mb  = (e.loaded  / 1048576).toFixed(1);
      const tot = (e.total   / 1048576).toFixed(1);
      barI.style.width = p + '%';
      pct.textContent  = p + '%  (' + mb + ' MB / ' + tot + ' MB)';
    }
  };

  xhr.onload = function() {
    btn.disabled = false;
    btn.textContent = 'Enviar';
    barI.style.width = '100%';
    if (xhr.status === 200) {
      pct.textContent = '100%';
      msg.textContent = '✅ ' + file.name + ' recibido correctamente.';
    } else {
      msg.textContent = '❌ Error del servidor (' + xhr.status + ').';
      msg.style.color = 'red';
    }
  };

  xhr.onerror = function() {
    btn.disabled = false;
    btn.textContent = 'Enviar';
    msg.textContent = '❌ Error de conexión. Comprueba que el servidor sigue activo.';
    msg.style.color = 'red';
  };

  xhr.send(file);
}
</script>"""


# ── Flask app factory ──────────────────────────────────────────────────────────

def _create_app(share_dir: str, upload_dir: str) -> Flask:
    app = Flask(__name__)
    CORS(app)
    os.makedirs(share_dir,  exist_ok=True)
    os.makedirs(upload_dir, exist_ok=True)

    @app.route("/")
    def index():
        body = f"""
  <h2>📁 Archivos disponibles</h2>
  <table>{_file_rows(share_dir)}</table>

  <div class="card">
    <h3>📤 Enviar archivo al PC</h3>
    <input type="file" id="fileInput">
    <button id="btn" class="btn" onclick="enviar()">Enviar</button>
    <div id="barOuter" class="bar-outer">
      <div id="barInner" class="bar-inner"></div>
    </div>
    <p id="pct"></p>
    <p id="msg"></p>
  </div>
  {_upload_script()}"""
        return _html_page("Compartir archivos", body)

    @app.route("/download/<path:nombre>")
    def download(nombre: str):
        ruta = Path(share_dir) / nombre
        if not ruta.exists() or not ruta.is_file():
            return "Archivo no encontrado.", 404
        return send_file(str(ruta), as_attachment=True, conditional=True)

    @app.route("/upload", methods=["POST", "OPTIONS"])
    def upload():
        if request.method == "OPTIONS":
            resp = app.make_default_options_response()
            resp.headers.update({
                "Access-Control-Allow-Origin":  "*",
                "Access-Control-Allow-Headers": "X-Filename, Content-Type, Content-Length",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
            })
            return resp

        filename = _safe_filename(request.headers.get("X-Filename", "archivo_recibido"))
        dest     = _unique_dest(Path(upload_dir), filename)

        wsgi_input = request.environ["wsgi.input"]
        with open(str(dest), "wb") as out:
            while chunk := wsgi_input.read(CHUNK_SIZE):
                out.write(chunk)

        body = f"""
  <h2>✅ Archivo recibido</h2>
  <p><b>{filename}</b> guardado en Recibidos.</p>
  <a href="/">← Volver</a>"""
        resp = app.response_class(_html_page("Archivo recibido", body), mimetype="text/html")
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp

    return app


# ── Background server runner ───────────────────────────────────────────────────

def _run_server(app: Flask) -> None:
    serve(
        app,
        host                 = "0.0.0.0",
        port                 = PORT,
        threads              = 4,
        channel_timeout      = CHANNEL_TIMEOUT,
        connection_limit     = 20,
        max_request_body_size = MAX_BODY,
    )


# ── Public API ─────────────────────────────────────────────────────────────────

def iniciar_servidor_compartir(carpeta: str | None = None) -> str:
    global _server_thread, _running, _share_dir, _upload_dir

    if _running:
        return (
            f"El servidor ya está activo.\n"
            f"🌐 Accede desde cualquier dispositivo: http://{_local_ip()}:{PORT}"
        )

    if carpeta:
        ruta = Path(carpeta).expanduser().resolve()
        if not ruta.exists():
            return f"⚠️  La carpeta '{carpeta}' no existe."
        _share_dir  = str(ruta)
        _upload_dir = str(ruta / "Recibidos")

    app = _create_app(_share_dir, _upload_dir)
    _server_thread = threading.Thread(target=_run_server, args=(app,), daemon=True)
    _server_thread.start()
    _running = True

    ip = _local_ip()
    return (
        f"✅ Servidor de archivos activo.\n"
        f"🌐 Abre esto en cualquier dispositivo de tu red:\n"
        f"   http://{ip}:{PORT}\n\n"
        f"📂 Archivos compartidos desde: {_share_dir}\n"
        f"📥 Archivos recibidos en:      {_upload_dir}\n\n"
        f"Di 'detener compartir' para apagarlo."
    )


def detener_servidor_compartir() -> str:
    global _running
    if not _running:
        return "El servidor de archivos no está activo."
    _running = False
    return "✅ Servidor de archivos detenido. Se cerrará al terminar las transferencias activas."


def estado_compartir() -> str:
    if not _running:
        return "El servidor de archivos no está activo."
    archivos  = [f for f in Path(_share_dir).glob("*")  if f.is_file()]
    recibidos = [f for f in Path(_upload_dir).glob("*") if f.is_file()]
    return (
        f"🟢 Servidor activo en http://{_local_ip()}:{PORT}\n"
        f"📂 Archivos compartidos: {len(archivos)}\n"
        f"📥 Archivos recibidos:   {len(recibidos)}"
    )