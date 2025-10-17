from fastapi import FastAPI, HTTPException, Depends
import requests
from pydantic import BaseModel

from Apps.Api.schemas.models import CookbookCreate, Cookbook, RecipeBase, Recipe
from Apps.Api.core.store import Store
from Apps.Api.services.parsers import extract_recipe_from_url

app = FastAPI(title="Recipeer API", version="0.0.1")

def get_store(): 
    return Store.instance()

@app.get("/health")
def health(): 
    return {"ok": True}

class RecipeCreateUrl(BaseModel): 
    url: str

@app.post("/cookbooks/{cookbook_id}/recipes:url", response_model=Recipe)
def add_recipe_via_url(cookbook_id: str, payload: RecipeCreateUrl, store: Store = Depends(get_store)):
    try: 
        data = extract_recipe_from_url(payload.url)
        return store.add_recipe(cookbook_id, data)
    except requests.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Upstream error: {e}")
    except requests.RequestException as e:
        raise HTTPException(status_code=504, detail=f"Failed to fetch URL: {e}")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.post("/cookbooks", response_model=Cookbook)
def create_cookbook(payload: CookbookCreate, store: Store = Depends(get_store)):
    return store.create_cookbook(payload)

@app.get("/cookbooks", response_model=list[Cookbook])
def list_cookbooks(store: Store = Depends(get_store)):
    return store.list_cookbooks()

@app.post("/cookbooks/{cookbook_id}/recipes", response_model=Recipe)
def add_recipe(cookbook_id: str, payload: RecipeBase, store: Store = Depends(get_store)):
    try: 
        return store.add_recipe(cookbook_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

