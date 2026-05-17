.DEFAULT_GOAL := help

.PHONY: help setup start stop logs \
        test-backend test-frontend \
        lint-backend lint-frontend quality \
        demo db-backup db-restore

help:
	@echo "MoneyPlanner Core — available targets:"
	@echo ""
	@echo "  make setup          Copy .env template and build containers"
	@echo "  make start          Start all services (detached)"
	@echo "  make stop           Stop all services"
	@echo "  make logs           Follow logs from all services"
	@echo "  make demo           Seed demo user with sample Spanish financial data"
	@echo ""
	@echo "  make db-backup                        Dump full database to backups/"
	@echo "  make db-restore FILE=backups/xxx.dump Restore database from a dump file"
	@echo ""
	@echo "  make test-backend   Run backend test suite"
	@echo "  make test-frontend  Run frontend unit tests"
	@echo ""
	@echo "  make lint-backend   Ruff + mypy on backend"
	@echo "  make lint-frontend  ESLint + typecheck on frontend"
	@echo "  make quality        Run all quality checks (backend + frontend)"

setup:
	@if [ ! -f backend/.env ]; then cp backend/.env.example backend/.env && echo "Created backend/.env"; fi
	docker compose build

start:
	docker compose up -d

stop:
	docker compose down

logs:
	docker compose logs -f

test-backend:
	docker compose exec backend python manage.py test accounts budget memberships net_worth core

test-frontend:
	docker compose exec frontend npm run test:unit

lint-backend:
	docker compose exec backend ruff check .
	docker compose exec backend ruff format --check .
	docker compose exec backend mypy .

lint-frontend:
	docker compose exec frontend npm run lint
	docker compose exec frontend npm run format:check
	docker compose exec frontend npm run typecheck

quality: lint-backend lint-frontend

demo:
	docker compose exec backend python manage.py seed_demo

db-backup:
	@mkdir -p backups
	$(eval FILE := backups/core_db_$(shell date +%Y%m%d_%H%M%S).dump)
	docker compose exec db pg_dump -U core -d core -Fc --no-owner --no-privileges > $(FILE)
	@echo "Backup saved: $(FILE)"

db-restore:
	@test -n "$(FILE)" || (echo "Usage: make db-restore FILE=backups/core_db_xxx.dump" && exit 1)
	@test -f "$(FILE)" || (echo "File not found: $(FILE)" && exit 1)
	@echo "WARNING: This will replace the current database with $(FILE)"
	@echo "Press Ctrl+C within 5 seconds to cancel..."
	@sleep 5
	docker compose exec -T db pg_restore -U core -d core --clean --if-exists --no-owner --no-privileges < $(FILE)
	docker compose restart backend
	@echo "Done. Database restored from $(FILE)"
