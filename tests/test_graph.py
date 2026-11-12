"""Тесты этапа 3: граф зависимостей, фильтр, циклы, тестовый режим."""

import contextlib
import io
import pathlib
import unittest

from depviz.__main__ import main
from depviz.apt_index import PackageIndex, parse_packages
from depviz.graph import GraphError, build_graph
from depviz.sources import (
    AptSource, GraphFileError, GraphFileSource, load_test_repo,
)

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
GRAPHS = FIXTURES / "graphs"
SAMPLE = FIXTURES / "ubuntu-noble-sample.packages"


def graph_of(name, root="A", substring=None):
    """Построить граф для тестового репозитория ``name``.txt."""
    source = GraphFileSource(load_test_repo(GRAPHS / f"{name}.txt"))
    return build_graph(source, root, substring)


class TestModeTest(unittest.TestCase):
    """Различные случаи тестового репозитория."""

    def test_chain(self):
        """Цепочка: все пакеты по порядку обхода."""
        graph = graph_of("chain")
        self.assertEqual(list(graph.edges), ["A", "B", "C", "D"])
        self.assertEqual(graph.cycles, [])

    def test_diamond(self):
        """Общая зависимость обходится один раз."""
        graph = graph_of("diamond")
        self.assertEqual(sorted(graph.edges), ["A", "B", "C", "D", "E"])
        self.assertEqual(graph.edge_count, 5)

    def test_cycle(self):
        """Цикл найден, обход завершился."""
        graph = graph_of("cycle")
        self.assertEqual(graph.cycles, [["A", "B", "C", "A"]])
        self.assertIn("D", graph.edges)

    def test_self_loop(self):
        """Зависимость пакета от самого себя."""
        self.assertEqual(graph_of("self_loop").cycles, [["A", "A"]])

    def test_missing(self):
        """Неописанный пакет попадает в граф как отсутствующий."""
        graph = graph_of("missing")
        self.assertEqual(graph.missing, {"X"})
        self.assertEqual(graph.edges["X"], [])

    def test_two_cycles(self):
        """В большом графе два независимых цикла."""
        graph = graph_of("complex")
        self.assertEqual(graph.cycles, [["B", "E", "B"],
                                        ["G", "J", "G"]])
        self.assertEqual(len(graph.edges), 11)

    def test_filter(self):
        """Фильтр убирает пакет и всё, что достижимо только через него."""
        graph = graph_of("complex", substring="G")
        self.assertNotIn("G", graph.edges)
        self.assertNotIn("J", graph.edges)
        self.assertEqual(graph.filtered, {"G"})
        self.assertEqual(graph.cycles, [["B", "E", "B"]])

    def test_filter_root(self):
        """Корень, исключённый фильтром, — ошибка."""
        with self.assertRaises(GraphError):
            graph_of("chain", substring="A")

    def test_start_from_middle(self):
        """Граф можно строить от любого пакета."""
        self.assertEqual(list(graph_of("chain", "C").edges), ["C", "D"])


class TestRepoFileTest(unittest.TestCase):
    """Ошибки файла тестового репозитория."""

    def test_bad_line(self):
        """Строка с маленькими буквами — ошибка с номером строки."""
        with self.assertRaisesRegex(GraphFileError, "строка 3"):
            load_test_repo(GRAPHS / "broken.txt")

    def test_missing_file(self):
        """Файла нет."""
        with self.assertRaisesRegex(GraphFileError, "не удалось"):
            load_test_repo(GRAPHS / "no_such.txt")


class AptGraphTest(unittest.TestCase):
    """Граф по реальным данным Ubuntu 24.04."""

    def setUp(self):
        """Загрузить индекс."""
        self.index = PackageIndex(parse_packages(SAMPLE.read_text()))

    def build(self, root, substring=None):
        """Построить граф пакета ``root``."""
        return build_graph(AptSource(self.index, root), root, substring)

    def test_tar(self):
        """tar: 7 пакетов и реальный цикл libc6 <-> libgcc-s1."""
        graph = self.build("tar")
        self.assertEqual(sorted(graph.edges), [
            "gcc-14-base", "libacl1", "libc6", "libgcc-s1",
            "libpcre2-8-0", "libselinux1", "tar",
        ])
        self.assertEqual(graph.cycles, [["libc6", "libgcc-s1", "libc6"]])

    def test_virtual_package(self):
        """Виртуальный awk заменяется на mawk."""
        graph = self.build("base-files")
        self.assertIn("mawk", graph.edges["base-files"])

    def test_filter_lib(self):
        """Фильтр 'lib' оставляет только пакеты без 'lib' в имени."""
        graph = self.build("apt", "lib")
        self.assertTrue(all("lib" not in name for name in graph.edges))
        self.assertIn("libc6", graph.filtered)


class MainGraphTest(unittest.TestCase):
    """Вывод графа через командную строку."""

    def test_cycle_output(self):
        """В выводе есть рёбра и раздел с циклами."""
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main(["--test-mode", "--package", "A", "--repo",
                         str(GRAPHS / "cycle.txt")])
        self.assertEqual(code, 0)
        text = out.getvalue()
        self.assertIn("  C -> A, D", text)
        self.assertIn("  A -> B -> C -> A", text)


if __name__ == "__main__":
    unittest.main()
