import importlib
import unittest


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


if __name__ == "__main__":
    unittest.main()
