"""
NACE → olası EWC önerileri (Torch yok; Docker imajında prediction/__init__ yüklenmesin diye
bu modül atik_ai kökünde tutulur — TechnicalMatcher kuralları + DB tamamlama).
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from .matching.technical import TechnicalMatcher


def _nace_matches_pattern(nace: str, pattern: str) -> bool:
    n = (nace or "").strip()
    if not n or not pattern:
        return False
    try:
        return bool(re.compile(pattern, re.IGNORECASE).match(n))
    except re.error:
        return False


def suggest_ewc_rules_for_nace(nace_code: str, limit: int = 30) -> List[Dict[str, Any]]:
    """NACE koduna uyan NACE–EWC kurallarını döndür (açıklayıcı öneri listesi)."""
    tm = TechnicalMatcher()
    nace = (nace_code or "").strip()
    out: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for rule in tm.rules:
        if not _nace_matches_pattern(nace, rule.receiver_nace):
            continue
        key = f"{rule.source_ewc}|{rule.receiver_nace}"
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "ewc_pattern": rule.source_ewc,
                "waste_category": rule.waste_category,
                "compatibility": rule.compatibility,
                "process_type": rule.process_type,
                "receiver_nace_pattern": rule.receiver_nace,
            }
        )
        if len(out) >= limit:
            break
    out.sort(key=lambda x: -float(x.get("compatibility") or 0))
    return out


def rank_waste_types_for_nace(
    nace_code: str,
    waste_rows: List[tuple],
    limit: int = 25,
) -> List[Dict[str, Any]]:
    """
    waste_rows: (waste_code, description, status) SQL satırları.
    Her kod için teknik uyumluluk skoru (varsa kuraldan).
    """
    tm = TechnicalMatcher()
    nace = (nace_code or "").strip()
    scored: List[Dict[str, Any]] = []
    for row in waste_rows:
        code = str(row[0] or "").strip()
        desc = str(row[1] or "") if len(row) > 1 else ""
        status = str(row[2] or "") if len(row) > 2 else ""
        ok, score, rule = tm.check_compatibility(code, nace)
        if not ok and score <= 0:
            continue
        entry: Dict[str, Any] = {
            "waste_code": code,
            "description": desc,
            "status": status,
            "technical_score": float(score),
            "rule": rule.to_dict() if rule else None,
        }
        scored.append(entry)
    scored.sort(key=lambda x: -x["technical_score"])
    return scored[:limit]


def merge_suggestions(
    nace_code: str,
    waste_rows: Optional[List[tuple]],
    rule_limit: int = 20,
    waste_limit: int = 20,
) -> Dict[str, Any]:
    rules = suggest_ewc_rules_for_nace(nace_code, limit=rule_limit)
    wastes: List[Dict[str, Any]] = []
    if waste_rows:
        wastes = rank_waste_types_for_nace(nace_code, waste_rows, limit=waste_limit)
    return {
        "nace_code": nace_code,
        "rule_based": rules,
        "ranked_waste_types": wastes,
        "note": "rule_based = NACE–EWC eşleşme kuralları; ranked_waste_types = waste_types tablosundan teknik skor.",
    }
