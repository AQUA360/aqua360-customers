import tempfile
from pathlib import Path
from types import SimpleNamespace

from django.test import SimpleTestCase, override_settings

from coredata.utils import db_sync_service as svc

USER = SimpleNamespace(username="tester")


class DbSyncServiceTests(SimpleTestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self._override = override_settings(DB_SYNC_CONTROL_DIR=str(self.dir), ENV="staging")
        self._override.enable()

    def tearDown(self):
        self._override.disable()
        self._tmp.cleanup()

    def test_test_environment_names(self):
        for env, expected in (("test", True), ("STAGING", True), (" Test ", True), ("LOCAL", True), ("prod", False), ("", False)):
            with self.subTest(env=env), override_settings(ENV=env):
                self.assertEqual(svc.is_test_environment(), expected)

    def test_toggle_nightly(self):
        self.assertTrue(svc.get_status()["nightly_enabled"])
        status = svc.set_nightly_enabled(False, USER)
        self.assertFalse(status["nightly_enabled"])
        self.assertEqual(status["disabled_by"], "tester")
        self.assertTrue((self.dir / svc.DISABLED_FILE).exists())
        self.assertTrue(svc.set_nightly_enabled(True, USER)["nightly_enabled"])
        self.assertFalse((self.dir / svc.DISABLED_FILE).exists())

    def test_enable_when_already_enabled(self):
        self.assertTrue(svc.set_nightly_enabled(True, USER)["nightly_enabled"])

    def test_missing_control_dir(self):
        with override_settings(DB_SYNC_CONTROL_DIR=str(self.dir / "missing")):
            self.assertFalse(svc.get_status()["control_dir_ok"])
            with self.assertRaises(svc.DbSyncError) as ctx:
                svc.set_nightly_enabled(False, USER)
            self.assertEqual(ctx.exception.code, "control_dir_unavailable")
