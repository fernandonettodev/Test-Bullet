import pytest
import asyncio
from decimal import Decimal
from fastapi.testclient import TestClient
from unittest.mock import patch
from datetime import datetime

from main import app
from repositories import reset_repositories, get_account_repository, get_idempotency_repository
from models import TransactionRequest, TransactionType

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_state():
    """Reset repositories before each test."""
    reset_repositories()


class TestBasicTransactions:
    """Test basic transaction functionality."""
    
    def test_credit_transaction_success(self):
        """Test successful credit transaction."""
        response = client.post("/transactions", json={
            "idempotencyKey": "test_credit_001",
            "accountId": "acc_001",
            "amount": 100.50,
            "type": "credit",
            "description": "Test credit transaction"
        })
        
        assert response.status_code == 201
        data = response.json()
        
        assert data["status"] == "processed"
        assert data["balance"] == 1100.50
        assert "transactionId" in data
        assert "timestamp" in data
    
    def test_debit_transaction_success(self):
        """Test successful debit transaction."""
        response = client.post("/transactions", json={
            "idempotencyKey": "test_debit_001",
            "accountId": "acc_001",
            "amount": -200.25,
            "type": "debit",
            "description": "Test debit transaction"
        })
        
        assert response.status_code == 201
        data = response.json()
        
        assert data["status"] == "processed"
        assert data["balance"] == 799.75
        assert "transactionId" in data
    
    def test_insufficient_funds(self):
        """Test debit transaction with insufficient funds."""
        response = client.post("/transactions", json={
            "idempotencyKey": "test_insufficient_001",
            "accountId": "acc_003",  # Balance is 0
            "amount": -100.00,
            "type": "debit",
            "description": "Should fail - insufficient funds"
        })
        
        assert response.status_code == 400
        assert "Insufficient funds" in response.json()["detail"]
    
    def test_account_not_found(self):
        """Test transaction with non-existent account."""
        response = client.post("/transactions", json={
            "idempotencyKey": "test_not_found_001",
            "accountId": "acc_999",
            "amount": 50.00,
            "type": "credit",
            "description": "Non-existent account"
        })
        
        assert response.status_code == 404
        assert "Account not found" in response.json()["detail"]


class TestIdempotency:
    """Test idempotency functionality."""
    
    def test_idempotent_requests(self):
        """Test that duplicate idempotency keys return same result."""
        transaction_data = {
            "idempotencyKey": "idempotent_test_001",
            "accountId": "acc_001",
            "amount": -150.00,
            "type": "debit",
            "description": "Idempotency test"
        }
        
        # First request
        response1 = client.post("/transactions", json=transaction_data)
        assert response1.status_code == 201
        
        # Second request with same idempotency key
        response2 = client.post("/transactions", json=transaction_data)
        assert response2.status_code == 201
        
        # Should return identical responses
        assert response1.json() == response2.json()
        
        # Balance should only be affected once
        # Check by making a different transaction
        check_response = client.post("/transactions", json={
            "idempotencyKey": "check_balance",
            "accountId": "acc_001",
            "amount": 0.01,
            "type": "credit",
            "description": "Balance check"
        })
        
        # Original balance (1000) - 150 + 0.01 = 850.01
        assert check_response.json()["balance"] == 850.01
    
    def test_different_idempotency_keys(self):
        """Test that different idempotency keys create separate transactions."""
        base_data = {
            "accountId": "acc_002",
            "amount": 25.00,
            "type": "credit",
            "description": "Multiple transactions test"
        }
        
        # First transaction
        response1 = client.post("/transactions", json={
            **base_data,
            "idempotencyKey": "multi_test_001"
        })
        
        # Second transaction with different key
        response2 = client.post("/transactions", json={
            **base_data,
            "idempotencyKey": "multi_test_002"
        })
        
        assert response1.status_code == 201
        assert response2.status_code == 201
        
        # Should have different transaction IDs
        assert response1.json()["transactionId"] != response2.json()["transactionId"]
        
        # Final balance should be 500 + 25 + 25 = 550
        assert response2.json()["balance"] == 550.00


class TestConcurrency:
    """Test concurrent transaction processing."""
    
    @pytest.mark.asyncio
    async def test_concurrent_transactions_same_account(self):
        """Test multiple concurrent transactions on same account."""
        import httpx
        
        async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
            # Create 10 concurrent debit transactions of $10 each
            tasks = []
            for i in range(10):
                task = ac.post("/transactions", json={
                    "idempotencyKey": f"concurrent_{i}",
                    "accountId": "acc_001",
                    "amount": -10.00,
                    "type": "debit",
                    "description": f"Concurrent test {i}"
                })
                tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # All should succeed (account has $1000, we're debiting $100 total)
            successful_results = [r for r in results if not isinstance(r, Exception)]
            assert len(successful_results) == 10
            
            for result in successful_results:
                assert result.status_code == 201
            
            # Verify final balance by making another transaction
            final_check = await ac.post("/transactions", json={
                "idempotencyKey": "final_check",
                "accountId": "acc_001",
                "amount": 0.01,
                "type": "credit",
                "description": "Final balance check"
            })
            
            # Should be 1000 - 100 + 0.01 = 900.01
            assert final_check.json()["balance"] == 900.01
    
    @pytest.mark.asyncio
    async def test_concurrent_insufficient_funds(self):
        """Test concurrent transactions that would cause insufficient funds."""
        import httpx
        
        async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
            # Try to debit $200 five times from acc_002 (balance: $500)
            # Only 2 should succeed, 3 should fail
            tasks = []
            for i in range(5):
                task = ac.post("/transactions", json={
                    "idempotencyKey": f"insufficient_{i}",
                    "accountId": "acc_002",
                    "amount": -200.00,
                    "type": "debit",
                    "description": f"Large debit {i}"
                })
                tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Count successful vs failed transactions
            successful = [r for r in results if not isinstance(r, Exception) and r.status_code == 201]
            failed = [r for r in results if not isinstance(r, Exception) and r.status_code == 400]
            
            assert len(successful) == 2  # Only 2 should succeed
            assert len(failed) == 3     # 3 should fail with insufficient funds


class TestValidation:
    """Test input validation."""
    
    def test_invalid_account_id_format(self):
        """Test invalid account ID format."""
        response = client.post("/transactions", json={
            "idempotencyKey": "test_invalid_account",
            "accountId": "invalid_account",
            "amount": 100.00,
            "type": "credit",
            "description": "Invalid account format"
        })
        
        assert response.status_code == 422  # Validation error
    
    def test_zero_amount(self):
        """Test zero amount validation."""
        response = client.post("/transactions", json={
            "idempotencyKey": "test_zero_amount",
            "accountId": "acc_001",
            "amount": 0.00,
            "type": "credit",
            "description": "Zero amount test"
        })
        
        assert response.status_code == 422
    
    def test_invalid_idempotency_key(self):
        """Test invalid idempotency key format."""
        response = client.post("/transactions", json={
            "idempotencyKey": "invalid key with spaces!",
            "accountId": "acc_001",
            "amount": 100.00,
            "type": "credit",
            "description": "Invalid idempotency key"
        })
        
        assert response.status_code == 422
    
    def test_type_amount_mismatch(self):
        """Test validation of type/amount consistency."""
        # Positive amount with debit type should fail
        response = client.post("/transactions", json={
            "idempotencyKey": "test_type_mismatch_1",
            "accountId": "acc_001",
            "amount": 100.00,  # Positive
            "type": "debit",   # But debit type
            "description": "Type mismatch test"
        })
        
        assert response.status_code == 422
        
        # Negative amount with credit type should fail
        response = client.post("/transactions", json={
            "idempotencyKey": "test_type_mismatch_2",
            "accountId": "acc_001",
            "amount": -100.00,  # Negative
            "type": "credit",   # But credit type
            "description": "Type mismatch test"
        })
        
        assert response.status_code == 422
    
    def test_empty_description(self):
        """Test empty description validation."""
        response = client.post("/transactions", json={
            "idempotencyKey": "test_empty_desc",
            "accountId": "acc_001",
            "amount": 100.00,
            "type": "credit",
            "description": ""
        })
        
        assert response.status_code == 422


class TestHealthAndUtility:
    """Test health check and utility endpoints."""
    
    def test_health_check(self):
        """Test health check endpoint."""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "accounts_count" in data
        assert "transactions_processed" in data
        assert data["accounts_count"] == 3  # Initial accounts
    
    def test_root_endpoint(self):
        """Test root endpoint."""
        response = client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "message" in data
        assert "docs" in data


class TestBusinessLogic:
    """Test complex business logic scenarios."""
    
    def test_large_transaction_sequence(self):
        """Test a sequence of various transactions."""
        transactions = [
            {"key": "seq_1", "account": "acc_001", "amount": 500.00, "type": "credit"},
            {"key": "seq_2", "account": "acc_001", "amount": -200.00, "type": "debit"},
            {"key": "seq_3", "account": "acc_001", "amount": 150.00, "type": "credit"},
            {"key": "seq_4", "account": "acc_001", "amount": -100.00, "type": "debit"},
        ]
        
        expected_balances = [1500.00, 1300.00, 1450.00, 1350.00]
        
        for i, txn in enumerate(transactions):
            response = client.post("/transactions", json={
                "idempotencyKey": txn["key"],
                "accountId": txn["account"],
                "amount": txn["amount"],
                "type": txn["type"],
                "description": f"Sequence test {i+1}"
            })
            
            assert response.status_code == 201
            assert response.json()["balance"] == expected_balances[i]
    
    def test_decimal_precision(self):
        """Test decimal precision handling."""
        response = client.post("/transactions", json={
            "idempotencyKey": "precision_test",
            "accountId": "acc_001",
            "amount": 99.99,
            "type": "credit",
            "description": "Precision test"
        })
        
        assert response.status_code == 201
        assert response.json()["balance"] == 1099.99
        
        # Test with more decimal places
        response = client.post("/transactions", json={
            "idempotencyKey": "precision_test_2",
            "accountId": "acc_001",
            "amount": -0.01,
            "type": "debit",
            "description": "Penny test"
        })
        
        assert response.status_code == 201
        assert response.json()["balance"] == 1099.98


class TestErrorHandling:
    """Test error handling scenarios."""
    
    def test_malformed_json(self):
        """Test malformed JSON handling."""
        response = client.post(
            "/transactions",
            data="{'invalid': 'json'",  # Invalid JSON
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 422
    
    def test_missing_required_fields(self):
        """Test missing required fields."""
        response = client.post("/transactions", json={
            "idempotencyKey": "test_missing_fields",
            "accountId": "acc_001",
            # Missing amount, type, description
        })
        
        assert response.status_code == 422
    
    @patch('services.logger')
    def test_logging_on_error(self, mock_logger):
        """Test that errors are properly logged."""
        response = client.post("/transactions", json={
            "idempotencyKey": "test_logging",
            "accountId": "acc_999",  # Non-existent account
            "amount": 100.00,
            "type": "credit",
            "description": "Logging test"
        })
        
        assert response.status_code == 404
        # Verify that warning was logged
        mock_logger.warning.assert_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])