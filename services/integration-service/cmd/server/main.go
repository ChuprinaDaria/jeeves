package main

import (
	"context"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/nexelin/integration-service/internal/api"
	"github.com/nexelin/integration-service/internal/hitl"
	"github.com/nexelin/integration-service/internal/matrix"
)

func main() {
	// Load configuration from environment variables
	homeserverURL := getEnv("MATRIX_HOMESERVER_URL", "https://matrix.org")
	botUserID := getEnv("MATRIX_BOT_USER_ID", "")
	botAccessToken := getEnv("MATRIX_BOT_ACCESS_TOKEN", "")
	djangoAPIURL := getEnv("DJANGO_API_URL", "")
	djangoAPIToken := getEnv("DJANGO_API_TOKEN", "")
	port := getEnv("PORT", "8080")

	// Validate required configuration
	if botUserID == "" || botAccessToken == "" {
		log.Fatal("MATRIX_BOT_USER_ID and MATRIX_BOT_ACCESS_TOKEN are required")
	}

	// Create Matrix client
	matrixClient, err := matrix.NewClient(homeserverURL, botUserID, botAccessToken)
	if err != nil {
		log.Fatalf("Failed to create Matrix client: %v", err)
	}

	log.Printf("Matrix client initialized: %s", botUserID)

	// Create HITL orchestrator
	orchestrator := hitl.NewOrchestrator(
		matrixClient,
		djangoAPIURL,
		djangoAPIToken,
	)

	// Start event processing
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	err = orchestrator.StartEventProcessing(ctx)
	if err != nil {
		log.Fatalf("Failed to start event processing: %v", err)
	}

	log.Println("Event processing started")

	// Create API handlers
	handlers := api.NewHandlers(orchestrator)

	// Setup routes
	router := api.SetupRoutes(handlers)

	// Create HTTP server
	srv := &http.Server{
		Addr:    ":" + port,
		Handler: router,
	}

	// Start server in a goroutine
	go func() {
		log.Printf("Server starting on port %s", port)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("Failed to start server: %v", err)
		}
	}()

	// Wait for interrupt signal to gracefully shutdown
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	log.Println("Shutting down server...")

	// Graceful shutdown
	shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer shutdownCancel()

	if err := srv.Shutdown(shutdownCtx); err != nil {
		log.Printf("Server forced to shutdown: %v", err)
	}

	// Stop orchestrator
	orchestrator.Stop()

	log.Println("Server exited")
}

// getEnv gets an environment variable or returns a default value
func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

