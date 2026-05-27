.PHONY: setup up down test lint migrate superuser logs build

setup:
	@echo "Setting up environment files..."
	@test -f backend/.env || cp backend/.env.example backend/.env
	@test -f frontend/.env || cp frontend/.env.example frontend/.env
	@echo "Done. Edit backend/.env to add your API keys and FIELD_ENCRYPTION_KEY."

up:
	cd backend && docker compose up -d

down:
	cd backend && docker compose down

test:
	cd backend && docker compose exec web pytest -v

lint:
	cd backend && docker compose exec web sh -c "black --check . && isort --check-only . && flake8"

migrate:
	cd backend && docker compose exec web python manage.py migrate

superuser:
	cd backend && docker compose exec web python manage.py createsuperuser

logs:
	cd backend && docker compose logs -f web

build:
	cd frontend && npm run build
