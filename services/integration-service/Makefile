.PHONY: build run test clean docker-build docker-run

# Build the service
build:
	go build -o bin/integration-service ./cmd/server

# Run the service locally
run:
	go run cmd/server/main.go

# Run tests
test:
	go test ./...

# Clean build artifacts
clean:
	rm -rf bin/
	go clean

# Build Docker image
docker-build:
	docker build -t integration-service:latest .

# Run with docker-compose
docker-run:
	docker-compose up -d

# Stop docker-compose
docker-stop:
	docker-compose down

# View logs
docker-logs:
	docker-compose logs -f integration-service

# Install dependencies
deps:
	go mod download
	go mod tidy

