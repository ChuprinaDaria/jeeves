from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterable

from django.db import connection


@dataclass
class QueryDiagnostics:
    used_index: bool
    total_cost: float | None
    scanned_rows: int | None
    recommendation: str
    raw_plan: str


def _parse_plan(plan_lines: list[str]) -> QueryDiagnostics:
    raw = "\n".join(plan_lines)
    used_index = any("Index Scan" in l or "Bitmap Index Scan" in l for l in plan_lines)
    # best-effort parsing
    total_cost = None
    scanned_rows = None
    for l in plan_lines:
        if "cost=" in l:
            try:
                cost_part = l.split("cost=")[1].split(" ")[0]
                total_cost = float(cost_part.split("..")[-1])
            except Exception:  # noqa: BLE001
                pass
        if "rows=" in l and scanned_rows is None:
            try:
                rows_part = l.split("rows=")[1].split(" ")[0]
                scanned_rows = int(rows_part)
            except Exception:  # noqa: BLE001
                pass

    if not used_index:
        recommendation = "Too few rows or high selectivity: Seq Scan is OK for small datasets."
    else:
        recommendation = "Index used. Consider tuning probes/ef_search for accuracy/speed trade-off."

    return QueryDiagnostics(
        used_index=used_index,
        total_cost=total_cost,
        scanned_rows=scanned_rows,
        recommendation=recommendation,
        raw_plan=raw,
    )


@contextmanager
def explain_context() -> Iterable[None]:
    with connection.cursor() as cursor:
        cursor.execute("SET LOCAL application_name = 'rag_diagnostics'")
        yield


def explain(sql: str, params: list | None = None) -> QueryDiagnostics:
    with explain_context():
        with connection.cursor() as cursor:
            cursor.execute("EXPLAIN (ANALYZE, BUFFERS, VERBOSE) " + sql, params or [])
            lines = [r[0] for r in cursor.fetchall()]
    return _parse_plan(lines)


