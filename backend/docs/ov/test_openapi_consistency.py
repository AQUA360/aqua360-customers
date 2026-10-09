"""Autocontenido, no requiere BBDD ni Django.

Comprueba que las dos vistas del documento OpenAPI de la Oficina Virtual no
derivin:

- Tot el llistat de endpoints del `info.description` (taula "Resumen de
  endpoints") té un `path` real a la secció `paths:`.
- Tot `path` de la secció `paths:` està documentat a la taula del
  `info.description`.

Escrit perquè `manage.py test` el descobreixi automàticament: `docs/` i
`docs/ov/` són paquets (tenen `__init__.py`) i el fitxer compleix el patró
`test*.py`.
"""

from pathlib import Path
import re
import unittest

import yaml

SPEC_PATH = Path(__file__).resolve().parent / "openapi.yaml"


def _index_table_paths(info_description):
    """Torna el conjunt de `path` documentats a la taula del `info.description`."""
    paths = set()
    for line in info_description.splitlines():
        match = re.match(r"\s*\|\s*`(/[^`]+)`\s*\|", line)
        if match:
            paths.add(match.group(1))
    return paths


class OpenApiIndexConsistencyTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with SPEC_PATH.open() as spec_file:
            cls.spec = yaml.safe_load(spec_file)
        cls.documented_paths = set(cls.spec["paths"].keys())
        cls.index_paths = _index_table_paths(cls.spec["info"]["description"])

    def test_every_path_in_paths_is_documented_in_index_table(self):
        undocumented = sorted(self.documented_paths - self.index_paths)
        self.assertEqual(
            undocumented,
            [],
            "Endpoints presents a `paths:` però absents de la taula "
            "«Resumen de endpoints» del `info.description`: "
            + ", ".join(undocumented),
        )

    def test_every_index_table_row_has_a_real_path(self):
        orphan_rows = sorted(self.index_paths - self.documented_paths)
        self.assertEqual(
            orphan_rows,
            [],
            "Files de la taula «Resumen de endpoints» del `info.description` "
            "sense `path` corresponent a `paths:`: " + ", ".join(orphan_rows),
        )

    def test_download_endpoints_are_documented(self):
        self.assertTrue(
            "/ov/consumption/{id}/download/" in self.documented_paths,
            "Falta el path /ov/consumption/{id}/download/ a `paths:`",
        )
        self.assertTrue(
            "/ov/consumptions/download/" in self.documented_paths,
            "Falta el path /ov/consumptions/download/ a `paths:`",
        )