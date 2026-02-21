# =============================================================================
# FGA CRM - Makefile
# =============================================================================

.PHONY: dev prod stop restart logs clean db-migrate db-upgrade seed

# Development
dev:
	docker compose up -d
	@echo "✅ FGA CRM running at http://localhost:3300"
	@echo "   API: http://localhost:8300/docs"

prod:
	docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

stop:
	docker compose down

restart:
	docker compose restart

logs:
	docker compose logs -f

logs-backend:
	docker compose logs -f backend

logs-frontend:
	docker compose logs -f frontend

# Database
db-migrate:
	docker compose exec backend alembic revision --autogenerate -m "$(msg)"

db-upgrade:
	docker compose exec backend alembic upgrade head

db-downgrade:
	docker compose exec backend alembic downgrade -1

seed:
	docker compose exec backend python -m scripts.seed

# Celery
worker:
	docker compose exec backend celery -A app.tasks worker --loglevel=info

beat:
	docker compose exec backend celery -A app.tasks beat --loglevel=info

# Testing
test:
	docker compose exec backend pytest -v

test-cov:
	docker compose exec backend pytest --cov=app --cov-report=html

# Cleanup
clean:
	docker compose down -v
	@echo "🗑️  Volumes supprimés"

# Network (shared with Startup Radar)
network:
	docker network create coptos-network 2>/dev/null || true
	@echo "✅ coptos-network ready"
