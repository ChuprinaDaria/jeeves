# Leads Page Enhancement — Design Spec

**Date:** 2026-03-24
**Status:** Approved

## Overview

Enhance the Leads page with three features: slide-in detail panel, single lead delete, CSV export. Plus bugfixes and minor improvements discovered during review.

## Scope

- CRM integrations — OUT OF SCOPE
- Manual lead creation (Add Lead) — OUT OF SCOPE (leads come only from AI)
- Bulk delete — OUT OF SCOPE (single delete only)
- XLSX export — OUT OF SCOPE (CSV only for now)
- Notes, Tags, AI Score explanation — OUT OF SCOPE (future iteration)

## Bugfixes (discovered during review)

### Pagination broken
Frontend reads `data.count` but backend returns `total`. Pagination never works — `totalPages` stays 1. Fix: change frontend to read `data.total`.

### Dark theme on table header
`dark:bg-gray-750` is not a standard Tailwind class. Fix: replace with `dark:bg-gray-800/50`.

### Missing Email in source filter
Model supports `SOURCE_EMAIL = 'email'` and frontend has icon/color for it, but the source filter dropdown is missing the Email option.

### N+1 query on backend
`LeadSerializer` accesses `conversation.id` but `LeadListView` doesn't use `select_related('conversation')`. Fix: add it.

## Feature 1: Slide-in Detail Panel

### Trigger
Click on any lead row in the table opens a slide-in panel from the right side.

### Layout
- Overlay panel, ~400px wide, slides in from right
- Semi-transparent backdrop behind it
- Dark theme support

### Content (top to bottom)
1. **Header**: Lead name (or "Anonymous #ID"), close button (X)
2. **Contact Info**: Email, Phone, Source (with SourceBadge icon)
3. **Status**: Current status with StatusDropdown (editable inline)
4. **Interest**: HeatIndicator with current score
5. **AI Summary**: `request_summary` field displayed as text block. Show "No summary yet" placeholder if empty.
6. **Date**: Created at, formatted
7. **Actions footer**: "View Conversation" button (navigates to `/history?conversation=X`), disabled if no conversation linked

### Closing
- Click X button
- Click outside panel (on backdrop)
- Press Escape key (must not close panel if StatusDropdown is open inside it — dropdown closes first)

### Interaction with table
- Clicking conversation ExternalLink icon in table should still work (navigate directly, NOT open panel)
- Clicking delete icon in table should NOT open panel
- Clicking StatusDropdown in table should NOT open panel

## Feature 2: Single Lead Delete

### UI
- Trash2 icon (lucide-react) added to Actions column, next to existing ExternalLink icon
- Subtle gray color, red on hover

### Flow
1. Click trash icon
2. Confirmation dialog appears (simple modal): "Delete lead {name}? This action cannot be undone."
3. Confirm → `DELETE /clients/leads/:id/` (existing endpoint)
4. Success → remove lead from local state (no refetch needed). Note: backend returns 204, do not rely on response body — check status code only.
5. Error → show inline error message

### Interaction
- Click on trash icon must NOT trigger row click (stopPropagation)

## Feature 3: CSV Export

### UI
- "Export" button with Download icon (lucide-react) in the filters bar, right side
- Styled consistently with existing filter controls

### Behavior
- Exports ALL filtered leads, not just current page
- Before export: fetch all leads matching current filters via API call with `per_page=10000`
- Columns: Name, Email, Phone, Source, Interest, Status, Date, AI Summary
- Interest score mapped to label (Cold/Cool/Warm/Hot/Fire)
- File name: `leads-export-YYYY-MM-DD.csv`
- Triggers browser download
- CSV escaping: fields containing commas, double quotes, or newlines must be wrapped in double quotes; inner double quotes escaped as `""`

### Edge cases
- Button disabled when leads array is empty or during export fetch
- Loading state on button during export

## Technical Notes

### Frontend (LeadsPage.jsx)
- New components within same file: `LeadDetailPanel`, `DeleteConfirmDialog`
- `LeadDetailPanel` is the largest new component; if file exceeds ~600 lines, extract to `components/leads/LeadDetailPanel.jsx`
- CSV generation: manual string building with proper escaping, no external library

### Backend (views_leads.py)
- Add `select_related('conversation')` to LeadListView queryset
- No other backend changes needed

### Data flow
- Panel reads from already-fetched lead object in `leads` state
- No additional API calls needed for panel
- CSV export makes one additional API call to fetch all filtered leads
