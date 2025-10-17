from pydantic import HttpUrl
from bs4 import BeautifulSoup
import requests

from Apps.Api.schemas.models import RecipeBase, Ingredient, InstructionStep
from Apps.Api.services.parsers_jsonld import extract_recipe_from_jsonld

def extract_recipe_from_url(url: HttpUrl) -> RecipeBase:
    rb = extract_recipe_from_jsonld(str(url))
    if rb: 
        return rb
    
    html = requests.get(str(url), headers={"User-Agent": "Recipeer/0.1"}, timeout=15).text
    soup = BeautifulSoup(html, "lxml")
    title = (soup.find("meta", property="og:title") or soup.find("title"))
    title_text = title.get("content") if title and title.has_attr("content") else (title.text.strip() if title else "Untitled Recipe")
    return RecipeBase(
        title=title_text,
        description=None,
        ingredients=[Ingredient(name="(parse me)")],
        steps=[InstructionStep(order=1, text="(parse me)")],
        servings=None,
        total_time=None,
        source_url=str(url),
        images=[]
    )