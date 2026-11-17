#!/usr/bin/env bash
# Установка и запуск проекта на чистой Ubuntu 22.04 / 24.04.
#   sudo ./install.sh [--no-seed] [--port N]
# Скрипт идемпотентный: повторный запуск ничего не ломает.
set -Eeuo pipefail
trap 'echo "[x] Установка прервана на строке $LINENO" >&2' ERR

cd "$(dirname "${BASH_SOURCE[0]}")"
ROOT_DIR="$(pwd)"
# Настройки из окружения разработчика не должны влиять на установку
unset COMPOSE_FILE COMPOSE_PROJECT_NAME

log()  { printf '\n\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[!]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m[x]\033[0m %s\n' "$*" >&2; exit 1; }

usage() {
  cat <<'EOF'
Использование: sudo ./install.sh [параметры]

  --no-seed   не наполнять базу демо-данными
  --port N    внешний порт приложения (по умолчанию 80)
  -h, --help  эта справка
EOF
}

SEED=1
PORT_ARG=""
while [ $# -gt 0 ]; do
  case "$1" in
    --no-seed) SEED=0 ;;
    --port)
      [ $# -ge 2 ] || die "--port требует номер порта"
      PORT_ARG="$2"
      shift
      ;;
    -h|--help) usage; exit 0 ;;
    *) die "Неизвестный параметр: $1 (см. --help)" ;;
  esac
  shift
done
if [ -n "$PORT_ARG" ] && ! [[ "$PORT_ARG" =~ ^[0-9]{1,5}$ ]]; then
  die "Некорректный порт: $PORT_ARG"
fi

[ "$(id -u)" -eq 0 ] || die "Запустите от root: sudo ./install.sh"
[ -f docker-compose.yml ] || die "Не найден docker-compose.yml: запускайте скрипт из корня репозитория"

# --- проверка системы ---

if [ -r /etc/os-release ]; then
  # shellcheck disable=SC1091
  . /etc/os-release
fi
case "${ID:-}:${VERSION_ID:-}" in
  ubuntu:22.04|ubuntu:24.04) ;;
  *) warn "Скрипт проверялся на Ubuntu 22.04 и 24.04, у вас: ${PRETTY_NAME:-неизвестная система}" ;;
esac
if grep -qi microsoft /proc/version 2>/dev/null; then
  warn "Обнаружен WSL. Для хорошей скорости держите репозиторий в Linux-файловой системе (~/...), а не в /mnt/c."
fi
case "$ROOT_DIR" in
  /mnt/*) warn "Репозиторий лежит на диске Windows ($ROOT_DIR): сборка будет медленной, права файлов могут быть неверными." ;;
esac

# --- вспомогательные программы ---

ensure_tools() {
  local missing=()
  for tool in curl openssl; do
    command -v "$tool" >/dev/null 2>&1 || missing+=("$tool")
  done
  if [ "${#missing[@]}" -gt 0 ]; then
    log "Устанавливаю: ${missing[*]}"
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -y
    apt-get install -y ca-certificates "${missing[@]}"
  fi
}

# --- Docker ---

have_compose() { docker compose version >/dev/null 2>&1; }

install_docker() {
  log "Устанавливаю Docker из официального apt-репозитория"
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -y
  apt-get install -y ca-certificates curl
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${UBUNTU_CODENAME:-${VERSION_CODENAME:-}} stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -y
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
}

ensure_docker_running() {
  if docker info >/dev/null 2>&1; then return 0; fi
  log "Запускаю Docker"
  if command -v systemctl >/dev/null 2>&1 && [ -d /run/systemd/system ]; then
    systemctl enable --now docker || true
  else
    service docker start || true  # WSL без systemd
  fi
  for _ in $(seq 1 30); do
    if docker info >/dev/null 2>&1; then return 0; fi
    sleep 1
  done
  die "Docker не отвечает. Если это WSL с Docker Desktop, запустите Docker Desktop; без него проверьте 'sudo service docker status'."
}

ensure_tools
if command -v docker >/dev/null 2>&1 && have_compose; then
  log "Docker уже установлен"
else
  install_docker
fi
ensure_docker_running

# --- .env ---

env_get() { grep -E "^$1=" .env | tail -n1 | cut -d= -f2- || true; }

append_env() {
  # если файл не оканчивается переводом строки, добавляем его, иначе ключи склеятся
  if [ -s .env ] && [ -n "$(tail -c1 .env)" ]; then echo >> .env; fi
  echo "$1=$2" >> .env
}

ensure_env() { grep -q "^$1=" .env || append_env "$1" "$2"; }

set_env() {
  if grep -q "^$1=" .env; then sed -i "s|^$1=.*|$1=$2|" .env; else append_env "$1" "$2"; fi
}

if [ ! -f .env ]; then
  log "Создаю .env со случайными секретами"
  ( umask 077; : > .env )
fi
ensure_env COMPOSE_PROJECT_NAME ytclone
ensure_env POSTGRES_USER app
ensure_env POSTGRES_PASSWORD "$(openssl rand -hex 16)"
ensure_env POSTGRES_DB app
ensure_env APP_ENV prod
ensure_env SECRET_KEY "$(openssl rand -hex 32)"
ensure_env COOKIE_SECURE false
ensure_env HTTP_PORT 80
ensure_env ADMIN_EMAIL admin@example.com
ensure_env ADMIN_USERNAME admin
ensure_env ADMIN_PASSWORD "$(openssl rand -hex 12)"
[ -z "$PORT_ARG" ] || set_env HTTP_PORT "$PORT_ARG"

chmod 600 .env
if [ -n "${SUDO_USER:-}" ]; then
  chown "$SUDO_USER:$(id -gn "$SUDO_USER")" .env  # владелец репозитория сможет редактировать файл
fi

PORT="$(env_get HTTP_PORT)"
ADMIN_EMAIL="$(env_get ADMIN_EMAIL)"
ADMIN_USERNAME="$(env_get ADMIN_USERNAME)"
ADMIN_PASSWORD="$(env_get ADMIN_PASSWORD)"

dc() { docker compose -f "$ROOT_DIR/docker-compose.yml" --project-directory "$ROOT_DIR" "$@"; }

# --- порт ---

if [ -z "$(dc ps -q nginx 2>/dev/null || true)" ]; then  # если наш nginx уже запущен, порт занят им, это нормально
  if ss -H -ltn "sport = :$PORT" 2>/dev/null | grep -q .; then
    die "Порт $PORT уже занят. Освободите его или запустите: sudo ./install.sh --port 8080"
  fi
fi

# --- сборка, миграции, запуск ---

log "Собираю образы (первый раз это несколько минут)"
dc build

log "Запускаю PostgreSQL"
dc up -d --wait --wait-timeout 120 postgres

log "Применяю миграции"
dc run --rm --no-deps -T api alembic upgrade head

log "Запускаю приложение"
dc up -d --build --wait --wait-timeout 300

log "Проверяю доступность"
ok=0
for _ in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:${PORT}/api/health" >/dev/null 2>&1; then ok=1; break; fi
  sleep 2
done
if [ "$ok" -ne 1 ]; then
  dc ps || true
  die "Приложение не отвечает на порту $PORT. Логи: docker compose logs --tail 50"
fi

# --- администратор и демо-данные ---

log "Создаю администратора"
dc exec -T api python -m scripts.create_admin \
  --email "$ADMIN_EMAIL" --username "$ADMIN_USERNAME" --password "$ADMIN_PASSWORD" --role admin

if [ "$SEED" -eq 1 ]; then
  log "Наполняю базу демо-данными"
  if ! dc exec -T api python -m scripts.seed; then
    warn "Демо-данные загрузить не удалось, приложение при этом работает."
    warn "Повторить: sudo docker compose exec api python -m scripts.seed (нужны видео в seed_assets/)"
  fi
else
  log "Демо-данные пропущены (--no-seed)"
fi

# --- итог ---

IP="$(hostname -I 2>/dev/null | awk '{print $1}' || true)"
SUFFIX=""
[ "$PORT" = "80" ] || SUFFIX=":$PORT"

cat <<EOF

========================================================
 Готово
--------------------------------------------------------
 Приложение:  http://${IP:-localhost}${SUFFIX}/
 Локально:    http://localhost${SUFFIX}/
 Swagger:     http://${IP:-localhost}${SUFFIX}/docs

 Администратор
   Логин (email):  ${ADMIN_EMAIL}
   Пароль:         ${ADMIN_PASSWORD}
 (пароль хранится в .env и печатается при каждом запуске;
  если вы сменили его в приложении, здесь он устарел)
========================================================
EOF