import sys
import time

# Allow running from the project root
sys.path.insert(0, __import__('os').path.join(__import__('os').path.dirname(__file__), '..'))
from backend.core import AsistenteSession

# ── Colores ANSI ──────────────────────────────────────────────────────────────
CYAN   = "\033[96m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
GREY   = "\033[90m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

SEGUNDOS_CIERRE = 5   # cuántos segundos esperar antes de cerrar la ventana

def imprimir_asistente(texto):
    print(f"\n{CYAN}{BOLD}Asistente:{RESET} {texto}\n")

def imprimir_herramienta(nombre):
    print(f"{GREY}  ⚙️  [herramienta ejecutada: {nombre}]{RESET}")

def cuenta_atras_y_cerrar():
    print(f"\n{YELLOW}Cerrando en {SEGUNDOS_CIERRE} segundos...{RESET}")
    for i in range(SEGUNDOS_CIERRE, 0, -1):
        print(f"\r{YELLOW}{i}...{RESET}", end="", flush=True)
        time.sleep(1)
    sys.exit(0)

def main():
    session = AsistenteSession()

    resultado = session.iniciar()
    imprimir_asistente(resultado["texto"])

    try:
        while session.activo:
            try:
                entrada = input(f"{GREEN}Tú:{RESET} ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break

            if not entrada:
                continue

            resultado = session.manejar(entrada)

            if resultado.get("herramienta"):
                imprimir_herramienta(resultado["herramienta"])

            imprimir_asistente(resultado["texto"])

            if resultado["terminado"]:
                break

    finally:
        session.cerrar()
        cuenta_atras_y_cerrar()


if __name__ == "__main__":
    main()