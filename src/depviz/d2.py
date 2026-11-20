"""Текстовое представление графа на языке диаграмм D2 (https://d2lang.com).

Имена пакетов всегда берутся в кавычки: точка в D2 означает
вложенность (``a.b`` — фигура ``b`` внутри ``a``), а в именах пакетов
Debian точки встречаются часто (``libapt-pkg6.0t64``).

Оформление:

* корневой пакет выделен заливкой;
* пакеты, которых нет в репозитории, — пунктирной рамкой;
* рёбра, замыкающие цикл, — красным пунктиром.
"""

ROOT_FILL = "#ffe08a"
CYCLE_STROKE = "#d33c3c"
DASH = 4
INDENT = "  "


def quote(name):
    """Имя пакета в кавычках, безопасное для D2."""
    escaped = name.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def to_d2(graph):
    """Вернуть описание графа ``graph`` на языке D2."""
    lines = ["direction: down", ""]
    lines.extend(_block(quote(graph.root),
                        [f'style.fill: "{ROOT_FILL}"', "style.bold: true"]))
    for name in sorted(graph.missing):
        lines.extend(_block(quote(name), [f"style.stroke-dash: {DASH}"]))
    lines.append("")
    closing = {(cycle[-2], cycle[-1]) for cycle in graph.cycles}
    for name, deps in graph.edges.items():
        for dep in deps:
            lines.extend(_edge(name, dep, (name, dep) in closing))
    return "\n".join(lines)


def _edge(source, target, closes_cycle):
    """Строки D2 для одного ребра."""
    edge = f"{quote(source)} -> {quote(target)}"
    if not closes_cycle:
        return [edge]
    return _block(edge, [
        f'style.stroke: "{CYCLE_STROKE}"',
        f"style.stroke-dash: {DASH}",
    ], label="цикл")


def _block(head, attributes, label=""):
    """Объект D2 с подписью и вложенными атрибутами в скобках."""
    opening = f"{head}: {label} {{" if label else f"{head}: {{"
    return [opening] + [INDENT + item for item in attributes] + ["}"]
