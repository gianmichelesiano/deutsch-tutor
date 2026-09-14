#!/usr/bin/env bash
# Avvia Deutsch-Tutor: db + api (backend) + web (frontend) via Docker Compose,
# poi applica migrazioni e seed e attende che i servizi rispondano.
#
# Uso:
#   ./start.sh            # avvio (dev: con docker-compose.override.yml, codice montato)
#   ./start.sh --build    # forza il rebuild delle immagini
#   ./start.sh --logs     # dopo l'avvio segue i log
#   ./start.sh --prod     # ignora l'override (build statica, nessun mount)
set -euo pipefail
cd "$(dirname "$0")"

BUILD=""; LOGS=0; COMPOSE=(docker compose)
for arg in "$@"; do
  case "$arg" in
    --build) BUILD="--build" ;;
    --logs) LOGS=1 ;;
    --prod) COMPOSE=(docker compose -f docker-compose.yml); BUILD="--build" ;;
    -h|--help) sed -n '2,10p' "$0"; exit 0 ;;
    *) echo "argomento sconosciuto: $arg" >&2; exit 1 ;;
  esac
done

if [ ! -f .env ]; then
  echo "→ .env mancante: copio infra/.env.example (ricorda LOCAL_LLM_API_KEY)"
  cp infra/.env.example .env
fi

WEB_PORT=$(grep -E '^WEB_PORT=' .env | cut -d= -f2 || true); WEB_PORT=${WEB_PORT:-3100}

echo "→ avvio container (db, api, web)"
"${COMPOSE[@]}" up -d $BUILD

echo "→ attendo il backend (http://localhost:8000/api/health)"
for i in $(seq 1 60); do
  if curl -fs http://localhost:8000/api/health >/dev/null 2>&1; then break; fi
  sleep 2
  [ "$i" -eq 60 ] && { echo "backend non risponde, log:"; "${COMPOSE[@]}" logs api --tail 30; exit 1; }
done

echo "→ migrazioni + seed"
"${COMPOSE[@]}" exec -T api alembic upgrade head 2>&1 | grep -v "^INFO" || true
"${COMPOSE[@]}" exec -T api python -m app.seed

echo "→ attendo il frontend (http://localhost:${WEB_PORT})"
for i in $(seq 1 60); do
  if curl -fs -o /dev/null "http://localhost:${WEB_PORT}"; then break; fi
  sleep 2
  [ "$i" -eq 60 ] && { echo "frontend non risponde, log:"; "${COMPOSE[@]}" logs web --tail 30; exit 1; }
done

if ! grep -qE '^LOCAL_LLM_API_KEY=.+' .env; then
  echo "⚠ LOCAL_LLM_API_KEY vuota in .env: warmup e roleplay falliranno finché non la imposti."
fi

echo
echo "✔ Deutsch-Tutor pronto"
echo "  frontend  http://localhost:${WEB_PORT}"
echo "  backend   http://localhost:8000/api/health"
echo "  stop      docker compose down"
[ "$LOGS" -eq 1 ] && "${COMPOSE[@]}" logs -f
exit 0
