package api

import (
	"github.com/gin-gonic/gin"
)

// SetupRoutes configures all API routes
func SetupRoutes(handlers *Handlers) *gin.Engine {
	router := gin.Default()

	// Health check
	router.GET("/health", handlers.HandleHealth)

	// API v1 routes
	v1 := router.Group("/api/v1")
	{
		// Status
		v1.GET("/status", handlers.HandleStatus)

		// HITL escalation
		hitl := v1.Group("/hitl")
		{
			hitl.POST("/escalate", handlers.HandleEscalation)
		}

		// Matrix management
		matrixGroup := v1.Group("/matrix")
		{
			matrixGroup.POST("/onboard-manager", handlers.HandleOnboardManager)
		}
	}

	return router
}

