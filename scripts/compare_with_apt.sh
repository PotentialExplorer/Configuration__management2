#!/bin/sh
# Сравнение порядка загрузки depviz с apt-get на «чистой» системе.
#
# Использование:
#   scripts/compare_with_apt.sh ПАКЕТ [URL_ИЛИ_ФАЙЛ_Packages]
#
# Скрипт скачивает индекс Packages, собирает из него локальный
# репозиторий и просит apt-get смоделировать установку пакета на
# системе, где ещё ничего не установлено (пустой dpkg status).
# Нужен Ubuntu/Debian (подойдёт WSL) с apt-get; права root не нужны.
set -e
PKG=$1
SRC=${2:-http://archive.ubuntu.com/ubuntu/dists/noble/main/binary-amd64/Packages.gz}
[ -n "$PKG" ] || { echo "usage: $0 PACKAGE [PACKAGES_URL]"; exit 2; }
ROOT=$(cd "$(dirname "$0")/.." && pwd)
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/repo" "$WORK/state/lists/partial" \
    "$WORK/cache/archives/partial" "$WORK/etc/apt.conf.d" \
    "$WORK/etc/preferences.d" "$WORK/etc/sources.list.d"
: > "$WORK/state/status"
case "$SRC" in
    http://*|https://*|file://*) curl -fsSL "$SRC" -o "$WORK/index" ;;
    *) cp "$SRC" "$WORK/index" ;;
esac
gzip -dc "$WORK/index" > "$WORK/repo/Packages" 2>/dev/null \
    || xz -dc "$WORK/index" > "$WORK/repo/Packages" 2>/dev/null \
    || cp "$WORK/index" "$WORK/repo/Packages"
echo "deb [trusted=yes] file:$WORK/repo ./" > "$WORK/etc/sources.list"
APT="-o Dir::Etc=$WORK/etc -o Dir::State=$WORK/state \
-o Dir::State::status=$WORK/state/status -o Dir::Cache=$WORK/cache \
-o Debug::NoLocking=1 -o APT::Sandbox::User=$(id -un)"
# shellcheck disable=SC2086
apt-get $APT update > /dev/null 2>&1
# shellcheck disable=SC2086
apt-get $APT install -s --no-install-recommends "$PKG" \
    | awk '/^Conf /{print $2}' > "$WORK/apt.txt"
"$ROOT/run.sh" --package "$PKG" --repo "file://$WORK/repo/Packages" \
    --mode order | awk '/^ *[0-9]+\. /{print $2}' > "$WORK/depviz.txt"
echo "apt-get (Conf): $(wc -l < "$WORK/apt.txt") пакетов," \
    "depviz: $(wc -l < "$WORK/depviz.txt") пакетов"
printf '%-32s %s\n' "apt-get" "depviz"
paste -d'|' "$WORK/apt.txt" "$WORK/depviz.txt" \
    | awk -F'|' '{printf "%-32s %s%s\n", $1, $2, ($1==$2?"":"   <-")}'
sort "$WORK/apt.txt" > "$WORK/a"; sort "$WORK/depviz.txt" > "$WORK/d"
echo "Только у apt-get: $(comm -23 "$WORK/a" "$WORK/d" | tr '\n' ' ')"
echo "Только у depviz:  $(comm -13 "$WORK/a" "$WORK/d" | tr '\n' ' ')"
