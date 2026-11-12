"""Точка входа: ``python -m depviz [параметры]``."""

import sys

from .apt_index import RepoError
from .cli import ConfigError, parse_args
from .graph import GraphError, build_graph, format_graph
from .order import format_order, load_order
from .sources import make_source

EXIT_USAGE = 2
EXIT_DATA = 1


def main(argv=None):
    """Запустить приложение и вернуть код завершения."""
    try:
        config = parse_args(argv)
    except ConfigError as error:
        print(f"ошибка: {error}", file=sys.stderr)
        return EXIT_USAGE
    try:
        print(run(config))
    except (RepoError, GraphError) as error:
        print(f"ошибка: {error}", file=sys.stderr)
        return EXIT_DATA
    return 0


def run(config):
    """Выполнить действие, выбранное параметром ``--mode``."""
    source = make_source(config)
    if config.mode == "deps":
        return "\n".join(source.direct_lines(config.package))
    graph = build_graph(source, config.package, config.filter)
    if config.mode == "order":
        return format_order(graph, load_order(graph))
    return format_graph(graph)


if __name__ == "__main__":
    sys.exit(main())
