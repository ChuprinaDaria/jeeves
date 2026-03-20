# XLSX Processor Skill — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add XLSX Processor as a builtin skill/middleware for creating, editing, and analyzing Excel files on the Nexelin platform.

**Architecture:** Builtin skill (like `translation`) that attaches to edges as middleware. Uses openpyxl for Excel operations, pandas for data analysis, LibreOffice headless for formula recalculation. No auth required — activated by attaching to edge.

**Tech Stack:** openpyxl, pandas, LibreOffice Calc (headless), Python 3.12

**Spec:** `docs/superpowers/specs/2026-03-20-tools-multi-connection-scopes-design.md` (multi-connection context)

**Branch:** `feature/sp1-mcp-core-engine`

**Working directories:**
- Backend: `/home/dchuprina/nexelin_web/p004_ai_nexelin/`
- Frontend: `/home/dchuprina/nexelin_web/nextlen/`

---

## File Structure

All paths relative to `p004_ai_nexelin/` (backend) or `nextlen/` (frontend).

| Action | Path | Responsibility |
|--------|------|----------------|
| Modify | `p004_ai_nexelin/requirements.txt` | Add openpyxl, pandas |
| Modify | `p004_ai_nexelin/Dockerfile` | Add libreoffice-calc |
| Modify | `p004_ai_nexelin/docker-compose.yml` | Add media/xlsx volume |
| Create | `p004_ai_nexelin/MASTER/mcp_hub/builtin/xlsx_processor.py` | Builtin handler: create, read, edit, recalculate |
| Create | `p004_ai_nexelin/scripts/recalc.py` | LibreOffice formula recalculation script |
| Modify | `p004_ai_nexelin/MASTER/tools/seed_data.py` | Add xlsx-processor entry |
| Create | `p004_ai_nexelin/MASTER/tools/migrations/0007_seed_xlsx_processor.py` | Data migration |
| Modify | `p004_ai_nexelin/MASTER/tools/admin.py` | Add skill_scopes, tagline_i18n to fieldsets |
| Modify | `nextlen/src/components/tools/ToolCatalogStrip.jsx` | Add xlsx-processor to SLUG_TO_GROUP |
| Modify | `nextlen/src/components/tools/toolTargets.js` | Add xlsx-processor targets |

---

### Task 1: Python dependencies

**Files:**
- Modify: `p004_ai_nexelin/requirements.txt:101` (append)

- [ ] **Step 1: Add openpyxl and pandas to requirements.txt**

Append to end of file:

```
openpyxl>=3.1.0
pandas>=2.2.0
```

- [ ] **Step 2: Verify no conflicts**

Run: `cd /home/dchuprina/nexelin_web/p004_ai_nexelin && pip install openpyxl>=3.1.0 pandas>=2.2.0 --dry-run`

Expected: no conflicts

- [ ] **Step 3: Commit**

```bash
cd /home/dchuprina/nexelin_web && git add p004_ai_nexelin/requirements.txt
git commit -m "deps: add openpyxl and pandas for xlsx-processor skill"
```

---

### Task 2: LibreOffice in Dockerfile

**Files:**
- Modify: `p004_ai_nexelin/Dockerfile:8-12`

- [ ] **Step 1: Add libreoffice-calc to Dockerfile apt-get**

Change the RUN apt-get block to include `libreoffice-calc`:

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    postgresql-client \
    libreoffice-calc \
 && rm -rf /var/lib/apt/lists/*
```

- [ ] **Step 2: Commit**

```bash
cd /home/dchuprina/nexelin_web && git add p004_ai_nexelin/Dockerfile
git commit -m "deps: add libreoffice-calc for xlsx formula recalculation"
```

---

### Task 3: Recalc script

**Files:**
- Create: `p004_ai_nexelin/scripts/recalc.py`

- [ ] **Step 1: Create the recalc script**

```python
"""Recalculate Excel formulas using LibreOffice headless.

Usage: python scripts/recalc.py <excel_file> [timeout_seconds]
Returns JSON with error details.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def recalculate(filepath: str, timeout: int = 60) -> dict:
    filepath = Path(filepath).resolve()
    if not filepath.exists():
        return {'status': 'error', 'message': f'File not found: {filepath}'}

    # Use a temp dir for LibreOffice profile to avoid locking issues
    with tempfile.TemporaryDirectory(prefix='lo_recalc_') as profile_dir:
        cmd = [
            'libreoffice',
            '--headless',
            '--calc',
            '--norestore',
            f'-env:UserInstallation=file://{profile_dir}',
            '--convert-to', 'xlsx',
            '--outdir', str(filepath.parent),
            str(filepath),
        ]

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return {'status': 'error', 'message': f'Timeout after {timeout}s'}
        except FileNotFoundError:
            return {'status': 'error', 'message': 'LibreOffice not installed'}

        if result.returncode != 0:
            return {
                'status': 'error',
                'message': f'LibreOffice error: {result.stderr.strip()}',
            }

    # Scan for formula errors
    return scan_errors(filepath)


def scan_errors(filepath: Path) -> dict:
    try:
        from openpyxl import load_workbook
    except ImportError:
        return {'status': 'error', 'message': 'openpyxl not installed'}

    # Load with formulas to count them
    wb_formulas = load_workbook(str(filepath), data_only=False)
    total_formulas = 0
    for sheet in wb_formulas.sheetnames:
        ws = wb_formulas[sheet]
        for row in ws.iter_rows():
            for cell in row:
                if cell.value and isinstance(cell.value, str) and cell.value.startswith('='):
                    total_formulas += 1
    wb_formulas.close()

    # Load with cached values to find errors
    wb = load_workbook(str(filepath), data_only=True)
    error_types = ('#REF!', '#DIV/0!', '#VALUE!', '#N/A', '#NAME?', '#NULL!', '#NUM!')
    error_summary = {}
    total_errors = 0

    for sheet_name in wb.sheetnames:
        sheet = wb[sheet_name]
        for row in sheet.iter_rows():
            for cell in row:
                if cell.value in error_types:
                    total_errors += 1
                    err_type = str(cell.value)
                    if err_type not in error_summary:
                        error_summary[err_type] = {'count': 0, 'locations': []}
                    error_summary[err_type]['count'] += 1
                    error_summary[err_type]['locations'].append(
                        f'{sheet_name}!{cell.coordinate}')

    wb.close()

    return {
        'status': 'errors_found' if total_errors > 0 else 'success',
        'total_errors': total_errors,
        'total_formulas': total_formulas,
        'error_summary': error_summary if error_summary else None,
    }


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(json.dumps({'status': 'error', 'message': 'Usage: python recalc.py <file> [timeout]'}))
        sys.exit(1)

    fpath = sys.argv[1]
    tout = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    result = recalculate(fpath, tout)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result['status'] == 'success' else 1)
```

- [ ] **Step 2: Test script exists and is parseable**

Run: `cd /home/dchuprina/nexelin_web/p004_ai_nexelin && python -c "import ast; ast.parse(open('scripts/recalc.py').read()); print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
cd /home/dchuprina/nexelin_web && git add p004_ai_nexelin/scripts/recalc.py
git commit -m "feat(tools): add recalc.py script for xlsx formula recalculation"
```

---

### Task 4: Builtin handler

**Files:**
- Create: `p004_ai_nexelin/MASTER/mcp_hub/builtin/xlsx_processor.py`

Reference: `MASTER/mcp_hub/builtin/rag_search.py` for handler pattern (async function with `connection, tool_name, **kwargs`).

- [ ] **Step 1: Create xlsx_processor.py**

```python
"""Builtin XLSX processor — create, read, edit, and analyze Excel files."""
import json
import logging
import os
import tempfile
from pathlib import Path

from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)

# Media dir for generated files
XLSX_OUTPUT_DIR = Path(os.environ.get(
    'XLSX_OUTPUT_DIR',
    Path(__file__).resolve().parent.parent.parent.parent / 'media' / 'xlsx'))


def _validate_path(filepath, output_dir):
    """Ensure filepath is within allowed output directory (prevent path traversal)."""
    resolved = Path(filepath).resolve()
    allowed = Path(output_dir).resolve()
    if not resolved.is_relative_to(allowed):
        return None, {'error': f'Access denied: path outside allowed directory'}
    return resolved, None


async def xlsx_processor(connection, tool_name, action='create', **kwargs):
    """Process XLSX operations.

    Actions:
        create  — create new workbook from data/formulas/formatting spec
        read    — read and return data from existing file
        edit    — modify existing file preserving formulas
        recalc  — recalculate formulas via LibreOffice
    """
    client = connection.client
    output_dir = XLSX_OUTPUT_DIR / str(client.pk)
    output_dir.mkdir(parents=True, exist_ok=True)

    handlers = {
        'create': _create_workbook,
        'read': _read_workbook,
        'edit': _edit_workbook,
        'recalc': _recalculate,
    }

    handler = handlers.get(action)
    if not handler:
        return {'error': f'Unknown action: {action}. Use: {", ".join(handlers)}'}

    try:
        return await sync_to_async(handler)(output_dir=output_dir, **kwargs)
    except Exception as e:
        logger.error(f'XLSX processor error for client {client.pk}: {e}')
        return {'error': str(e)}


def _create_workbook(output_dir, filename='report.xlsx', sheets=None, **kwargs):
    """Create a new Excel workbook.

    Args:
        filename: output filename
        sheets: list of sheet specs, each with:
            - name: sheet name
            - headers: list of column headers
            - rows: list of row data (lists)
            - formulas: dict of {cell: formula} e.g. {"B10": "=SUM(B2:B9)"}
            - column_widths: dict of {col_letter: width}
            - formatting: dict of cell formatting specs
    """
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    wb = Workbook()

    if not sheets:
        sheets = [{'name': 'Sheet1', 'headers': [], 'rows': []}]

    for i, sheet_spec in enumerate(sheets):
        if i == 0:
            ws = wb.active
            ws.title = sheet_spec.get('name', 'Sheet1')
        else:
            ws = wb.create_sheet(sheet_spec.get('name', f'Sheet{i + 1}'))

        # Headers
        headers = sheet_spec.get('headers', [])
        if headers:
            ws.append(headers)
            for col_idx, _ in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col_idx)
                cell.font = Font(name='Arial', bold=True, size=11)
                cell.fill = PatternFill('solid', fgColor='E2EFDA')
                cell.alignment = Alignment(horizontal='center')

        # Data rows
        for row_data in sheet_spec.get('rows', []):
            ws.append(row_data)

        # Formulas
        for cell_ref, formula in sheet_spec.get('formulas', {}).items():
            ws[cell_ref] = formula
            ws[cell_ref].font = Font(name='Arial', color='000000')

        # Column widths
        for col_letter, width in sheet_spec.get('column_widths', {}).items():
            ws.column_dimensions[col_letter].width = width

        # Default font for data cells
        for row in ws.iter_rows(min_row=2, max_row=ws.max_row,
                                max_col=ws.max_column):
            for cell in row:
                if cell.font == Font():
                    cell.font = Font(name='Arial', size=11)

    filepath = output_dir / filename
    wb.save(str(filepath))
    wb.close()

    return {
        'status': 'created',
        'filepath': str(filepath),
        'filename': filename,
        'sheets': [s.get('name', f'Sheet{i+1}') for i, s in enumerate(sheets)],
    }


def _read_workbook(filepath=None, sheet_name=None, output_dir=None, **kwargs):
    """Read Excel file and return structured data."""
    import pandas as pd

    if not filepath:
        return {'error': 'filepath is required'}

    path, err = _validate_path(filepath, output_dir)
    if err:
        return err
    if not path.exists():
        return {'error': f'File not found: {filepath}'}

    try:
        if sheet_name:
            df = pd.read_excel(str(path), sheet_name=sheet_name)
            return {
                'status': 'ok',
                'sheet': sheet_name,
                'columns': list(df.columns),
                'row_count': len(df),
                'data': df.head(100).to_dict(orient='records'),
                'dtypes': {col: str(dt) for col, dt in df.dtypes.items()},
            }
        else:
            all_sheets = pd.read_excel(str(path), sheet_name=None)
            result = {'status': 'ok', 'sheets': {}}
            for name, df in all_sheets.items():
                result['sheets'][name] = {
                    'columns': list(df.columns),
                    'row_count': len(df),
                    'data': df.head(50).to_dict(orient='records'),
                }
            return result
    except Exception as e:
        return {'error': f'Failed to read: {e}'}


def _edit_workbook(filepath=None, operations=None, output_dir=None, **kwargs):
    """Edit existing Excel file preserving formulas and formatting.

    Args:
        filepath: path to existing file
        operations: list of operations:
            - {type: 'set_cell', sheet: 'Sheet1', cell: 'A1', value: 'New Value'}
            - {type: 'set_formula', sheet: 'Sheet1', cell: 'B10', formula: '=SUM(B2:B9)'}
            - {type: 'insert_row', sheet: 'Sheet1', row: 2}
            - {type: 'delete_row', sheet: 'Sheet1', row: 3}
            - {type: 'add_sheet', name: 'NewSheet'}
    """
    from openpyxl import load_workbook

    if not filepath:
        return {'error': 'filepath is required'}

    path, err = _validate_path(filepath, output_dir)
    if err:
        return err
    if not path.exists():
        return {'error': f'File not found: {filepath}'}

    wb = load_workbook(str(path))
    applied = []

    for op in (operations or []):
        op_type = op.get('type')
        sheet_name = op.get('sheet')
        ws = wb[sheet_name] if sheet_name and sheet_name in wb.sheetnames else wb.active

        if op_type == 'set_cell':
            ws[op['cell']] = op['value']
            applied.append(f"set {sheet_name}!{op['cell']}")
        elif op_type == 'set_formula':
            ws[op['cell']] = op['formula']
            applied.append(f"formula {sheet_name}!{op['cell']}")
        elif op_type == 'insert_row':
            ws.insert_rows(op['row'])
            applied.append(f"insert row {op['row']} in {sheet_name}")
        elif op_type == 'delete_row':
            ws.delete_rows(op['row'])
            applied.append(f"delete row {op['row']} in {sheet_name}")
        elif op_type == 'add_sheet':
            wb.create_sheet(op['name'])
            applied.append(f"add sheet {op['name']}")

    wb.save(str(path))
    wb.close()

    return {
        'status': 'edited',
        'filepath': str(path),
        'operations_applied': applied,
    }


def _recalculate(filepath=None, output_dir=None, **kwargs):
    """Recalculate formulas using LibreOffice."""
    if not filepath:
        return {'error': 'filepath is required'}

    path, err = _validate_path(filepath, output_dir)
    if err:
        return err

    # Import recalc script
    import importlib.util
    recalc_path = Path(__file__).resolve().parent.parent.parent.parent / 'scripts' / 'recalc.py'

    if not recalc_path.exists():
        return {'error': 'recalc.py script not found'}

    spec = importlib.util.spec_from_file_location('recalc', str(recalc_path))
    recalc_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(recalc_mod)

    return recalc_mod.recalculate(filepath)
```

- [ ] **Step 2: Verify syntax**

Run: `cd /home/dchuprina/nexelin_web/p004_ai_nexelin && python -c "import ast; ast.parse(open('MASTER/mcp_hub/builtin/xlsx_processor.py').read()); print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
cd /home/dchuprina/nexelin_web && git add p004_ai_nexelin/MASTER/mcp_hub/builtin/xlsx_processor.py
git commit -m "feat(tools): add xlsx_processor builtin handler"
```

---

### Task 5: Seed data

**Files:**
- Modify: `p004_ai_nexelin/MASTER/tools/seed_data.py:171` (append before closing bracket)

- [ ] **Step 1: Add xlsx-processor to INITIAL_TOOLS**

Append after the `translation` entry (before `]`):

```python
    {
        'slug': 'xlsx-processor',
        'name': 'XLSX Processor',
        'tagline': 'Створення, редагування та аналіз Excel-файлів',
        'tagline_i18n': {
            'en': 'Create, edit, and analyze Excel spreadsheets',
            'de': 'Excel-Tabellen erstellen, bearbeiten und analysieren',
        },
        'icon': 'file-spreadsheet',
        'category': 'ai',
        'color': '#217346',
        'transport_type': 'builtin',
        'is_builtin': True,
        'builtin_handler': 'mcp_hub.builtin.xlsx_processor',
        'auth_type': 'none',
        'skill_scopes': {'scopes': ['assistant', 'manager'], 'bidirectional': True},
    },
```

- [ ] **Step 2: Commit**

```bash
cd /home/dchuprina/nexelin_web && git add p004_ai_nexelin/MASTER/tools/seed_data.py
git commit -m "feat(tools): add xlsx-processor to seed data"
```

---

### Task 6: Data migration

**Files:**
- Create: `p004_ai_nexelin/MASTER/tools/migrations/0007_seed_xlsx_processor.py`

- [ ] **Step 1: Create the migration**

```python
from django.db import migrations


def forward(apps, schema_editor):
    ToolCard = apps.get_model('tools', 'ToolCard')
    ToolCard.objects.get_or_create(
        slug='xlsx-processor',
        defaults={
            'name': 'XLSX Processor',
            'tagline': 'Створення, редагування та аналіз Excel-файлів',
            'tagline_i18n': {
                'en': 'Create, edit, and analyze Excel spreadsheets',
                'de': 'Excel-Tabellen erstellen, bearbeiten und analysieren',
            },
            'description': '',
            'icon': 'file-spreadsheet',
            'category': 'ai',
            'color': '#217346',
            'transport_type': 'builtin',
            'is_builtin': True,
            'builtin_handler': 'mcp_hub.builtin.xlsx_processor',
            'auth_type': 'none',
            'skill_scopes': {'scopes': ['assistant', 'manager'], 'bidirectional': True},
        })


def reverse(apps, schema_editor):
    ToolCard = apps.get_model('tools', 'ToolCard')
    ToolCard.objects.filter(slug='xlsx-processor').delete()


class Migration(migrations.Migration):
    dependencies = [('tools', '0006_edgemiddleware_toolcard_skill_scopes')]
    operations = [migrations.RunPython(forward, reverse)]
```

- [ ] **Step 2: Commit**

```bash
cd /home/dchuprina/nexelin_web && git add p004_ai_nexelin/MASTER/tools/migrations/0007_seed_xlsx_processor.py
git commit -m "feat(tools): add migration to seed xlsx-processor tool card"
```

---

### Task 7: Admin fieldsets update

**Files:**
- Modify: `p004_ai_nexelin/MASTER/tools/admin.py:14-28`

- [ ] **Step 1: Add skill_scopes and tagline_i18n to fieldsets**

Update the Identity fieldset to include `tagline_i18n`, and add `skill_scopes` to the MCP Connection fieldset:

```python
    fieldsets = (
        ('Identity', {
            'fields': ('name', 'slug', 'tagline', 'tagline_i18n', 'description', 'icon',
                       'color', 'category', 'is_featured', 'sort_order'),
        }),
        ('MCP Connection', {
            'fields': ('transport_type', 'mcp_server_url', 'is_builtin',
                       'builtin_handler', 'tools_schema', 'skill_scopes'),
            'classes': ('collapse',),
        }),
        ('Auth', {
            'fields': ('auth_type', 'auth_config'),
            'classes': ('collapse',),
        }),
        ('Status', {'fields': ('is_active',)}),
    )
```

- [ ] **Step 2: Commit**

```bash
cd /home/dchuprina/nexelin_web && git add p004_ai_nexelin/MASTER/tools/admin.py
git commit -m "fix(tools): add skill_scopes and tagline_i18n to admin fieldsets"
```

---

### Task 8: Frontend — tool category mapping

**Files:**
- Modify: `nextlen/src/components/tools/ToolCatalogStrip.jsx:6-19`
- Modify: `nextlen/src/components/tools/toolTargets.js:1-14`

- [ ] **Step 1: Add xlsx-processor to SLUG_TO_GROUP in ToolCatalogStrip.jsx**

Add to the SLUG_TO_GROUP object:

```js
const SLUG_TO_GROUP = {
  'rag-search':      'servers',
  'translation':     'skills',
  'xlsx-processor':  'skills',
  'email-smtp':      'servers',
  'telegram':        'servers',
  'web-widget':      'servers',
  'whatsapp-meta':   'servers',
  'whatsapp-bridge': 'servers',
  'hitl-matrix':     'servers',
  'instagram':       'servers',
  'calendar':        'tools',
  'crm':             'tools',
  'analytics':       'tools',
};
```

- [ ] **Step 2: Add xlsx-processor to TOOL_TARGETS in toolTargets.js**

Add entry:

```js
export const TOOL_TARGETS = {
  'whatsapp-meta':   ['assistant', 'manager'],
  'whatsapp-bridge': ['assistant', 'manager'],
  'telegram':        ['assistant', 'manager'],
  'instagram':       ['assistant', 'manager'],
  'email-smtp':      ['assistant', 'manager'],
  'web-widget':      ['assistant', 'manager', 'leads'],
  'rag-search':      ['assistant'],
  'translation':     ['assistant'],
  'xlsx-processor':  ['assistant', 'manager'],
  'hitl-matrix':     ['manager'],
  'calendar':        ['manager'],
  'crm':             ['assistant', 'manager'],
  'analytics':       ['assistant', 'manager'],
};
```

- [ ] **Step 3: Commit**

```bash
cd /home/dchuprina/nexelin_web && git add nextlen/src/components/tools/ToolCatalogStrip.jsx nextlen/src/components/tools/toolTargets.js
git commit -m "feat(tools): add xlsx-processor to frontend tool catalog and targets"
```

---

### Task 9: Verification

- [ ] **Step 1: Run Django check**

Run: `cd /home/dchuprina/nexelin_web/p004_ai_nexelin && python manage.py check`

Expected: `System check identified no issues.`

- [ ] **Step 2: Run migrations dry-run**

Run: `python manage.py migrate --plan`

Expected: shows `0007_seed_xlsx_processor` as unapplied

- [ ] **Step 3: Apply migration**

Run: `python manage.py migrate tools`

Expected: `Applying tools.0007_seed_xlsx_processor... OK`

- [ ] **Step 4: Verify tool card in DB**

Run: `python manage.py shell -c "from MASTER.tools.models import ToolCard; t = ToolCard.objects.get(slug='xlsx-processor'); print(f'{t.name} | {t.category} | {t.skill_scopes}')"`

Expected: `XLSX Processor | ai | {'scopes': ['assistant', 'manager'], 'bidirectional': True}`

- [ ] **Step 5: Verify frontend build**

Run: `cd /home/dchuprina/nexelin_web/nextlen && npm run build`

Expected: build succeeds

- [ ] **Step 6: Final commit (if any fixes needed)**

```bash
cd /home/dchuprina/nexelin_web && git add -A
git commit -m "feat(tools): xlsx-processor skill — complete integration"
```
