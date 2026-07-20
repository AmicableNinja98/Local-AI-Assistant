# How to Add a New Feature to the Assistant

This guide walks you through adding a completely new capability to the assistant,
step by step. By the end you will understand every layer of the system and be able
to add any feature you can imagine.

We will use a concrete example throughout: **adding a note-taking feature** that
lets you save, list and delete short notes stored in the database.

---

## How the assistant works (the big picture)

Before touching any code it helps to understand how a user message travels through
the system:

```
User types something
        │
        ▼
  frontend/cli.py          ← displays text, reads keyboard
        │
        ▼
  backend/session.py       ← decides what to do with the message
        │
        ├──► backend/intents.py   ← tries to recognise the command directly (no AI)
        │            │
        │            └── calls a function in management.py / sports.py / sharing.py
        │
        └──► backend/llama.cpp    ← if no intent matched, the AI handles it
                     │
                     └── may call a tool, which also ends up in those same files
```

**Key insight:** most features bypass the AI completely. The AI is only used for
conversation and web search. Everything else is matched in `intents.py` and
executed by a Python function. This is why the assistant is fast and reliable for
structured commands.

---

## The four files you will always touch

| File | What it does | What you add |
|---|---|---|
| `backend/management.py` (or a new file) | Contains the actual logic and database code | One or more functions that do the work |
| `backend/intents.py` | Pattern-matches user text and calls the right function | A handler function + a registry entry |
| `backend/session.py` | Exposes tools to the AI model | A TOOLS entry + a FUNCIONES_MAPA entry |
| `estructura_db.sql` | Database schema | A new table if your feature needs one |

You never need to touch `frontend/cli.py`, `backend/llama.py`, `backend/core.py`
or `backend/session.py` (beyond the two small additions described below).

---

## Step 1 — Design your feature

Answer these three questions before writing a single line of code:

**1. What does the user say?**
Write down 5–10 natural phrasings a real person might use.
```
"Guarda una nota: comprar leche"
"Añade una nota que diga recordar dentista"
"Muestra mis notas"
"Borra la nota sobre dentista"
"Save a note: call mum"
```

**2. What information does the function need?**
For saving: the note text.
For listing: nothing.
For deleting: the note text or an ID.

**3. Does it need a database table?**
Notes need to be stored permanently → yes, we need a table.

---

## Step 2 — Create the database table

Open MariaDB and run:

```sql
CREATE TABLE IF NOT EXISTS notas (
    id    INT AUTO_INCREMENT PRIMARY KEY,
    texto TEXT         NOT NULL,
    fecha DATETIME     DEFAULT CURRENT_TIMESTAMP
);
```

**Rules for good tables:**
- Always include an `id INT AUTO_INCREMENT PRIMARY KEY`
- Use `TEXT` for variable-length strings (notes, descriptions)
- Use `VARCHAR(100)` for short fixed strings (names, statuses)
- Add `DEFAULT CURRENT_TIMESTAMP` to date columns so you never have to set them manually

---

## Step 3 — Write the backend functions

Create a new file `backend/notes.py` (or add to `management.py` if the feature is small):

```python
# backend/notes.py

from .db import _db   # _db() returns a fresh database connection


def guardar_nota(texto: str) -> str:
    """Saves a note to the database."""
    try:
        conn = _db()
        cur  = conn.cursor(buffered=True)
        cur.execute("INSERT INTO notas (texto) VALUES (%s)", (texto,))
        conn.commit()
        cur.close()
        conn.close()
        return f"✅ Nota guardada: '{texto}'"
    except Exception as e:
        return f"Error al guardar nota: {e}"


def listar_notas() -> str:
    """Returns all saved notes."""
    try:
        conn = _db()
        cur  = conn.cursor(buffered=True)
        cur.execute("SELECT id, texto, fecha FROM notas ORDER BY fecha DESC")
        notas = cur.fetchall()
        cur.close()
        conn.close()

        if not notas:
            return "No tienes notas guardadas."

        lineas = ["📝 Tus notas:", "─" * 40]
        for id_, texto, fecha in notas:
            lineas.append(f"  [{id_}] {texto}  ({fecha.strftime('%d/%m/%Y %H:%M')})")
        lineas.append("─" * 40)
        return "\n".join(lineas)
    except Exception as e:
        return f"Error al listar notas: {e}"


def borrar_nota(id_o_texto: str) -> str:
    """Deletes a note by ID or by matching text."""
    try:
        conn = _db()
        cur  = conn.cursor(buffered=True)

        # Try numeric ID first
        if id_o_texto.strip().isdigit():
            cur.execute("DELETE FROM notas WHERE id = %s", (int(id_o_texto),))
        else:
            # Partial text match
            cur.execute("DELETE FROM notas WHERE texto LIKE %s", (f"%{id_o_texto}%",))

        deleted = cur.rowcount
        conn.commit()
        cur.close()
        conn.close()

        if deleted:
            return f"✅ Nota eliminada."
        return f"⚠️  No encontré ninguna nota con '{id_o_texto}'."
    except Exception as e:
        return f"Error al borrar nota: {e}"
```

**Good practices for backend functions:**
- Always wrap everything in `try/except` and return a readable error string
- Always call `cur.close()` and `conn.close()` before returning
- Always use `buffered=True` on cursors: `conn.cursor(buffered=True)`
- Use `%s` placeholders, never f-strings inside SQL (prevents SQL injection)
- Return a human-readable string — the CLI will print it directly

---

## Step 4 — Add intent handlers to `intents.py`

This is where you teach the assistant to recognise what the user said.

### 4a — Import your new functions

At the top of `intents.py`, add your import:

```python
from .notes import guardar_nota, listar_notas, borrar_nota
```

### 4b — Write a handler function for each action

A handler receives the original text and its lowercased version, and returns
a response dict or `None`.

Add these anywhere in `intents.py` before the `INTENT_REGISTRY` list:

```python
def _handle_guardar_nota(texto, t):
    # Extract the note text — everything after "nota:" or "nota que diga"
    m = re.search(
        r'(?:nota[:\s]+|nota\s+que\s+diga\s+|note[:\s]+|save\s+(?:a\s+)?note[:\s]+)'
        r'(.+)$',
        texto, re.IGNORECASE
    )
    contenido = m.group(1).strip() if m else None

    if not contenido:
        return _r("respuesta", "¿Qué quieres que guarde en la nota?")

    return _r("herramienta", guardar_nota(contenido), "guardar_nota")


def _handle_listar_notas(texto, t):
    return _r("herramienta", listar_notas(), "listar_notas")


def _handle_borrar_nota(texto, t):
    # Extract what to delete — ID or text fragment
    m = re.search(
        r'(?:borra|elimina|delete|remove)\s+(?:la\s+)?nota\s+(?:sobre\s+|de\s+|with\s+|about\s+)?(.+)$',
        texto, re.IGNORECASE
    )
    # Also accept "borra nota 3" (by ID)
    m_id = re.search(r'nota\s+(\d+)', texto, re.IGNORECASE)

    referencia = None
    if m_id:
        referencia = m_id.group(1)
    elif m:
        referencia = m.group(1).strip().strip("\"'.,")

    if not referencia:
        return _r("respuesta", "¿Qué nota quieres borrar? Dime el ID o una parte del texto.")

    return _r("herramienta", borrar_nota(referencia), "borrar_nota")
```

### 4c — Add entries to the `INTENT_REGISTRY`

Find the `INTENT_REGISTRY = [` list and add your entries. Order matters —
put more specific triggers before general ones:

```python
    # ── Notes ──────────────────────────────────────────────────────────────
    {
        "triggers": ["guarda una nota", "guarda nota", "añade una nota",
                     "añade nota", "save a note", "save note",
                     "crea una nota", "nueva nota", "apunta"],
        "handler": _handle_guardar_nota,
    },
    {
        "triggers": ["muestra mis notas", "ver notas", "lista notas",
                     "muestra notas", "show notes", "list notes",
                     "mis notas", "mis apuntes", "qué notas tengo",
                     "que notas tengo"],
        "handler": _handle_listar_notas,
    },
    {
        "triggers": ["borra la nota", "borra nota", "elimina nota",
                     "elimina la nota", "delete note", "remove note",
                     "borrar nota"],
        "handler": _handle_borrar_nota,
    },
```

---

## Step 5 — Register the tools in `session.py`

This makes the AI aware of your new functions so it can call them when the
intent system doesn't catch the phrase. This is a safety net — most commands
will be caught by `intents.py` in step 4.

### 5a — Add to the TOOLS list

Find the `TOOLS = [` list in `session.py` and add:

```python
    {"type": "function", "function": {
        "name": "guardar_nota",
        "description": "Guarda una nota de texto para el usuario.",
        "parameters": {
            "type": "object",
            "properties": {
                "texto": {"type": "string", "description": "Contenido de la nota"}
            },
            "required": ["texto"]
        }
    }},
    {"type": "function", "function": {
        "name": "listar_notas",
        "description": "Muestra todas las notas guardadas por el usuario.",
        "parameters": {"type": "object", "properties": {}}
    }},
    {"type": "function", "function": {
        "name": "borrar_nota",
        "description": "Borra una nota por ID o por texto.",
        "parameters": {
            "type": "object",
            "properties": {
                "id_o_texto": {"type": "string", "description": "ID numérico o fragmento del texto de la nota"}
            },
            "required": ["id_o_texto"]
        }
    }},
```

### 5b — Add to FUNCIONES_MAPA

Find the `FUNCIONES_MAPA = {` dict in `session.py` and add:

```python
    "guardar_nota":  guardar_nota,
    "listar_notas":  listar_notas,
    "borrar_nota":   borrar_nota,
```

Also add the import at the top of `session.py`:

```python
from .notes import guardar_nota, listar_notas, borrar_nota
```

---

## Step 6 — Update the help menu

Find `ayuda_asistente()` in `backend/help.py` (or wherever it lives in your
project) and add a line:

```python
"7. 📝 Notas: 'Guarda una nota: comprar leche', 'Muestra mis notas', 'Borra nota 3'\n"
```

---

## Step 7 — Write tests

Add a new test class to `test_backend_refactor.py`:

```python
class NotesIntentTests(unittest.TestCase):

    def _dispatch(self, text):
        from backend.intents import intentar_accion_deportiva
        return intentar_accion_deportiva(None, text)

    @patch("backend.intents.guardar_nota", return_value="ok")
    def test_save_note_spanish(self, mock):
        resp = self._dispatch("guarda una nota: comprar leche")
        self.assertEqual(resp["herramienta"], "guardar_nota")
        mock.assert_called_once_with("comprar leche")

    @patch("backend.intents.guardar_nota", return_value="ok")
    def test_save_note_english(self, mock):
        resp = self._dispatch("save a note: call mum")
        self.assertEqual(resp["herramienta"], "guardar_nota")
        mock.assert_called_once_with("call mum")

    @patch("backend.intents.listar_notas", return_value="ok")
    def test_list_notes(self, mock):
        resp = self._dispatch("muestra mis notas")
        self.assertEqual(resp["herramienta"], "listar_notas")
        mock.assert_called_once()

    @patch("backend.intents.borrar_nota", return_value="ok")
    def test_delete_note_by_text(self, mock):
        resp = self._dispatch("borra la nota sobre dentista")
        self.assertEqual(resp["herramienta"], "borrar_nota")
        mock.assert_called_once_with("dentista")

    @patch("backend.intents.borrar_nota", return_value="ok")
    def test_delete_note_by_id(self, mock):
        resp = self._dispatch("borra nota 3")
        self.assertEqual(resp["herramienta"], "borrar_nota")
        mock.assert_called_once_with("3")

    def test_save_note_without_content_asks(self):
        resp = self._dispatch("guarda una nota")
        self.assertEqual(resp["tipo"], "respuesta")
```

Run your tests:
```
venv\Scripts\python -m pytest test_backend_refactor.py -v
```

---

## Checklist — use this every time you add a feature

```
□ Designed the feature (what user says, what info is needed, DB table needed?)
□ Created the database table (if needed)
□ Wrote backend functions in their own file or management.py
  □ Every function has try/except
  □ Every function returns a readable string
  □ All cursors use buffered=True
  □ All cursors and connections are closed before returning
□ Added import in intents.py
□ Wrote a handler function for each action
  □ Each handler extracts arguments from the text
  □ Each handler validates before calling the backend
  □ Each handler returns _r("respuesta", "...") when info is missing
□ Added entries to INTENT_REGISTRY in the right order
□ Added TOOLS entries in session.py
□ Added FUNCIONES_MAPA entries in session.py
□ Added import in session.py
□ Updated ayuda_asistente()
□ Wrote at least one test per action
□ All tests pass
```

---

## Common mistakes and how to avoid them

**The assistant doesn't recognise my phrase**
Your trigger in `INTENT_REGISTRY` doesn't match. Add a `print(t)` at the top of
`intentar_accion_deportiva` to see exactly what string is being checked, then
adjust your triggers.

**The assistant routes to the wrong feature**
A more general trigger earlier in the registry is matching first. Move your entry
higher in the list, or add an `"extra_check"` condition to make the match more
specific:
```python
{
    "triggers": ["nota"],
    "extra_check": lambda t: "guarda" in t or "save" in t,
    "handler": _handle_guardar_nota,
}
```

**`Error: Unread result found`**
You are using `conn.cursor()` without `buffered=True`. Change every cursor to
`conn.cursor(buffered=True)`.

**`Error: cursor already closed`**
You called `cur.close()` inside the loop and then tried to use it again. Open a
new cursor for each independent query.

**The AI ignores the tool and answers from memory**
This is expected for small models. The fix is to handle the intent in
`intents.py` (steps 4a–4c) rather than relying on the AI's tool choice. The AI
is a fallback, not the primary path.

**`ImportError: cannot import name X`**
You added to `FUNCIONES_MAPA` or `TOOLS` in `session.py` but forgot the import
at the top. Check every file where you reference your new functions has the
correct `from .yourfile import yourfunction` line.

---

## Summary

Every new feature follows the same four-layer pattern:

```
1. Database table   →  estructura_db.sql
2. Python function  →  backend/yourfile.py
3. Intent handler   →  backend/intents.py  (+ INTENT_REGISTRY entry)
4. Tool definition  →  backend/session.py  (TOOLS + FUNCIONES_MAPA)
```

Once you have done this two or three times it becomes second nature. The system
is designed so that each layer is completely independent — you can change how a
feature is triggered without touching the database code, or change the database
schema without touching the intent routing.
