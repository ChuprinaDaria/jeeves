package matrix

import (
	"context"
	"fmt"
	"log"

	"github.com/matrix-org/gomatrix"
)

// Client wraps the Matrix client with additional functionality
type Client struct {
	homeserverURL string
	userID        string
	accessToken   string
	client        *gomatrix.Client
}

// NewClient creates a new Matrix client
func NewClient(homeserverURL, userID, accessToken string) (*Client, error) {
	client, err := gomatrix.NewClient(homeserverURL, userID, accessToken)
	if err != nil {
		return nil, fmt.Errorf("failed to create Matrix client: %w", err)
	}

	return &Client{
		homeserverURL: homeserverURL,
		userID:        userID,
		accessToken:   accessToken,
		client:        client,
	}, nil
}

// CreateRoom creates a new Matrix room with the given name, topic, and invited users
func (c *Client) CreateRoom(ctx context.Context, name, topic string, inviteUserIDs []string) (string, error) {
	req := &gomatrix.ReqCreateRoom{
		Name:      name,
		Topic:     topic,
		Invite:    inviteUserIDs,
		Preset:    "private_chat",
		IsDirect:  false,
		Visibility: "private",
	}

	resp, err := c.client.CreateRoom(req)
	if err != nil {
		return "", fmt.Errorf("failed to create Matrix room: %w", err)
	}

	log.Printf("Created Matrix room: %s (name: %s)", resp.RoomID, name)
	return resp.RoomID, nil
}

// SendMessage sends a text message to a Matrix room
func (c *Client) SendMessage(ctx context.Context, roomID, message string) (string, error) {
	resp, err := c.client.SendText(roomID, message)
	if err != nil {
		return "", fmt.Errorf("failed to send Matrix message: %w", err)
	}

	log.Printf("Sent message to room %s, event ID: %s", roomID, resp.EventID)
	return resp.EventID, nil
}

// SendFormattedMessage sends a formatted message (HTML/Markdown) to a Matrix room
func (c *Client) SendFormattedMessage(ctx context.Context, roomID, message, format string) (string, error) {
	content := map[string]interface{}{
		"msgtype": "m.text",
		"body":    message,
	}

	if format == "org.matrix.custom.html" {
		content["format"] = format
		content["formatted_body"] = message
	}

	resp, err := c.client.SendMessageEvent(roomID, "m.room.message", content)
	if err != nil {
		return "", fmt.Errorf("failed to send formatted Matrix message: %w", err)
	}

	log.Printf("Sent formatted message to room %s, event ID: %s", roomID, resp.EventID)
	return resp.EventID, nil
}

// InviteUser invites a user to a Matrix room
func (c *Client) InviteUser(ctx context.Context, roomID, userID string) error {
	_, err := c.client.InviteUser(roomID, &gomatrix.ReqInviteUser{
		UserID: userID,
	})
	if err != nil {
		return fmt.Errorf("failed to invite user %s to room %s: %w", userID, roomID, err)
	}

	log.Printf("Invited user %s to room %s", userID, roomID)
	return nil
}

// GetUserID returns the Matrix user ID of this client
func (c *Client) GetUserID() string {
	return c.userID
}

// GetJoinedMembers returns the user IDs of all members in a room
func (c *Client) GetJoinedMembers(roomID string) ([]string, error) {
	resp, err := c.client.JoinedMembers(roomID)
	if err != nil {
		return nil, fmt.Errorf("failed to get joined members for room %s: %w", roomID, err)
	}

	members := make([]string, 0, len(resp.Joined))
	for userID := range resp.Joined {
		members = append(members, userID)
	}
	return members, nil
}

// GetClient returns the underlying gomatrix client (for sync operations)
func (c *Client) GetClient() *gomatrix.Client {
	return c.client
}

