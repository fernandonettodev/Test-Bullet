import asyncio
from typing import Dict
from collections import defaultdict

accounts: Dict[str, float] = {
    "acc_001": 1000.0,
    "acc_002": 500.0,
    "acc_003": 0.0
}

# Transações processadas (por idempotencyKey)
idempotency_store: Dict[str, dict] = {}

# Locks por conta
account_locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
