# Chat WOW Features — Component Integration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate the 4 existing chat components (LiveStatus, ThinkingPipeline, QuickActions, DataCard) into ChatWindow and add per-type message animations. All components and CSS are already built — this is purely integration work.

**Architecture:** ChatWindow.jsx already imports all 4 components but doesn't render them. Each task adds one component to the JSX render tree, replacing or augmenting existing UI. DataCard needs SSE result parsing to detect structured data types.

**Tech Stack:** React 18, Tailwind CSS, Lucide icons

---

## Current State

**Already built (DO NOT modify these files):**
- `nextlen/src/components/sandbox/chat/ToolExecutionNode.jsx` — ✅ integrated
- `nextlen/src/components/sandbox/chat/ThinkingPipeline.jsx` — built, imported, NOT rendered
- `nextlen/src/components/sandbox/chat/QuickActions.jsx` — built, imported, NOT rendered
- `nextlen/src/components/sandbox/chat/LiveStatus.jsx` — built, imported, NOT rendered
- `nextlen/src/components/sandbox/chat/DataCard.jsx` — built, NOT imported, NOT rendered
- `nextlen/src/index.css` — all keyframes exist: `chat-msg-user`, `chat-msg-bot`, `chat-chip-pop`, `chat-shimmer`, `flow-node-enter`

**SSE backend** — fully working: emits `tool_start`, `tool_result`, `tool_error` events

---

### Task 1: Add per-type message animations

**Files:**
- Modify: `nextlen/src/components/sandbox/ChatWindow.jsx:508-512`

- [ ] **Step 1: Replace generic `animate-in` with per-type animation classes**

Currently at line 511:
```jsx
className={`flex gap-2 ${msg.sender === 'user' ? 'justify-end' : 'justify-start'} animate-in`}
```

Replace with:
```jsx
className={`flex gap-2 ${msg.sender === 'user' ? 'justify-end chat-msg-user' : 'justify-start chat-msg-bot'}`}
```

Also update the loading indicator at line 614:
```jsx
<div className="flex gap-2 justify-start chat-msg-bot">
```

- [ ] **Step 2: Verify CSS classes exist in index.css**

Confirm these classes exist in `nextlen/src/index.css`:
- `.chat-msg-user` with `animation: chat-msg-user 0.3s ease-out both`
- `.chat-msg-bot` with `animation: chat-msg-bot 0.4s cubic-bezier(0.16, 1, 0.3, 1) both`

- [ ] **Step 3: Commit**

```bash
git add nextlen/src/components/sandbox/ChatWindow.jsx
git commit -m "feat(chat): replace generic animate-in with per-type message animations"
```

---

### Task 2: Integrate LiveStatus under header

**Files:**
- Modify: `nextlen/src/components/sandbox/ChatWindow.jsx:493-504`

- [ ] **Step 1: Add LiveStatus below the header**

LiveStatus is already imported at line 10. Add it after the header `<div>` (after line 503):

```jsx
{/* Header with Clear History Button */}
<div className="flex items-center justify-between mb-2">
  <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">{t('sandbox.chatTest')}</h3>
  <button
    onClick={handleClearHistory}
    className="flex items-center justify-center w-8 h-8 rounded-lg bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-red-100 dark:hover:bg-red-900 hover:text-red-600 dark:hover:text-red-400 transition"
    title={t('sandbox.clearHistory') || 'Clear History'}
    aria-label={t('sandbox.clearHistory') || 'Clear History'}
  >
    <Trash2 size={18} />
  </button>
</div>
<div className="mb-3">
  <LiveStatus />
</div>
```

Note: change header `mb-4` to `mb-2` to keep spacing tight.

- [ ] **Step 2: Commit**

```bash
git add nextlen/src/components/sandbox/ChatWindow.jsx
git commit -m "feat(chat): integrate LiveStatus indicator under header"
```

---

### Task 3: Replace bouncing dots with ThinkingPipeline

**Files:**
- Modify: `nextlen/src/components/sandbox/ChatWindow.jsx:613-648`

- [ ] **Step 1: Add pipeline steps state**

Add a new state variable after `toolExecutions` (line 53):

```jsx
const [pipelineSteps, setPipelineSteps] = useState([]);
```

- [ ] **Step 2: Build pipeline steps from tool events**

Update `handleToolEvent` to also build pipeline steps. After the existing `setToolExecutions` logic (after line 162), add:

```jsx
const handleToolEvent = useCallback((eventType, data) => {
  const toolCallId = data?.tool_call_id;
  const toolName = data?.tool_name;
  if (!toolCallId) return;

  setToolExecutions(prev => {
    // ... existing logic unchanged ...
  });

  // Build ThinkingPipeline steps from tool events
  setPipelineSteps(prev => {
    if (eventType === 'tool_start') {
      const mapped = TOOL_MAP[toolName] || { label: toolName };
      if (prev.some(s => s.id === toolCallId)) return prev;
      // Mark previous active step as done
      const updated = prev.map(s => s.status === 'active' ? { ...s, status: 'done' } : s);
      return [...updated, { id: toolCallId, label: mapped.label, status: 'active' }];
    }
    if (eventType === 'tool_result' || eventType === 'tool_error') {
      return prev.map(s => s.id === toolCallId ? { ...s, status: 'done' } : s);
    }
    return prev;
  });
}, []);
```

- [ ] **Step 3: Replace bouncing dots + ToolCallBadge with ThinkingPipeline**

Replace the loading section (lines 613-648) with:

```jsx
{loading && (
  <div className="flex gap-2 justify-start chat-msg-bot">
    <BotAvatar />
    <div className="bg-gray-100 dark:bg-gray-700/50 p-3 rounded-2xl rounded-bl-md min-w-[200px]">
      <ThinkingPipeline
        steps={pipelineSteps.length > 0 ? pipelineSteps : []}
        currentStep={mcpStatus?.step || 'thinking'}
      />

      {toolExecutions.length > 0 && (
        <div className="space-y-2 mt-1.5 max-h-[180px] overflow-y-auto pr-1">
          {toolExecutions.map((te, idx) => (
            <ToolExecutionNode
              key={te.tool_call_id || idx}
              tool={te.tool}
              params={te.params}
              status={te.status}
              summary={te.summary}
              error={te.error}
            />
          ))}
        </div>
      )}
    </div>
  </div>
)}
```

- [ ] **Step 4: Clear pipeline steps when sending a new message**

In `handleSend`, after `setToolExecutions([])` (line 225), add:

```jsx
setPipelineSteps([]);
```

- [ ] **Step 5: Commit**

```bash
git add nextlen/src/components/sandbox/ChatWindow.jsx
git commit -m "feat(chat): replace bouncing dots with ThinkingPipeline component"
```

---

### Task 4: Integrate QuickActions after bot messages

**Files:**
- Modify: `nextlen/src/components/sandbox/ChatWindow.jsx:578-610`

- [ ] **Step 1: Track last completed tool for QuickActions context**

Add state after `pipelineSteps`:

```jsx
const [lastCompletedTool, setLastCompletedTool] = useState(null);
```

Update `handleToolEvent` — when `tool_result` arrives, save the tool info:

```jsx
if (eventType === 'tool_result') {
  setLastCompletedTool({ tool: toolName, color: (TOOL_MAP[toolName] || {}).color || 'gray' });
}
```

Clear in `handleSend` along with other resets:

```jsx
setLastCompletedTool(null);
```

- [ ] **Step 2: Add QuickActions after the last bot message**

After the message bubble's timestamp `<p>` (after line 609), add QuickActions for the last AI message that isn't streaming:

```jsx
{msg.sender === 'ai' && !msg.streaming && msg.id === messages[messages.length - 1]?.id && (
  <QuickActions
    lastTool={lastCompletedTool?.tool}
    toolColor={lastCompletedTool?.color}
    onAction={(action) => {
      setInput(action);
      // Auto-send after a brief delay for user to see what's happening
      setTimeout(() => {
        setInput(action);
        handleSend();
      }, 100);
    }}
  />
)}
```

- [ ] **Step 3: Commit**

```bash
git add nextlen/src/components/sandbox/ChatWindow.jsx
git commit -m "feat(chat): integrate QuickActions chips after bot messages"
```

---

### Task 5: Integrate DataCard for structured tool results

**Files:**
- Modify: `nextlen/src/components/sandbox/ChatWindow.jsx`

- [ ] **Step 1: Import DataCard**

Add import at line 7 area:

```jsx
import DataCard from './chat/DataCard';
```

- [ ] **Step 2: Add state for data cards**

```jsx
const [dataCards, setDataCards] = useState([]); // [{ type, data }]
```

- [ ] **Step 3: Parse tool results to detect structured data**

Update `handleToolEvent` — when `tool_result` arrives, try to parse structured data:

```jsx
if (eventType === 'tool_result') {
  // ... existing setToolExecutions logic ...

  // Detect structured data for DataCard rendering
  const resultStr = (data?.result || '').toString();
  try {
    const parsed = JSON.parse(resultStr);
    const toolBase = toolName?.replace(/-/g, '_');

    if (toolBase === 'search_leads' || toolBase === 'lead_search') {
      const items = parsed.leads || parsed.results || (Array.isArray(parsed) ? parsed : []);
      if (items.length > 0) {
        setDataCards(prev => [...prev, { type: 'leads', data: { items } }]);
      }
    } else if (toolBase === 'create_lead' || toolBase === 'lead_create') {
      if (parsed.name || parsed.email) {
        setDataCards(prev => [...prev, { type: 'lead', data: parsed }]);
      }
    } else if (toolBase === 'send_email' || toolBase === 'send-email') {
      if (parsed.to || parsed.subject) {
        setDataCards(prev => [...prev, { type: 'email', data: parsed }]);
      }
    } else if (toolBase === 'search' || toolBase === 'rag_search' || toolBase === 'rag-search') {
      const chunks = parsed.chunks || [];
      if (chunks.length > 0) {
        setDataCards(prev => [...prev, {
          type: 'kb_results',
          data: { items: chunks.map(c => ({ title: c.document_title, content: c.content, score: c.similarity })) },
        }]);
      }
    } else if (toolBase === 'generate_file' || toolBase === 'generate-file') {
      if (parsed.name || parsed.url || parsed.file_name) {
        setDataCards(prev => [...prev, { type: 'file', data: { name: parsed.file_name || parsed.name, url: parsed.url, size: parsed.size } }]);
      }
    }
  } catch (_) {
    // Not JSON — no DataCard
  }
}
```

- [ ] **Step 4: Render DataCards after tool executions in the loading bubble**

In the loading section, after the `toolExecutions` map (after the `</div>` closing the tool executions list), add:

```jsx
{dataCards.length > 0 && (
  <div className="space-y-2 mt-2">
    {dataCards.map((card, idx) => (
      <DataCard
        key={idx}
        type={card.type}
        data={card.data}
        style={{ animationDelay: `${idx * 100}ms` }}
      />
    ))}
  </div>
)}
```

- [ ] **Step 5: Also render DataCards in completed bot messages**

After a bot message finishes streaming, move `dataCards` into the message object. In the `onDone` callback (line 249-252):

```jsx
() => {
  setMessages(prev => {
    const updated = prev.map(m => ({ ...m, streaming: false }));
    // Attach data cards to the last AI message
    if (dataCards.length > 0) {
      const lastAi = [...updated].reverse().find(m => m.sender === 'ai');
      if (lastAi) lastAi.dataCards = [...dataCards];
    }
    return updated;
  });
  setMcpStatus(null);
  setLoading(false);
  setDataCards([]);
},
```

Then in the message render, after the timestamp `<p>` and before QuickActions:

```jsx
{msg.dataCards?.length > 0 && (
  <div className="space-y-2 mt-2">
    {msg.dataCards.map((card, idx) => (
      <DataCard
        key={idx}
        type={card.type}
        data={card.data}
        style={{ animationDelay: `${idx * 100}ms` }}
      />
    ))}
  </div>
)}
```

- [ ] **Step 6: Clear dataCards when sending new message**

In `handleSend`, add with other resets:

```jsx
setDataCards([]);
```

- [ ] **Step 7: Commit**

```bash
git add nextlen/src/components/sandbox/ChatWindow.jsx
git commit -m "feat(chat): integrate DataCard for structured tool result display"
```

---

### Task 6: Remove ToolCallBadge (dead code)

**Files:**
- Modify: `nextlen/src/components/sandbox/ChatWindow.jsx:25-39`

- [ ] **Step 1: Remove the ToolCallBadge component definition**

Delete lines 25-39 (the `ToolCallBadge` component). It's no longer used since ThinkingPipeline replaced it in Task 3.

- [ ] **Step 2: Commit**

```bash
git add nextlen/src/components/sandbox/ChatWindow.jsx
git commit -m "chore(chat): remove unused ToolCallBadge component"
```

---

### Task 7: Add dark theme scrollbar styling

**Files:**
- Modify: `nextlen/src/index.css`

- [ ] **Step 1: Add scrollbar styles for the chat messages area**

Add after the existing chat animation section:

```css
/* Chat — dark scrollbar */
.dark .overflow-y-auto::-webkit-scrollbar {
  width: 6px;
}
.dark .overflow-y-auto::-webkit-scrollbar-track {
  background: transparent;
}
.dark .overflow-y-auto::-webkit-scrollbar-thumb {
  background: rgb(75 85 99); /* gray-600 */
  border-radius: 3px;
}
.dark .overflow-y-auto::-webkit-scrollbar-thumb:hover {
  background: rgb(107 114 128); /* gray-500 */
}
```

- [ ] **Step 2: Commit**

```bash
git add nextlen/src/index.css
git commit -m "feat(chat): add dark theme scrollbar styling"
```
