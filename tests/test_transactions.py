import pytest
from fastapi.testclient import TestClient
from main import app
from storage import accounts, idempotency_store

client = TestClient(app)

def test_credit_transaction():
    # limpa estado
    accounts["acc_001"] = 1000.0
    idempotency_store.clear()

    response = client.post("/transactions", json={
        "idempotencyKey": "txn_credit_1",
        "accountId": "acc_001",
        "amount": 100.0,
        "type": "credit",
        "description": "Test credit"
    })

    assert response.status_code == 201
    data = response.json()
    assert data["balance"] == 1100.0
    assert data["status"] == "processed"

def test_debit_transaction():
    accounts["acc_001"] = 1000.0
    idempotency_store.clear()

    response = client.post("/transactions", json={
        "idempotencyKey": "txn_debit_1",
        "accountId": "acc_001",
        "amount": -200.0,
        "type": "debit",
        "description": "Test debit"
    })

    assert response.status_code == 201
    data = response.json()
    assert data["balance"] == 800.0

def test_insufficient_funds():
    accounts["acc_003"] = 0.0
    idempotency_store.clear()

    response = client.post("/transactions", json={
        "idempotencyKey": "txn_insufficient",
        "accountId": "acc_003",
        "amount": -100.0,
        "type": "debit",
        "description": "Should fail"
    })

    assert response.status_code == 400
    assert response.json()["detail"] == "Insufficient funds"

def test_invalid_account():
    idempotency_store.clear()

    response = client.post("/transactions", json={
        "idempotencyKey": "txn_invalid",
        "accountId": "acc_xyz",
        "amount": 50.0,
        "type": "credit",
        "description": "Invalid account"
    })

    assert response.status_code == 404
    assert response.json()["detail"] == "Account not found"
