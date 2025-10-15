from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, List
from datetime import datetime
import uuid

def gen_id() -> str: 
    return uuid.uuid4().hex

class Ingredient(BaseModel):
    name: str
    quantity: Optional[str] = None
    unit: Optional[str] = None
    notes: Optional[str] = None

class InstructionStep(BaseModel): 
    order: int
    text: str

class RecipeBase(BaseModel): 
    title: str
    description: Optional[str] = None
    ingridients: List[Ingredient] = Field(default_factory=list)
    steps: List[InstructionStep] = Field(default_factory=list)
    servings: Optional[str] = None
    total_time: Optional[str] = None
    source_url: Optional[HttpUrl] = None
    images: List[str] = Field(default_factory=list)

class Recipe(RecipeBase): 
    id: str=Field(default_factory=gen_id)
    cookbook_id: str
    version: int = 1
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class CookbookCreate(BaseModel):
    name: str
    is_premium: bool = False

class Cookbook(BaseModel): 
    id: str = Field(default_factory=gen_id)
    name: str
    is_premium: bool = False
    member_ids: List[str] = Field(default_factory=list)

class RequestChange(BaseModel): 
    title: Optional[str] = None
    description: Optional[str] = None
    ingredients: Optional[List[Ingredient]] = None
    steps: Optional[List[InstructionStep]] = None
    servings: Optional[str] = None
    total_time: Optional[str] = None

class Request(BaseModel): 
    id: str = Field(default_factory=gen_id)
    recipe_id: str
    message: str
    changes: RequestChange
    status: str = "open"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class Rating(BaseModel): 
    id: str = Field(default_factory=gen_id)
    recipe_id: str
    stars: int = Field(ge=1, le=5)
    note: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Comment(BaseModel): 
    id: str = Field(default_factory=gen_id)
    recipe_id: str
    text: str
    created_at: datetime = Field(default_factory=datetime.utcnow)