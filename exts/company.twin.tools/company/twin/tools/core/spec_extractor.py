# SPDX-FileCopyrightText: Copyright (c) 2024-2026 BuildTeam AI. All rights reserved.
# SPDX-License-Identifier: Proprietary

"""
Spec Extractor Interface - Data structures for spec sheet extraction results.

The actual extraction is performed offline by the standalone tools/extract_spec.py
script (runs outside Kit with API access). Results are saved as .spec.json files
and imported into Kit via the Equipment Catalog's "Import Spec JSON" button.

This module defines the shared data structures used by the import pipeline.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List


@dataclass
class ExtractionResult:
    """Result from spec sheet extraction (produced by tools/extract_spec.py)."""
    entry_id: str
    confidence: float
    params: Dict[str, Any]
    source_file: str
    raw_text: str = ""
    warnings: List[str] = field(default_factory=list)
