import pytest

DEV = {"X-Dev-User": "test-user-001"}
OTHER = {"X-Dev-User": "other-user-999"}

RECEIPT = {
    "vendor": "Tesco",
    "date": "2024-03-01",
    "total": 25.50,
    "category": "food",
    "notes": "weekly shop",
}


@pytest.mark.asyncio
async def test_create_receipt(client):
    res = await client.post("/api/receipts", json=RECEIPT, headers=DEV)
    assert res.status_code == 200
    data = res.json()
    assert data["vendor"] == "Tesco"
    assert data["total"] == pytest.approx(25.50)
    assert data["category"] == "food"
    assert "id" in data


@pytest.mark.asyncio
async def test_list_receipts_only_own(client):
    await client.post("/api/receipts", json=RECEIPT, headers=DEV)
    await client.post(
        "/api/receipts",
        json={"vendor": "Shell", "date": "2024-03-02", "total": 60.00, "category": "transport"},
        headers=OTHER,
    )

    res = await client.get("/api/receipts", headers=DEV)
    assert res.status_code == 200
    receipts = res.json()
    assert len(receipts) == 1
    assert receipts[0]["vendor"] == "Tesco"


@pytest.mark.asyncio
async def test_analytics_aggregations(client):
    for item in [
        {"vendor": "Tesco", "date": "2024-03-01", "total": 20.00, "category": "food"},
        {"vendor": "Shell", "date": "2024-03-02", "total": 50.00, "category": "transport"},
    ]:
        await client.post("/api/receipts", json=item, headers=DEV)

    res = await client.get("/api/analytics", headers=DEV)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == pytest.approx(70.00)
    assert data["count"] == 2
    assert data["by_category"]["food"] == pytest.approx(20.00)
    assert data["by_category"]["transport"] == pytest.approx(50.00)
    assert "by_month" in data


@pytest.mark.asyncio
async def test_delete_rejects_other_user(client):
    res = await client.post("/api/receipts", json=RECEIPT, headers=DEV)
    receipt_id = res.json()["id"]

    res2 = await client.delete(f"/api/receipts/{receipt_id}", headers=OTHER)
    assert res2.status_code == 404

    res3 = await client.get("/api/receipts", headers=DEV)
    assert len(res3.json()) == 1


@pytest.mark.asyncio
async def test_delete_own_receipt(client):
    res = await client.post("/api/receipts", json=RECEIPT, headers=DEV)
    receipt_id = res.json()["id"]

    del_res = await client.delete(f"/api/receipts/{receipt_id}", headers=DEV)
    assert del_res.status_code == 200

    list_res = await client.get("/api/receipts", headers=DEV)
    assert list_res.json() == []
