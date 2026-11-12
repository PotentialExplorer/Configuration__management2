"""Источники прямых зависимостей: реальный индекс apt и тестовый файл.

Источник отвечает на один вопрос — «от каких пакетов напрямую зависит
пакет X» — и запоминает пакеты, которых нет в репозитории. Обход графа
(:mod:`depviz.graph`) работает с любым источником одинаково.

Формат файла тестового репозитория — по пакету на строку::

    A: B C
    B: D
    D:

Имена пакетов — большие латинские буквы, зависимости через пробел.
Пустые строки и строки, начинающиеся с символа решётки, пропускаются.
"""

import re

from .apt_index import RepoError, load_index

TEST_LINE_RE = re.compile(r"^(?P<name>[A-Z]+)\s*:(?P<deps>(\s+[A-Z]+)*)\s*$")
COMMENT_PREFIX = "#"


class GraphFileError(RepoError):
    """Ошибка в файле тестового репозитория."""


class AptSource:
    """Зависимости из индекса Packages реального репозитория."""

    def __init__(self, index, root, root_version=None):
        """Источник над :class:`~depviz.apt_index.PackageIndex`.

        Для корневого пакета берётся версия ``root_version``,
        для остальных — самая новая.
        """
        self.index = index
        self.root = root
        self.root_version = root_version
        self.missing = set()

    def record(self, name):
        """Запись индекса для пакета ``name``."""
        version = self.root_version if name == self.root else None
        return self.index.find(name, version)

    def direct_lines(self, name):
        """Строки отчёта о прямых зависимостях с версиями и видом."""
        record = self.record(name)
        lines = [f"{record.name} {record.version}: "
                 f"прямых зависимостей {len(record.dependencies)}"]
        lines.extend(
            f"  {group.kind}: {group}" for group in record.dependencies
        )
        return lines

    def dependencies(self, name):
        """Прямые зависимости пакета ``name`` (имена без повторов)."""
        if name not in self.index.versions:
            self.missing.add(name)
            return []
        names = []
        for group in self.record(name).dependencies:
            target = self.index.resolve(group)
            if target is None:
                target = group.alternatives[0].name
                self.missing.add(target)
            if target not in names:
                names.append(target)
        return names


class GraphFileSource:
    """Зависимости из файла тестового репозитория."""

    def __init__(self, graph):
        """Источник над словарём «пакет → список зависимостей»."""
        self.graph = graph
        self.missing = set()

    def direct_lines(self, name):
        """Строки отчёта о прямых зависимостях."""
        deps = self.dependencies(name)
        lines = [f"{name}: прямых зависимостей {len(deps)}"]
        lines.extend(f"  {dep}" for dep in deps)
        return lines

    def dependencies(self, name):
        """Прямые зависимости пакета ``name``."""
        if name not in self.graph:
            self.missing.add(name)
            return []
        return list(self.graph[name])


def load_test_repo(path):
    """Прочитать файл тестового репозитория.

    :raises GraphFileError: при ошибке чтения или формата.
    """
    try:
        with open(path, encoding="utf-8") as file:
            lines = file.read().splitlines()
    except (OSError, UnicodeDecodeError) as error:
        raise GraphFileError(f"не удалось прочитать '{path}': {error}") \
            from error
    graph = {}
    for number, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line or line.startswith(COMMENT_PREFIX):
            continue
        name, deps = _parse_test_line(line, number, path)
        if name in graph:
            raise GraphFileError(
                f"{path}, строка {number}: пакет {name} описан повторно"
            )
        graph[name] = deps
    return graph


def _parse_test_line(line, number, path):
    """Разобрать строку ``A: B C`` тестового репозитория."""
    match = TEST_LINE_RE.match(line)
    if not match:
        raise GraphFileError(
            f"{path}, строка {number}: ожидается 'A: B C' (имена — "
            f"большие латинские буквы), получено '{line}'"
        )
    return match.group("name"), match.group("deps").split()


def make_source(config):
    """Создать источник зависимостей по параметрам запуска."""
    if config.test_mode:
        graph = load_test_repo(config.repo)
        if config.package not in graph:
            raise GraphFileError(
                f"пакет {config.package} не описан в '{config.repo}'"
            )
        return GraphFileSource(graph)
    index = load_index(config.repo)
    index.find(config.package, config.version)
    return AptSource(index, config.package, config.version)
