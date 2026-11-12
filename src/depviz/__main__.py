"""Точка входа: ``python -m depviz [параметры]``."""

import sys

from .cli import ConfigError, parse_args

EXIT_USAGE = 2


def main(argv=None):
    """Запустить приложение и вернуть код завершения."""
    try:
        config = parse_args(argv)
    except ConfigError as error:
        print(f"ошибка: {error}", file=sys.stderr)
        return EXIT_USAGE
    for key, value in config.as_pairs():
        print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
