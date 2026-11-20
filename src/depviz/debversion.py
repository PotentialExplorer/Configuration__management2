"""Сравнение версий пакетов по правилам Debian Policy (раздел 5.6.12).

Версия имеет вид ``[эпоха:]основная_часть[-ревизия]``. Части
сравниваются по очереди: эпоха как число, затем основная часть и
ревизия алгоритмом dpkg — нецифровые фрагменты посимвольно (``~``
меньше всего, буквы меньше прочих знаков), цифровые — как числа.
"""

TILDE_ORDER = -1
END_ORDER = 0
NON_LETTER_SHIFT = 256


def compare(left, right):
    """Сравнить две версии Debian.

    :return: отрицательное число, 0 или положительное число —
        как ``left < right``, ``left == right``, ``left > right``.
    """
    left_epoch, left_main, left_rev = _split(left)
    right_epoch, right_main, right_rev = _split(right)
    if left_epoch != right_epoch:
        return left_epoch - right_epoch
    result = _compare_part(left_main, right_main)
    if result:
        return result
    return _compare_part(left_rev, right_rev)


def _split(version):
    """Разделить версию на эпоху, основную часть и ревизию."""
    epoch = 0
    if ":" in version:
        head, version = version.split(":", 1)
        epoch = int(head) if head.isdigit() else 0
    main, revision = version, ""
    if "-" in version:
        main, revision = version.rsplit("-", 1)
    return epoch, main, revision


def _compare_part(left, right):
    """Сравнить основные части или ревизии алгоритмом dpkg."""
    while left or right:
        left_text, left = _take(left, digits=False)
        right_text, right = _take(right, digits=False)
        result = _compare_text(left_text, right_text)
        if result:
            return result
        left_num, left = _take(left, digits=True)
        right_num, right = _take(right, digits=True)
        result = int(left_num or 0) - int(right_num or 0)
        if result:
            return result
    return 0


def _take(text, digits):
    """Отделить от начала ``text`` цифры (или нецифровые символы)."""
    index = 0
    while index < len(text) and text[index].isdigit() == digits:
        index += 1
    return text[:index], text[index:]


def _compare_text(left, right):
    """Посимвольно сравнить нецифровые фрагменты."""
    for index in range(max(len(left), len(right))):
        left_char = left[index] if index < len(left) else ""
        right_char = right[index] if index < len(right) else ""
        result = _order(left_char) - _order(right_char)
        if result:
            return result
    return 0


def _order(char):
    """Вес символа при сравнении версий."""
    if char == "~":
        return TILDE_ORDER
    if not char:
        return END_ORDER
    if char.isalpha():
        return ord(char)
    return ord(char) + NON_LETTER_SHIFT
