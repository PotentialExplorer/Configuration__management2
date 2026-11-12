"""Точка входа: ``python -m depviz [параметры]``."""

import sys

from .apt_index import RepoError, load_index
from .cli import ConfigError, parse_args

EXIT_USAGE = 2
EXIT_DATA = 1


def main(argv=None):
    """Запустить приложение и вернуть код завершения."""
    try:
        config = parse_args(argv)
    except ConfigError as error:
        print(f"ошибка: {error}", file=sys.stderr)
        return EXIT_USAGE
    if config.test_mode:
        print("ошибка: тестовый режим ещё не реализован", file=sys.stderr)
        return EXIT_USAGE
    try:
        print_direct_dependencies(config)
    except RepoError as error:
        print(f"ошибка: {error}", file=sys.stderr)
        return EXIT_DATA
    return 0


def print_direct_dependencies(config):
    """Найти пакет в репозитории и вывести его прямые зависимости."""
    index = load_index(config.repo)
    record = index.find(config.package, config.version)
    groups = record.dependencies
    print(f"{record.name} {record.version}: "
          f"прямых зависимостей {len(groups)}")
    for group in groups:
        print(f"  {group.kind}: {group}")


if __name__ == "__main__":
    sys.exit(main())
