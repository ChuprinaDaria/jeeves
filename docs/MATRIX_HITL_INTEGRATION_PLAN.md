# Matrix.org Integration for Human-in-the-Loop (HITL)

## Overview

This document outlines the integration of Matrix.org for Human-in-the-Loop escalation, replacing the current Telegram-only notification system with a unified Matrix room-based approach that supports both Telegram and WhatsApp conversations.

## Current HITL Implementation

### Existing Flow
1. AI detects need for escalation (via `[[ESCALATE_TO_MANAGER]]` token)
2. `notify_manager_of_escalation` Celery task triggered
3. Managers receive Telegram notification with escalation details
4. Managers reply via Telegram (handled in `TelegramWebhookView`)
5. Reply forwarded to original conversation (WhatsApp/Telegram/Web)

### Limitations
- **Telegram-only notifications**: Managers must use Telegram
- **No unified interface**: Different channels handled separately
- **No conversation history**: Escalations are isolated messages
- **No team collaboration**: Managers can't see each other's responses
- **No persistent context**: Escalation context lost between messages

## Matrix.org Integration Benefits

1. **Unified Interface**: All escalations in Matrix rooms
2. **Multi-channel Support**: Telegram, WhatsApp, Web widget in one place
3. **Team Collaboration**: Multiple managers can see and respond
4. **Conversation History**: Full context preserved in Matrix
5. **Rich Features**: File sharing, reactions, threading
6. **Federation**: Can connect to other Matrix servers
7. **Mobile Apps**: Native Matrix clients available

## Architecture

### High-Level Flow

```
┌─────────────────┐
│  User Message   │
│ (WhatsApp/TG)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   RAG Service   │
│  (Detects need   │
│   for HITL)      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐      ┌──────────────────┐
│ Integration     │─────▶│  Matrix.org      │
│ Service (Go)    │      │  Room Created    │
│                 │      │  Managers Invited │
└─────────────────┘      └────────┬─────────┘
         │                         │
         │                         ▼
         │                ┌──────────────────┐
         │                │ Manager Replies  │
         │                │ in Matrix Room   │
         │                └────────┬─────────┘
         │                         │
         └─────────────────────────┘
                   │
                   ▼
         ┌──────────────────┐
         │ Reply Forwarded  │
         │ to Original       │
         │ Channel           │
         └──────────────────┘
```

## Implementation Plan

### Phase 1: Matrix.org Setup & Infrastructure

#### 1.1 Matrix Server Deployment

**Option A: Self-Hosted Synapse**
- Full control, data privacy
- Requires server resources
- More complex setup

**Option B: Matrix.org Hosted (Recommended for MVP)**
- Quick setup
- Free tier available
- Less control

**Recommendation**: Start with Matrix.org hosted, migrate to self-hosted later if needed.

#### 1.2 Matrix Bot Account

Create a dedicated bot account for the integration service:
- Username: `@nexelin-bot:matrix.org` (or your domain)
- Purpose: Create rooms, invite managers, bridge messages
- Permissions: Room creation, message sending, user management

#### 1.3 Database Schema Updates

Add Matrix-related fields to `ClientWhatsAppConversation` model:

```python
# In MASTER/clients/models.py

class ClientWhatsAppConversation(models.Model):
    # ... existing fields ...
    
    # Matrix.org HITL fields
    matrix_room_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Matrix room ID for HITL escalation (e.g., !abc123:matrix.org)"
    )
    matrix_room_alias = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Matrix room alias (e.g., #escalation-123:matrix.org)"
    )
    matrix_escalation_active = models.BooleanField(
        default=False,
        help_text="Whether there's an active escalation in Matrix room"
    )
    matrix_last_event_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Last processed Matrix event ID (for sync)"
    )
```

Add Matrix configuration to `Client` model:

```python
class Client(models.Model):
    # ... existing fields ...
    
    # Matrix.org HITL configuration
    matrix_hitl_enabled = models.BooleanField(
        default=False,
        help_text="Enable Matrix.org for HITL escalations"
    )
    matrix_manager_user_ids = models.JSONField(
        default=list,
        blank=True,
        help_text="List of Matrix user IDs for managers (e.g., ['@manager1:matrix.org', '@manager2:matrix.org'])"
    )
    matrix_homeserver_url = models.CharField(
        max_length=255,
        default='https://matrix.org',
        help_text="Matrix homeserver URL"
    )
    matrix_bot_access_token = models.TextField(
        blank=True,
        help_text="Matrix bot access token for this client (optional, can use global)"
    )
```

### Phase 2: Integration Service (Go Implementation)

#### 2.1 Project Structure

```
services/integration-service/
├── cmd/
│   └── server/
│       └── main.go
├── internal/
│   ├── matrix/
│   │   ├── client.go          # Matrix client wrapper
│   │   ├── room.go            # Room management
│   │   ├── events.go          # Event handling
│   │   └── sync.go            # Sync loop
│   ├── telegram/
│   │   └── bot.go
│   ├── whatsapp/
│   │   └── webhook.go
│   ├── hitl/
│   │   ├── orchestrator.go    # HITL orchestration
│   │   ├── escalation.go     # Escalation logic
│   │   └── bridge.go          # Message bridging
│   └── api/
│       ├── handlers.go        # HTTP handlers
│       └── routes.go
├── pkg/
│   └── models/
│       └── escalation.go      # Data models
├── go.mod
├── go.sum
├── Dockerfile
└── docker-compose.yml
```

#### 2.2 Matrix Client Implementation

**File**: `internal/matrix/client.go`

```go
package matrix

import (
    "context"
    "github.com/matrix-org/gomatrix"
)

type Client struct {
    homeserverURL string
    userID        string
    accessToken   string
    client        *gomatrix.Client
}

func NewClient(homeserverURL, userID, accessToken string) (*Client, error) {
    client, err := gomatrix.NewClient(homeserverURL, userID, accessToken)
    if err != nil {
        return nil, err
    }
    
    return &Client{
        homeserverURL: homeserverURL,
        userID:        userID,
        accessToken:   accessToken,
        client:        client,
    }, nil
}

func (c *Client) CreateRoom(ctx context.Context, name, topic string, inviteUserIDs []string) (string, error) {
    req := &gomatrix.ReqCreateRoom{
        Name:      name,
        Topic:     topic,
        Invite:    inviteUserIDs,
        Preset:    "private_chat",
        IsDirect:  false,
    }
    
    resp, err := c.client.CreateRoom(req)
    if err != nil {
        return "", err
    }
    
    return resp.RoomID, nil
}

func (c *Client) SendMessage(ctx context.Context, roomID, message string) (string, error) {
    resp, err := c.client.SendText(roomID, message)
    if err != nil {
        return "", err
    }
    
    return resp.EventID, nil
}

func (c *Client) InviteUser(ctx context.Context, roomID, userID string) error {
    return c.client.InviteUser(roomID, &gomatrix.ReqInviteUser{
        UserID: userID,
    })
}
```

**File**: `internal/matrix/sync.go`

```go
package matrix

import (
    "context"
    "sync"
    "github.com/matrix-org/gomatrix"
)

type SyncHandler struct {
    client      *Client
    eventChan   chan *gomatrix.Event
    stopChan    chan struct{}
    wg          sync.WaitGroup
}

func NewSyncHandler(client *Client) *SyncHandler {
    return &SyncHandler{
        client:    client,
        eventChan: make(chan *gomatrix.Event, 100),
        stopChan:  make(chan struct{}),
    }
}

func (sh *SyncHandler) Start(ctx context.Context) error {
    sh.wg.Add(1)
    go sh.syncLoop(ctx)
    return nil
}

func (sh *SyncHandler) syncLoop(ctx context.Context) {
    defer sh.wg.Done()
    
    syncToken := ""
    
    for {
        select {
        case <-ctx.Done():
            return
        case <-sh.stopChan:
            return
        default:
            resp, err := sh.client.client.SyncRequest(syncToken, 30000, false, "")
            if err != nil {
                // Log error and retry
                continue
            }
            
            syncToken = resp.NextBatch
            
            // Process room events
            for roomID, roomData := range resp.Rooms.Join {
                for _, event := range roomData.Timeline.Events {
                    if event.Type == "m.room.message" {
                        select {
                        case sh.eventChan <- &event:
                        default:
                            // Channel full, log warning
                        }
                    }
                }
            }
        }
    }
}

func (sh *SyncHandler) GetEventChan() <-chan *gomatrix.Event {
    return sh.eventChan
}

func (sh *SyncHandler) Stop() {
    close(sh.stopChan)
    sh.wg.Wait()
}
```

#### 2.3 HITL Orchestrator

**File**: `internal/hitl/orchestrator.go`

```go
package hitl

import (
    "context"
    "encoding/json"
    "fmt"
    "log"
    
    "github.com/gin-gonic/gin"
    "services/integration-service/internal/matrix"
    "services/integration-service/pkg/models"
)

type Orchestrator struct {
    matrixClient *matrix.Client
    syncHandler  *matrix.SyncHandler
    bridge       *Bridge
}

func NewOrchestrator(matrixClient *matrix.Client) *Orchestrator {
    syncHandler := matrix.NewSyncHandler(matrixClient)
    bridge := NewBridge()
    
    return &Orchestrator{
        matrixClient: matrixClient,
        syncHandler:  syncHandler,
        bridge:       bridge,
    }
}

func (o *Orchestrator) HandleEscalation(ctx context.Context, escalation *models.Escalation) error {
    // 1. Create Matrix room
    roomName := fmt.Sprintf("Escalation: %s - %s", escalation.ClientName, escalation.Channel)
    roomTopic := fmt.Sprintf("Customer question requiring human assistance. Original channel: %s", escalation.Channel)
    
    roomID, err := o.matrixClient.CreateRoom(ctx, roomName, roomTopic, escalation.ManagerUserIDs)
    if err != nil {
        return fmt.Errorf("failed to create Matrix room: %w", err)
    }
    
    // 2. Send escalation message to room
    message := o.formatEscalationMessage(escalation)
    _, err = o.matrixClient.SendMessage(ctx, roomID, message)
    if err != nil {
        return fmt.Errorf("failed to send escalation message: %w", err)
    }
    
    // 3. Store room ID in database (via API call to Django)
    err = o.storeEscalationRoom(ctx, escalation.ConversationID, roomID)
    if err != nil {
        log.Printf("Warning: failed to store room ID: %v", err)
    }
    
    // 4. Register bridge for this conversation
    o.bridge.RegisterConversation(escalation.ConversationID, roomID, escalation.Channel)
    
    return nil
}

func (o *Orchestrator) formatEscalationMessage(escalation *models.Escalation) string {
    return fmt.Sprintf(
        `🆘 **ESCALATION NEEDED**

**Customer**: %s
**Channel**: %s
**Question**: %s
**Language**: %s
**Context**: %s

Please respond in this room. Your response will be forwarded to the customer.`,
        escalation.CustomerName,
        escalation.Channel,
        escalation.Question,
        escalation.Language,
        escalation.Context,
    )
}

func (o *Orchestrator) StartEventProcessing(ctx context.Context) error {
    // Start Matrix sync
    err := o.syncHandler.Start(ctx)
    if err != nil {
        return err
    }
    
    // Process events
    go o.processEvents(ctx)
    
    return nil
}

func (o *Orchestrator) processEvents(ctx context.Context) {
    eventChan := o.syncHandler.GetEventChan()
    
    for {
        select {
        case <-ctx.Done():
            return
        case event := <-eventChan:
            o.handleMatrixEvent(ctx, event)
        }
    }
}

func (o *Orchestrator) handleMatrixEvent(ctx context.Context, event *gomatrix.Event) {
    // Check if this is a message in an escalation room
    roomID := event.RoomID
    
    conversationID, channel, found := o.bridge.GetConversationByRoom(roomID)
    if !found {
        // Not an escalation room, ignore
        return
    }
    
    // Extract message content
    content, ok := event.Content["body"].(string)
    if !ok {
        return
    }
    
    // Check if message is from a manager (not the bot)
    if event.Sender == o.matrixClient.UserID {
        return // Ignore bot's own messages
    }
    
    // Forward message to original channel
    err := o.forwardToChannel(ctx, conversationID, channel, content)
    if err != nil {
        log.Printf("Error forwarding message: %v", err)
    }
}
```

#### 2.4 Message Bridge

**File**: `internal/hitl/bridge.go`

```go
package hitl

import (
    "sync"
)

type Bridge struct {
    mu              sync.RWMutex
    roomToConv      map[string]*ConversationMapping
    convToRoom      map[int64]string
}

type ConversationMapping struct {
    ConversationID int64
    RoomID         string
    Channel        string // "telegram", "whatsapp", "web"
}

func NewBridge() *Bridge {
    return &Bridge{
        roomToConv: make(map[string]*ConversationMapping),
        convToRoom: make(map[int64]string),
    }
}

func (b *Bridge) RegisterConversation(conversationID int64, roomID, channel string) {
    b.mu.Lock()
    defer b.mu.Unlock()
    
    mapping := &ConversationMapping{
        ConversationID: conversationID,
        RoomID:         roomID,
        Channel:        channel,
    }
    
    b.roomToConv[roomID] = mapping
    b.convToRoom[conversationID] = roomID
}

func (b *Bridge) GetConversationByRoom(roomID string) (int64, string, bool) {
    b.mu.RLock()
    defer b.mu.RUnlock()
    
    mapping, found := b.roomToConv[roomID]
    if !found {
        return 0, "", false
    }
    
    return mapping.ConversationID, mapping.Channel, true
}

func (b *Bridge) GetRoomByConversation(conversationID int64) (string, bool) {
    b.mu.RLock()
    defer b.mu.RUnlock()
    
    roomID, found := b.convToRoom[conversationID]
    return roomID, found
}
```

#### 2.5 API Handlers

**File**: `internal/api/handlers.go`

```go
package api

import (
    "net/http"
    
    "github.com/gin-gonic/gin"
    "services/integration-service/internal/hitl"
    "services/integration-service/pkg/models"
)

type Handlers struct {
    orchestrator *hitl.Orchestrator
}

func NewHandlers(orchestrator *hitl.Orchestrator) *Handlers {
    return &Handlers{
        orchestrator: orchestrator,
    }
}

// POST /api/v1/hitl/escalate
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
    }
    
    err := h.orchestrator.HandleEscalation(c.Request.Context(), escalation)
    if err != nil {
        c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
        return
    }
    
    c.JSON(http.StatusOK, gin.H{"status": "escalation_created"})
}
```

### Phase 3: Django Integration

#### 3.1 Update RAG Service

Modify `MASTER/rag/response_generator.py` to call Integration Service:

```python
# In _generate_complete method

if requires_escalation and getattr(client, 'matrix_hitl_enabled', False):
    # Call Integration Service API
    import httpx
    
    escalation_data = {
        "conversation_id": conversation.id if conversation else None,
        "client_id": client.id,
        "client_name": client.company_name,
        "customer_name": customer_name,
        "channel": channel,  # "telegram", "whatsapp", "web"
        "question": query,
        "context": escalation_summary,
        "language": language,
        "manager_user_ids": client.matrix_manager_user_ids or [],
    }
    
    try:
        async with httpx.AsyncClient() as client_http:
            response = await client_http.post(
                f"{settings.INTEGRATION_SERVICE_URL}/api/v1/hitl/escalate",
                json=escalation_data,
                timeout=5.0
            )
            if response.status_code == 200:
                logger.info(f"Matrix escalation created for conversation {conversation.id}")
    except Exception as e:
        logger.error(f"Failed to create Matrix escalation: {e}")
```

#### 3.2 Update Conversation Model

Add method to store Matrix room ID:

```python
class ClientWhatsAppConversation(models.Model):
    # ... existing fields ...
    
    def set_matrix_room(self, room_id: str, room_alias: str = None):
        """Store Matrix room information for HITL escalation."""
        self.matrix_room_id = room_id
        self.matrix_room_alias = room_alias
        self.matrix_escalation_active = True
        self.save(update_fields=['matrix_room_id', 'matrix_room_alias', 'matrix_escalation_active'])
    
    def mark_escalation_resolved(self):
        """Mark escalation as resolved."""
        self.matrix_escalation_active = False
        self.save(update_fields=['matrix_escalation_active'])
```

### Phase 4: Channel-Specific Integration

#### 4.1 Telegram Integration

When manager replies in Matrix room, forward to Telegram:

```go
// In internal/hitl/orchestrator.go

func (o *Orchestrator) forwardToChannel(ctx context.Context, conversationID int64, channel, message string) error {
    switch channel {
    case "telegram":
        return o.forwardToTelegram(ctx, conversationID, message)
    case "whatsapp":
        return o.forwardToWhatsApp(ctx, conversationID, message)
    case "web":
        return o.forwardToWeb(ctx, conversationID, message)
    default:
        return fmt.Errorf("unknown channel: %s", channel)
    }
}

func (o *Orchestrator) forwardToTelegram(ctx context.Context, conversationID int64, message string) error {
    // Get conversation details from Django API
    conv, err := o.getConversation(ctx, conversationID)
    if err != nil {
        return err
    }
    
    // Send message via Telegram Bot API
    return o.telegramClient.SendMessage(ctx, conv.TelegramChatID, message)
}
```

#### 4.2 WhatsApp Integration

Similar implementation for WhatsApp forwarding.

### Phase 5: Testing & Deployment

#### 5.1 Testing Checklist

- [ ] Matrix room creation works
- [ ] Managers receive invitations
- [ ] Escalation messages appear in room
- [ ] Manager replies are forwarded to original channel
- [ ] Multi-manager collaboration works
- [ ] Room persistence across service restarts
- [ ] Error handling for Matrix API failures
- [ ] Rate limiting for Matrix API calls

#### 5.2 Deployment Steps

1. **Deploy Matrix Server** (or use matrix.org)
2. **Create Bot Account** and obtain access token
3. **Deploy Integration Service** with Matrix client
4. **Configure Client Settings** in Django admin
5. **Test Escalation Flow** end-to-end
6. **Monitor Matrix API Usage** and rate limits
7. **Gradual Rollout** to selected clients

## Configuration

### Environment Variables

```bash
# Integration Service
MATRIX_HOMESERVER_URL=https://matrix.org
MATRIX_BOT_USER_ID=@nexelin-bot:matrix.org
MATRIX_BOT_ACCESS_TOKEN=your_access_token
INTEGRATION_SERVICE_PORT=8080

# Django Settings
INTEGRATION_SERVICE_URL=http://integration-service:8080
```

### Client Configuration (Django Admin)

1. Enable `matrix_hitl_enabled` for client
2. Add manager Matrix user IDs: `["@manager1:matrix.org", "@manager2:matrix.org"]`
3. Set Matrix homeserver URL (default: `https://matrix.org`)

## Monitoring & Observability

### Metrics to Track

- Matrix room creation rate
- Escalation response time
- Message forwarding latency
- Matrix API error rate
- Active escalation rooms
- Manager response rate

### Logging

- All Matrix API calls
- Room creation events
- Message forwarding events
- Error conditions

## Future Enhancements

1. **Rich Media Support**: Forward images/files from Matrix to channels
2. **Threading**: Support Matrix threads for multiple escalations
3. **Reactions**: Allow managers to react to messages
4. **Bot Commands**: `/resolve`, `/assign`, `/notes` commands in Matrix
5. **Analytics**: Track escalation metrics in Matrix rooms
6. **Mobile Push Notifications**: Matrix clients support push notifications

## Migration from Telegram-Only HITL

1. **Parallel Run**: Support both Telegram and Matrix HITL
2. **Feature Flag**: Allow clients to choose HITL method
3. **Gradual Migration**: Move clients to Matrix one by one
4. **Deprecation**: Remove Telegram-only HITL after full migration

## Security Considerations

1. **Access Token Security**: Store Matrix tokens securely (secrets manager)
2. **Room Privacy**: Ensure rooms are private and invite-only
3. **User Verification**: Verify manager Matrix user IDs
4. **Rate Limiting**: Implement rate limits for Matrix API calls
5. **Error Handling**: Don't expose sensitive info in error messages

