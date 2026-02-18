package matrix

import (
	"context"
	"log"
	"sync"
	"time"

	"github.com/matrix-org/gomatrix"
)

// SyncHandler handles Matrix sync operations to receive events
type SyncHandler struct {
	client    *Client
	eventChan chan *gomatrix.Event
	stopChan  chan struct{}
	wg        sync.WaitGroup
	running   bool
	mu        sync.RWMutex
}

// NewSyncHandler creates a new sync handler
func NewSyncHandler(client *Client) *SyncHandler {
	return &SyncHandler{
		client:    client,
		eventChan: make(chan *gomatrix.Event, 100),
		stopChan:  make(chan struct{}),
		running:   false,
	}
}

// Start begins the sync loop in a goroutine
func (sh *SyncHandler) Start(ctx context.Context) error {
	sh.mu.Lock()
	if sh.running {
		sh.mu.Unlock()
		return nil // Already running
	}
	sh.running = true
	sh.mu.Unlock()

	sh.wg.Add(1)
	go sh.syncLoop(ctx)
	return nil
}

// syncLoop continuously syncs with Matrix server
func (sh *SyncHandler) syncLoop(ctx context.Context) {
	defer sh.wg.Done()
	defer func() {
		sh.mu.Lock()
		sh.running = false
		sh.mu.Unlock()
	}()

	syncToken := ""
	timeout := 30000 // 30 seconds
	retryDelay := 5 * time.Second

	for {
		select {
		case <-ctx.Done():
			log.Println("Sync loop context cancelled")
			return
		case <-sh.stopChan:
			log.Println("Sync loop stopped")
			return
		default:
			// Perform sync request
			resp, err := sh.client.GetClient().SyncRequest(syncToken, timeout, false, "")
			if err != nil {
				log.Printf("Matrix sync error: %v, retrying in %v", err, retryDelay)
				time.Sleep(retryDelay)
				continue
			}

			// Update sync token for next request
			if resp.NextBatch != "" {
				syncToken = resp.NextBatch
			}

			// Process room events
			for roomID, roomData := range resp.Rooms.Join {
				for _, event := range roomData.Timeline.Events {
					if event.Type == "m.room.message" {
						select {
						case sh.eventChan <- &event:
							// Event sent successfully
						default:
							log.Printf("Warning: event channel full, dropping event from room %s", roomID)
						}
					}
				}
			}

			// Small delay to prevent tight loop
			time.Sleep(100 * time.Millisecond)
		}
	}
}

// GetEventChan returns the channel for receiving Matrix events
func (sh *SyncHandler) GetEventChan() <-chan *gomatrix.Event {
	return sh.eventChan
}

// Stop stops the sync loop
func (sh *SyncHandler) Stop() {
	sh.mu.Lock()
	if !sh.running {
		sh.mu.Unlock()
		return
	}
	sh.mu.Unlock()

	close(sh.stopChan)
	sh.wg.Wait()
	log.Println("Sync handler stopped")
}

// IsRunning returns whether the sync handler is currently running
func (sh *SyncHandler) IsRunning() bool {
	sh.mu.RLock()
	defer sh.mu.RUnlock()
	return sh.running
}

