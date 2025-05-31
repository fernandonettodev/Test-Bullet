from pydantic import BaseModel, Field
from enum import Enum
from typing import Literal
from datetime import datetime


class TransactionType(str, Enum):
    debit = "debit"
    credit = "credit"


class TransactionRequest(BaseModel):
    idempotencyKey: str
    accountId: str
    amount: float
    type: TransactionType
    description: str


class TransactionResponse(BaseModel):
    transactionId: str
    status: Literal["processed"]
    balance: float
    timestamp: datetime