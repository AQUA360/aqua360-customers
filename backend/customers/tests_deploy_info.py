import json
import tempfile
from pathlib import Path
from unittest import mock

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIClient

from coredata.models import DeployRecord

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


BACKEND_BUILD = {
    "source": "deploy",
    "release": "v9.99.00",
    "commit": "01234567",
    "commit_full": "0123456789abcdef",
    "branch": "",
    "deployed_at": "2026-01-02T04:00:00Z",
    "built_at": "2026-01-02T04:00:00Z",
}


class RecordDeployTests(TestCase):
    def test_first_run_of_a_version_is_recorded_once(self):
        first = deploy_info.record_deploy("backend", BACKEND_BUILD)
        again = deploy_info.record_deploy("backend", BACKEND_BUILD)
        self.assertEqual(first, again)
        record = DeployRecord.objects.get()
        self.assertEqual(record.release, "v9.99.00")
        self.assertEqual(record.commit, "0123456789abcdef")
        self.assertEqual(record.built_at.isoformat(), "2026-01-02T04:00:00+00:00")

    def test_new_version_and_rollback_are_new_deploys(self):
        deploy_info.record_deploy("backend", BACKEND_BUILD)
        deploy_info.record_deploy("backend", {**BACKEND_BUILD, "release": "v9.99.01", "commit_full": "abcdef"})
        deploy_info.record_deploy("backend", BACKEND_BUILD)
        self.assertEqual(
            list(DeployRecord.objects.order_by("id").values_list("release", flat=True)),
            ["v9.99.00", "v9.99.01", "v9.99.00"],
        )

    def test_components_are_independent(self):
        deploy_info.record_deploy("backend", BACKEND_BUILD)
        deploy_info.record_deploy("frontend", BACKEND_BUILD)
        self.assertEqual(DeployRecord.objects.count(), 2)

    def test_development_and_unknown_are_not_recorded(self):
        self.assertIsNone(deploy_info.record_deploy("backend", {**BACKEND_BUILD, "source": "git"}))
        self.assertIsNone(deploy_info.record_deploy("backend", {"source": "build", "release": "", "commit": ""}))
        self.assertFalse(DeployRecord.objects.exists())

    def test_deploy_date_replaces_build_date(self):
        info = deploy_info.with_deploy_date("backend", BACKEND_BUILD)
        record = DeployRecord.objects.get()
        self.assertEqual(info["deployed_at"], record.deployed_at.isoformat().replace("+00:00", "Z"))
        self.assertEqual(info["built_at"], "2026-01-02T04:00:00Z")
        self.assertEqual(BACKEND_BUILD["deployed_at"], "2026-01-02T04:00:00Z")


class DeployInfoViewTests(TestCase):
    url = "/coredata/deploy-info/"

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(User.objects.create_user("deploy-test"))

    def test_get_returns_backend_with_recorded_deploy_date(self):
        with mock.patch("coredata.views.deploy_info_view.get_deploy_info", return_value=BACKEND_BUILD):
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        record = DeployRecord.objects.get(component="backend")
        self.assertEqual(response.data["deployed_at"], record.deployed_at.isoformat().replace("+00:00", "Z"))

    def test_post_records_frontend_version(self):
        payload = {
            "release": "v9.99.00", "commit": "01234567", "commit_full": "0123456789abcdef",
            "branch": "develop", "built_at": "2026-01-02T04:00:00Z", "source": "build",
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, 200)
        record = DeployRecord.objects.get(component="frontend")
        self.assertEqual(record.branch, "develop")
        self.assertEqual(response.data["deployed_at"], record.deployed_at.isoformat().replace("+00:00", "Z"))

    def test_post_rejects_invalid_commit(self):
        response = self.client.post(self.url, {"commit": "not-a-commit"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(DeployRecord.objects.exists())

    def test_requires_authentication(self):
        self.assertIn(APIClient().get(self.url).status_code, (401, 403))
