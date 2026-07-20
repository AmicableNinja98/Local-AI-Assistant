<div align="center">

# 🤖 Alfred — Local AI Desktop Assistant

**A fully local, private, free AI assistant for your PC.**
No cloud. No subscriptions. No data leaving your machine.

![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python&logoColor=white)
![llama.cpp](https://img.shields.io/badge/llama.cpp-local%20LLM-green)
![MariaDB](https://img.shields.io/badge/MariaDB-database-orange?logo=mariadb)
![Flask](https://img.shields.io/badge/Flask-file%20sharing-lightgrey?logo=flask)

</div>

---

## What is Alfred?

Alfred is a command-line AI assistant that runs entirely on your own hardware.
It understands natural language in **English and Spanish**, manages a local
database, launches apps, searches the web, shares files across your local
network, and manages full sports tournaments — all without sending a single byte
to an external server.

---

## Features

### 🧠 AI Conversation
- Powered by [llama.cpp](https://github.com/ggerganov/llama.cpp) — runs any
  GGUF model locally
- Bilingual: understands and responds in English and Spanish
- Remembers your name and the assistant's name across sessions (stored in DB)
- Falls back to web search when it doesn't know something recent

### 🔍 Web Search & Page Reading (WIP)
- Searches the web via DuckDuckGo (no API key needed)
- Reads the full content of any URL you provide
- Never makes up facts — always fetches real data before answering
- Force a search manually with `/buscar [query]`

### 🖥️ App Launcher
- Opens any installed application by name (`open Discord`, `abre Steam`)
- Searches your system automatically (PATH, Start Menu, Program Files)
- Asks for the path if it can't find an app and remembers it permanently
- Also accepts inline path: `open MyApp, the path is C:\...\app.exe`

### ⚽ Sports Tournament Manager
A complete tournament management system modelled after real competitions
like the FIFA World Cup:

| Feature | Description |
|---|---|
| Teams & Players | Create teams, register players, assign them to teams |
| Tournaments | Create tournaments, inscribe all teams in one command |
| Group Stage Draw | Automatic random draw — adapts to 4, 6, 8, 12, 16, 24, 32 or 48 teams |
| Fixtures | Auto-generated group stage fixtures after the draw |
| Results | Update match results with goalscorers and assisters |
| Standings | Group standings table with points, GF, GA, GD |
| Player Stats | Goals, assists, yellow/red cards, matches played per tournament |
| Knockout Draw | Auto-generated from group stage standings (1st A vs 2nd B…) |
| Knockout Rounds | Advance winners round by round through to the Final |
| Rankings | Top scorers, top assisters, most goals scored, fewest conceded |

### 📁 Local Network File Sharing
- Starts a local HTTP server accessible from any device on your Wi-Fi
- Download files from your PC on your phone, tablet or another computer
- Upload files from any device back to your PC
- Handles files of any size (tested up to 60 GB) via chunked streaming
- Progress bar shown during upload — no apps needed, just a browser
- Activate with: `compartir archivos` / `share files`

---

## Prerequisites

Before installing Alfred you need three things:

| Requirement | Version | Download |
|---|---|---|
| Python | 3.11 or higher | https://python.org |
| llama.cpp | Latest release | https://github.com/ggerganov/llama.cpp/releases |
| MariaDB | 10.6 or higher | https://mariadb.org/download |

> **Windows users:** when installing Python, tick **"Add Python to PATH"**
> before clicking Install.

---

## Installation

### 1 — Clone the repository

```bash
git clone https://github.com/yourusername/alfred-assistant.git
cd alfred-assistant
```

### 2 — Create and activate a virtual environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### 3 — Install Python dependencies

```bash
pip install -r requirements.txt
```

### 4 — Download a language model

Alfred uses any GGUF-format model. We recommend one of these depending on
your hardware:

| RAM / VRAM | Recommended model | Where to download |
|---|---|---|
| 4 GB | `phi-3-mini-Q4_K_M.gguf` | [Hugging Face](https://huggingface.co/microsoft/Phi-3-mini-4k-instruct-gguf) |
| 8 GB | `Meta-Llama-3.1-8B-Instruct-Q5_K_M.gguf` | [Hugging Face](https://huggingface.co/bartowski/Meta-Llama-3.1-8B-Instruct-GGUF) |
| 16 GB | `Mistral-7B-Instruct-v0.3-Q8_0.gguf` | [Hugging Face](https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.3-GGUF) |

Place the downloaded `.gguf` file anywhere on your PC and note the full path.

### 5 — Set up the database

Open MariaDB and run:

```sql
CREATE DATABASE asistente_ia CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE asistente_ia;
SOURCE estructura_db.sql;
```

Then insert your name and the assistant's name:

```sql
INSERT INTO usuario (clave, valor) VALUES ('nombre_usuario',   'YourName');
INSERT INTO usuario (clave, valor) VALUES ('nombre_asistente', 'Alfred');
```

### 6 — Configure the environment

Copy the example file and fill in your own values:

```bash
cp .env.example .env
```

Open `.env` in any text editor and set:

```env
# Path to your llama-server executable
RUTA_LLAMA=C:\llama-cpp\llama-server.exe

# Path to your downloaded model
RUTA_MODELO=C:\llama-cpp\models\Meta-Llama-3.1-8B-Instruct-Q5_K_M.gguf

# GPU layers to offload (0 = CPU only, higher = faster with a GPU)
# For an 8 GB VRAM GPU start with 24 and increase until you run out of VRAM
GPU_LAYERS=24

# Database connection
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=your_mariadb_password
DB_NAME=asistente_ia
```

> **How many GPU layers?**
> Each layer offloaded to the GPU speeds up inference. A rough guide:
> - No GPU → `GPU_LAYERS=0`
> - 4 GB VRAM → `GPU_LAYERS=16`
> - 8 GB VRAM → `GPU_LAYERS=24`
> - 12 GB VRAM → `GPU_LAYERS=33`
> - 16 GB+ VRAM → `GPU_LAYERS=99` (all layers)

### 7 — Run Alfred

```bash
python frontend/cli.py
```

Alfred will start llama.cpp automatically, wait for the model to load, then
greet you.

---

## Usage Examples

### General conversation
```
You: What is the speed of light?
Alfred: The speed of light in a vacuum is approximately 299,792 km/s.

You: /buscar Champions League results 2025
Alfred: [searches the web and summarises real results]
```

### Launching apps
```
You: Open Discord
Alfred: Discord launched correctly.

You: Open MyApp, the path is C:\Games\MyApp\myapp.exe
Alfred: Path saved and MyApp opened. Next time I'll open it automatically.
```

### Tournament management
```
You: Create a tournament called "World Cup 2026"
You: Create the team Spain
You: Add all teams to World Cup 2026
You: Do the group draw for World Cup 2026
You: Show groups and matches of World Cup 2026
You: Update the match Spain vs Germany in World Cup 2026, result 2-1,
     goals by Torres and Morata, assist by Pedri
You: Show Group A standings of World Cup 2026
You: Generate the knockout stage of World Cup 2026
You: Generate the next round of World Cup 2026
```

### File sharing
```
You: Share files
Alfred: ✅ Server active. Open http://192.168.1.14:8765 on any device.

The server will stop once you close the app.
```

---

## Project Structure

```
alfred-assistant/
│
├── backend/
│   ├── __init__.py          # re-exports AsistenteSession
│   ├── config.py            # loads .env, exposes settings
│   ├── core.py              # entry point — imports session
│   ├── db.py                # database connection factory
│   ├── management.py        # teams, players, tournaments (DB operations)
│   ├── sports.py            # draw, results, standings, knockout logic
│   ├── intents.py           # pattern matching — the command router
│   ├── session.py           # AsistenteSession class + TOOLS + FUNCIONES_MAPA
│   ├── llama.py             # llama.cpp server management
│   ├── apps.py              # app launching logic
│   ├── web.py               # DuckDuckGo search + page fetcher
│   ├── sharing.py           # local network file server (Flask + Waitress)
│   └── help.py              # ayuda_asistente() text
│
├── frontend/
│   └── cli.py               # command-line interface (the only UI file)
│
├── tests/
│   └── test_backend_refactor.py   # test suite
│
├── estructura_db.sql        # full database schema — run this first
├── requirements.txt         # Python dependencies
├── .env.example             # environment variable template
├── .gitignore               # keeps secrets and venv out of git
└── README.md
```

> **Frontend isolation:** `cli.py` only ever calls three methods on
> `AsistenteSession`: `iniciar()`, `manejar(text)`, and `cerrar()`.
> Swapping the CLI for a GUI, a web app, or a REST API requires only
> creating a new file in `frontend/` — the backend never changes.

---

## Running the Tests

```bash
python -m pytest tests/test_backend_refactor.py -v
```

Tests use mocks for all database and LLM calls, so they run without
MariaDB or llama.cpp running.

---

## Adding Your Own Features

See [`GUIDE_adding_features.md`](GUIDE_adding_features.md) for a detailed
step-by-step walkthrough of how to add any new capability to Alfred.
The guide includes a full working example, a reusable checklist, and a
common mistakes section.

---

## Dependencies

| Package | Purpose |
|---|---|
| `openai` | OpenAI-compatible client for llama.cpp's API |
| `ddgs` | DuckDuckGo web search (no API key) |
| `mysql-connector-python` | MariaDB database driver |
| `psutil` | Process management (closing the llama server) |
| `python-dotenv` | Loads `.env` configuration |
| `requests` | HTTP client for page fetching |
| `beautifulsoup4` | HTML parser for page content extraction |
| `flask` | Web server for file sharing |
| `flask-cors` | CORS headers for browser uploads |
| `waitress` | Production WSGI server (handles large file transfers) |

---

## Security Notes

- Alfred runs entirely on your local network. The file sharing server
  is **not** protected by a password — only run it on a trusted network.
- Your `.env` file contains your database password. It is listed in
  `.gitignore` and will never be uploaded to GitHub.
- Never commit `.env` — always commit `.env.example` with placeholder values.

---

## Troubleshooting

**Alfred starts but immediately closes**
→ Run `python frontend/cli.py` from a terminal (not the bat file) to see
the error message. The most common cause is a wrong path in `.env`.

**`ImportError: cannot import name X`**
→ A function is referenced but not yet added to the file that imports it.
Check all `from .module import function` lines match the actual function names.

**`Error: Unread result found`**
→ A database cursor is missing `buffered=True`. All cursors in the project
should be `conn.cursor(buffered=True)`.

**The AI ignores commands and just talks**
→ This is expected for commands that are handled by `intents.py`. If a
command isn't being caught, add more trigger phrases to `INTENT_REGISTRY`.

**File upload fails at 0%**
→ Run the PowerShell command below as Administrator to open the firewall port:
```powershell
netsh advfirewall firewall add rule name="Alfred File Sharing" dir=in action=allow protocol=TCP localport=8765
```

**The model is very slow**
→ Increase `GPU_LAYERS` in `.env` if you have a GPU. Each layer moved to
the GPU significantly speeds up inference.

---
