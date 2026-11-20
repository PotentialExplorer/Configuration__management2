"""Тесты этапа 5: описание графа на языке D2."""

import contextlib
import io
import os
import pathlib
import re
import tempfile
import unittest

from depviz.__main__ import main
from depviz.apt_index import PackageIndex, parse_packages
from depviz.cli import ConfigError, parse_args
from depviz.d2 import quote, to_d2
from depviz.graph import build_graph
from depviz.sources import AptSource, GraphFileSource, load_test_repo

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
GRAPHS = FIXTURES / "graphs"
SAMPLE = FIXTURES / "ubuntu-noble-sample.packages"
EDGE_RE = re.compile(r'^"([^"]+)" -> "([^"]+)"')


def d2_of(name):
    """Граф тестового репозитория и его описание на D2."""
    source = GraphFileSource(load_test_repo(GRAPHS / f"{name}.txt"))
    graph = build_graph(source, "A")
    return graph, to_d2(graph)


def edges_in(text):
    """Множество рёбер, найденных в тексте D2."""
    return {EDGE_RE.match(line).groups() for line in text.splitlines()
            if EDGE_RE.match(line)}


class D2Test(unittest.TestCase):
    """Содержимое описания D2."""

    def test_all_edges(self):
        """Каждое ребро графа есть в D2, и только оно."""
        for name in ("chain", "diamond", "cycle", "complex", "missing"):
            graph, text = d2_of(name)
            expected = {(a, b) for a, deps in graph.edges.items()
                        for b in deps}
            self.assertEqual(edges_in(text), expected, name)

    def test_root_and_missing(self):
        """Корень залит цветом, отсутствующий пакет — пунктир."""
        _, text = d2_of("missing")
        self.assertIn('"A": {\n  style.fill: "#ffe08a"', text)
        self.assertIn('"X": {\n  style.stroke-dash: 4\n}', text)

    def test_cycle_edge(self):
        """Ребро, замыкающее цикл, подписано и выделено."""
        _, text = d2_of("cycle")
        self.assertIn('"C" -> "A": цикл {', text)
        self.assertIn('"C" -> "D"\n', text + "\n")

    def test_quote(self):
        """Имена с точками и плюсами берутся в кавычки."""
        self.assertEqual(quote("libapt-pkg6.0t64"), '"libapt-pkg6.0t64"')
        self.assertEqual(quote("libstdc++6"), '"libstdc++6"')

    def test_braces_balanced(self):
        """Фигурные скобки сбалансированы на реальном графе apt."""
        index = PackageIndex(parse_packages(SAMPLE.read_text()))
        graph = build_graph(AptSource(index, "apt"), "apt")
        text = to_d2(graph)
        self.assertEqual(text.count("{"), text.count("}"))
        self.assertEqual(len(edges_in(text)), graph.edge_count)


class OutputOptionTest(unittest.TestCase):
    """Параметр --output."""

    def test_writes_file(self):
        """Описание сохраняется в файл и выводится на экран."""
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = os.path.join(folder.name, "graph.d2")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main(["--test-mode", "--package", "A", "--repo",
                         str(GRAPHS / "chain.txt"), "--mode", "d2",
                         "--output", path])
        self.assertEqual(code, 0)
        with open(path, encoding="utf-8") as file:
            self.assertEqual(file.read(), out.getvalue())

    def test_errors(self):
        """--output без d2 и в несуществующую папку."""
        base = ["--test-mode", "--package", "A", "--repo",
                str(GRAPHS / "chain.txt")]
        with self.assertRaisesRegex(ConfigError, "--mode d2"):
            parse_args(base + ["--output", "x.d2"])
        with self.assertRaisesRegex(ConfigError, "не существует"):
            parse_args(base + ["--mode", "d2", "--output", "/no/x.d2"])


if __name__ == "__main__":
    unittest.main()
