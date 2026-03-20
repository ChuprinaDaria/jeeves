# Код ескалації в Matrix та ланцюжок: Користувач → Ескалація → Менеджер → Відповідь користувачу

## 1. Ескалація в Matrix (створення кімнати та надсилання повідомлення)

### 1.1. Django: Відправка ескалації до Integration Service
**Файл:** `p004_ai_nexelin/MASTER/clients/tasks.py`

```python
def send_matrix_escalation(conversation, client, channel, message_body, escalation_summary, language):
    """
    Send escalation to Matrix via Integration Service.
    """
    if not getattr(client, 'matrix_hitl_enabled', False):
        return
    
    matrix_manager_ids = getattr(client, 'matrix_manager_user_ids', [])
    if not matrix_manager_ids:
        return
    
    try:
        import httpx
        from django.conf import settings
        
        # Determine customer name based on channel
        customer_name = "Customer"
        if channel == "telegram" and hasattr(conversation, 'telegram_chat_id') and conversation.telegram_chat_id:
            customer_name = f"Telegram User {conversation.telegram_chat_id}"
        elif channel == "whatsapp" and hasattr(conversation, 'customer_phone') and conversation.customer_phone:
            customer_name = conversation.customer_phone or "WhatsApp User"
        elif channel == "web" and hasattr(conversation, 'session_id') and conversation.session_id:
            customer_name = f"Web User {conversation.session_id[:8]}"
        
        escalation_data = {
            "conversation_id": conversation.id,
            "client_id": client.id,
            "client_name": str(client.company_name or client.user),
            "customer_name": customer_name,
            "channel": channel,
            "question": message_body,
            "context": escalation_summary or message_body[:200],
            "language": language or "en",
            "manager_user_ids": matrix_manager_ids,
        }
        
        url = getattr(settings, 'INTEGRATION_SERVICE_URL', 'http://ai_nexelin_integration_service:8080')
        response = httpx.post(
            f"{url}/api/v1/hitl/escalate",
            json=escalation_data,
            timeout=5.0
        )
        if response.status_code == 200:
            logger.info(f"Matrix escalation created for conversation {conversation.id}")
        else:
            logger.warning(f"Matrix escalation failed: {response.status_code} {response.text}")
    except Exception as e:
        logger.error(f"Failed to create Matrix escalation: {e}", exc_info=True)
```

**Виклик з Telegram view:**
```python
# p004_ai_nexelin/MASTER/clients/views_telegram.py (рядок ~1182)
if rag_response.requires_escalation:
    from MASTER.clients.tasks import send_matrix_escalation
    send_matrix_escalation(conversation, client, "telegram", message_body, rag_response.escalation_summary, language)
```

### 1.2. Go: Обробка ескалації та створення Matrix кімнати
**Файл:** `services/integration-service/internal/hitl/orchestrator.go`

```go
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

	// 4. Register bridge for this conversation
	o.bridge.RegisterConversation(escalation.ConversationID, roomID, escalation.Channel, escalation.ClientID)
	log.Printf("DEBUG: Registered bridge mapping: conversation=%d -> room=%s", escalation.ConversationID, roomID)

	log.Printf("Escalation handled: conversation_id=%d, room_id=%s, reused=%v", escalation.ConversationID, roomID, escalation.RoomID != "")
	return nil
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

	return html
}
```

### 1.3. Bridge: Зв'язок Matrix кімнати з розмовою
**Файл:** `services/integration-service/internal/hitl/bridge.go`

```go
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
```

---

## 2. Ланцюжок: Користувач → Ескалація → Менеджер → Відповідь користувачу

### 2.1. Користувач надсилає повідомлення → Ескалація
**Файл:** `p004_ai_nexelin/MASTER/rag/response_generator.py`

```python
# Відповідь AI містить токен ескалації
requires_escalation = False
escalation_summary = ""

# Перевірка токену ескалації в відповіді AI
if "[[ESCALATE_TO_MANAGER]]" in answer:
    requires_escalation = True
    # Витягуємо summary після токену
    parts = answer.split("[[ESCALATE_TO_MANAGER]]", 1)
    if len(parts) > 1:
        summary_part = parts[1].split("\n", 1)[0]
        escalation_summary = summary_part.replace("Question summary:", "").strip()
```

**Файл:** `p004_ai_nexelin/MASTER/clients/views_telegram.py`

```python
# Після отримання відповіді від RAG
if rag_response.requires_escalation:
    # Matrix HITL escalation
    from MASTER.clients.tasks import send_matrix_escalation
    send_matrix_escalation(conversation, client, "telegram", message_body, rag_response.escalation_summary, language)
```

### 2.2. Менеджер відповідає в Matrix кімнаті
**Файл:** `services/integration-service/internal/hitl/orchestrator.go`

```go
// handleMatrixEvent handles a single Matrix event
func (o *Orchestrator) handleMatrixEvent(ctx context.Context, event *gomatrix.Event) {
	// Check if this is a message in an escalation room
	roomID := event.RoomID

	log.Printf("DEBUG: Received event in room=%s, sender=%s, type=%s", event.RoomID, event.Sender, event.Type)

	conversationID, channel, clientID, found := o.bridge.GetConversationByRoom(roomID)
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

	log.Printf("Processing manager reply: room=%s, conversation=%d, channel=%s, message=%s",
		roomID, conversationID, channel, content[:min(50, len(content))])

	// Forward message to original channel
	err := o.forwardToChannel(ctx, conversationID, channel, content, clientID)
	if err != nil {
		log.Printf("Error forwarding message: %v", err)
	}
}

// forwardToChannel forwards a message to the original channel
func (o *Orchestrator) forwardToChannel(ctx context.Context, conversationID int64, channel, message string, clientID int64) error {
	// Call Django API to forward the message
	url := fmt.Sprintf("%s/api/v1/integration/forward-message", o.djangoAPIURL)

	reqBody := models.ForwardMessageRequest{
		ConversationID: conversationID,
		Message:        message,
		Channel:        channel,
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

	log.Printf("Message forwarded successfully: conversation=%d, channel=%s", conversationID, channel)
	return nil
}
```

### 2.3. Django API отримує повідомлення від менеджера
**Файл:** `MASTER/api/views.py`

```python
def integration_forward_message(request):
    import json
    data = json.loads(request.body)
    conversation_id = data.get('conversation_id')
    message = data.get('message')
    try:
        from MASTER.clients.tasks import process_manager_hitl_response
        process_manager_hitl_response.delay(conversation_id, message, None)
        return JsonResponse({'status': 'ok'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
```

### 2.4. Обробка відповіді менеджера та надсилання користувачу
**Файл:** `p004_ai_nexelin/MASTER/clients/tasks.py`

```python
@shared_task
def process_manager_hitl_response(conversation_id: int, manager_response: str, manager_telegram_id: int = None) -> Dict[str, Any]:
    """
    Process manager's response to an escalated question.
    
    The AI will rephrase the manager's response to maintain tone of voice,
    then send it to the customer.
    """
    from MASTER.clients.models import ClientWhatsAppConversation
    from MASTER.rag.llm_client import LLMClient
    from django.utils import timezone
    from MASTER.clients.views_telegram import send_telegram_message
    
    try:
        # Use select_for_update to lock the row and prevent race conditions
        from django.db import transaction
        with transaction.atomic():
            conversation = ClientWhatsAppConversation.objects.select_for_update().select_related('client').get(id=conversation_id)
            client = conversation.client
            
            # Check if still waiting for manager (Matrix escalation)
            is_matrix_response = manager_telegram_id is None
            if is_matrix_response:
                if not getattr(conversation, 'matrix_escalation_active', False):
                    logger.warning(
                        f"Conversation {conversation_id} Matrix escalation was not active "
                        f"(likely already handled by another manager)"
                    )
                    return {"success": False, "error": "Not waiting for manager", "already_handled": True}
        
        # Get customer's language from escalation context
        customer_language = conversation.escalation_language or getattr(conversation, 'language', None) or 'en'
        logger.info(f"Processing manager response for conversation {conversation_id}, customer language: {customer_language}")
        
        # 1. AI Rephrasing & Translation
        try:
            llm_client = LLMClient()
            
            system_prompt = (
                "You are a customer service assistant. "
                "Rewrite the manager's message as a clear, polite response to the customer. "
                "Do NOT add greetings like 'Dear Guest', sign-offs like 'Best regards', or placeholder text like '[Your Name]'. "
                "Output ONLY the response body text. "
                f"Write ONLY in {customer_language} language, no other language."
            )
            
            user_prompt = f"Manager raw input: {manager_response}"
            
            ai_response = llm_client.get_response(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                client=client,
                temperature=0.7
            )
            
            final_response = ai_response if ai_response else manager_response
            logger.info(f"AI rephrased manager response for conv {conversation_id}")

        except Exception as e:
            logger.error(f"LLM rephrasing failed: {e}. Falling back to raw translation.")
            final_response = manager_response
        
        # Send response to customer based on platform
        platform = conversation.context_metadata.get('platform', 'unknown') if conversation.context_metadata else 'unknown'
        
        # If platform is unknown but we have Matrix escalation, try to infer from conversation fields
        if platform == 'unknown' and is_matrix_response:
            if conversation.telegram_chat_id:
                platform = 'telegram'
            elif conversation.customer_phone:
                platform = 'whatsapp'
            elif conversation.session_id:
                platform = 'web'
        
        send_success = False
        
        if platform == 'telegram' and conversation.telegram_chat_id:
            bot_token = client.telegram_bot_token
            if bot_token:
                send_success = send_telegram_message(bot_token, int(conversation.telegram_chat_id), final_response)
        elif platform == 'whatsapp' and conversation.customer_phone:
            logger.info(f"WhatsApp response would be sent to {conversation.customer_phone}")
            send_success = True
        elif platform in ('web', 'web_widget', 'iframe'):
            logger.info(f"Web chat HITL response saved for conversation {conversation_id}, client will receive via polling")
            send_success = True
        
        # Update conversation messages
        if not conversation.messages:
            conversation.messages = []
        
        # Add manager response as assistant message
        manager_metadata = {'hitl_response': True}
        if manager_telegram_id is not None:
            manager_metadata['manager_id'] = manager_telegram_id
        else:
            manager_metadata['source'] = 'matrix'
        
        conversation.messages.append({
            'role': 'assistant',
            'content': final_response,
            'timestamp': timezone.now().isoformat(),
            'metadata': manager_metadata
        })
        
        # Atomically update conversation state (Matrix escalation)
        if is_matrix_response:
            updated = ClientWhatsAppConversation.objects.filter(
                id=conversation_id,
                matrix_escalation_active=True
            ).update(
                matrix_escalation_active=False,
                messages=conversation.messages,
                total_messages=len(conversation.messages),
                last_activity_at=timezone.now()
            )
        
        if updated == 0:
            logger.warning(
                f"Conversation {conversation_id} was already processed by another manager"
            )
            return {
                "success": False,
                "error": "Conversation already processed by another manager",
                "already_handled": True
            }
        
        logger.info(
            f"HITL response processed for conversation {conversation_id} "
            f"(customer language: {customer_language})"
        )
        
        return {
            "success": send_success,
            "conversation_id": conversation_id,
            "response_sent": final_response[:200],
            "platform": platform
        }
        
    except ClientWhatsAppConversation.DoesNotExist:
        logger.error(f"Conversation {conversation_id} not found")
        return {"success": False, "error": "Conversation not found"}
```

---

## Повний ланцюжок (підсумок)

```
1. КОРИСТУВАЧ надсилає повідомлення
   ↓
2. RAG Service обробляє запит, AI визначає потребу в ескалації
   ↓
3. Django: send_matrix_escalation() → POST до Integration Service
   ↓
4. Integration Service (Go): HandleEscalation()
   - Створює Matrix кімнату
   - Надсилає повідомлення ескалації менеджерам
   - Реєструє в Bridge (зв'язок conversation_id ↔ room_id)
   ↓
5. МЕНЕДЖЕР бачить повідомлення в Matrix кімнаті та відповідає
   ↓
6. Integration Service: handleMatrixEvent()
   - Витягує повідомлення менеджера
   - Знаходить conversation_id через Bridge
   - forwardToChannel() → POST до Django API
   ↓
7. Django API: integration_forward_message()
   - Викликає process_manager_hitl_response.delay()
   ↓
8. Celery Task: process_manager_hitl_response()
   - AI переформулює відповідь менеджера
   - Визначає платформу (telegram/whatsapp/web)
   - Надсилає відповідь користувачу
   - Оновлює стан розмови (matrix_escalation_active = False)
   ↓
9. КОРИСТУВАЧ отримує відповідь
```

---

## Ключові файли

1. **Ескалація:**
   - `p004_ai_nexelin/MASTER/clients/tasks.py` - `send_matrix_escalation()`
   - `services/integration-service/internal/hitl/orchestrator.go` - `HandleEscalation()`

2. **Bridge (зв'язок кімнат з розмовами):**
   - `services/integration-service/internal/hitl/bridge.go`

3. **Обробка відповіді менеджера:**
   - `services/integration-service/internal/hitl/orchestrator.go` - `handleMatrixEvent()`, `forwardToChannel()`
   - `MASTER/api/views.py` - `integration_forward_message()`
   - `p004_ai_nexelin/MASTER/clients/tasks.py` - `process_manager_hitl_response()`

