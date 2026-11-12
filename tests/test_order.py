"""Тесты этапа 4: порядок загрузки зависимостей."""

import contextlib
import io
import pathlib
import unittest

from depviz.__main__ import main
from depviz.apt_index import PackageIndex, parse_packages
from depviz.graph import build_graph
from depviz.order import load_order
from depviz.sources import AptSource, GraphFileSource, load_test_repo

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
GRAPHS = FIXTURES / "graphs"
SAMPLE = FIXTURES / "ubuntu-noble-sample.packages"


def order_of(name, root="A", substring=None):
    """Граф и порядок загрузки для тестового репозитория."""
    source = GraphFileSource(load_test_repo(GRAPHS / f"{name}.txt"))
    graph = build_graph(source, root, substring)
    return graph, load_order(graph)


def broken_edges(graph):
    """Рёбра, по которым циклы разрываются (последнее ребро цикла)."""
    return {(cycle[-2], cycle[-1]) for cycle in graph.cycles}


class OrderTest(unittest.TestCase):
    """Порядок загрузки на тестовых репозиториях."""

    def assert_topological(self, graph, order):
        """Каждая зависимость раньше пакета, кроме разорванных рёбер."""
        position = {name: index for index, name in enumerate(order)}
        skip = broken_edges(graph)
        for name, deps in graph.edges.items():
            for dep in deps:
                if (name, dep) not in skip:
                    self.assertLess(position[dep], position[name],
                                    (dep, name))
        self.assertEqual(order[-1], graph.root)
        self.assertEqual(len(order), len(set(order)))

    def test_chain(self):
        """Цепочка загружается с конца."""
        _, order = order_of("chain")
        self.assertEqual(order, ["D", "C", "B", "A"])

    def test_diamond(self):
        """Общая зависимость загружается один раз и раньше всех."""
        graph, order = order_of("diamond")
        self.assertEqual(order, ["E", "D", "B", "C", "A"])
        self.assert_topological(graph, order)

    def test_cycle(self):
        """Цикл разрывается, каждый пакет встречается один раз."""
        graph, order = order_of("cycle")
        self.assertEqual(order, ["D", "C", "B", "A"])
        self.assert_topological(graph, order)

    def test_complex_and_filter(self):
        """Большой граф и он же с фильтром."""
        for substring in (None, "G", "B"):
            graph, order = order_of("complex", substring=substring)
            self.assert_topological(graph, order)
            if substring:
                self.assertNotIn(substring, order)

    def test_missing(self):
        """Отсутствующий пакет тоже попадает в порядок."""
        _, order = order_of("missing")
        self.assertEqual(order, ["B", "X", "A"])


class AptOrderTest(unittest.TestCase):
    """Порядок на реальных данных совпадает с apt-get install -s."""

    def test_tar_matches_apt(self):
        """Порядок Conf из apt-get для tar на Ubuntu 24.04."""
        index = PackageIndex(parse_packages(SAMPLE.read_text()))
        graph = build_graph(AptSource(index, "tar"), "tar")
        self.assertEqual(load_order(graph), [
            "gcc-14-base", "libgcc-s1", "libc6", "libacl1",
            "libpcre2-8-0", "libselinux1", "tar",
        ])

    def test_output(self):
        """Вывод через командную строку."""
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            main(["--test-mode", "--package", "A", "--repo",
                  str(GRAPHS / "cycle.txt"), "--mode", "order"])
        lines = out.getvalue().splitlines()
        self.assertEqual(lines[1:5], ["  1. D", "  2. C", "  3. B",
                                      "  4. A"])
        self.assertEqual(lines[5], "Цикл разорван: A -> B -> C -> A")


if __name__ == "__main__":
    unittest.main()
