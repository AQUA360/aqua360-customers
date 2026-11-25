"""Autocontingut, no requereix BBDD ni Django.

El document OpenAPI de l'Oficina Virtual existeix en dues versions:
`openapi.yaml` (castellà) i `openapi.ca.yaml` (català). Aquests tests
comproven que no derivin:

- A cada versió, tot endpoint de la taula de resum del `info.description` té
  un `path` real a la secció `paths:`, i tot `path` hi està documentat.
- Les dues versions tenen la mateixa estructura: mateixos paths, mètodes,
  paràmetres, cossos, respostes, esquemes, camps, enums i exemples. Només
  poden diferir els textos (`description`, `summary`, `title`) i els noms de
  les etiquetes (`tags`).

Escrit perquè `manage.py test` el descobreixi automàticament: `docs/` i
`docs/ov/` són paquets (tenen `__init__.py`) i el fitxer compleix el patró
`test*.py`.
"""

from pathlib import Path
import re
import unittest

import yaml

SPEC_DIR = Path(__file__).resolve().parent
SPEC_PATHS = {
    "es": SPEC_DIR / "openapi.yaml",
    "ca": SPEC_DIR / "openapi.ca.yaml",
}

# Claus de text lliure, que es tradueixen i per tant poden diferir entre versions.
TEXT_KEYS = {"description", "summary", "title"}

# Seccions de nivell superior que només porten text o metadades traduïdes.
TOP_LEVEL_TEXT_SECTIONS = {"info", "servers", "tags"}


def _load_spec(path):
    with path.open() as spec_file:
        return yaml.safe_load(spec_file)


def _index_table_paths(info_description):
    """Torna el conjunt de `path` documentats a la taula del `info.description`."""
    paths = set()
    for line in info_description.splitlines():
        match = re.match(r"\s*\|\s*`(/[^`]+)`\s*\|", line)
        if match:
            paths.add(match.group(1))
    return paths


def _structure(node):
    """Torna el node sense els textos traduïbles.

    Les etiquetes d'una operació (`tags`) es redueixen al seu nombre: el nom
    es tradueix, però cada operació ha de tenir les mateixes.
    """
    if isinstance(node, dict):
        result = {}
        for key, value in node.items():
            if key in TEXT_KEYS and isinstance(value, str):
                continue
            if key == "tags" and isinstance(value, list):
                result[key] = len(value)
                continue
            result[key] = _structure(value)
        return result
    if isinstance(node, list):
        return [_structure(item) for item in node]
    return node


def _differences(left, right, path="", limit=20):
    """Llista llegible (limitada) de les diferències entre dues estructures."""
    found = []

    def walk(a, b, where):
        if len(found) >= limit:
            return
        if isinstance(a, dict) and isinstance(b, dict):
            for key in sorted(set(a) | set(b), key=str):
                child = f"{where}/{key}"
                if key not in a:
                    found.append(f"{child}: només a la versió en català")
                elif key not in b:
                    found.append(f"{child}: només a la versió en castellà")
                else:
                    walk(a[key], b[key], child)
        elif isinstance(a, list) and isinstance(b, list):
            if len(a) != len(b):
                found.append(f"{where}: {len(a)} elements (es) vs {len(b)} (ca)")
                return
            for index, (item_a, item_b) in enumerate(zip(a, b)):
                walk(item_a, item_b, f"{where}[{index}]")
        elif a != b:
            found.append(f"{where}: {a!r} (es) vs {b!r} (ca)")

    walk(left, right, path)
    return found


class OpenApiIndexConsistencyTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.specs = {lang: _load_spec(path) for lang, path in SPEC_PATHS.items()}

    def test_every_path_in_paths_is_documented_in_index_table(self):
        for lang, spec in self.specs.items():
            with self.subTest(lang=lang):
                documented = set(spec["paths"].keys())
                index = _index_table_paths(spec["info"]["description"])
                undocumented = sorted(documented - index)
                self.assertEqual(
                    undocumented,
                    [],
                    f"[{lang}] Endpoints presents a `paths:` però absents de la "
                    "taula de resum del `info.description`: "
                    + ", ".join(undocumented),
                )

    def test_every_index_table_row_has_a_real_path(self):
        for lang, spec in self.specs.items():
            with self.subTest(lang=lang):
                documented = set(spec["paths"].keys())
                index = _index_table_paths(spec["info"]["description"])
                orphan_rows = sorted(index - documented)
                self.assertEqual(
                    orphan_rows,
                    [],
                    f"[{lang}] Files de la taula de resum del `info.description` "
                    "sense `path` corresponent a `paths:`: " + ", ".join(orphan_rows),
                )

    def test_download_endpoints_are_documented(self):
        for lang, spec in self.specs.items():
            with self.subTest(lang=lang):
                for path in ("/ov/consumption/{id}/download/", "/ov/consumptions/download/"):
                    self.assertIn(path, spec["paths"], f"[{lang}] Falta el path {path} a `paths:`")


class OpenApiTranslationsParityTests(unittest.TestCase):
    """Les versions en castellà i en català han de descriure la mateixa API."""

    @classmethod
    def setUpClass(cls):
        cls.es = _load_spec(SPEC_PATHS["es"])
        cls.ca = _load_spec(SPEC_PATHS["ca"])

    def test_same_top_level_sections(self):
        self.assertEqual(list(self.es.keys()), list(self.ca.keys()))

    def test_same_number_of_tags_and_servers(self):
        self.assertEqual(len(self.es.get("tags", [])), len(self.ca.get("tags", [])))
        self.assertEqual(len(self.es.get("servers", [])), len(self.ca.get("servers", [])))

    def test_same_structure(self):
        es = {k: v for k, v in self.es.items() if k not in TOP_LEVEL_TEXT_SECTIONS}
        ca = {k: v for k, v in self.ca.items() if k not in TOP_LEVEL_TEXT_SECTIONS}
        differences = _differences(_structure(es), _structure(ca))
        self.assertEqual(
            differences,
            [],
            "Les versions en castellà (openapi.yaml) i en català (openapi.ca.yaml) "
            "no descriuen la mateixa API. Qualsevol canvi s'ha de fer a les dues:\n"
            + "\n".join(differences),
        )

    def test_operations_use_declared_tags(self):
        for lang, spec in (("es", self.es), ("ca", self.ca)):
            declared = {tag["name"] for tag in spec.get("tags", [])}
            for path, operations in spec["paths"].items():
                for method, operation in operations.items():
                    if not isinstance(operation, dict):
                        continue
                    for tag in operation.get("tags", []):
                        with self.subTest(lang=lang, path=path, method=method):
                            self.assertIn(tag, declared)
