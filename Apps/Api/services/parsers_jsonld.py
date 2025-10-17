from __future__ import annotations
from typing import Any, Iterable, List, Optional, Union
import json
import re

import requests
from bs4 import BeautifulSoup

from Apps.Api.schemas.models import RecipeBase, Ingredient, InstructionStep
from Apps.Api.services.ingredient_utils import parse_ingredient_line

def fetch_html(url: str, timeout: float = 15.0) -> str: 
    resp = requests.get(
        url,
        headers={"User-Agent": "Recipeer/0.1 (+educational-parser)"}, 
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.text

def detect_lang(html: str, url: str) -> str:
    try:
        soup = BeautifulSoup(html, "lxml")
        html_tag = soup.find("html")
        if(html_tag and html_tag.has_attr("lang")):
            val = (html_tag["lang"] or "").lower()
            if val.startswith("sv"):
                return "sv"
            if val.startswith("en"):
                return "en"
        og = soup.find("meta", attrs={"property": "og:locale"})
        if og and og.has_attr("content"):
            loc = (og["content"] or "").lower()
            if loc.startswith("sv"):
                return "sv"
            if loc.startswith("en"):
                return "en"
    except Exception:
        pass

    if url.lower().endswith(".se") or ".se/" in url.lower():
        return "sv"
    return "en"

def find_jsonld_blocks(html: str) -> List[str]: 
    soup = BeautifulSoup(html, "lxml")
    blocks: List[str] = []
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        if not tag.string: 
            text = tag.text
        else: 
            text = tag.string
        if text:
            blocks.append(text.strip())
    return blocks

def try_load_json_candidates(text: str) -> List[Any]:
    candidates: List[Any] = []
    try: 
        data = json.loads(text)
        candidates.append(data)
    except json.JSONDecodeError:
        for m in re.finditer(r"(\{.*\}|\[.*\])", text, flags=re.DOTALL):
            frag = m.group(1)
            try:
                candidates.append(json.loads(frag))
            except Exception:
                pass
        
    return candidates

def is_type_recipe(obj: Any) -> bool:
    t = obj.get("@type") if isinstance(obj, dict) else None
    if t is None: 
        return False
    if isinstance(t, str):
        return t.lower() == "recipe"
    if isinstance(t, list): 
        return any(isinstance(x, str) and x.lower() == "recipe" for x in t)
    return False

def flatten_graph(obj: Any) -> List[dict]:
    out: List[dict] = []
    def rec(x: Any):
        if isinstance(x, dict):
            out.append(x)
            for v in x.values():
                rec(v)
        elif isinstance(x, list):
            for v in x: 
                rec(v)
    rec(obj)
    return out

def find_first_recipe(objs: Iterable[Any]) -> Optional[dict]:
    for o in objs:
        if isinstance(o, dict):
            if is_type_recipe(o):
                return o
            for cand in flatten_graph(o):
                if is_type_recipe(cand):
                    return cand
        elif isinstance(o, list):
            for item in o:
                if isinstance(item, dict) and is_type_recipe(item):
                    return item
    return None

def as_list(x: Any) -> List[Any]: 
    if x is None: 
        return []
    if isinstance(x, list):
        return x
    return [x]

def extract_title(recipe: dict) -> str:
    name = recipe.get("name") or recipe.get("headline")
    if isinstance(name, str) and name.strip():
        return name.strip()
    return "Untitled Recipe"

def extract_ingredients(recipe: dict, lang: str) -> List[Ingredient]:
    raw_list = as_list(recipe.get("recipeIngredient"))
    out: List[Ingredient] = []
    for raw in raw_list:
        if isinstance(raw, str):
            out.append(parse_ingredient_line(raw, lang=lang))
        elif isinstance(raw, dict):
            nm = raw.get("name") or raw.get("text") or ""
            out.append(parse_ingredient_line(str(nm), lang=lang))
        else:
            out.append(parse_ingredient_line(str(raw), lang=lang))
    return out

def _flatten_instructions(instr: Any) -> List[str]: 
    steps: List[str] = []

    def add(x: str):
        s = x.strip()
        if s:
            steps.append(s)

    def rec(node: Any):
        if node is None:
            return
        if isinstance(node, str): 
            add(node)
            return
        if isinstance(node, list): 
            for it in node: 
                rec(it)
            return
        if isinstance(node, dict):
            if "itemListElement" in node:
                rec(node["itemListElement"])
            if "text" in node and isinstance(node["text"], str):
                add(node["text"])
            elif "name" in node and isinstance(node["name"], str):
                add(node["name"])
            return
    rec(instr)
    return steps

def extract_steps(recipe: dict) -> List[InstructionStep]:
    raw = recipe.get("recipeInstructions")
    lines = _flatten_instructions(raw)

    if not lines:
        for key in ("instruction", "instructions", "steps"):
            if key in recipe:
                lines = _flatten_instructions(recipe[key])
                if lines:
                    break

    return [InstructionStep(order= i + 1, text=txt) for i, txt in enumerate(lines)]

def clean_servings(s: str) -> str:
    s = re.sub(r"\bundefined\b", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s+", " ", s).strip()

    m = re.search(r"\b(\d+(?:\s*-\s*\d+)?)\b", s)
    if m:
        num = m.group(1).replace(" ", "")
        if re.search(r"\bport(?:ion(?:er)?)?\b", s, flags=re.IGNORECASE):
            return f"{num} portioner"
        return num
    return s

def extract_servings(recipe: dict) -> Optional[str]:
    ry = recipe.get("recipeYield")
    if isinstance(ry, (int, float)):
        return str(int(ry))
    if isinstance(ry, str) and ry.strip():
        return clean_servings(ry.strip())
    if isinstance(ry, list):
        for it in ry:
            if isinstance(it, str) and it.strip():
                return clean_servings(it.strip())
    return None

_ISO_DUR_RE = re.compile(
    r"""^P
        (?:(?P<years>\d+)Y)?           # år
        (?:(?P<months>\d+)M)?          # månader (före T)
        (?:(?P<days>\d+)D)?            # dagar
        (?:T                           # tidsdel (om den finns måste T finnas)
            (?:(?P<hours>\d+)H)?       # timmar
            (?:(?P<mins>\d+)M)?        # minuter (efter T)
            (?:(?P<secs>\d+)S)?        # sekunder
        )?$""",
    re.IGNORECASE | re.VERBOSE
)

def parse_iso8601_duration_to_human(s: str) -> Optional[str]:
    if not isinstance(s, str):
        return None
    m = _ISO_DUR_RE.fullmatch(s.strip())
    if not m:
        return None
    h = m.group("hours")
    mi = m.group("mins")
    se = m.group("secs")
    parts = []
    if h: parts.append(f"{int(h)} h")
    if mi: parts.append(f"{int(mi)} min")
    if se and not parts:
        parts.append(f"{int(se)} s")
    return " ".join(parts) if parts else None

def extract_total_time(recipe: dict) -> Optional[str]:
    for key in ("totalTime", "total_time", "cookTime", "prepTime"):
        val = recipe.get(key)
        if isinstance(val, str) and val:
            if val.startswith("P"):
                human = parse_iso8601_duration_to_human(val)
                if human: 
                    return human
            return val
    return None

def extract_recipe_from_jsonld(url: str) -> Optional[RecipeBase]:
    html = fetch_html(url)
    lang = detect_lang(html, url)
    blocks = find_jsonld_blocks(html)

    candidates: List[Any] = []
    for block in blocks:
        candidates.extend(try_load_json_candidates(block))
    
    recipe_obj = find_first_recipe(candidates)
    if not recipe_obj:
        return None

    title = extract_title(recipe_obj)
    ingredients = extract_ingredients(recipe_obj, lang=lang)
    steps = extract_steps(recipe_obj)
    servings = extract_servings(recipe_obj)
    total_time = extract_total_time(recipe_obj)

    return RecipeBase(
        title=title,
        description=None,
        ingredients=ingredients,
        steps=steps,
        servings=servings,
        total_time=total_time,
        source_url=url,
        images=[],
    )

