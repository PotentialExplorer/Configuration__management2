"""Порядок загрузки зависимостей.

Пакет можно установить только после всех его зависимостей, поэтому
порядок — это обратный обход в глубину (post-order) по графу: пакет
добавляется в список, когда обработаны все его зависимости. Корневой
пакет оказывается последним.

В цикле «все зависимости раньше» выполнить нельзя. Ребро в пакет,
который сейчас в стеке обхода, пропускается — цикл разрывается в том
месте, где обход в него вошёл.
"""

GRAY = "gray"
BLACK = "black"


def load_order(graph):
    """Вернуть список пакетов в порядке загрузки для графа ``graph``."""
    order, state = [], {}

    def visit(name):
        """Добавить зависимости ``name``, затем сам пакет."""
        state[name] = GRAY
        for dep in graph.edges.get(name, []):
            if dep not in state:
                visit(dep)
        state[name] = BLACK
        order.append(name)

    visit(graph.root)
    return order


def format_order(graph, order):
    """Текстовое представление порядка загрузки."""
    width = len(str(len(order)))
    lines = [
        f"Порядок загрузки зависимостей {graph.root} "
        f"(пакетов: {len(order)}):"
    ]
    for number, name in enumerate(order, start=1):
        mark = " (нет в репозитории)" if name in graph.missing else ""
        lines.append(f"  {number:>{width}}. {name}{mark}")
    for cycle in graph.cycles:
        lines.append("Цикл разорван: " + " -> ".join(cycle))
    return "\n".join(lines)
