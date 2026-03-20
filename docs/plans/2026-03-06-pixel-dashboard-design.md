# Pixel Dashboard Design

## Overview

A pixel art Canvas 2D visualization module for the Nexelin dashboard that displays real-time system processes (RAG queries, document processing, HITL escalations, Celery tasks, server status) as animated characters in a miniature office/factory scene. Enabled per-client via Django admin.

## Architecture

### Module Structure

Self-contained module at `nextlen/src/modules/pixelDashboard/` with zero dependencies on other project components except `clientAPI`, `useAuth`, and `i18next`.

```
nextlen/src/modules/pixelDashboard/
├── PixelDashboard.jsx          # Main component (Canvas container)
├── engine/
│   ├── GameLoop.js             # requestAnimationFrame loop
│   ├── SpriteSheet.js          # Sprite sheet loading and slicing
│   ├── Character.js            # Character class (state, animation, movement)
│   └── Scene.js                # Scene — zones, tiles, camera
├── zones/
│   ├── ArchiveZone.js          # RAG retrieval — searching in archive
│   ├── DeliveryZone.js         # RAG response — running with paper
│   ├── DeskZone.js             # Document processing — writing at desk
│   ├── ManagerRoom.js          # HITL escalation — running to manager
│   └── FactoryZone.js         # Celery tasks + server status — conveyor/gears
├── hooks/
│   └── usePixelStatus.js       # Polling hook — GET /api/clients/pixel-status/
├── assets/                     # Sprite sheets (PNG) from itch.io
│   ├── characters.png
│   ├── tiles.png
│   └── furniture.png
└── constants.js                # Tile sizes, FPS, polling interval
```

### Integration Point

`DashboardPage.jsx` conditionally renders `<PixelDashboard />` only when `client.pixel_dashboard_enabled === true`. The field comes from the existing `/api/clients/me/` endpoint.

## Backend

### New Model Field

```python
# Client model
pixel_dashboard_enabled = models.BooleanField(
    default=False,
    help_text="Enable pixel art dashboard visualization"
)
```

Exposed in existing `/api/clients/me/` serializer. Toggled manually in Django admin.

### New Endpoint: `GET /api/clients/pixel-status/`

Returns current system state for the authenticated client:

```json
{
  "rag": {
    "active_queries": 2,
    "recent_responses": 1
  },
  "documents": {
    "processing": 3
  },
  "escalations": {
    "active": 1
  },
  "celery": {
    "pending": 5,
    "running": 2,
    "failed": 0
  },
  "server": {
    "cpu_percent": 45,
    "memory_percent": 62,
    "status": "healthy"
  }
}
```

**Data sources:**
- `rag` — count active conversations with recent activity (last 30s for queries, last 60s for responses)
- `documents` — `ClientDocument.objects.filter(client=client, is_processed=False).count()`
- `escalations` — active HITL escalations from Matrix/Telegram
- `celery` — Celery inspect for client-related tasks
- `server` — `psutil` for CPU/memory, or cached Redis values

### Authorization

Same as other client endpoints — JWT token or API Key. Only returns data if `pixel_dashboard_enabled=True`, otherwise 403.

## Frontend

### Canvas Rendering

- Internal scene size: **480x160 px**
- Canvas scaled to container width with `image-rendering: pixelated`
- Tile size: **16x16 px**, characters: **16x32 px**
- Frame rate: **15 FPS**

### Scene Layout (left to right)

```
[Archive/Library] [Desk] [Corridor] [Manager Room] [Factory]
   RAG search     Docs    Delivery     HITL        Celery/Server
                         (running)
```

### State-to-Scene Mapping

| Data                      | Zone          | Visualization                              |
|---------------------------|---------------|--------------------------------------------|
| `rag.active_queries > 0`  | Archive       | Character flipping through documents       |
| `rag.recent_responses > 0`| Delivery      | Character running with paper               |
| `documents.processing > 0`| Desk          | Character writing at desk                  |
| `escalations.active > 0`  | Manager Room  | Character running to manager               |
| `celery.running > 0`      | Factory       | Conveyor spinning, smoke rising            |
| `server.cpu_percent`      | Factory       | Gear speed / indicator color               |
| `server.status`           | Factory       | Green/yellow/red light                     |

When no processes are active — characters idle (sitting, drinking coffee, resting). Number of active processes = number of moving characters in that zone.

### Character Animations (sprite sheet frames)

| State  | Frames | Description                    |
|--------|--------|--------------------------------|
| `idle` | 2      | Standing, breathing            |
| `walk` | 4      | Walking left-right or back     |
| `work` | 2      | Writing / flipping documents   |
| `run`  | 4      | Running with paper / to manager|

### Background Elements

- Bookshelves (Archive)
- Desk with lamp (Desk)
- Door with sign (Manager Room)
- Conveyor, gears, chimney (Factory) — gears always animated, speed depends on `cpu_percent`
- Server status light — green/yellow/red circle

### Responsive

- Canvas scales via CSS `width: 100%`, internal resolution stays 480x160
- Mobile: horizontal scroll or scale down

### Assets

Free asset packs from itch.io (CC0 or similar license):
- Office/RPG character sprites (16x32, 4-directional)
- Interior tileset (16x16 — furniture, shelves, desks)
- Factory/industrial tileset (gears, conveyor, chimney)

### Polling

`usePixelStatus` hook:
- `GET /api/clients/pixel-status/` every 5 seconds
- Does not start if `pixel_dashboard_enabled === false`
- Graceful error handling — scene shows idle state on failure

### i18n

All UI text (zone labels, tooltips) via existing `react-i18next`. English by default, keys added to locale files.

## Access Control

- `pixel_dashboard_enabled` field on `Client` model, default `False`
- Toggled manually in Django admin
- Frontend checks the field from `/api/clients/me/` response
- Backend endpoint returns 403 if feature is disabled
