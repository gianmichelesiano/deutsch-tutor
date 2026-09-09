SHELL := /bin/bash
COMPOSE := docker compose

.PHONY: up down build logs migrate seed test test-integration ps reset

up: ## Avvia lo stack (build + up -d)
	$(COMPOSE) up -d --build

down: ## Ferma lo stack
	$(COMPOSE) down

build: ## (Ri)compila le immagini
	$(COMPOSE) build

logs: ## Segue i log
	$(COMPOSE) logs -f

migrate: ## Applica le migrazioni Alembic
	$(COMPOSE) exec api alembic upgrade head

seed: ## Popola il DB (idempotente)
	$(COMPOSE) exec api python -m app.seed

seed-update: ## Seed + sovrascrive i contenuti degli scenari esistenti
	$(COMPOSE) exec api python -m app.seed --update

test: ## Test unitari (senza DB)
	$(COMPOSE) exec api pytest -m "not integration"

test-integration: ## Test che richiedono il DB (richiede `make migrate`)
	$(COMPOSE) exec api pytest -m integration

reset: ## Ricostruisce da zero (rimuove anche il volume dati)
	$(COMPOSE) down -v
	$(COMPOSE) up -d --build

ps: ## Stato dei servizi
	$(COMPOSE) ps
