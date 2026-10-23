"""Hybrid ranking, explicit score explanations and leave-one-out evaluation."""
import random
import threading

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from platform_core import Store, now


def catalog():
    groups = {
        "Outdoors": [("Trail Daypack", "hiking travel lightweight backpack"), ("Field Bottle", "camping hiking steel water bottle"), ("Ridge Shell", "hiking waterproof jacket trail"), ("Camp Lantern", "camping light portable outdoor"), ("Foldaway Stool", "camping travel folding seat"), ("Trail Socks", "hiking merino wool socks")],
        "Home": [("Stoneware Mug", "coffee ceramic kitchen handmade"), ("Linen Throw", "home cotton linen blanket"), ("Desk Lamp", "home office reading light"), ("Coffee Grinder", "coffee kitchen manual brewing"), ("Cedar Tray", "home wood storage handmade"), ("Woven Basket", "home storage natural woven")],
        "Studio": [("Sketch Journal", "art drawing paper notebook"), ("Graphite Set", "drawing pencils sketch art"), ("Watercolor Kit", "painting art color travel"), ("Studio Headphones", "music audio recording sound"), ("Pocket Recorder", "music recording audio portable"), ("Canvas Roll", "art painting canvas studio")],
        "Technology": [("Compact Keyboard", "office computer mechanical keyboard"), ("USB-C Hub", "computer desk travel adapter"), ("Portable SSD", "computer storage backup travel"), ("Wireless Mouse", "office computer desk mouse"), ("Webcam", "video computer meetings office"), ("Desk Microphone", "audio video recording computer")],
    }
    rows = []
    for category, items in groups.items():
        for name, description in items:
            rows.append(dict(id=len(rows) + 1, name=name, category=category, description=description,
                             price=round(18 + (len(rows) * 17) % 160, 2)))
    return rows


def sample_ratings(items):
    rng = random.Random(21)
    ratings = []
    for user in range(1, 51):
        favorite = ["Outdoors", "Home", "Studio", "Technology"][(user - 1) % 4]
        for item in rng.sample(items, 12):
            rating = min(5, max(1, round((4.6 if item["category"] == favorite else 2.7) + rng.gauss(0, .7))))
            ratings.append(dict(user_id=user, item_id=item["id"], rating=rating))
    return ratings


class Recommendations:
    def __init__(self, root):
        self.store = Store(root)
        self.lock = threading.RLock()
        self.items = self.store.get("catalog") or catalog()
        self.store.put("catalog", self.items)
        self.users = self.store.get("users") or [{"id": i, "name": "Demo customer " + str(i).zfill(2)} for i in range(1, 51)]
        self.ratings = self.store.get("ratings")
        if self.ratings is None:
            self.ratings = sample_ratings(self.items)
            self.persist()
        self.text = TfidfVectorizer(stop_words="english").fit_transform(
            [r["category"] + " " + r["description"] for r in self.items])
        self.evaluation = self.store.get("evaluation")
        if self.evaluation is None:
            self.evaluate()

    def persist(self):
        self.store.put("ratings", self.ratings)
        self.store.put("users", self.users)

    def _components(self, user_id, ratings):
        n = len(self.items)
        user_ids = sorted({r["user_id"] for r in ratings} | {user_id})
        user_index = {u: i for i, u in enumerate(user_ids)}
        matrix = np.zeros((len(user_ids), n))
        for r in ratings:
            matrix[user_index[r["user_id"]], r["item_id"] - 1] = r["rating"]
        own = matrix[user_index[user_id]]
        observed = matrix > 0
        count = observed.sum(axis=0)
        # Bayesian shrinkage keeps a single high rating from dominating popularity.
        popularity = (matrix.sum(axis=0) + 3.0 * 5) / (count + 5) / 5
        if not own.any():
            return popularity, popularity, popularity, own, True
        positive = np.where(own >= 4, own - 3, 0)
        if not positive.any():
            positive = np.where(own > 0, 1, 0)
        profile = positive @ self.text / positive.sum()
        content = cosine_similarity(np.asarray(profile).reshape(1, -1), self.text).ravel()
        centered = np.where(observed, matrix - 3, 0)
        similarities = cosine_similarity(centered[user_index[user_id]].reshape(1, -1), centered).ravel()
        similarities[user_index[user_id]] = 0
        similarities = np.maximum(similarities, 0)
        denominator = similarities @ observed
        collaborative = np.divide(similarities @ matrix, denominator, out=popularity * 5, where=denominator > 0) / 5
        return np.clip(content, 0, 1), np.clip(collaborative, 0, 1), popularity, own, False

    def recommend(self, user_id, weight=.5, limit=8, ratings=None):
        if user_id not in {u["id"] for u in self.users}:
            raise ValueError("Customer not found.")
        data = self.ratings if ratings is None else ratings
        content, collaborative, popularity, own, cold = self._components(user_id, data)
        scores = popularity if cold else weight * content + (1 - weight) * collaborative
        ranked = sorted((i for i in range(len(self.items)) if own[i] == 0), key=lambda i: (-scores[i], i))[:limit]
        return [{"item": self.items[i], "score": float(scores[i]), "content": float(content[i]),
                 "collaborative": float(collaborative[i]), "cold_start": cold,
                 "reason": "Catalog popularity; this customer has no ratings." if cold else
                           "Content affinity " + str(round(content[i] * 100)) + "%; neighbor rating score " + str(round(collaborative[i] * 100)) + "%."}
                for i in ranked]

    def evaluate(self):
        with self.lock:
            held = {}
            for r in self.ratings:
                if r["rating"] >= 4:
                    held[r["user_id"]] = r
            training = [r for r in self.ratings if held.get(r["user_id"]) is not r]
            hits = 0
            for user_id, target in held.items():
                result = self.recommend(user_id, .5, 5, training)
                hits += int(target["item_id"] in {r["item"]["id"] for r in result})
            version = (self.store.get("evaluation") or {}).get("version", 0) + 1
            result = dict(version=version, created=now(), users_evaluated=len(held), held_out=len(held),
                          hit_rate_at_5=hits / len(held) if held else 0, method="One positive item per user held out; fixed 50/50 blend",
                          source="Synthetic demo ratings; not a real-world benchmark")
            self.evaluation = result
            self.store.put("evaluation", result)
            self.store.audit("Evaluation completed", result)
            return result

    def rate(self, user_id, item_id, rating):
        with self.lock:
            if user_id not in {u["id"] for u in self.users} or item_id not in {i["id"] for i in self.items}:
                raise ValueError("Customer or item not found.")
            self.ratings = [r for r in self.ratings if (r["user_id"], r["item_id"]) != (user_id, item_id)]
            self.ratings.append(dict(user_id=user_id, item_id=item_id, rating=rating))
            self.persist()
            self.store.audit("Rating saved", {"user_id": user_id, "item_id": item_id, "rating": rating})

    def customer(self, name):
        with self.lock:
            user = {"id": max(u["id"] for u in self.users) + 1, "name": name}
            self.users.append(user)
            self.persist()
            return user
