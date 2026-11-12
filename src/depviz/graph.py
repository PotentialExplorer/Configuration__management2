"""Построение графа зависимостей рекурсивным обходом в глубину (DFS).

Каждый пакет посещается один раз. Цвета вершин:

* «серый» — пакет на текущем пути обхода (в стеке рекурсии);
* «чёрный» — пакет и все его зависимости уже обработаны.

Ребро в серую вершину означает цикл: он записывается, но обход по нему
не продолжается, поэтому циклические зависимости не приводят к
бесконечной рекурсии. Пакеты, имя которых содержит подстроку фильтра,
в граф не попадают и не обходятся.
"""

from dataclasses import dataclass, field

GRAY = "gray"
BLACK = "black"


class GraphError(Exception):
    """Граф невозможно построить для заданных параметров."""


@dataclass
class DependencyGraph:
    """Граф зависимостей.

    :ivar root: корневой пакет.
    :ivar edges: пакет → список прямых зависимостей; порядок ключей —
        порядок обнаружения при обходе.
    :ivar cycles: найденные циклы, каждый — путь от пакета до него же.
    :ivar filtered: пакеты, исключённые фильтром.
    :ivar missing: пакеты, которых нет в репозитории.
    """

    root: str
    edges: dict = field(default_factory=dict)
    cycles: list = field(default_factory=list)
    filtered: set = field(default_factory=set)
    missing: set = field(default_factory=set)

    @property
    def edge_count(self):
        """Число рёбер графа."""
        return sum(len(deps) for deps in self.edges.values())


class _Builder:
    """Состояние одного обхода графа."""

    def __init__(self, source, root, substring):
        """Подготовить обход от пакета ``root``."""
        self.source = source
        self.substring = substring
        self.graph = DependencyGraph(root)
        self.state = {}
        self.path = []

    def excluded(self, name):
        """Исключён ли пакет фильтром."""
        return bool(self.substring) and self.substring in name

    def visit(self, name):
        """Рекурсивно обойти пакет ``name`` и его зависимости."""
        self.state[name] = GRAY
        self.path.append(name)
        self.graph.edges[name] = []
        for dep in self.source.dependencies(name):
            if self.excluded(dep):
                self.graph.filtered.add(dep)
                continue
            self.graph.edges[name].append(dep)
            status = self.state.get(dep)
            if status is None:
                self.visit(dep)
            elif status == GRAY:
                start = self.path.index(dep)
                self.graph.cycles.append(self.path[start:] + [dep])
        self.path.pop()
        self.state[name] = BLACK


def build_graph(source, root, substring=None):
    """Построить граф зависимостей пакета ``root``.

    :param source: источник прямых зависимостей (apt или тестовый).
    :param substring: пакеты с этой подстрокой в имени пропускаются.
    :raises GraphError: если корневой пакет исключён фильтром.
    """
    builder = _Builder(source, root, substring)
    if builder.excluded(root):
        raise GraphError(
            f"пакет {root} сам содержит подстроку '{substring}' "
            "и исключён фильтром"
        )
    builder.visit(root)
    builder.graph.missing = set(source.missing)
    return builder.graph


def format_graph(graph):
    """Текстовое представление графа: строки ``пакет -> зависимости``."""
    lines = [
        f"Граф зависимостей {graph.root}: пакетов {len(graph.edges)}, "
        f"связей {graph.edge_count}"
    ]
    for name, deps in graph.edges.items():
        mark = " (нет в репозитории)" if name in graph.missing else ""
        targets = ", ".join(deps) if deps else "нет зависимостей"
        lines.append(f"  {name}{mark} -> {targets}")
    lines.extend(_format_extras(graph))
    return "\n".join(lines)


def _format_extras(graph):
    """Строки о циклах и исключённых пакетах."""
    lines = []
    if graph.cycles:
        lines.append(f"Циклы ({len(graph.cycles)}):")
        lines.extend("  " + " -> ".join(c) for c in graph.cycles)
    if graph.filtered:
        names = ", ".join(sorted(graph.filtered))
        lines.append(f"Исключены фильтром: {names}")
    return lines
