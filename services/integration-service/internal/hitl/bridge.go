package hitl

import (
	"sync"
)

// Bridge maintains the mapping between Matrix rooms and conversations
type Bridge struct {
	mu         sync.RWMutex
	roomToConv map[string]*ConversationMapping
	convToRoom map[int64]string
}

// ConversationMapping maps a Matrix room to a conversation
type ConversationMapping struct {
	ConversationID int64
	RoomID         string
	Channel        string // "telegram", "whatsapp", "web"
	ClientID       int64
}

// NewBridge creates a new bridge instance
func NewBridge() *Bridge {
	return &Bridge{
		roomToConv: make(map[string]*ConversationMapping),
		convToRoom: make(map[int64]string),
	}
}

// RegisterConversation registers a conversation with a Matrix room
func (b *Bridge) RegisterConversation(conversationID int64, roomID, channel string, clientID int64) {
	b.mu.Lock()
	defer b.mu.Unlock()

	mapping := &ConversationMapping{
		ConversationID: conversationID,
		RoomID:         roomID,
		Channel:        channel,
		ClientID:       clientID,
	}

	b.roomToConv[roomID] = mapping
	b.convToRoom[conversationID] = roomID
}

// GetConversationByRoom returns conversation details for a given Matrix room ID
func (b *Bridge) GetConversationByRoom(roomID string) (int64, string, int64, bool) {
	b.mu.RLock()
	defer b.mu.RUnlock()

	mapping, found := b.roomToConv[roomID]
	if !found {
		return 0, "", 0, false
	}

	return mapping.ConversationID, mapping.Channel, mapping.ClientID, true
}

// GetRoomByConversation returns the Matrix room ID for a given conversation ID
func (b *Bridge) GetRoomByConversation(conversationID int64) (string, bool) {
	b.mu.RLock()
	defer b.mu.RUnlock()

	roomID, found := b.convToRoom[conversationID]
	return roomID, found
}

// UnregisterConversation removes a conversation from the bridge
func (b *Bridge) UnregisterConversation(conversationID int64) {
	b.mu.Lock()
	defer b.mu.Unlock()

	roomID, found := b.convToRoom[conversationID]
	if found {
		delete(b.convToRoom, conversationID)
		delete(b.roomToConv, roomID)
	}
}

// GetAllRooms returns all registered room IDs
func (b *Bridge) GetAllRooms() []string {
	b.mu.RLock()
	defer b.mu.RUnlock()

	rooms := make([]string, 0, len(b.roomToConv))
	for roomID := range b.roomToConv {
		rooms = append(rooms, roomID)
	}
	return rooms
}

