from __future__ import annotations
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Optional, Dict, Tuple

from Apps.Api.schemas.models import Ingredient

@lru_cache(maxsize=4)
def load_notes_rules(lang: str) -> dict:
    data_dir = Path(__file__).resolve().parents[1] / "data"
    p = data_dir / f"notes_rules.{lang}.json"
    try: 
        raw = json.loads(p.read_text(encoding="utf-8"))
        return {
            "trailing_phrases": [re.compile(r, re.IGNORECASE) for r in raw.get("trailing_phrases", [])],
            "leading_adverbs": [re.compile(rf"^(?:{r})\b", re.IGNORECASE) for r in raw.get("leading_adverbs", [])],
            "cleanup": raw.get("cleanup", {})
        }
    except Exception:
        return {"trailing_phrases": [], "leading_adverbs": [], "cleanup": {}}

def extract_parentheticals_to_notes(name: str) -> tuple[str, list[str]]:
    notes: list[str] = []
    def repl(m: re.Match):
        content = m.group(1).strip()
        if content: 
            notes.append(content)
        return ""
    clean = re.sub(r"\(([^)]+)\)", repl, name).strip()
    return clean, notes

def extract_trailing_phrases(name: str, rules: dict) -> tuple [str, list[str]]:
    notes: list[str] = []
    for rx in rules["trailing_phrases"]:
        m = rx.search(name)
        if m:
            notes.append(m.group(0).strip())
            name = name[:m.start()].rstrip(",; .").strip()
    return name, notes

def extract_leading_adverbs(name: str, rules: dict) -> tuple[str, list[str]]:
    notes: list[str] = []
    for rx in rules["leading_adverbs"]:
        m = rx.search(name)
        if m: 
            notes.append(m.group(0).strip())
            name = name[m.end():].lstrip(",; .").strip()
    return name, notes

def normalize_phrase_in_name(name: str, enabled: bool) -> tuple[str, Optional[str]]:
    if not enabled:
        return name, None
    m = re.search(r"\bà\b\s*([0-9]+)\s*([a-zA-Z]+)", name, flags=re.IGNORECASE)
    if not m:
        return name, None
    note = f"à {m.group(1)} {m.group(2)}"
    clean = (name[:m.start()] + name[m.end():]).strip().rstrip(",;.")
    return clean, note

@lru_cache(maxsize=4)
def load_unit_aliases(lang: str) -> Dict[str, str]:
    data_dir = Path(__file__).resolve().parents[1]
    p = data_dir / f"units.{lang}.json"
    try: 
        text = p.read_text(encoding="utf-8")
        raw = json.loads(text)
        return {k.lower().rstrip("."): v for k, v in raw.items()}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    
def normalize_unit(u: Optional[str], lang: str) -> Optional[str]: 
    if not u: 
        return None
    key = u.strip().lower().rstrip(".")
    aliases = load_unit_aliases(lang)
    return aliases.get(key, key)

def is_known_unit(u: Optional[str], lang:str) -> bool: 
    if not u: 
        return False
    key = u.strip().lower().rstrip(".")
    return key in load_unit_aliases(lang)

FRACTION_CHAR_MAP = {
    "½":"1/2","¼":"1/4","¾":"3/4","⅓":"1/3","⅔":"2/3",
    "⅛":"1/8","⅜":"3/8","⅝":"5/8","⅞":"7/8",
}

def replace_fraction_chars(s: str) -> str:
    for ch, rep in FRACTION_CHAR_MAP.items():
        s = s.replace(ch, rep)
    return s

def fraction_to_float(s: str) -> Optional[float]: 
    s = s.strip()
    m = re.match(r"^\s*(\d+)?(?:\s+)?(\d+/\d+)\s*$", s)
    if m:
        whole, frac = m.groups()
        num, den = frac.split("/")
        base = int(whole) if whole else 0
        return base + (int(num) / int(den))
    try:
        return float(s.replace(",", "."))
    except ValueError:
        return None

def parse_quantity(qty_raw: Optional[str]) -> Optional[str]:
    if not qty_raw:
        return None
    s = replace_fraction_chars(qty_raw)
    parts = [p.strip() for p in re.split(r"[-–]", s) if p.strip()]
    vals = []
    for p in parts:
        v = fraction_to_float(p)
        if v is None:
            return qty_raw.strip()
        vals.append(v)
    if not vals:
        return None
    if len(vals) == 1:
        return f"{vals[0]:g}"
    return f"{min(vals):g}-{max(vals):g}"

LINE_RE = re.compile(r"""
    ^\s*
    (?P<qty>
        (?:
            (?:\d+[.,]\d+|\d+)(?:\s+\d+/\d+)?   # 1.5 | 1 | 1 1/2
            |
            \d+/\d+                              # 1/2
        )
        (?:\s*[-–]\s*
            (?:
                (?:\d+[.,]\d+|\d+)(?:\s+\d+/\d+)? | \d+/\d+
            )
        )?
    )?
    \s*
    (?P<unit>[A-Za-zÅÄÖåäö\.%]+)?               # ev. enhet
    \s+
    (?P<name>.+?)                                # resten = namn
    (?:\s*\((?P<notes>[^)]+)\))?                 # ev. parentes-noter
    \s*$
""", re.VERBOSE)

def parse_ingredient_line(line: str, lang: str = "sv") -> Ingredient:
    raw = replace_fraction_chars(line.strip())
    m = LINE_RE.match(raw)
    if not m: 
        return Ingredient(name=raw)
    
    qty_s = m.group("qty")
    unit_s = m.group("unit")
    name_s = (m.group("name") or "").strip()
    notes_s = m.group("notes")

    qty = parse_quantity(qty_s)
    unit = normalize_unit(unit_s, lang)
    
    if unit_s and not is_known_unit(unit_s, lang): 
        name_s = f"{unit_s} {name_s}".strip()
        unit = None

    if qty is None and unit_s:
        name_s = f"{unit_s} {name_s}".strip()
        unit = None

    rules = load_notes_rules(lang)
    name_s, a_note = normalize_phrase_in_name(name_s, enabled=rules["cleanup"].get("normalize_a_pack", False))
    name_s, parent_notes = extract_parentheticals_to_notes(name_s)
    name_s, lead_notes = extract_leading_adverbs(name_s, rules)
    name_s, trail_notes = extract_trailing_phrases(name_s, rules)

    notes_parts = [notes_s, a_note, *parent_notes, *lead_notes, *trail_notes]
    notes_joined = " ".join([n for n in notes_parts if n]).strip() or None

    if not name_s:
        return Ingredient(name=raw)
    
    return Ingredient(
        name=name_s,
        quantity=qty,
        unit=unit,
        notes=notes_joined,
    )