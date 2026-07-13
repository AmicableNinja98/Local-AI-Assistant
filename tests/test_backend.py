"""
test_backend_refactor.py
────────────────────────
Run with:  python -m pytest test_backend_refactor.py -v
       or: python -m unittest test_backend_refactor.py -v

Tests are grouped into classes by domain so new tests are easy to add.
All database and LLM calls are mocked — tests run without MariaDB or llama.cpp.
"""

import importlib
import io
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch


# ══════════════════════════════════════════════════════════════════════════════
# 1. Module structure
# ══════════════════════════════════════════════════════════════════════════════

class ModuleStructureTests(unittest.TestCase):
    """Verify every backend module can be imported and exposes expected names."""

    MODULES = [
        "backend.config",
        "backend.db",
        "backend.management",
        "backend.web",
        "backend.apps",
        "backend.sports",
        "backend.intents",
        "backend.llama",
        "backend.session",
        "backend.core",
        "backend.sharing",
    ]

    def test_all_modules_are_importable(self):
        for name in self.MODULES:
            with self.subTest(module=name):
                mod = importlib.import_module(name)
                self.assertTrue(hasattr(mod, "__name__"))

    def test_core_reexports_assistant_session(self):
        core = importlib.import_module("backend.core")
        self.assertTrue(hasattr(core, "AsistenteSession"))

    def test_session_exposes_tools_and_funciones_mapa(self):
        from backend.session import FUNCIONES_MAPA, TOOLS
        self.assertIsInstance(TOOLS, list)
        self.assertIsInstance(FUNCIONES_MAPA, dict)
        self.assertGreater(len(TOOLS), 0)
        self.assertGreater(len(FUNCIONES_MAPA), 0)

    def test_every_tool_has_a_matching_function(self):
        from backend.session import FUNCIONES_MAPA, TOOLS
        tool_names = {t["function"]["name"] for t in TOOLS}
        for name in tool_names:
            with self.subTest(tool=name):
                self.assertIn(name, FUNCIONES_MAPA)

    def test_sharing_module_exposes_public_api(self):
        from backend import sharing
        for fn in ("iniciar_servidor_compartir", "detener_servidor_compartir", "estado_compartir"):
            with self.subTest(fn=fn):
                self.assertTrue(callable(getattr(sharing, fn)))


# ══════════════════════════════════════════════════════════════════════════════
# 2. Session behaviour
# ══════════════════════════════════════════════════════════════════════════════

class SessionBehaviourTests(unittest.TestCase):
    """Tests for AsistenteSession state machine (no DB or LLM needed)."""

    def _make_session(self):
        from backend.session import AsistenteSession
        return AsistenteSession()

    def test_pending_app_cancelled_by_keyword(self):
        session = self._make_session()
        session._app_pendiente = "Discord"
        resp = session.manejar("cancelar")
        self.assertEqual(resp["tipo"], "respuesta")
        self.assertIn("cancel", resp["texto"].lower())
        self.assertIsNone(session._app_pendiente)

    def test_salir_sets_terminado(self):
        session = self._make_session()
        resp = session.manejar("salir")
        self.assertTrue(resp["terminado"])
        self.assertEqual(resp["tipo"], "adios")

    def test_ayuda_returns_ayuda_tipo(self):
        session = self._make_session()
        resp = session.manejar("/ayuda")
        self.assertEqual(resp["tipo"], "ayuda")
        self.assertFalse(resp["terminado"])

    def test_empty_input_does_not_crash(self):
        session = self._make_session()
        resp = session.manejar("   ")
        self.assertIn("tipo", resp)

    def test_response_always_has_required_keys(self):
        session = self._make_session()
        for text in ["salir", "/ayuda", "cancelar", "hola"]:
            with self.subTest(input=text):
                resp = session.manejar(text)
                for key in ("tipo", "texto", "herramienta", "terminado"):
                    self.assertIn(key, resp)


# ══════════════════════════════════════════════════════════════════════════════
# 3. Intent routing — team & player registration
# ══════════════════════════════════════════════════════════════════════════════

class TeamPlayerRegistrationIntentTests(unittest.TestCase):
    """Verify that registration phrases route to the correct handler."""

    def _dispatch(self, text):
        from backend.intents import intentar_accion_deportiva
        return intentar_accion_deportiva(None, text)

    # ── Teams ──────────────────────────────────────────────────────────────

    @patch("backend.intents.inscribir_equipo_en_torneo", return_value="ok")
    def test_team_with_quotes(self, mock):
        resp = self._dispatch('registra el equipo "Barcelona" en el torneo "Liga"')
        self.assertEqual(resp["herramienta"], "inscribir_equipo_en_torneo")
        mock.assert_called_once_with("Barcelona", "Liga")

    @patch("backend.intents.inscribir_equipo_en_torneo", return_value="ok")
    def test_team_without_quotes(self, mock):
        resp = self._dispatch("registra el equipo Japón en el torneo World Cup Test")
        self.assertEqual(resp["herramienta"], "inscribir_equipo_en_torneo")
        mock.assert_called_once_with("Japón", "World Cup Test")

    @patch("backend.intents.inscribir_equipo_en_torneo", return_value="ok")
    def test_team_with_añade(self, mock):
        resp = self._dispatch("añade el equipo Japón al torneo World Cup Test")
        self.assertEqual(resp["herramienta"], "inscribir_equipo_en_torneo")
        mock.assert_called_once_with("Japón", "World Cup Test")

    @patch("backend.intents.inscribir_equipo_en_torneo", return_value="ok")
    def test_team_english(self, mock):
        resp = self._dispatch("add team Japan to tournament World Cup Test")
        self.assertEqual(resp["herramienta"], "inscribir_equipo_en_torneo")
        mock.assert_called_once_with("Japan", "World Cup Test")

    @patch("backend.intents.inscribir_equipo_en_torneo", return_value="ok")
    def test_team_inscribe_keyword(self, mock):
        resp = self._dispatch("Inscribe España en World Cup Test")
        self.assertEqual(resp["herramienta"], "inscribir_equipo_en_torneo")

    # ── Players ────────────────────────────────────────────────────────────

    @patch("backend.intents.inscribir_jugador_en_torneo", return_value="ok")
    def test_player_with_quotes(self, mock):
        resp = self._dispatch('registra al jugador "Ana" en el torneo "Liga"')
        self.assertEqual(resp["herramienta"], "inscribir_jugador_en_torneo")
        mock.assert_called_once_with("Ana", "Liga")

    @patch("backend.intents.inscribir_jugador_en_torneo", return_value="ok")
    def test_player_without_quotes(self, mock):
        resp = self._dispatch("registra al jugador Genzo Wakabayashi en el torneo World Cup Test")
        self.assertEqual(resp["herramienta"], "inscribir_jugador_en_torneo")
        mock.assert_called_once_with("Genzo Wakabayashi", "World Cup Test")

    @patch("backend.intents.inscribir_jugador_en_torneo", return_value="ok")
    def test_player_with_añade(self, mock):
        resp = self._dispatch("añade al jugador Genzo Wakabayashi en el torneo World Cup Test")
        self.assertEqual(resp["herramienta"], "inscribir_jugador_en_torneo")
        mock.assert_called_once_with("Genzo Wakabayashi", "World Cup Test")


# ══════════════════════════════════════════════════════════════════════════════
# 4. Intent routing — tournament & team creation
# ══════════════════════════════════════════════════════════════════════════════

class CreationIntentTests(unittest.TestCase):

    def _dispatch(self, text):
        from backend.intents import intentar_accion_deportiva
        return intentar_accion_deportiva(None, text)

    @patch("backend.intents.crear_torneo", return_value="ok")
    def test_crear_torneo_with_quotes(self, mock):
        resp = self._dispatch('crea el torneo "Copa del Rey"')
        self.assertEqual(resp["herramienta"], "crear_torneo")
        mock.assert_called_once()
        args = mock.call_args[0]
        self.assertEqual(args[0], "Copa del Rey")

    @patch("backend.intents.crear_torneo", return_value="ok")
    def test_crear_torneo_llamado(self, mock):
        resp = self._dispatch("crea un torneo llamado Champions League")
        self.assertEqual(resp["herramienta"], "crear_torneo")

    @patch("backend.intents.crear_equipo", return_value="ok")
    def test_crear_equipo_with_quotes(self, mock):
        resp = self._dispatch('crea el equipo "Real Madrid"')
        self.assertEqual(resp["herramienta"], "crear_equipo")
        mock.assert_called_once()

    @patch("backend.intents.crear_equipo", return_value="ok")
    def test_nuevo_equipo_keyword(self, mock):
        resp = self._dispatch("nuevo equipo Barcelona")
        self.assertEqual(resp["herramienta"], "crear_equipo")

    def test_crear_torneo_without_name_asks_for_it(self):
        resp = self._dispatch("crea un torneo")
        self.assertEqual(resp["tipo"], "respuesta")
        self.assertIn("torneo", resp["texto"].lower())


# ══════════════════════════════════════════════════════════════════════════════
# 5. Intent routing — match update
# ══════════════════════════════════════════════════════════════════════════════

class MatchUpdateIntentTests(unittest.TestCase):

    def _dispatch(self, text):
        from backend.intents import intentar_accion_deportiva
        return intentar_accion_deportiva(None, text)

    @patch("backend.intents.actualizar_partido_completo", return_value="ok")
    def test_full_match_update_routed(self, mock):
        resp = self._dispatch(
            "Actualiza el partido Brasil vs Francia del torneo World Cup Test, "
            "resultado 2-0, goles de Neymar y Vinicius, asistencia de Rodrygo"
        )
        self.assertEqual(resp["herramienta"], "actualizar_partido_completo")
        args = mock.call_args[0]
        self.assertIn("Brasil",  args[1])
        self.assertIn("Francia", args[2])
        self.assertEqual(args[3], 2)
        self.assertEqual(args[4], 0)

    @patch("backend.intents.actualizar_partido_completo", return_value="ok")
    def test_goalscorers_extracted(self, mock):
        self._dispatch(
            "Actualiza el partido España vs Alemania del torneo Liga, "
            "resultado 3-1, goles de Torres, Morata y Ferran, asistencia de Pedri"
        )
        args = mock.call_args[0]
        goleadores = args[5]
        self.assertIn("Torres", goleadores)
        self.assertIn("Morata", goleadores)
        self.assertIn("Ferran", goleadores)

    @patch("backend.intents.actualizar_partido_completo", return_value="ok")
    def test_assisters_extracted(self, mock):
        self._dispatch(
            "Actualiza el partido España vs Alemania del torneo Liga, "
            "resultado 1-0, gol de Torres, asistencia de Pedri"
        )
        args = mock.call_args[0]
        asistentes = args[6]
        self.assertIn("Pedri", asistentes)

    def test_missing_score_asks_for_it(self):
        resp = self._dispatch(
            "Actualiza el partido Brasil vs Francia del torneo World Cup Test"
        )
        self.assertEqual(resp["tipo"], "respuesta")

    def test_missing_teams_asks_for_them(self):
        resp = self._dispatch("Actualiza el partido del torneo World Cup Test resultado 2-0")
        self.assertEqual(resp["tipo"], "respuesta")


# ══════════════════════════════════════════════════════════════════════════════
# 6. Intent routing — views
# ══════════════════════════════════════════════════════════════════════════════

class ViewIntentTests(unittest.TestCase):

    def _dispatch(self, text):
        from backend.intents import intentar_accion_deportiva
        return intentar_accion_deportiva(None, text)

    @patch("backend.intents.ver_clasificacion_grupos", return_value="ok")
    def test_all_group_standings(self, mock):
        resp = self._dispatch("muestra la clasificación de todos los grupos de World Cup Test")
        self.assertEqual(resp["herramienta"], "ver_clasificacion_grupos")

    @patch("backend.intents.ver_clasificacion", return_value="ok")
    def test_specific_group_standings(self, mock):
        resp = self._dispatch("clasificación del Grupo A de World Cup Test")
        self.assertEqual(resp["herramienta"], "ver_clasificacion")

    @patch("backend.intents.ver_partidos", return_value="ok")
    def test_ver_partidos_routed(self, mock):
        resp = self._dispatch("muestra los partidos del World Cup Test")
        self.assertEqual(resp["herramienta"], "ver_partidos")

    @patch("backend.intents.ver_partidos", return_value="ok")
    def test_ver_partidos_programados(self, mock):
        resp = self._dispatch("partidos programados del World Cup Test")
        self.assertEqual(resp["herramienta"], "ver_partidos")
        args = mock.call_args[0]
        self.assertEqual(args[1], "programado")

    @patch("backend.intents.ver_grupos_y_partidos", return_value="ok")
    def test_grupos_y_partidos_routed(self, mock):
        resp = self._dispatch("muestra los grupos y partidos del World Cup Test")
        self.assertEqual(resp["herramienta"], "ver_grupos_y_partidos")

    @patch("backend.intents.ver_ranking_jugadores", return_value="ok")
    def test_ranking_goleadores_routed(self, mock):
        resp = self._dispatch("top goleadores del World Cup Test")
        self.assertEqual(resp["herramienta"], "ver_ranking_jugadores")

    @patch("backend.intents.ver_ranking_equipos", return_value="ok")
    def test_ranking_equipos_routed(self, mock):
        resp = self._dispatch("ranking de equipos del World Cup Test")
        self.assertEqual(resp["herramienta"], "ver_ranking_equipos")

    def test_ver_partidos_without_torneo_asks(self):
        resp = self._dispatch("ver partidos")
        self.assertEqual(resp["tipo"], "respuesta")


# ══════════════════════════════════════════════════════════════════════════════
# 7. Intent routing — draws & knockout
# ══════════════════════════════════════════════════════════════════════════════

class DrawIntentTests(unittest.TestCase):

    def _dispatch(self, text):
        from backend.intents import intentar_accion_deportiva
        return intentar_accion_deportiva(None, text)

    @patch("backend.intents.realizar_sorteo_grupos", return_value="ok")
    def test_sorteo_grupos_routed(self, mock):
        resp = self._dispatch("haz el sorteo de grupos del World Cup Test")
        self.assertEqual(resp["herramienta"], "realizar_sorteo_grupos")

    @patch("backend.intents.realizar_sorteo_eliminatorias", return_value="ok")
    def test_sorteo_eliminatorias_routed(self, mock):
        resp = self._dispatch("genera las eliminatorias del World Cup Test")
        self.assertEqual(resp["herramienta"], "realizar_sorteo_eliminatorias")

    @patch("backend.intents.ver_cuadro_eliminatorias", return_value="ok")
    def test_ver_cuadro_routed(self, mock):
        resp = self._dispatch("ver cuadro del World Cup Test")
        self.assertEqual(resp["herramienta"], "ver_cuadro_eliminatorias")

    @patch("backend.intents.avanzar_eliminatorias", return_value="ok")
    def test_siguiente_ronda_routed(self, mock):
        resp = self._dispatch("genera la siguiente ronda del World Cup Test")
        self.assertEqual(resp["herramienta"], "avanzar_eliminatorias")

    def test_sorteo_without_torneo_asks(self):
        resp = self._dispatch("haz el sorteo de grupos")
        self.assertEqual(resp["tipo"], "respuesta")


# ══════════════════════════════════════════════════════════════════════════════
# 8. Sharing module — unit tests (no real server started)
# ══════════════════════════════════════════════════════════════════════════════

class SharingHelperTests(unittest.TestCase):
    """Tests for sharing.py helper functions — no server or disk I/O needed."""

    def test_format_size_bytes(self):
        from backend.sharing import _format_size
        self.assertEqual(_format_size(500), "500 B")

    def test_format_size_kb(self):
        from backend.sharing import _format_size
        self.assertEqual(_format_size(2048), "2 KB")

    def test_format_size_mb(self):
        from backend.sharing import _format_size
        self.assertEqual(_format_size(5 * 1024 * 1024), "5 MB")

    def test_format_size_gb(self):
        from backend.sharing import _format_size
        self.assertIn("GB", _format_size(2 * 1024 ** 3))

    def test_safe_filename_decodes_url(self):
        from backend.sharing import _safe_filename
        self.assertEqual(_safe_filename("GTA%20Trilogy.zip"), "GTA Trilogy.zip")

    def test_safe_filename_strips_path(self):
        from backend.sharing import _safe_filename
        self.assertEqual(_safe_filename("../../etc/passwd"), "passwd")

    def test_safe_filename_empty_falls_back(self):
        from backend.sharing import _safe_filename
        self.assertEqual(_safe_filename(""), "archivo_recibido")

    def test_unique_dest_no_collision(self, tmp_path=None):
        import tempfile, pathlib
        from backend.sharing import _unique_dest
        with tempfile.TemporaryDirectory() as d:
            dest = _unique_dest(pathlib.Path(d), "test.zip")
            self.assertEqual(dest.name, "test.zip")

    def test_unique_dest_avoids_collision(self):
        import tempfile, pathlib
        from backend.sharing import _unique_dest
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d) / "test.zip"
            p.touch()
            dest = _unique_dest(pathlib.Path(d), "test.zip")
            self.assertEqual(dest.name, "test_1.zip")

    def test_estado_compartir_when_not_running(self):
        from backend import sharing
        sharing._running = False
        result = sharing.estado_compartir()
        self.assertIn("no está activo", result)

    def test_detener_when_not_running(self):
        from backend import sharing
        sharing._running = False
        result = sharing.detener_servidor_compartir()
        self.assertIn("no está activo", result)


# ══════════════════════════════════════════════════════════════════════════════
# 9. Sharing Flask routes — in-process HTTP tests
# ══════════════════════════════════════════════════════════════════════════════

class SharingFlaskTests(unittest.TestCase):
    """Test Flask routes directly using the test client — no real server needed."""

    def setUp(self):
        import tempfile
        from backend.sharing import _create_app
        self.tmp = tempfile.mkdtemp()
        self.upload_dir = tempfile.mkdtemp()
        self.app = _create_app(self.tmp, self.upload_dir)
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def test_index_returns_200(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Archivos disponibles", resp.data)

    def test_index_lists_shared_files(self):
        (Path(self.tmp) / "hola.txt").write_text("hola")
        resp = self.client.get("/")
        self.assertIn(b"hola.txt", resp.data)

    def test_download_existing_file(self):
        (Path(self.tmp) / "doc.txt").write_text("contenido")
        resp = self.client.get("/download/doc.txt")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"contenido", resp.data)

    def test_download_missing_file_returns_404(self):
        resp = self.client.get("/download/no_existe.zip")
        self.assertEqual(resp.status_code, 404)

    def test_upload_saves_file(self):
        from pathlib import Path as P
        resp = self.client.post(
            "/upload",
            data=b"contenido de prueba",
            content_type="application/octet-stream",
            headers={"X-Filename": "prueba.txt"},
        )
        self.assertEqual(resp.status_code, 200)
        saved = list(P(self.upload_dir).glob("prueba.txt"))
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0].read_text(), "contenido de prueba")

    def test_upload_no_overwrite(self):
        from pathlib import Path as P
        (P(self.upload_dir) / "dup.txt").write_text("original")
        self.client.post(
            "/upload",
            data=b"nuevo",
            content_type="application/octet-stream",
            headers={"X-Filename": "dup.txt"},
        )
        files = sorted(P(self.upload_dir).glob("dup*.txt"))
        self.assertEqual(len(files), 2)
        originals = [f for f in files if f.name == "dup.txt"]
        self.assertEqual(originals[0].read_text(), "original")

    def test_upload_options_preflight(self):
        resp = self.client.options("/upload")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("POST", resp.headers.get("Access-Control-Allow-Methods", ""))

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp,        ignore_errors=True)
        shutil.rmtree(self.upload_dir, ignore_errors=True)


# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    unittest.main(verbosity=2)