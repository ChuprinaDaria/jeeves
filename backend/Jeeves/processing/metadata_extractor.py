from __future__ import annotations

import mimetypes
import os
from typing import Any, Dict


def extract_metadata(file_path: str, file_type: str) -> Dict[str, Any]:
    """Extracts metadata for supported file types.

    Returns a dict with general fields and type-specific fields.
    """
    stats = os.stat(file_path)
    mime_type, _ = mimetypes.guess_type(file_path)

    metadata: Dict[str, Any] = {
        "file_name": os.path.basename(file_path),
        "file_size": int(stats.st_size),
        "mime_type": mime_type or "application/octet-stream",
    }

    if file_type == "pdf":
        try:
            import PyPDF2
            from datetime import datetime
            with open(file_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                doc_info = getattr(reader, "metadata", None) or {}
                
                # Отримуємо creation_date та конвертуємо в строку якщо потрібно
                creation_date = getattr(doc_info, "creation_date", None) or doc_info.get("/CreationDate")
                if isinstance(creation_date, datetime):
                    creation_date = creation_date.isoformat()
                elif creation_date and not isinstance(creation_date, str):
                    creation_date = str(creation_date)
                
                metadata.update({
                    "title": getattr(doc_info, "title", None) or doc_info.get("/Title"),
                    "author": getattr(doc_info, "author", None) or doc_info.get("/Author"),
                    "creation_date": creation_date,
                    "keywords": getattr(doc_info, "keywords", None) or doc_info.get("/Keywords"),
                    "page_count": len(reader.pages),
                })
        except Exception:
            pass

    elif file_type == "docx":
        try:
            import docx
            d = docx.Document(file_path)
            core = d.core_properties
            metadata.update({
                "title": core.title,
                "author": core.author,
                "last_modified": core.modified.isoformat() if core.modified else None,
            })
        except Exception:
            pass

    return metadata


