try:
    import requests
except ImportError:  # pragma: no cover - optional dependency
    requests = None

try:
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover - optional dependency
    BeautifulSoup = None

try:
    from ddgs import DDGS
except ImportError:  # pragma: no cover - optional dependency
    DDGS = None


def buscar_en_internet(consulta):
    if DDGS is None:
        return "No se pudo obtener información de internet."
    try:
        with DDGS() as ddgs:
            resultados = list(ddgs.text(consulta, max_results=3))
            return "\n".join([f"Fuente: {r['href']}\n{r['body']}" for r in resultados])
    except Exception:
        return "No se pudo obtener información de internet."


def leer_pagina_web(url: str) -> str:
    if requests is None or BeautifulSoup is None:
        return f"No se pudo leer la página: dependencias no instaladas"
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
