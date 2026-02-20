package api

import (
	"net/http"

	"github.com/gin-gonic/gin"
	"github.com/nexelin/integration-service/internal/hitl"
	"github.com/nexelin/integration-service/pkg/models"
)

// Handlers contains HTTP request handlers
type Handlers struct {
	orchestrator *hitl.Orchestrator
}

// NewHandlers creates a new handlers instance
func NewHandlers(orchestrator *hitl.Orchestrator) *Handlers {
	return &Handlers{
		orchestrator: orchestrator,
	}
}

// HandleEscalation handles POST /api/v1/hitl/escalate
func (h *Handlers) HandleEscalation(c *gin.Context) {
	var req models.EscalationRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	escalation := &models.Escalation{
		ConversationID: req.ConversationID,
		ClientID:       req.ClientID,
		ClientName:     req.ClientName,
		CustomerName:   req.CustomerName,
		Channel:        req.Channel,
		Question:       req.Question,
		Context:        req.Context,
		Language:       req.Language,
		ManagerUserIDs: req.ManagerUserIDs,
		RoomID:         req.RoomID,
	}

	err := h.orchestrator.HandleEscalation(c.Request.Context(), escalation)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"status": "escalation_created",
		"message": "Matrix room created and managers notified",
	})
}

// HandleOnboardManager handles POST /api/v1/matrix/onboard-manager
func (h *Handlers) HandleOnboardManager(c *gin.Context) {
	var req models.OnboardManagerRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	roomID, err := h.orchestrator.OnboardManager(c.Request.Context(), req.ManagerUserID, req.ClientName)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, models.OnboardManagerResponse{
		Status: "ok",
		RoomID: roomID,
	})
}

// HandleHealth handles GET /health
func (h *Handlers) HandleHealth(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"status": "healthy",
		"service": "integration-service",
	})
}

// HandleStatus handles GET /api/v1/status
func (h *Handlers) HandleStatus(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"status": "running",
		"service": "integration-service",
		"version": "1.0.0",
	})
}

