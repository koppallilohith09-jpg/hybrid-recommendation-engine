from pathlib import Path
from fastapi import Query
from pydantic import BaseModel, Field
from platform_core import create_app
from domain import Recommendations

ROOT = Path(__file__).parent
engine = Recommendations(ROOT)
app = create_app(ROOT, "Shelf")


class Rating(BaseModel):
    user_id: int = Field(ge=1)
    item_id: int = Field(ge=1)
    rating: int = Field(ge=1, le=5)


class Customer(BaseModel):
    name: str = Field(min_length=1, max_length=80)


@app.get("/api/state")
def state():
    return dict(catalog=engine.items, users=engine.users, ratings=len(engine.ratings), evaluation=engine.evaluation)


@app.get("/api/recommend")
def recommend(user_id: int = Query(1, ge=1), weight: float = Query(.5, ge=0, le=1)):
    return engine.recommend(user_id, weight)


@app.post("/api/rating")
def rating(body: Rating):
    engine.rate(body.user_id, body.item_id, body.rating)
    return {"ok": True}


@app.post("/api/customers")
def customer(body: Customer):
    if not body.name.strip():
        raise ValueError("Enter a customer name.")
    return engine.customer(body.name.strip())


@app.post("/api/evaluate")
def evaluate():
    return engine.evaluate()


@app.get("/api/audit")
def history():
    return engine.store.history()
