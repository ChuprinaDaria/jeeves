# Pixel Dashboard Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a Canvas 2D pixel art visualization to the dashboard that shows real-time system processes (RAG, documents, escalations, Celery, server) as animated characters, enabled per-client via Django admin.

**Architecture:** Self-contained React module at `nextlen/src/modules/pixelDashboard/` with Canvas 2D rendering. Backend exposes a polling endpoint for real-time process counts. Feature gated by `pixel_dashboard_enabled` boolean on Client model.

**Tech Stack:** Django (model field, API view), React (Canvas 2D, requestAnimationFrame), free pixel art assets from itch.io, existing i18next for text.

---

### Task 1: Add `pixel_dashboard_enabled` field to Client model

**Files:**
- Modify: `p004_ai_nexelin/MASTER/clients/models.py:202-203`
- Create: `p004_ai_nexelin/MASTER/clients/migrations/0044_client_pixel_dashboard_enabled.py`

**Step 1: Add field to model**

In `p004_ai_nexelin/MASTER/clients/models.py`, after `extension_enabled` field (line 202), add:

```python
    # Pixel art dashboard visualization
    pixel_dashboard_enabled = models.BooleanField(
        default=False,
        help_text="Enable pixel art dashboard visualization for this client"
    )
```

**Step 2: Generate migration**

Run: `cd p004_ai_nexelin && python manage.py makemigrations clients -n client_pixel_dashboard_enabled`
Expected: Migration file created

**Step 3: Apply migration**

Run: `cd p004_ai_nexelin && python manage.py migrate clients`
Expected: Migration applied successfully

**Step 4: Commit**

```bash
git add p004_ai_nexelin/MASTER/clients/models.py p004_ai_nexelin/MASTER/clients/migrations/0044_*
git commit -m "feat: add pixel_dashboard_enabled field to Client model"
```

---

### Task 2: Expose field in serializer and admin

**Files:**
- Modify: `p004_ai_nexelin/MASTER/clients/serializers.py:48`
- Modify: `p004_ai_nexelin/MASTER/clients/admin.py:42,112-116`

**Step 1: Add to ClientSerializer**

In `p004_ai_nexelin/MASTER/clients/serializers.py`, in the `fields` list after `'extension_enabled'` (line 48), add:

```python
            'pixel_dashboard_enabled',
```

**Step 2: Add to admin list_display**

In `p004_ai_nexelin/MASTER/clients/admin.py`, in `list_display` after `'extension_enabled'` (line 42), add:

```python
        'pixel_dashboard_enabled',
```

**Step 3: Add admin fieldset**

In `p004_ai_nexelin/MASTER/clients/admin.py`, after the 'Browser Extension' fieldset (lines 109-116), add:

```python
        (
            'Pixel Dashboard',
            {
                'fields': ('pixel_dashboard_enabled',),
                'classes': ('collapse',),
                'description': 'Enable pixel art visualization on client dashboard showing real-time system processes',
            },
        ),
```

**Step 4: Add to list_filter**

In `p004_ai_nexelin/MASTER/clients/admin.py`, in `list_filter` (line 52), add `'pixel_dashboard_enabled'`.

**Step 5: Verify admin loads**

Run: `cd p004_ai_nexelin && python manage.py check`
Expected: System check identified no issues

**Step 6: Commit**

```bash
git add p004_ai_nexelin/MASTER/clients/serializers.py p004_ai_nexelin/MASTER/clients/admin.py
git commit -m "feat: expose pixel_dashboard_enabled in serializer and admin"
```

---

### Task 3: Create pixel-status API endpoint

**Files:**
- Modify: `p004_ai_nexelin/MASTER/clients/views.py` (append new view)
- Modify: `p004_ai_nexelin/MASTER/clients/urls.py:25`

**Step 1: Add PixelDashboardStatusView**

Append to `p004_ai_nexelin/MASTER/clients/views.py`:

```python
class PixelDashboardStatusView(APIView):
    """
    GET /api/clients/pixel-status/
    Returns real-time process counts for pixel dashboard visualization.
    """
    permission_classes = []

    def get(self, request):
        client = get_client_from_request(request)

        if not client and 'HTTP_X_API_KEY' in request.META:
            api_key = request.META['HTTP_X_API_KEY']
            try:
                key_obj = ClientAPIKey.objects.select_related('client').get(
                    key=api_key,
                    is_active=True
                )
                if key_obj.is_valid():
                    client = key_obj.client
            except ClientAPIKey.DoesNotExist:
                pass

        if not client:
            return Response(
                {'error': 'Client not found'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        if not client.pixel_dashboard_enabled:
            return Response(
                {'error': 'Pixel dashboard not enabled'},
                status=status.HTTP_403_FORBIDDEN
            )

        from django.utils import timezone
        from datetime import timedelta
        import psutil

        now = timezone.now()

        # RAG: active conversations with recent activity
        recent_queries = ClientWhatsAppConversation.objects.filter(
            client=client,
            is_active=True,
            last_activity_at__gte=now - timedelta(seconds=30)
        ).count()

        recent_responses = ClientWhatsAppConversation.objects.filter(
            client=client,
            last_activity_at__gte=now - timedelta(seconds=60),
            total_messages__gte=2
        ).count()

        # Documents being processed
        docs_processing = ClientDocument.objects.filter(
            client=client,
            is_processed=False
        ).count()

        # Active escalations (HITL)
        active_escalations = 0
        if client.hitl_enabled or client.matrix_hitl_enabled:
            active_escalations = ClientWhatsAppConversation.objects.filter(
                client=client,
                is_active=True,
                context_metadata__contains={'escalated': True}
            ).count()

        # Celery tasks
        celery_stats = {'pending': 0, 'running': 0, 'failed': 0}
        try:
            from celery import current_app
            inspect = current_app.control.inspect(timeout=1.0)
            active = inspect.active() or {}
            reserved = inspect.reserved() or {}
            for worker_tasks in active.values():
                for task in worker_tasks:
                    if str(client.id) in str(task.get('args', '')) or str(client.tag) in str(task.get('args', '')):
                        celery_stats['running'] += 1
            for worker_tasks in reserved.values():
                for task in worker_tasks:
                    if str(client.id) in str(task.get('args', '')) or str(client.tag) in str(task.get('args', '')):
                        celery_stats['pending'] += 1
        except Exception:
            pass

        # Server status
        try:
            cpu = psutil.cpu_percent(interval=0)
            memory = psutil.virtual_memory().percent
            server_status = 'healthy' if cpu < 80 and memory < 85 else ('warning' if cpu < 95 and memory < 95 else 'critical')
        except Exception:
            cpu, memory, server_status = 0, 0, 'unknown'

        return Response({
            'rag': {
                'active_queries': recent_queries,
                'recent_responses': recent_responses,
            },
            'documents': {
                'processing': docs_processing,
            },
            'escalations': {
                'active': active_escalations,
            },
            'celery': celery_stats,
            'server': {
                'cpu_percent': cpu,
                'memory_percent': memory,
                'status': server_status,
            },
        })
```

**Step 2: Add URL pattern**

In `p004_ai_nexelin/MASTER/clients/urls.py`, after line 25 (`model-status` path), add:

```python
    path('pixel-status/', views.PixelDashboardStatusView.as_view(), name='client-pixel-status'),
```

**Step 3: Verify endpoint loads**

Run: `cd p004_ai_nexelin && python manage.py check`
Expected: No issues

**Step 4: Commit**

```bash
git add p004_ai_nexelin/MASTER/clients/views.py p004_ai_nexelin/MASTER/clients/urls.py
git commit -m "feat: add pixel-status API endpoint"
```

---

### Task 4: Add frontend API method and i18n keys

**Files:**
- Modify: `nextlen/src/api/client.js:114`
- Modify: `nextlen/src/locales/en/translation.json`
- Modify: `nextlen/src/locales/uk/translation.json` (and other locale files)

**Step 1: Add clientAPI method**

In `nextlen/src/api/client.js`, after `getModelStatus` (line 114), add:

```javascript
  // Pixel Dashboard Status API
  getPixelStatus: () => api.get('/clients/pixel-status/'),
```

**Step 2: Add English i18n keys**

In `nextlen/src/locales/en/translation.json`, add a new `"pixelDashboard"` section:

```json
"pixelDashboard": {
  "title": "System Monitor",
  "zones": {
    "archive": "Knowledge Base",
    "desk": "Processing",
    "delivery": "Responses",
    "manager": "Escalations",
    "factory": "System"
  },
  "status": {
    "healthy": "Healthy",
    "warning": "Warning",
    "critical": "Critical",
    "idle": "Idle"
  }
}
```

**Step 3: Add Ukrainian i18n keys**

In `nextlen/src/locales/uk/translation.json`, add matching section:

```json
"pixelDashboard": {
  "title": "Монітор системи",
  "zones": {
    "archive": "База знань",
    "desk": "Обробка",
    "delivery": "Відповіді",
    "manager": "Ескалації",
    "factory": "Система"
  },
  "status": {
    "healthy": "Працює",
    "warning": "Увага",
    "critical": "Критично",
    "idle": "Спокій"
  }
}
```

**Step 4: Add keys to other locale files (de, es, fr, it, nl, da)**

Add English keys as fallback to each locale file.

**Step 5: Commit**

```bash
git add nextlen/src/api/client.js nextlen/src/locales/
git commit -m "feat: add pixel dashboard API method and i18n keys"
```

---

### Task 5: Download pixel art assets

**Files:**
- Create: `nextlen/src/modules/pixelDashboard/assets/` directory
- Download sprite sheets from itch.io

**Step 1: Create assets directory**

```bash
mkdir -p nextlen/src/modules/pixelDashboard/assets
```

**Step 2: Find and download free assets**

Search itch.io for free CC0/open-license assets:
- **Characters**: 16x32 RPG characters with idle/walk/work animations (e.g., "Tiny RPG - Character Asset Pack" or similar)
- **Interior tiles**: 16x16 office furniture, shelves, desks (e.g., "Modern Interiors" or "Office Tileset")
- **Factory/industrial**: gears, conveyor, chimney elements

Download PNGs to `nextlen/src/modules/pixelDashboard/assets/`.

**Step 3: Create asset manifest**

Create `nextlen/src/modules/pixelDashboard/assets/ASSETS.md` with attribution info:
- Asset pack name, author, license, URL for each downloaded pack

**Step 4: Commit**

```bash
git add nextlen/src/modules/pixelDashboard/assets/
git commit -m "feat: add pixel art sprite assets for dashboard"
```

---

### Task 6: Build Canvas engine core

**Files:**
- Create: `nextlen/src/modules/pixelDashboard/constants.js`
- Create: `nextlen/src/modules/pixelDashboard/engine/GameLoop.js`
- Create: `nextlen/src/modules/pixelDashboard/engine/SpriteSheet.js`

**Step 1: Create constants**

Create `nextlen/src/modules/pixelDashboard/constants.js`:

```javascript
export const TILE_SIZE = 16;
export const CANVAS_WIDTH = 480;
export const CANVAS_HEIGHT = 160;
export const FPS = 15;
export const FRAME_DURATION = 1000 / FPS;
export const POLLING_INTERVAL = 5000;
export const CHARACTER_WIDTH = 16;
export const CHARACTER_HEIGHT = 32;

export const ZONES = {
  ARCHIVE:  { x: 0,   y: 0, width: 96,  height: 160, label: 'archive' },
  DESK:     { x: 96,  y: 0, width: 96,  height: 160, label: 'desk' },
  CORRIDOR: { x: 192, y: 0, width: 96,  height: 160, label: 'delivery' },
  MANAGER:  { x: 288, y: 0, width: 96,  height: 160, label: 'manager' },
  FACTORY:  { x: 384, y: 0, width: 96,  height: 160, label: 'factory' },
};

export const CHARACTER_STATES = {
  IDLE: 'idle',
  WALK: 'walk',
  WORK: 'work',
  RUN:  'run',
};
```

**Step 2: Create GameLoop**

Create `nextlen/src/modules/pixelDashboard/engine/GameLoop.js`:

```javascript
import { FRAME_DURATION } from '../constants';

export default class GameLoop {
  constructor(updateFn, renderFn) {
    this.update = updateFn;
    this.render = renderFn;
    this.animationId = null;
    this.lastTime = 0;
    this.accumulated = 0;
  }

  start() {
    this.lastTime = performance.now();
    this.tick(this.lastTime);
  }

  tick = (currentTime) => {
    this.animationId = requestAnimationFrame(this.tick);
    const delta = currentTime - this.lastTime;
    this.lastTime = currentTime;
    this.accumulated += delta;

    while (this.accumulated >= FRAME_DURATION) {
      this.update(FRAME_DURATION);
      this.accumulated -= FRAME_DURATION;
    }

    this.render();
  };

  stop() {
    if (this.animationId) {
      cancelAnimationFrame(this.animationId);
      this.animationId = null;
    }
  }
}
```

**Step 3: Create SpriteSheet**

Create `nextlen/src/modules/pixelDashboard/engine/SpriteSheet.js`:

```javascript
export default class SpriteSheet {
  constructor(image, frameWidth, frameHeight) {
    this.image = image;
    this.frameWidth = frameWidth;
    this.frameHeight = frameHeight;
    this.cols = Math.floor(image.width / frameWidth);
  }

  static async load(src, frameWidth, frameHeight) {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => resolve(new SpriteSheet(img, frameWidth, frameHeight));
      img.onerror = reject;
      img.src = src;
    });
  }

  draw(ctx, frameIndex, x, y, flipX = false) {
    const col = frameIndex % this.cols;
    const row = Math.floor(frameIndex / this.cols);
    const sx = col * this.frameWidth;
    const sy = row * this.frameHeight;

    if (flipX) {
      ctx.save();
      ctx.scale(-1, 1);
      ctx.drawImage(
        this.image,
        sx, sy, this.frameWidth, this.frameHeight,
        -x - this.frameWidth, y, this.frameWidth, this.frameHeight
      );
      ctx.restore();
    } else {
      ctx.drawImage(
        this.image,
        sx, sy, this.frameWidth, this.frameHeight,
        x, y, this.frameWidth, this.frameHeight
      );
    }
  }
}
```

**Step 4: Commit**

```bash
git add nextlen/src/modules/pixelDashboard/constants.js nextlen/src/modules/pixelDashboard/engine/
git commit -m "feat: add pixel dashboard canvas engine core"
```

---

### Task 7: Build Character class

**Files:**
- Create: `nextlen/src/modules/pixelDashboard/engine/Character.js`

**Step 1: Create Character class**

Create `nextlen/src/modules/pixelDashboard/engine/Character.js`:

```javascript
import { CHARACTER_STATES, CHARACTER_HEIGHT } from '../constants';

const ANIMATION_FRAMES = {
  [CHARACTER_STATES.IDLE]: { start: 0, count: 2, speed: 500 },
  [CHARACTER_STATES.WALK]: { start: 2, count: 4, speed: 150 },
  [CHARACTER_STATES.WORK]: { start: 6, count: 2, speed: 400 },
  [CHARACTER_STATES.RUN]:  { start: 8, count: 4, speed: 100 },
};

export default class Character {
  constructor(spriteSheet, x, y) {
    this.spriteSheet = spriteSheet;
    this.x = x;
    this.y = y;
    this.targetX = x;
    this.targetY = y;
    this.state = CHARACTER_STATES.IDLE;
    this.frameTimer = 0;
    this.currentFrame = 0;
    this.speed = 1;
    this.flipX = false;
    this.visible = false;
    this.animRow = 0;
  }

  setState(state) {
    if (this.state !== state) {
      this.state = state;
      this.currentFrame = 0;
      this.frameTimer = 0;
    }
  }

  moveTo(x, y) {
    this.targetX = x;
    this.targetY = y;
  }

  update(dt) {
    if (!this.visible) return;

    const anim = ANIMATION_FRAMES[this.state];
    this.frameTimer += dt;
    if (this.frameTimer >= anim.speed) {
      this.frameTimer -= anim.speed;
      this.currentFrame = (this.currentFrame + 1) % anim.count;
    }

    const dx = this.targetX - this.x;
    const dy = this.targetY - this.y;
    const dist = Math.sqrt(dx * dx + dy * dy);

    if (dist > 1) {
      const moveSpeed = this.state === CHARACTER_STATES.RUN ? this.speed * 2 : this.speed;
      this.x += (dx / dist) * moveSpeed;
      this.y += (dy / dist) * moveSpeed;
      this.flipX = dx < 0;
    } else {
      this.x = this.targetX;
      this.y = this.targetY;
    }
  }

  render(ctx) {
    if (!this.visible) return;
    const anim = ANIMATION_FRAMES[this.state];
    const frameIndex = (this.animRow * this.spriteSheet.cols) + anim.start + this.currentFrame;
    this.spriteSheet.draw(ctx, frameIndex, Math.round(this.x), Math.round(this.y) - CHARACTER_HEIGHT, this.flipX);
  }
}
```

**Step 2: Commit**

```bash
git add nextlen/src/modules/pixelDashboard/engine/Character.js
git commit -m "feat: add Character class with animation state machine"
```

---

### Task 8: Build Scene with zones

**Files:**
- Create: `nextlen/src/modules/pixelDashboard/engine/Scene.js`
- Create: `nextlen/src/modules/pixelDashboard/zones/ArchiveZone.js`
- Create: `nextlen/src/modules/pixelDashboard/zones/DeskZone.js`
- Create: `nextlen/src/modules/pixelDashboard/zones/DeliveryZone.js`
- Create: `nextlen/src/modules/pixelDashboard/zones/ManagerRoom.js`
- Create: `nextlen/src/modules/pixelDashboard/zones/FactoryZone.js`

**Step 1: Create base Zone pattern**

Each zone file exports a class with `update(dt, statusData)` and `render(ctx, tileSheet)` methods, plus manages its own characters. The zone reads relevant data from the status object and activates/deactivates characters accordingly.

Example zone — `ArchiveZone.js`:

```javascript
import { ZONES, CHARACTER_STATES } from '../constants';

export default class ArchiveZone {
  constructor(characters) {
    this.zone = ZONES.ARCHIVE;
    this.characters = characters;
    this.shelfY = 80;
  }

  update(dt, status) {
    const activeQueries = status?.rag?.active_queries || 0;

    this.characters.forEach((char, i) => {
      if (i < activeQueries) {
        char.visible = true;
        char.setState(CHARACTER_STATES.WORK);
        char.moveTo(this.zone.x + 20 + i * 24, this.shelfY);
      } else {
        char.visible = false;
      }
    });
  }

  render(ctx) {
    // Draw bookshelves background
    ctx.fillStyle = '#5b3a29';
    for (let i = 0; i < 3; i++) {
      ctx.fillRect(this.zone.x + 8 + i * 28, 16, 24, 48);
      ctx.fillStyle = '#8b6914';
      for (let j = 0; j < 3; j++) {
        ctx.fillRect(this.zone.x + 10 + i * 28, 20 + j * 14, 20, 10);
      }
      ctx.fillStyle = '#5b3a29';
    }
  }
}
```

Other zones follow same pattern but with different visual elements and state mappings. `FactoryZone` draws animated gears based on `server.cpu_percent` and a status light based on `server.status`.

**Step 2: Create Scene**

Create `nextlen/src/modules/pixelDashboard/engine/Scene.js`:

```javascript
import { CANVAS_WIDTH, CANVAS_HEIGHT } from '../constants';
import ArchiveZone from '../zones/ArchiveZone';
import DeskZone from '../zones/DeskZone';
import DeliveryZone from '../zones/DeliveryZone';
import ManagerRoom from '../zones/ManagerRoom';
import FactoryZone from '../zones/FactoryZone';

export default class Scene {
  constructor(characterSpriteSheet) {
    this.spriteSheet = characterSpriteSheet;
    this.characters = [];
    this.zones = [];
    this.status = {};
  }

  async init(spriteSheet) {
    const Character = (await import('./Character')).default;

    // Create character pool (max 3 per zone)
    for (let i = 0; i < 15; i++) {
      this.characters.push(new Character(spriteSheet, 0, 0));
    }

    // Assign characters to zones
    this.zones = [
      new ArchiveZone(this.characters.slice(0, 3)),
      new DeskZone(this.characters.slice(3, 6)),
      new DeliveryZone(this.characters.slice(6, 9)),
      new ManagerRoom(this.characters.slice(9, 12)),
      new FactoryZone(this.characters.slice(12, 15)),
    ];
  }

  setStatus(status) {
    this.status = status;
  }

  update(dt) {
    this.zones.forEach(zone => zone.update(dt, this.status));
    this.characters.forEach(char => char.update(dt));
  }

  render(ctx) {
    // Clear
    ctx.fillStyle = '#1a1a2e';
    ctx.fillRect(0, 0, CANVAS_WIDTH, CANVAS_HEIGHT);

    // Floor
    ctx.fillStyle = '#2d2d44';
    ctx.fillRect(0, CANVAS_HEIGHT - 32, CANVAS_WIDTH, 32);

    // Zone backgrounds and decorations
    this.zones.forEach(zone => zone.render(ctx));

    // Characters on top
    this.characters.forEach(char => char.render(ctx));
  }
}
```

**Step 3: Create all zone files**

Create `DeskZone.js`, `DeliveryZone.js`, `ManagerRoom.js`, `FactoryZone.js` following the same pattern as ArchiveZone but with their own visual logic:

- **DeskZone**: characters with WORK state when `documents.processing > 0`, draws desk + lamp
- **DeliveryZone**: characters with RUN state when `rag.recent_responses > 0`, draws corridor
- **ManagerRoom**: characters with RUN state when `escalations.active > 0`, draws door + sign
- **FactoryZone**: animated gears (rotation angle based on `cpu_percent`), status light, smoke particles when `celery.running > 0`

**Step 4: Commit**

```bash
git add nextlen/src/modules/pixelDashboard/engine/Scene.js nextlen/src/modules/pixelDashboard/zones/
git commit -m "feat: add Scene manager and all zone renderers"
```

---

### Task 9: Build usePixelStatus hook

**Files:**
- Create: `nextlen/src/modules/pixelDashboard/hooks/usePixelStatus.js`

**Step 1: Create polling hook**

Create `nextlen/src/modules/pixelDashboard/hooks/usePixelStatus.js`:

```javascript
import { useState, useEffect, useRef } from 'react';
import { clientAPI } from '../../../api/client';
import { POLLING_INTERVAL } from '../constants';

export default function usePixelStatus(enabled) {
  const [status, setStatus] = useState(null);
  const intervalRef = useRef(null);

  useEffect(() => {
    if (!enabled) return;

    const fetchStatus = async () => {
      try {
        const response = await clientAPI.getPixelStatus();
        setStatus(response.data);
      } catch {
        // Keep last known status on error
      }
    };

    fetchStatus();
    intervalRef.current = setInterval(fetchStatus, POLLING_INTERVAL);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [enabled]);

  return status;
}
```

**Step 2: Commit**

```bash
git add nextlen/src/modules/pixelDashboard/hooks/usePixelStatus.js
git commit -m "feat: add usePixelStatus polling hook"
```

---

### Task 10: Build PixelDashboard main component

**Files:**
- Create: `nextlen/src/modules/pixelDashboard/PixelDashboard.jsx`

**Step 1: Create main component**

Create `nextlen/src/modules/pixelDashboard/PixelDashboard.jsx`:

```jsx
import { useRef, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { CANVAS_WIDTH, CANVAS_HEIGHT } from './constants';
import GameLoop from './engine/GameLoop';
import Scene from './engine/Scene';
import SpriteSheet from './engine/SpriteSheet';
import usePixelStatus from './hooks/usePixelStatus';

import charactersSrc from './assets/characters.png';

const PixelDashboard = ({ enabled }) => {
  const canvasRef = useRef(null);
  const sceneRef = useRef(null);
  const gameLoopRef = useRef(null);
  const { t } = useTranslation();
  const status = usePixelStatus(enabled);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!enabled) return;

    let cancelled = false;

    const init = async () => {
      const spriteSheet = await SpriteSheet.load(charactersSrc, 16, 32);
      if (cancelled) return;

      const scene = new Scene();
      await scene.init(spriteSheet);
      sceneRef.current = scene;

      const canvas = canvasRef.current;
      const ctx = canvas.getContext('2d');
      ctx.imageSmoothingEnabled = false;

      const gameLoop = new GameLoop(
        (dt) => scene.update(dt),
        () => scene.render(ctx)
      );
      gameLoopRef.current = gameLoop;
      gameLoop.start();
      setReady(true);
    };

    init();

    return () => {
      cancelled = true;
      if (gameLoopRef.current) {
        gameLoopRef.current.stop();
      }
    };
  }, [enabled]);

  useEffect(() => {
    if (sceneRef.current && status) {
      sceneRef.current.setStatus(status);
    }
  }, [status]);

  if (!enabled) return null;

  return (
    <div className="rounded-lg overflow-hidden border border-gray-200 dark:border-gray-700 bg-gray-900">
      <div className="px-4 py-2 border-b border-gray-700 flex items-center justify-between">
        <span className="text-sm font-medium text-gray-300">
          {t('pixelDashboard.title')}
        </span>
        {status?.server?.status && (
          <span className={`inline-block w-2 h-2 rounded-full ${
            status.server.status === 'healthy' ? 'bg-green-400' :
            status.server.status === 'warning' ? 'bg-yellow-400' : 'bg-red-400'
          }`} />
        )}
      </div>
      <canvas
        ref={canvasRef}
        width={CANVAS_WIDTH}
        height={CANVAS_HEIGHT}
        className="w-full"
        style={{ imageRendering: 'pixelated' }}
      />
    </div>
  );
};

export default PixelDashboard;
```

**Step 2: Commit**

```bash
git add nextlen/src/modules/pixelDashboard/PixelDashboard.jsx
git commit -m "feat: add PixelDashboard main component with Canvas rendering"
```

---

### Task 11: Integrate into DashboardPage

**Files:**
- Modify: `nextlen/src/pages/DashboardPage.jsx`

**Step 1: Add conditional render**

In `nextlen/src/pages/DashboardPage.jsx`:

1. Add import at top:
```javascript
import { lazy, Suspense } from 'react';
const PixelDashboard = lazy(() => import('../modules/pixelDashboard/PixelDashboard'));
```

2. Get client data from AuthContext — change line 10:
```javascript
const { isAuthenticated, loading: authLoading, user } = useAuth();
```

3. Add `<PixelDashboard />` before the stats grid (before `<div className="grid ..."`):
```jsx
{user?.pixel_dashboard_enabled && (
  <Suspense fallback={null}>
    <PixelDashboard enabled={user.pixel_dashboard_enabled} />
  </Suspense>
)}
```

**Step 2: Verify frontend builds**

Run: `cd nextlen && npm run build`
Expected: Build succeeds

**Step 3: Commit**

```bash
git add nextlen/src/pages/DashboardPage.jsx
git commit -m "feat: integrate PixelDashboard into DashboardPage with lazy loading"
```

---

### Task 12: Polish zones with proper pixel art rendering

**Files:**
- Modify: all zone files in `nextlen/src/modules/pixelDashboard/zones/`

**Step 1: Refine each zone**

Replace placeholder rectangles with sprite-based tile rendering using the downloaded tile assets. Add:

- **ArchiveZone**: bookshelf tiles, books with varied colors, reading lamp
- **DeskZone**: desk tile, paper stack, lamp with glow effect
- **DeliveryZone**: floor tiles for corridor, door frames on sides
- **ManagerRoom**: door with "Manager" sign tile, desk behind door
- **FactoryZone**: gear sprites (rotated each frame), conveyor belt tiles, chimney with smoke particles (simple pixel particles moving upward), status light (filled circle with color)

**Step 2: Add idle behavior**

When no processes are active in a zone, show one idle character (sitting, or standing with coffee cup frame if available in sprite sheet).

**Step 3: Test visually**

Run dev server: `cd nextlen && npm run dev`
Open dashboard with a client that has `pixel_dashboard_enabled=True`.
Verify all zones render correctly and respond to status changes.

**Step 4: Commit**

```bash
git add nextlen/src/modules/pixelDashboard/zones/
git commit -m "feat: polish zone rendering with sprite-based tiles and idle states"
```

---

### Task 13: End-to-end testing

**Step 1: Enable pixel dashboard for a test client in Django admin**

Go to `/admin/clients/client/`, select a test client, check `pixel_dashboard_enabled`, save.

**Step 2: Verify API endpoint**

```bash
curl -H "Authorization: Bearer <token>" http://localhost:8000/api/clients/pixel-status/
```

Expected: JSON with rag, documents, escalations, celery, server sections.

**Step 3: Verify disabled client gets 403**

Test with a client where `pixel_dashboard_enabled=False`:
Expected: `{"error": "Pixel dashboard not enabled"}` with 403 status.

**Step 4: Verify frontend**

- Login as enabled client — pixel dashboard visible above stats
- Login as disabled client — no pixel dashboard shown
- Check that polling works (network tab shows requests every 5s)
- Trigger a RAG query and verify archive zone activates
- Upload a document and verify desk zone activates

**Step 5: Commit final state**

```bash
git add -A
git commit -m "feat: pixel dashboard - complete implementation"
```
