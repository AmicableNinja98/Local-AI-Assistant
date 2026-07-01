import importlib
import unittest
from unittest.mock import patch


class BackendRefactorTests(unittest.TestCase):
    def test_refactored_modules_are_importable(self):
        modules = [
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
        ]

        for name in modules:
            with self.subTest(module=name):
                module = importlib.import_module(name)
                self.assertTrue(hasattr(module, "__name__"))

    def test_core_reexports_assistant_session(self):
        core = importlib.import_module("backend.core")
        self.assertTrue(hasattr(core, "AsistenteSession"))

    def test_pending_app_can_be_cancelled(self):
        from backend.session import AsistenteSession

        session = AsistenteSession()
        session._app_pendiente = "Discord"

        response = session.manejar("cancelar")

        self.assertEqual(response["tipo"], "respuesta")
        self.assertIn("cancel", response["texto"].lower())
        self.assertIsNone(session._app_pendiente)

    @patch("backend.intents.inscribir_equipo_en_torneo", return_value="ok")
    def test_existing_team_can_be_registered_to_tournament(self, mock_inscribir):
        from backend.intents import intentar_accion_deportiva

        response = intentar_accion_deportiva(None, 'registra el equipo "Barcelona" en el torneo "Liga"')

        self.assertEqual(response["tipo"], "herramienta")
        self.assertEqual(response["herramienta"], "inscribir_equipo_en_torneo")
        mock_inscribir.assert_called_once_with("Barcelona", "Liga")

    @patch("backend.intents.inscribir_jugador_en_torneo", return_value="ok")
    def test_existing_player_can_be_registered_to_tournament(self, mock_inscribir):
        from backend.intents import intentar_accion_deportiva

        response = intentar_accion_deportiva(None, 'registra al jugador "Ana" en el torneo "Liga"')

        self.assertEqual(response["tipo"], "herramienta")
        self.assertEqual(response["herramienta"], "inscribir_jugador_en_torneo")
        mock_inscribir.assert_called_once_with("Ana", "Liga")

    @patch("backend.intents.inscribir_equipo_en_torneo", return_value="ok")
    def test_team_registration_without_quotes_is_routed(self, mock_inscribir):
        from backend.intents import intentar_accion_deportiva

        response = intentar_accion_deportiva(None, "registra el equipo Japón en el torneo World Cup Test")

        self.assertEqual(response["tipo"], "herramienta")
        self.assertEqual(response["herramienta"], "inscribir_equipo_en_torneo")
        mock_inscribir.assert_called_once_with("Japón", "World Cup Test")

    @patch("backend.intents.inscribir_jugador_en_torneo", return_value="ok")
    def test_player_registration_without_quotes_is_routed(self, mock_inscribir):
        from backend.intents import intentar_accion_deportiva

        response = intentar_accion_deportiva(None, "registra al jugador Genzo Wakabayashi en el torneo World Cup Test")

        self.assertEqual(response["tipo"], "herramienta")
        self.assertEqual(response["herramienta"], "inscribir_jugador_en_torneo")
        mock_inscribir.assert_called_once_with("Genzo Wakabayashi", "World Cup Test")

    @patch("backend.intents.inscribir_equipo_en_torneo", return_value="ok")
    def test_team_registration_with_add_phrase_is_routed(self, mock_inscribir):
        from backend.intents import intentar_accion_deportiva

        response = intentar_accion_deportiva(None, "añade el equipo Japón al torneo World Cup Test")

        self.assertEqual(response["tipo"], "herramienta")
        self.assertEqual(response["herramienta"], "inscribir_equipo_en_torneo")
        mock_inscribir.assert_called_once_with("Japón", "World Cup Test")

    @patch("backend.intents.inscribir_jugador_en_torneo", return_value="ok")
    def test_player_registration_with_add_phrase_is_routed(self, mock_inscribir):
        from backend.intents import intentar_accion_deportiva

        response = intentar_accion_deportiva(None, "añade al jugador Genzo Wakabayashi en el torneo World Cup Test")

        self.assertEqual(response["tipo"], "herramienta")
        self.assertEqual(response["herramienta"], "inscribir_jugador_en_torneo")
        mock_inscribir.assert_called_once_with("Genzo Wakabayashi", "World Cup Test")

    @patch("backend.intents.inscribir_equipo_en_torneo", return_value="ok")
    def test_english_team_registration_is_routed(self, mock_inscribir):
        from backend.intents import intentar_accion_deportiva

        response = intentar_accion_deportiva(None, "add team Japan to tournament World Cup Test")

        self.assertEqual(response["tipo"], "herramienta")
        self.assertEqual(response["herramienta"], "inscribir_equipo_en_torneo")
        mock_inscribir.assert_called_once_with("Japan", "World Cup Test")

    def test_session_exposes_tournament_registration_tools(self):
        from backend.session import FUNCIONES_MAPA, TOOLS

        tool_names = {tool["function"]["name"] for tool in TOOLS}
        self.assertIn("inscribir_equipo_en_torneo", tool_names)
        self.assertIn("inscribir_jugador_en_torneo", tool_names)
        self.assertIn("inscribir_equipo_en_torneo", FUNCIONES_MAPA)
        self.assertIn("inscribir_jugador_en_torneo", FUNCIONES_MAPA)


if __name__ == "__main__":
    unittest.main()
