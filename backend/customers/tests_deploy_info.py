import json
import tempfile
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase, override_settings

from customers import deploy_info


class BuildFromEnvTests(SimpleTestCase):
    def test_uses_build_args(self):
        info = deploy_info.build_from_env({
            "APP_VERSION": "v9.99.00",
            "GIT_COMMIT": "0123456789abcdef",
            "GIT_COMMIT_DATE": "2026-01-02T03:04:05+00:00",
            "GIT_BRANCH": "develop",
            "BUILD_DATE": "2026-01-02T04:00:00Z",
        })
        self.assertEqual(info["release"], "v9.99.00")
        self.assertEqual(info["commit"], "01234567")
        self.assertEqual(info["commit_full"], "0123456789abcdef")
        self.assertEqual(info["commit_date"], "2026-01-02T03:04:05+00:00")
        self.assertEqual(info["branch"], "develop")
        self.assertEqual(info["deployed_at"], "2026-01-02T04:00:00Z")
        self.assertEqual(info["source"], "build")
        self.assertEqual(info["component"], "backend")

    def test_without_args_records_build_time_only(self):
        info = deploy_info.build_from_env({"GIT_COMMIT": "  ", "BUILD_DATE": ""})
        self.assertEqual(info["commit"], "")
        self.assertEqual(info["release"], "")
        self.assertRegex(info["deployed_at"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

    def test_write_deploy_info_writes_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / deploy_info.DEPLOY_INFO_FILENAME
            deploy_info.write_deploy_info(path, {"APP_VERSION": "v9.99.00", "BUILD_DATE": "2026-01-02T04:00:00Z"})
            data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(data["release"], "v9.99.00")
        self.assertEqual(data["deployed_at"], "2026-01-02T04:00:00Z")


class GetDeployInfoTests(SimpleTestCase):
    def setUp(self):
        deploy_info._cache = None
        deploy_info._cache_mtime = None
        self.addCleanup(setattr, deploy_info, "_cache", None)
        self.addCleanup(setattr, deploy_info, "_cache_mtime", None)

    def test_reads_file_written_at_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            deploy_info.write_deploy_info(
                Path(tmp) / deploy_info.DEPLOY_INFO_FILENAME,
                {"APP_VERSION": "v9.99.00", "GIT_COMMIT": "0123456789abcdef", "BUILD_DATE": "2026-01-02T04:00:00Z"},
            )
            with override_settings(BASE_DIR=Path(tmp)), mock.patch.object(deploy_info, "_git") as git:
                info = deploy_info.get_deploy_info(refresh=True)
        git.assert_not_called()
        self.assertEqual(info["release"], "v9.99.00")
        self.assertEqual(info["commit"], "01234567")
        self.assertEqual(info["deployed_at"], "2026-01-02T04:00:00Z")

    def test_falls_back_to_local_git(self):
        answers = {
            ("rev-parse", "HEAD"): "fedcba9876543210",
            ("log", "-1", "--format=%cI"): "2026-01-02T03:04:05+00:00",
            ("log", "-1", "--format=%s"): "subject",
            ("rev-parse", "--abbrev-ref", "HEAD"): "feature",
            ("describe", "--tags", "--always"): "v9.99.00-3-gfedcba98",
        }
        with tempfile.TemporaryDirectory() as tmp, override_settings(BASE_DIR=Path(tmp)), \
                mock.patch.object(deploy_info, "_git", side_effect=lambda _base, *args: answers.get(args, "")):
            info = deploy_info.get_deploy_info(refresh=True)
        self.assertEqual(info["source"], "git")
        self.assertIsNone(info["deployed_at"])
        self.assertEqual(info["commit"], "fedcba98")
        self.assertEqual(info["branch"], "feature")
        self.assertEqual(info["release"], "v9.99.00-3-gfedcba98")

    def test_without_file_nor_git_returns_empty_fields(self):
        with tempfile.TemporaryDirectory() as tmp, override_settings(BASE_DIR=Path(tmp)), \
                mock.patch.object(deploy_info, "_git", return_value=""):
            info = deploy_info.get_deploy_info(refresh=True)
        self.assertEqual(info["source"], "unknown")
        self.assertEqual(info["commit"], "")
        self.assertIsNone(info["deployed_at"])
