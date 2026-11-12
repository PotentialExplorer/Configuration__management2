"""Разбор и проверка параметров командной строки."""

import argparse
import os
import re
from dataclasses import dataclass
from urllib.parse import urlparse

REAL_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9+.-]+$")
TEST_NAME_RE = re.compile(r"^[A-Z]+$")
VERSION_RE = re.compile(r"^(\d+:)?[0-9][A-Za-z0-9.+~-]*$")
URL_SCHEMES = ("http", "https", "file")
MODES = ("deps", "graph", "order")
DEFAULT_MODE = "graph"
NETWORK_SCHEMES = ("http", "https")
ARGPARSE_MESSAGES = {
    "unrecognized arguments": "неизвестные аргументы",
    "expected one argument": "ожидается одно значение",
    "argument ": "параметр ",
    "ignored explicit argument": "лишнее значение",
    "invalid choice": "недопустимое значение",
    "choose from": "допустимые",
}


class ConfigError(Exception):
    """Ошибка в параметрах командной строки."""


@dataclass
class Config:
    """Параметры, заданные пользователем.

    :ivar package: имя анализируемого пакета.
    :ivar repo: URL репозитория или путь к файлу тестового репозитория.
    :ivar test_mode: режим работы с тестовым репозиторием.
    :ivar version: версия пакета или ``None``.
    :ivar filter: подстрока для фильтрации пакетов или ``None``.
    :ivar mode: что выводить: ``deps`` — прямые зависимости,
        ``graph`` — граф с учётом транзитивности, ``order`` — порядок
        загрузки зависимостей.
    """

    package: str
    repo: str
    test_mode: bool = False
    version: str | None = None
    filter: str | None = None
    mode: str = DEFAULT_MODE


class RussianArgumentParser(argparse.ArgumentParser):
    """Парсер, сообщающий об ошибках через :class:`ConfigError`."""

    def error(self, message):
        """Превратить ошибку argparse в :class:`ConfigError`."""
        for english, russian in ARGPARSE_MESSAGES.items():
            message = message.replace(english, russian)
        raise ConfigError(message)


def build_parser():
    """Создать парсер аргументов командной строки."""
    parser = RussianArgumentParser(
        prog="depviz",
        description="Граф зависимостей пакетов Ubuntu (apt).",
    )
    parser.add_argument("--package", help="имя анализируемого пакета")
    parser.add_argument(
        "--repo",
        help="URL индекса Packages(.gz/.xz) или путь к тестовому файлу",
    )
    parser.add_argument(
        "--test-mode", action="store_true",
        help="работать с файлом тестового репозитория",
    )
    parser.add_argument("--version", help="версия пакета")
    parser.add_argument("--filter", help="исключать пакеты с подстрокой")
    parser.add_argument(
        "--mode", choices=MODES, default=DEFAULT_MODE,
        help="deps — прямые зависимости, graph — полный граф, "
        "order — порядок загрузки",
    )
    return parser


def parse_args(argv=None):
    """Разобрать и проверить аргументы.

    :raises ConfigError: если параметры заданы неверно.
    """
    ns = build_parser().parse_args(argv)
    config = Config(
        package=ns.package, repo=ns.repo, test_mode=ns.test_mode,
        version=ns.version, filter=ns.filter, mode=ns.mode,
    )
    validate(config)
    return config


def validate(config):
    """Проверить все параметры :class:`Config`.

    :raises ConfigError: при первой найденной ошибке.
    """
    _check_package(config)
    _check_repo(config)
    _check_version(config)
    _check_filter(config.filter)


def _check_package(config):
    """Проверить имя пакета."""
    if not config.package:
        raise ConfigError("не задано имя пакета (--package)")
    if config.test_mode:
        if not TEST_NAME_RE.match(config.package):
            raise ConfigError(
                f"имя пакета '{config.package}' в тестовом режиме должно "
                "состоять из больших латинских букв"
            )
    elif not REAL_NAME_RE.match(config.package):
        raise ConfigError(
            f"недопустимое имя пакета '{config.package}': разрешены "
            "строчные латинские буквы, цифры и знаки + . -"
        )


def _check_repo(config):
    """Проверить URL репозитория или путь к тестовому файлу."""
    if not config.repo:
        raise ConfigError("не задан репозиторий (--repo)")
    if config.test_mode:
        _check_test_file(config.repo)
    else:
        _check_url(config.repo)


def _check_test_file(path):
    """Проверить путь к файлу тестового репозитория."""
    if urlparse(path).scheme in URL_SCHEMES:
        raise ConfigError(
            "в тестовом режиме --repo должен быть путём к файлу, а не URL"
        )
    if not os.path.isfile(path):
        raise ConfigError(f"файл тестового репозитория '{path}' не найден")


def _check_url(url):
    """Проверить URL индекса пакетов."""
    parts = urlparse(url)
    if parts.scheme not in URL_SCHEMES:
        raise ConfigError(
            f"'{url}' не является URL (ожидается http://, https:// или "
            "file://); для файла тестового репозитория укажите --test-mode"
        )
    if parts.scheme in NETWORK_SCHEMES and not parts.netloc:
        raise ConfigError(f"в URL '{url}' не указан адрес сервера")
    if parts.scheme == "file" and not os.path.isfile(parts.path):
        raise ConfigError(f"файл '{parts.path}' из URL не найден")


def _check_version(config):
    """Проверить версию пакета."""
    if config.version is None:
        return
    if config.test_mode:
        raise ConfigError("версия пакета не используется в тестовом режиме")
    if not VERSION_RE.match(config.version):
        raise ConfigError(
            f"недопустимая версия '{config.version}': ожидается формат "
            "Debian, например 1.35+dfsg-3 или 2:9.1.0016-1"
        )


def _check_filter(substring):
    """Проверить подстроку фильтрации."""
    if substring is None:
        return
    if not substring or substring.strip() != substring or " " in substring:
        raise ConfigError(
            "подстрока фильтра (--filter) не может быть пустой "
            "или содержать пробелы"
        )
