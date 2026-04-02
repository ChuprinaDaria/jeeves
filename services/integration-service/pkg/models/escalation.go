package models

// EscalationRequest represents the incoming escalation request from Django
type EscalationRequest struct {
	ConversationID int64    `json:"conversation_id" binding:"required"`
	ClientID       int64    `json:"client_id" binding:"required"`
	ClientName     string   `json:"client_name" binding:"required"`
	CustomerName   string   `json:"customer_name"`
	Channel        string   `json:"channel" binding:"required"` // "telegram", "whatsapp", "web"
	Question       string   `json:"question" binding:"required"`
	Context        string   `json:"context"`
	Language       string   `json:"language"`
	ManagerUserIDs []string `json:"manager_user_ids" binding:"required"` // Matrix user IDs like ["@manager1:matrix.org"]
	RoomID         string   `json:"room_id"`                             // Existing Matrix room ID to reuse
}

// Escalation represents an internal escalation object
type Escalation struct {
	ConversationID int64
	ClientID       int64
	ClientName     string
	CustomerName   string
	Channel        string
	Question       string
	Context        string
	Language       string
	ManagerUserIDs []string
	RoomID         string // Existing room to reuse (empty = create new)
}

// ConversationInfo represents conversation details fetched from Django
type ConversationInfo struct {
	ID             int64  `json:"id"`
	TelegramChatID string `json:"telegram_chat_id,omitempty"`
	CustomerPhone  string `json:"customer_phone,omitempty"`
	SessionID      string `json:"session_id,omitempty"`
	Channel        string `json:"channel"`
	ClientID       int64  `json:"client_id"`
}

// OnboardManagerRequest represents a request to send a welcome DM to a new Matrix manager
type OnboardManagerRequest struct {
	ManagerUserID string `json:"manager_user_id" binding:"required"`
	ClientName    string `json:"client_name" binding:"required"`
}

// OnboardManagerResponse represents the response after onboarding a manager
type OnboardManagerResponse struct {
	Status string `json:"status"`
	RoomID string `json:"room_id"`
}

// ForwardMessageRequest represents a request to forward a message to a channel
type ForwardMessageRequest struct {
	ConversationID int64  `json:"conversation_id" binding:"required"`
	Message        string `json:"message" binding:"required"`
	Channel        string `json:"channel" binding:"required"`
	BridgeType     string `json:"bridge_type,omitempty"` // "whatsapp", "meta-facebook", "meta-instagram", "linkedin"
}

// UpdateRoomRequest represents a request to update Matrix room info in Django
type UpdateRoomRequest struct {
	ConversationID      int64  `json:"conversation_id" binding:"required"`
	MatrixRoomID       string `json:"matrix_room_id" binding:"required"`
	MatrixRoomAlias    string `json:"matrix_room_alias,omitempty"`
	MatrixEventID      string `json:"matrix_event_id,omitempty"`
	MatrixEscalationActive bool `json:"matrix_escalation_active"`
}

