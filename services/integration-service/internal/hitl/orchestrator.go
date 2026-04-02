package hitl

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"strings"
	"time"

	"github.com/matrix-org/gomatrix"
	"github.com/nexelin/integration-service/internal/matrix"
	"github.com/nexelin/integration-service/pkg/models"
)

// botToBridgeType maps Matrix bridge bot user ID prefixes to bridge types
var botToBridgeType = map[string]string{
	"whatsappbot":  "whatsapp",
	"facebookbot":  "meta-facebook",
	"instagrambot": "meta-instagram",
	"linkedinbot":  "linkedin",
}

// Orchestrator orchestrates HITL escalation flow
type Orchestrator struct {
	matrixClient      *matrix.Client
	syncHandler       *matrix.SyncHandler
	bridge            *Bridge
	djangoAPIURL      string
	djangoAPIToken    string
	httpClient        *http.Client
}

// NewOrchestrator creates a new HITL orchestrator
func NewOrchestrator(
	matrixClient *matrix.Client,
	djangoAPIURL string,
	djangoAPIToken string,
) *Orchestrator {
	syncHandler := matrix.NewSyncHandler(matrixClient)
	bridge := NewBridge()

	return &Orchestrator{
		matrixClient:   matrixClient,
		syncHandler:    syncHandler,
		bridge:         bridge,
		djangoAPIURL:    djangoAPIURL,
		djangoAPIToken:  djangoAPIToken,
		httpClient: &http.Client{
			Timeout: 10 * time.Second,
		},
	}
}

// HandleEscalation handles a new escalation request
func (o *Orchestrator) HandleEscalation(ctx context.Context, escalation *models.Escalation) error {
	var roomID string
	var err error

	if escalation.RoomID != "" {
		// Reuse existing room
		roomID = escalation.RoomID
		log.Printf("Reusing existing Matrix room %s for conversation %d", roomID, escalation.ConversationID)
	} else {
		// Create new Matrix room
		roomName := fmt.Sprintf("Escalation: %s - %s", escalation.ClientName, escalation.Channel)
		roomTopic := fmt.Sprintf("Customer question requiring human assistance. Original channel: %s", escalation.Channel)

		roomID, err = o.matrixClient.CreateRoom(ctx, roomName, roomTopic, escalation.ManagerUserIDs)
		if err != nil {
			return fmt.Errorf("failed to create Matrix room: %w", err)
		}
	}

	// 2. Send escalation message to room
	message := o.formatEscalationMessage(escalation)
	eventID, err := o.matrixClient.SendFormattedMessage(ctx, roomID, message, "org.matrix.custom.html")
	if err != nil {
		log.Printf("Warning: failed to send escalation message: %v", err)
		// Continue even if message send fails
	}

	// 3. Store room ID in Django database
	err = o.storeEscalationRoom(ctx, escalation.ConversationID, roomID, "", eventID, true)
	if err != nil {
		log.Printf("Warning: failed to store room ID in Django: %v", err)
		// Continue even if storage fails - bridge will handle it
	}

	// 4. Detect bridge type from room members and register bridge
	bridgeType := o.detectBridgeType(roomID)
	o.bridge.RegisterConversation(escalation.ConversationID, roomID, escalation.Channel, escalation.ClientID, bridgeType)
	log.Printf("DEBUG: Registered bridge mapping: conversation=%d -> room=%s, bridge_type=%s", escalation.ConversationID, roomID, bridgeType)

	log.Printf("Escalation handled: conversation_id=%d, room_id=%s, reused=%v", escalation.ConversationID, roomID, escalation.RoomID != "")
	return nil
}

// OnboardManager creates a DM room with a new manager and sends a welcome message
func (o *Orchestrator) OnboardManager(ctx context.Context, managerUserID, clientName string) (string, error) {
	log.Printf("Onboarding manager %s for client %s", managerUserID, clientName)

	// Create a direct message room inviting the manager
	roomName := fmt.Sprintf("Nexelin Bot — %s", clientName)
	roomTopic := fmt.Sprintf("Welcome room for manager of %s", clientName)
	roomID, err := o.matrixClient.CreateRoom(ctx, roomName, roomTopic, []string{managerUserID})
	if err != nil {
		return "", fmt.Errorf("failed to create DM room for manager %s: %w", managerUserID, err)
	}

	// Send welcome message
	welcomeMsg := fmt.Sprintf(
		`<p>👋 <strong>Welcome!</strong></p>`+
			`<p>You have been added as a manager for <strong>%s</strong>.</p>`+
			`<p>Escalation messages from customers will appear in dedicated rooms. Please respond directly in those rooms.</p>`+
			`<p><em>This is an automated message from the Nexelin bot.</em></p>`,
		escapeHTML(clientName),
	)
	_, err = o.matrixClient.SendFormattedMessage(ctx, roomID, welcomeMsg, "org.matrix.custom.html")
	if err != nil {
		log.Printf("Warning: failed to send welcome message to %s in room %s: %v", managerUserID, roomID, err)
	}

	log.Printf("Manager %s onboarded successfully, room_id=%s", managerUserID, roomID)
	return roomID, nil
}

// formatEscalationMessage formats the escalation message for Matrix
func (o *Orchestrator) formatEscalationMessage(escalation *models.Escalation) string {
	// Use HTML formatting for better presentation in Matrix
	html := fmt.Sprintf(
		`<h2>🆘 <strong>ESCALATION NEEDED</strong></h2>
<p><strong>Customer:</strong> %s<br/>
<strong>Channel:</strong> %s<br/>
<strong>Question:</strong> %s<br/>
<strong>Language:</strong> %s</p>
%s
<p><em>Please respond in this room. Your response will be forwarded to the customer.</em></p>`,
		escapeHTML(escalation.CustomerName),
		escapeHTML(escalation.Channel),
		escapeHTML(escalation.Question),
		escapeHTML(escalation.Language),
		formatContext(escalation.Context),
	)

	// Plain text fallback (commented out - using HTML only)
	// plain := fmt.Sprintf(
	// 	`🆘 ESCALATION NEEDED
	//
	// Customer: %s
	// Channel: %s
	// Question: %s
	// Language: %s
	// %s
	//
	// Please respond in this room. Your response will be forwarded to the customer.`,
	// 	escalation.CustomerName,
	// 	escalation.Channel,
	// 	escalation.Question,
	// 	escalation.Language,
	// 	escalation.Context,
	// )

	// Return HTML, Matrix client will handle fallback
	return html
}

func escapeHTML(s string) string {
	s = strings.ReplaceAll(s, "&", "&amp;")
	s = strings.ReplaceAll(s, "<", "&lt;")
	s = strings.ReplaceAll(s, ">", "&gt;")
	s = strings.ReplaceAll(s, "\"", "&quot;")
	s = strings.ReplaceAll(s, "'", "&#39;")
	return s
}

func formatContext(context string) string {
	if context == "" {
		return ""
	}
	return fmt.Sprintf("<p><strong>Context:</strong><br/>%s</p>", escapeHTML(context))
}

// detectBridgeType detects the bridge type for a room by examining its members.
// Bridge bot users follow the pattern @<botprefix>_...:homeserver.
// Returns "whatsapp" as default if no bridge bot is detected.
func (o *Orchestrator) detectBridgeType(roomID string) string {
	members, err := o.matrixClient.GetJoinedMembers(roomID)
	if err != nil {
		log.Printf("Warning: could not get room members for bridge type detection (room=%s): %v", roomID, err)
		return "whatsapp"
	}

	for _, member := range members {
		// Matrix user IDs look like @whatsappbot_123:homeserver
		// Strip the leading '@' for prefix matching
		localpart := strings.TrimPrefix(member, "@")
		for prefix, bridgeType := range botToBridgeType {
			if strings.HasPrefix(localpart, prefix) {
				log.Printf("Detected bridge type %q from member %s in room %s", bridgeType, member, roomID)
				return bridgeType
			}
		}
	}

	log.Printf("No bridge bot detected in room %s, defaulting to whatsapp", roomID)
	return "whatsapp"
}

// StartEventProcessing starts processing Matrix events
func (o *Orchestrator) StartEventProcessing(ctx context.Context) error {
	// Start Matrix sync
	err := o.syncHandler.Start(ctx)
	if err != nil {
		return fmt.Errorf("failed to start Matrix sync: %w", err)
	}

	// Process events
	go o.processEvents(ctx)

	return nil
}

// processEvents processes incoming Matrix events
func (o *Orchestrator) processEvents(ctx context.Context) {
	eventChan := o.syncHandler.GetEventChan()

	for {
		select {
		case <-ctx.Done():
			log.Println("Event processing stopped (context cancelled)")
			return
		case event, ok := <-eventChan:
			if !ok {
				log.Println("Event channel closed")
				return
			}
			o.handleMatrixEvent(ctx, event)
		}
	}
}

// handleMatrixEvent handles a single Matrix event
func (o *Orchestrator) handleMatrixEvent(ctx context.Context, event *gomatrix.Event) {
	// Check if this is a message in an escalation room
	roomID := event.RoomID

	log.Printf("DEBUG: Received event in room=%s, sender=%s, type=%s", event.RoomID, event.Sender, event.Type)

	conversationID, channel, clientID, bridgeType, found := o.bridge.GetConversationByRoom(roomID)
	if !found {
		log.Printf("DEBUG: Room %s not found in bridge. Registered rooms: %v", roomID, o.bridge.GetAllRooms())
		// Not an escalation room, ignore
		return
	}

	// Check if message is from the bot itself
	if event.Sender == o.matrixClient.GetUserID() {
		return // Ignore bot's own messages
	}

	// Extract message content
	content, ok := event.Content["body"].(string)
	if !ok {
		log.Printf("Warning: could not extract body from event in room %s", roomID)
		return
	}

	// Ignore empty messages
	if strings.TrimSpace(content) == "" {
		return
	}

	log.Printf("Processing manager reply: room=%s, conversation=%d, channel=%s, bridge_type=%s, message=%s",
		roomID, conversationID, channel, bridgeType, content[:min(50, len(content))])

	// Forward message to original channel
	err := o.forwardToChannel(ctx, conversationID, channel, content, clientID, bridgeType)
	if err != nil {
		log.Printf("Error forwarding message: %v", err)
	}
}

// forwardToChannel forwards a message to the original channel via Django bridge endpoint
func (o *Orchestrator) forwardToChannel(ctx context.Context, conversationID int64, channel, message string, clientID int64, bridgeType string) error {
	// Use universal bridge endpoint; fall back to legacy whatsapp endpoint if needed
	url := fmt.Sprintf("%s/api/v1/clients/bridges/message/", o.djangoAPIURL)

	if bridgeType == "" {
		bridgeType = "whatsapp"
	}

	reqBody := models.ForwardMessageRequest{
		ConversationID: conversationID,
		Message:        message,
		Channel:        channel,
		BridgeType:     bridgeType,
	}

	jsonData, err := json.Marshal(reqBody)
	if err != nil {
		return fmt.Errorf("failed to marshal request: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, "POST", url, strings.NewReader(string(jsonData)))
	if err != nil {
		return fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")
	if o.djangoAPIToken != "" {
		req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", o.djangoAPIToken))
	}

	resp, err := o.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("failed to send request to universal endpoint: %w", err)
	}
	defer resp.Body.Close()

	// Fallback to legacy WhatsApp endpoint if universal returns 404
	if resp.StatusCode == http.StatusNotFound && bridgeType == "whatsapp" {
		log.Printf("Universal bridge endpoint returned 404, falling back to legacy WhatsApp endpoint")
		fallbackURL := fmt.Sprintf("%s/api/v1/clients/whatsapp/bridge/message/", o.djangoAPIURL)

		fallbackReq, err := http.NewRequestWithContext(ctx, "POST", fallbackURL, strings.NewReader(string(jsonData)))
		if err != nil {
			return fmt.Errorf("failed to create fallback request: %w", err)
		}

		fallbackReq.Header.Set("Content-Type", "application/json")
		if o.djangoAPIToken != "" {
			fallbackReq.Header.Set("Authorization", fmt.Sprintf("Bearer %s", o.djangoAPIToken))
		}

		fallbackResp, err := o.httpClient.Do(fallbackReq)
		if err != nil {
			return fmt.Errorf("failed to send fallback request: %w", err)
		}
		defer fallbackResp.Body.Close()

		if fallbackResp.StatusCode != http.StatusOK {
			return fmt.Errorf("Django legacy API returned status %d", fallbackResp.StatusCode)
		}

		log.Printf("Message forwarded via legacy endpoint: conversation=%d, channel=%s", conversationID, channel)
		return nil
	}

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("Django API returned status %d", resp.StatusCode)
	}

	log.Printf("Message forwarded successfully: conversation=%d, channel=%s, bridge_type=%s", conversationID, channel, bridgeType)
	return nil
}

// storeEscalationRoom stores Matrix room information in Django
func (o *Orchestrator) storeEscalationRoom(ctx context.Context, conversationID int64, roomID, roomAlias, eventID string, active bool) error {
	if o.djangoAPIURL == "" {
		return nil // Django API not configured, skip
	}

	url := fmt.Sprintf("%s/api/v1/integration/update-room", o.djangoAPIURL)

	reqBody := models.UpdateRoomRequest{
		ConversationID:        conversationID,
		MatrixRoomID:          roomID,
		MatrixRoomAlias:       roomAlias,
		MatrixEventID:         eventID,
		MatrixEscalationActive: active,
	}

	jsonData, err := json.Marshal(reqBody)
	if err != nil {
		return fmt.Errorf("failed to marshal request: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, "POST", url, strings.NewReader(string(jsonData)))
	if err != nil {
		return fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")
	if o.djangoAPIToken != "" {
		req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", o.djangoAPIToken))
	}

	resp, err := o.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("failed to send request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("Django API returned status %d", resp.StatusCode)
	}

	return nil
}

// Stop stops the orchestrator
func (o *Orchestrator) Stop() {
	o.syncHandler.Stop()
	log.Println("Orchestrator stopped")
}

// Helper function
func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}

