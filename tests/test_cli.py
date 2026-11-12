"""Тесты этапа 1: параметры командной строки и их проверка."""

import contextlib
import io
import os
import tempfile
import unittest

from depviz.__main__ import main
from depviz.cli import ConfigError, parse_args

URL = "http://archive.ubuntu.com/ubuntu/dists/noble/main/binary-amd64/" \
    "Packages.gz"


class ParseArgsTest(unittest.TestCase):
    """Корректные наборы параметров."""

    def test_real_mode(self):
        """Все параметры реального режима."""
        config = parse_args([
            "--package", "tar", "--repo", URL,
            "--version", "1.35+dfsg-3", "--filter", "lib",
        ])
        self.assertEqual(config.package, "tar")
        self.assertFalse(config.test_mode)
        self.assertEqual(config.version, "1.35+dfsg-3")
        self.assertEqual(config.filter, "lib")

    def test_epoch_version(self):
        """Версия с эпохой."""
        config = parse_args(["--package", "vim", "--repo", URL,
                             "--version", "2:9.1.0016-1ubuntu7"])
        self.assertEqual(config.version, "2:9.1.0016-1ubuntu7")

    def test_test_mode(self):
        """Тестовый режим с существующим файлом."""
        handle, path = tempfile.mkstemp()
        os.close(handle)
        self.addCleanup(os.remove, path)
        config = parse_args(["--package", "A", "--repo", path,
                             "--test-mode"])
        self.assertTrue(config.test_mode)

    def test_key_value_output(self):
        """Параметры печатаются в формате ключ=значение."""
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main(["--package", "tar", "--repo", URL])
        self.assertEqual(code, 0)
        self.assertEqual(out.getvalue().splitlines(), [
            "package=tar", f"repo={URL}", "test_mode=false",
            "version=<не задан>", "filter=<не задан>",
        ])


class ErrorTest(unittest.TestCase):
    """Ошибки для каждого параметра."""

    def assert_error(self, argv, fragment):
        """Проверить, что разбор падает с сообщением ``fragment``."""
        with self.assertRaises(ConfigError) as caught:
            parse_args(argv)
        self.assertIn(fragment, str(caught.exception))

    def test_package(self):
        """Имя пакета: нет, недопустимые символы, тестовый режим."""
        self.assert_error(["--repo", URL], "--package")
        self.assert_error(["--package", "Tar!", "--repo", URL],
                          "недопустимое имя")
        self.assert_error(["--package", "tar", "--repo", __file__,
                           "--test-mode"], "больших латинских")

    def test_repo(self):
        """Репозиторий: нет, не URL, нет сервера, нет файла."""
        self.assert_error(["--package", "tar"], "--repo")
        self.assert_error(["--package", "tar", "--repo", "C:/x"],
                          "не является URL")
        self.assert_error(["--package", "tar", "--repo", "http://"],
                          "адрес сервера")
        self.assert_error(["--package", "tar", "--repo",
                           "file:///no/such"], "не найден")
        self.assert_error(["--package", "A", "--repo", "/no/such",
                           "--test-mode"], "не найден")
        self.assert_error(["--package", "A", "--repo", URL,
                           "--test-mode"], "а не URL")

    def test_version(self):
        """Версия: неверный формат, тестовый режим."""
        self.assert_error(["--package", "tar", "--repo", URL,
                           "--version", "abc"], "недопустимая версия")
        self.assert_error(["--package", "A", "--repo", __file__,
                           "--test-mode", "--version", "1.0"],
                          "тестовом режиме")

    def test_filter(self):
        """Фильтр: пустой или с пробелами."""
        self.assert_error(["--package", "tar", "--repo", URL,
                           "--filter", ""], "фильтра")
        self.assert_error(["--package", "tar", "--repo", URL,
                           "--filter", "a b"], "фильтра")

    def test_unknown_argument(self):
        """Неизвестный аргумент."""
        self.assert_error(["--package", "tar", "--repo", URL, "--x"],
                          "неизвестные аргументы")

    def test_exit_code(self):
        """При ошибке main возвращает код 2 и пишет в stderr."""
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = main(["--package", "tar"])
        self.assertEqual(code, 2)
        self.assertIn("ошибка:", err.getvalue())


if __name__ == "__main__":
    unittest.main()
