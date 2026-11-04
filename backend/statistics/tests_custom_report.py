from django.contrib.auth.models import Permission, User
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIClient

from statistics.utils import custom_report_service as service


class CustomReportSqlTests(SimpleTestCase):
    def test_params_are_bound_not_concatenated(self):
        sql, params = service.build_sql(
            "SELECT * FROM t WHERE a = $$code|Codi:X$$ AND b LIKE 'x%' AND c = $$code$$",
            {"code": "1' OR '1'='1"},
        )
        self.assertEqual(
            sql, "SELECT * FROM t WHERE a = %(p_code)s AND b LIKE 'x%%' AND c = %(p_code)s"
        )
        self.assertEqual(params, {"p_code": "1' OR '1'='1"})

    def test_missing_param_uses_default(self):
        _, params = service.build_sql("SELECT $$n:5$$, $$m$$", {})
        self.assertEqual(params, {"p_n": "5", "p_m": ""})

    def test_get_params(self):
        self.assertEqual(
            service.get_params("SELECT $$date_from|From:2026-01-01$$, $$Zone$$"),
            [
                {"name": "date_from", "label": "From", "default": "2026-01-01"},
                {"name": "zone", "label": "zone", "default": ""},
            ],
        )

    def test_validate_sql_rejects_writes_and_multiple_statements(self):
        for sql in (
            "",
            "DELETE FROM t",
            "UPDATE t SET a = 1",
            "WITH x AS (DELETE FROM t RETURNING *) SELECT * FROM x",
            "DROP TABLE t",
            "SELECT 1; SELECT 2",
        ):
            with self.subTest(sql=sql), self.assertRaises(service.CustomReportError):
                service.validate_sql(sql)

    def test_params_inside_quotes_comments_or_identifiers_are_rejected(self):
        # Dins d'un literal, el valor enllaçat tancaria la cadena: injecció per a usuaris de lectura.
        for sql in (
            "SELECT * FROM t WHERE name = '$$c$$'",
            "SELECT * FROM t WHERE name LIKE '%$$c$$%'",
            "SELECT * FROM t -- $$c$$\nWHERE 1 = 1",
            "SELECT * FROM t /* $$c$$ */",
            'SELECT "$$c$$" FROM t',
            "SELECT * FROM t WHERE a = E'$$c$$'",
        ):
            with self.subTest(sql=sql), self.assertRaises(service.CustomReportError):
                service.validate_sql(sql)

    def test_params_as_values_are_accepted(self):
        for sql in (
            "SELECT * FROM t WHERE code = $$c$$",
            "SELECT * FROM t WHERE d >= $$d|From:2026-01-01$$::date AND n IN ($$a$$, $$b$$)",
            "SELECT * FROM t WHERE name LIKE '%' || $$c$$ || '%'",
        ):
            with self.subTest(sql=sql):
                service.validate_sql(sql)

    def test_exports_do_not_produce_formulas(self):
        result = {"columns": ["a"], "rows": [["=HYPERLINK(\"http://x\")"], ["@SUM(1)"], [-5]]}
        content, _, _ = service.export(result, "csv")
        self.assertIn(b"'=HYPERLINK", content)
        self.assertIn(b"'@SUM(1)", content)
        self.assertIn(b"\r\n-5\r\n", content)

        import io
        from openpyxl import load_workbook
        content, _, _ = service.export(result, "xlsx")
        sheet = load_workbook(io.BytesIO(content)).active
        self.assertEqual(sheet["A2"].data_type, "s")
        self.assertEqual(sheet["A2"].value, '=HYPERLINK("http://x")')

    def test_validate_sql_accepts_select_and_strips_semicolon(self):
        self.assertEqual(service.validate_sql(" SELECT replace('a', 'a', 'b'); "), "SELECT replace('a', 'a', 'b')")

    @override_settings(CUSTOM_REPORTS_DB_ALIAS="not_configured")
    def test_not_configured(self):
        self.assertFalse(service.is_enabled())
        with self.assertRaises(service.CustomReportNotConfigured):
            service.get_connection()

    def test_export_formats(self):
        result = {"columns": ["a", "b"], "rows": [[1, None], [2, "x"]]}
        content, content_type, filename = service.export(result, "csv", "My report")
        self.assertTrue(filename.startswith("My_report_") and filename.endswith(".csv"))
        self.assertIn(b"a;b", content)
        content, _, filename = service.export(result, "xlsx", "My report")
        self.assertTrue(filename.endswith(".xlsx"))
        self.assertTrue(content.startswith(b"PK"))


# A les proves, la connexió d'informes és la de per defecte (dins la transacció del test).
@override_settings(CUSTOM_REPORTS_DB_ALIAS="default", CUSTOM_REPORTS_MAX_ROWS=3)
class CustomReportApiTests(TestCase):
    def setUp(self):
        self.editor = User.objects.create_user("editor")
        self.editor.user_permissions.add(Permission.objects.get(codename="change_query", content_type__app_label="explorer"))
        self.viewer = User.objects.create_user("viewer")
        self.viewer.user_permissions.add(Permission.objects.get(codename="view_query", content_type__app_label="explorer"))
        self.nobody = User.objects.create_user("nobody")

    def client_for(self, user):
        client = APIClient(HTTP_HOST="localhost")
        client.force_authenticate(user)
        return client

    def test_create_run_and_export(self):
        editor = self.client_for(self.editor)
        response = editor.post(
            "/statistics/custom-report/",
            {"title": "Series", "sql": "SELECT generate_series(1, $$n|Rows:2$$::int) AS g"},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        report_id = response.json()["id"]
        self.assertEqual(response.json()["params"], [{"name": "n", "label": "Rows", "default": "2"}])

        viewer = self.client_for(self.viewer)
        response = viewer.post(f"/statistics/custom-report/{report_id}/run/", {"params": {"n": "5"}}, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["columns"], ["g"])
        self.assertEqual(response.json()["rows"], [[1], [2], [3]])
        self.assertTrue(response.json()["truncated"])

        response = viewer.post(f"/statistics/custom-report/{report_id}/export/", {"format": "csv"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"g\r\n1\r\n2\r\n", response.content)

        response = viewer.get("/statistics/custom-report/")
        self.assertEqual(response.json()[0]["run_count"], 2)

    def test_run_is_read_only(self):
        response = self.client_for(self.editor).post(
            "/statistics/custom-report/run/",
            {"sql": "SELECT nextval(pg_get_serial_sequence('auth_user', 'id'))"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("read-only", response.json()["error"])

    def test_sql_errors_are_reported(self):
        response = self.client_for(self.editor).post(
            "/statistics/custom-report/run/", {"sql": "SELECT * FROM missing_table"}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("missing_table", response.json()["error"])

    def test_permissions(self):
        viewer = self.client_for(self.viewer)
        self.assertEqual(viewer.get("/statistics/custom-report/").status_code, 200)
        self.assertEqual(viewer.post("/statistics/custom-report/run/", {"sql": "SELECT 1"}, format="json").status_code, 403)
        self.assertEqual(
            viewer.post("/statistics/custom-report/", {"title": "x", "sql": "SELECT 1"}, format="json").status_code, 403
        )
        self.assertEqual(viewer.get("/statistics/custom-report/schema/").status_code, 403)

        nobody = self.client_for(self.nobody)
        self.assertEqual(nobody.get("/statistics/custom-report/").status_code, 403)
        self.assertEqual(nobody.get("/statistics/custom-report/status/").status_code, 403)
