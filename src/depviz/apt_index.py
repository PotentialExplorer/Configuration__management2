"""Загрузка и разбор индекса пакетов репозитория Ubuntu (файл Packages).

Индекс — текст из блоков «поле: значение», разделённых пустой строкой
(формат RFC 822, Debian Policy 5.1). Строка, начинающаяся с пробела,
продолжает значение предыдущего поля. Зависимости берутся из полей
``Pre-Depends`` и ``Depends``: группы через запятую, альтернативы
внутри группы через ``|``, ограничение версии в скобках.
"""

import functools
import gzip
import lzma
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from . import debversion

GZIP_MAGIC = b"\x1f\x8b"
XZ_MAGIC = b"\xfd7zXZ\x00"
TIMEOUT_SECONDS = 60
DEPENDENCY_FIELDS = ("Pre-Depends", "Depends")
VERSION_KEY = functools.cmp_to_key(debversion.compare)
DEP_RE = re.compile(
    r"^\s*(?P<name>[a-z0-9][a-z0-9+.-]*)(?::[a-z0-9-]+)?"
    r"\s*(?:\((?P<constraint>[^)]*)\))?\s*(?:\[[^\]]*\])?\s*$"
)


class RepoError(Exception):
    """Ошибка загрузки индекса или поиска пакета в нём."""


@dataclass
class Dependency:
    """Одна альтернатива зависимости: имя и ограничение версии."""

    name: str
    constraint: str = ""

    def __str__(self):
        """Запись как в индексе: ``libc6 (>= 2.38)``."""
        return f"{self.name} ({self.constraint})" if self.constraint \
            else self.name


@dataclass
class DependencyGroup:
    """Группа альтернатив ``a | b`` и поле, откуда она взята."""

    alternatives: list
    kind: str = "Depends"

    def __str__(self):
        """Запись как в индексе: ``a (>= 1) | b``."""
        return " | ".join(str(dep) for dep in self.alternatives)


@dataclass
class PackageRecord:
    """Запись о версии пакета из индекса."""

    name: str
    version: str
    dependencies: list = field(default_factory=list)
    provides: list = field(default_factory=list)


def fetch(url):
    """Скачать индекс по URL и вернуть его текст.

    Сжатые индексы (``Packages.gz``, ``Packages.xz``) распознаются
    по сигнатуре и распаковываются.

    :raises RepoError: при ошибке сети или распаковки.
    """
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT_SECONDS) as resp:
            data = resp.read()
    except urllib.error.HTTPError as error:
        raise RepoError(f"сервер ответил {error.code} для {url}") from error
    except (urllib.error.URLError, OSError) as error:
        raise RepoError(f"не удалось загрузить {url}: {error}") from error
    return _decode(data, url)


def _decode(data, url):
    """Распаковать (при необходимости) и декодировать индекс."""
    try:
        if data.startswith(GZIP_MAGIC):
            data = gzip.decompress(data)
        elif data.startswith(XZ_MAGIC):
            data = lzma.decompress(data)
    except (OSError, EOFError, lzma.LZMAError) as error:
        raise RepoError(f"повреждённый архив индекса {url}") from error
    return data.decode("utf-8", errors="replace")


def parse_packages(text):
    """Разобрать текст индекса в список :class:`PackageRecord`."""
    records = []
    for block in re.split(r"\n\s*\n", text):
        fields = _parse_block(block)
        if "Package" in fields and "Version" in fields:
            records.append(_make_record(fields))
    return records


def _parse_block(block):
    """Разобрать один блок «поле: значение» с продолжениями строк."""
    fields, current = {}, None
    for line in block.splitlines():
        if line[:1] in (" ", "\t") and current:
            fields[current] += " " + line.strip()
        elif ":" in line:
            current, value = line.split(":", 1)
            fields[current] = value.strip()
    return fields


def _make_record(fields):
    """Создать запись о пакете из словаря полей."""
    dependencies = []
    for kind in DEPENDENCY_FIELDS:
        dependencies.extend(parse_depends(fields.get(kind, ""), kind))
    provides = [
        group.alternatives[0].name
        for group in parse_depends(fields.get("Provides", ""), "Provides")
    ]
    return PackageRecord(
        fields["Package"], fields["Version"], dependencies, provides,
    )


def parse_depends(value, kind="Depends"):
    """Разобрать значение поля зависимостей в список групп.

    ``"libc6 (>= 2.38), base-passwd | adduser"`` → две группы,
    во второй две альтернативы. Квалификатор архитектуры ``:any``
    отбрасывается.
    """
    groups = []
    for chunk in value.split(","):
        alternatives = [
            _parse_dependency(item) for item in chunk.split("|")
            if item.strip()
        ]
        alternatives = [dep for dep in alternatives if dep]
        if alternatives:
            groups.append(DependencyGroup(alternatives, kind))
    return groups


def _parse_dependency(text):
    """Разобрать одну альтернативу; ``None``, если не распознана."""
    match = DEP_RE.match(text)
    if not match:
        return None
    constraint = " ".join((match.group("constraint") or "").split())
    return Dependency(match.group("name"), constraint)


class PackageIndex:
    """Индекс пакетов: поиск версий и виртуальных пакетов."""

    def __init__(self, records):
        """Построить индекс из списка :class:`PackageRecord`."""
        self.versions = {}
        self.providers = {}
        for record in records:
            self.versions.setdefault(record.name, []).append(record)
            for virtual in record.provides:
                self.providers.setdefault(virtual, []).append(record.name)

    def find(self, name, version=None):
        """Найти пакет ``name`` нужной (или самой новой) версии.

        :raises RepoError: если пакета или версии нет в индексе.
        """
        records = self.versions.get(name)
        if not records:
            raise RepoError(f"пакет '{name}' не найден в репозитории")
        if version is None:
            return max(records, key=lambda rec: VERSION_KEY(rec.version))
        for record in records:
            if record.version == version:
                return record
        available = ", ".join(sorted(r.version for r in records))
        raise RepoError(
            f"версия {version} пакета '{name}' не найдена; "
            f"доступные версии: {available}"
        )

    def resolve(self, group):
        """Выбрать пакет для группы альтернатив, как apt по умолчанию.

        Берётся первая альтернатива, которая есть в индексе как
        реальный пакет; иначе первая, которую предоставляет
        (``Provides``) другой пакет. ``None`` — ничего не найдено.
        """
        for dep in group.alternatives:
            if dep.name in self.versions:
                return dep.name
        for dep in group.alternatives:
            if dep.name in self.providers:
                return self.providers[dep.name][0]
        return None


def load_index(url):
    """Скачать и разобрать индекс, вернуть :class:`PackageIndex`."""
    records = parse_packages(fetch(url))
    if not records:
        raise RepoError(f"по адресу {url} нет ни одного пакета")
    return PackageIndex(records)
