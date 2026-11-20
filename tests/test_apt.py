"""Тесты этапа 2: индекс apt, версии Debian, прямые зависимости."""

import contextlib
import gzip
import io
import lzma
import os
import pathlib
import tempfile
import unittest

from depviz.__main__ import main
from depviz.apt_index import (
    PackageIndex, RepoError, fetch, load_index, parse_depends,
    parse_packages,
)
from depviz.debversion import compare

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
SAMPLE = FIXTURES / "ubuntu-noble-sample.packages"
MULTI = FIXTURES / "multi-version.packages"


def url_of(path):
    """URL вида file:// для локального файла."""
    return pathlib.Path(path).resolve().as_uri()


class VersionTest(unittest.TestCase):
    """Сравнение версий Debian."""

    def test_order(self):
        """Версии упорядочены как в dpkg."""
        ordered = ["1.0~rc1", "1.0", "1.0-1", "1.0a", "1.0+b1",
                   "1.0.1", "1.10", "1:0.9"]
        for low, high in zip(ordered, ordered[1:]):
            self.assertLess(compare(low, high), 0, (low, high))
            self.assertGreater(compare(high, low), 0, (high, low))

    def test_equal(self):
        """Ведущие нули и нулевая эпоха не влияют."""
        self.assertEqual(compare("1.00", "1.0"), 0)
        self.assertEqual(compare("0:1.0", "1.0"), 0)


class ParseTest(unittest.TestCase):
    """Разбор полей и блоков индекса."""

    def test_depends(self):
        """Группы, альтернативы, ограничения, квалификаторы."""
        groups = parse_depends(
            "libc6 (>= 2.38), base-passwd (>= 3.6.1) | adduser, "
            "python3:any, foo [amd64]"
        )
        self.assertEqual([str(g) for g in groups], [
            "libc6 (>= 2.38)", "base-passwd (>= 3.6.1) | adduser",
            "python3", "foo",
        ])

    def test_continuation_lines(self):
        """Значение поля может продолжаться на следующей строке."""
        records = parse_packages(MULTI.read_text())
        app = [r for r in records if r.version == "1.10-1"][0]
        self.assertEqual([str(g) for g in app.dependencies],
                         ["demo-lib (>= 1.10)", "demo-extra | demo-alt"])

    def test_pre_depends_first(self):
        """Pre-Depends и Depends помечены своим видом."""
        index = PackageIndex(parse_packages(SAMPLE.read_text()))
        kinds = [g.kind for g in index.find("bash").dependencies]
        self.assertEqual(kinds, ["Pre-Depends", "Pre-Depends",
                                 "Depends", "Depends"])


class IndexTest(unittest.TestCase):
    """Поиск пакетов и выбор альтернатив."""

    def setUp(self):
        """Загрузить индексы из файлов."""
        self.multi = PackageIndex(parse_packages(MULTI.read_text()))
        self.sample = PackageIndex(parse_packages(SAMPLE.read_text()))

    def test_latest_version(self):
        """Без версии берётся самая новая по правилам Debian."""
        self.assertEqual(self.multi.find("demo-app").version, "1.10-1")

    def test_exact_version(self):
        """Заданная версия находится точно."""
        record = self.multi.find("demo-app", "1.10~rc1-1")
        self.assertEqual([str(g) for g in record.dependencies],
                         ["demo-lib"])

    def test_missing(self):
        """Нет пакета или нет версии — понятная ошибка."""
        with self.assertRaisesRegex(RepoError, "не найден"):
            self.multi.find("nothing")
        with self.assertRaisesRegex(RepoError, "доступные версии"):
            self.multi.find("demo-app", "9.9")

    def test_resolve(self):
        """Первая существующая альтернатива или поставщик Provides."""
        groups = parse_depends("nothing | demo-lib, demo-alt, absent")
        names = [self.multi.resolve(g) for g in groups]
        self.assertEqual(names, ["demo-lib", "demo-provider", None])

    def test_virtual_awk(self):
        """Реальный случай: base-files требует awk, его даёт mawk."""
        group = self.sample.find("base-files").dependencies[0]
        self.assertEqual(str(group), "awk")
        self.assertEqual(self.sample.resolve(group), "mawk")


class FetchTest(unittest.TestCase):
    """Загрузка индекса по URL, в том числе сжатого."""

    def write_temp(self, data, suffix):
        """Записать байты во временный файл и вернуть его URL."""
        handle, path = tempfile.mkstemp(suffix=suffix)
        with os.fdopen(handle, "wb") as file:
            file.write(data)
        self.addCleanup(os.remove, path)
        return url_of(path)

    def test_plain_gzip_xz(self):
        """Обычный, gzip и xz индексы читаются одинаково."""
        raw = SAMPLE.read_bytes()
        for data, suffix in ((raw, ""), (gzip.compress(raw), ".gz"),
                             (lzma.compress(raw), ".xz")):
            index = load_index(self.write_temp(data, suffix))
            self.assertIn("tar", index.versions)

    def test_errors(self):
        """Нет файла, битый архив, пустой индекс."""
        with self.assertRaisesRegex(RepoError, "не удалось загрузить"):
            fetch("file:///no/such/Packages")
        broken = self.write_temp(b"\x1f\x8bbroken", ".gz")
        with self.assertRaisesRegex(RepoError, "повреждённый"):
            fetch(broken)
        with self.assertRaisesRegex(RepoError, "нет ни одного"):
            load_index(self.write_temp(b"hello\n", ""))


class MainTest(unittest.TestCase):
    """Вывод прямых зависимостей."""

    def run_main(self, argv):
        """Запустить main и вернуть (код, stdout, stderr)."""
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(err):
            code = main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_tar(self):
        """Прямые зависимости tar из реальных данных Ubuntu 24.04."""
        code, out, _ = self.run_main(
            ["--package", "tar", "--repo", url_of(SAMPLE),
             "--mode", "deps"])
        self.assertEqual(code, 0)
        self.assertEqual(out.splitlines(), [
            "tar 1.35+dfsg-3ubuntu0.4: прямых зависимостей 3",
            "  Pre-Depends: libacl1 (>= 2.2.23)",
            "  Pre-Depends: libc6 (>= 2.38)",
            "  Pre-Depends: libselinux1 (>= 3.1~)",
        ])

    def test_unknown_version(self):
        """Неизвестная версия — код 1 и список доступных."""
        code, _, err = self.run_main(
            ["--package", "tar", "--repo", url_of(SAMPLE),
             "--version", "1.0"])
        self.assertEqual(code, 1)
        self.assertIn("доступные версии: 1.35+dfsg-3ubuntu0.4", err)


if __name__ == "__main__":
    unittest.main()
