from typing import Dict, List
from datetime import datetime
from Apps.Api.schemas.models import Cookbook, CookbookCreate, Recipe, RecipeBase

class Store: 
    _instance = None

    @classmethod
    def instance(cls): 
        if cls._instance is None: 
            cls._instance = Store()
        return cls._instance
    
    def __init__(self):
        self.cookbooks: Dict[str, Cookbook] = {}
        self.recipes: Dict[str, Recipe] = {}

    #region Cookbooks

    def create_cookbook(self, payload: CookbookCreate) -> Cookbook:
        cb = Cookbook(name=payload.name, is_premium=payload.is_premium)
        self.cookbooks[cb.id] = cb
        return cb
    
    def list_cookbooks(self) -> List[Cookbook]:
        return list(self.cookbooks.values())
    
    #endregion

    #region Recipes

    def add_recipe(self, cookbook_id: str, data: RecipeBase) -> Recipe:
        if cookbook_id not in self.cookbooks: 
            raise ValueError("Cookbook not found")
        r = Recipe(cookbook_id=cookbook_id, **data.model_dump())
        self.recipes[r.id] = r
        return r

    #endregion
