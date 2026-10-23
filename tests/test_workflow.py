def test_ranked_results_exclude_rated_items(workspace):
    c, engine = workspace.client, workspace.engine
    result = c.get("/api/recommend?user_id=1").json()
    known = {r["item_id"] for r in engine.ratings if r["user_id"] == 1}
    assert len(result) == 8
    assert all(r["item"]["id"] not in known for r in result)
    assert all(0 <= r["score"] <= 1 for r in result)
    assert result == sorted(result, key=lambda r: -r["score"])


def test_cold_start_feedback_and_weight_extremes(workspace):
    c = workspace.client
    customer = c.post("/api/customers", json={"name": "Cold-start tester"}).json()
    uid = customer["id"]
    before = c.get("/api/recommend?user_id=" + str(uid)).json()
    assert before[0]["cold_start"]
    item = before[0]["item"]["id"]
    assert c.post("/api/rating", json={"user_id": uid, "item_id": item, "rating": 5}).status_code == 200
    after = c.get("/api/recommend?user_id=" + str(uid)).json()
    assert not after[0]["cold_start"]
    assert item not in {r["item"]["id"] for r in after}
    content = c.get("/api/recommend?user_id=" + str(uid) + "&weight=1").json()
    collaborative = c.get("/api/recommend?user_id=" + str(uid) + "&weight=0").json()
    assert all(abs(r["score"]-r["content"]) < 1e-9 for r in content)
    assert all(abs(r["score"]-r["collaborative"]) < 1e-9 for r in collaborative)
    assert c.post("/api/rating", json={"user_id": uid, "item_id": item, "rating": 6}).status_code == 422


def test_evaluation_counts_only_eligible_customers(workspace):
    c = workspace.client
    result = c.post("/api/evaluate").json()
    assert result["version"] == 2
    assert 0 <= result["hit_rate_at_5"] <= 1
    assert result["held_out"] == result["users_evaluated"] > 0
    assert c.get("/api/recommend?user_id=99999").status_code == 400
