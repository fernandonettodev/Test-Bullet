from abc import ABC, abstractmethod
from typing import Dict, Optional
from decimal import Decimal
import asyncio
from collections import defaultdict
from models import TransactionResponse


class AccountRepository(ABC):
    @abstractmethod
    async def get_balance(self, account_id: str) -> Optional[Decimal]:
        """Get account balance. Returns None if account doesn't exist."""
        pass
    
    @abstractmethod
    async def update_balance(self, account_id: str, new_balance: Decimal) -> None:
        """Update account balance."""
        pass
    
    @abstractmethod
    async def account_exists(self, account_id: str) -> bool:
        """Check if account exists."""
        pass
    
    @abstractmethod
    async def get_accounts_count(self) -> int:
        """Get total number of accounts."""
        pass


class IdempotencyRepository(ABC):
    @abstractmethod
    async def get_transaction(self, idempotency_key: str) -> Optional[TransactionResponse]:
        """Get stored transaction by idempotency key."""
        pass
    
    @abstractmethod
    async def store_transaction(self, idempotency_key: str, response: TransactionResponse) -> None:
        """Store transaction response for idempotency."""
        pass
    
    @abstractmethod
    async def get_transactions_count(self) -> int:
        """Get total number of stored transactions."""
        pass


class InMemoryAccountRepository(AccountRepository):
    def __init__(self):
        self.accounts: Dict[str, Decimal] = {
            "acc_001": Decimal("1000.00"),
            "acc_002": Decimal("500.00"),
            "acc_003": Decimal("0.00")
        }
        self.locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
    
    async def get_balance(self, account_id: str) -> Optional[Decimal]:
        return self.accounts.get(account_id)
    
    async def update_balance(self, account_id: str, new_balance: Decimal) -> None:
        if account_id not in self.accounts:
            raise ValueError(f"Account {account_id} does not exist")
        self.accounts[account_id] = new_balance
    
    async def account_exists(self, account_id: str) -> bool:
        return account_id in self.accounts
    
    async def get_accounts_count(self) -> int:
        return len(self.accounts)
    
    def get_lock(self, account_id: str) -> asyncio.Lock:
        """Get lock for specific account."""
        return self.locks[account_id]


class InMemoryIdempotencyRepository(IdempotencyRepository):
    def __init__(self):
        self.store: Dict[str, TransactionResponse] = {}
    
    async def get_transaction(self, idempotency_key: str) -> Optional[TransactionResponse]:
        return self.store.get(idempotency_key)
    
    async def store_transaction(self, idempotency_key: str, response: TransactionResponse) -> None:
        self.store[idempotency_key] = response
    
    async def get_transactions_count(self) -> int:
        return len(self.store)
    
    def clear(self) -> None:
        """Clear all stored transactions (for testing)."""
        self.store.clear()


# Singleton instances (em produção, usar dependency injection)
_account_repo = InMemoryAccountRepository()
_idempotency_repo = InMemoryIdempotencyRepository()


def get_account_repository() -> AccountRepository:
    return _account_repo


def get_idempotency_repository() -> IdempotencyRepository:
    return _idempotency_repo


# Para testes
def reset_repositories():
    """Reset all repositories to initial state (for testing only)."""
    global _account_repo, _idempotency_repo
    _account_repo = InMemoryAccountRepository()
    _idempotency_repo = InMemoryIdempotencyRepository()