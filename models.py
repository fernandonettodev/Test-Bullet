from pydantic import BaseModel, Field, validator
from enum import Enum
from typing import Literal
from datetime import datetime
from decimal import Decimal
import re


class TransactionType(str, Enum):
    debit = "debit"
    credit = "credit"


class TransactionRequest(BaseModel):
    idempotencyKey: str = Field(
        ..., 
        min_length=1, 
        max_length=100,
        description="Unique key to ensure idempotency"
    )
    accountId: str = Field(
        ..., 
        min_length=1, 
        max_length=50,
        description="Account identifier"
    )
    amount: Decimal = Field(
        ..., 
        max_digits=12, 
        decimal_places=2,
        description="Transaction amount (positive for credit, negative for debit)"
    )
    type: TransactionType = Field(..., description="Transaction type")
    description: str = Field(
        ..., 
        min_length=1, 
        max_length=500,
        description="Transaction description"
    )

    @validator('idempotencyKey')
    def validate_idempotency_key(cls, v):
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('Idempotency key must contain only alphanumeric characters, underscores, and hyphens')
        return v

    @validator('accountId')
    def validate_account_id(cls, v):
        if not re.match(r'^acc_[0-9]+$', v):
            raise ValueError('Account ID must follow format: acc_XXX')
        return v

    @validator('amount')
    def validate_amount(cls, v):
        if v == 0:
            raise ValueError('Amount cannot be zero')
        return v

    @validator('amount', always=True)
    def validate_amount_type_consistency(cls, v, values):
        transaction_type = values.get('type')
        if transaction_type == TransactionType.debit and v > 0:
            raise ValueError('Debit transactions must have negative amounts')
        elif transaction_type == TransactionType.credit and v < 0:
            raise ValueError('Credit transactions must have positive amounts')
        return v


class TransactionResponse(BaseModel):
    transactionId: str = Field(..., description="Unique transaction identifier")
    status: Literal["processed"] = Field(..., description="Transaction status")
    balance: Decimal = Field(..., max_digits=12, decimal_places=2, description="Account balance after transaction")
    timestamp: datetime = Field(..., description="Transaction timestamp")

    class Config:
        json_encoders = {
            Decimal: lambda v: float(v),
            datetime: lambda v: v.isoformat()
        }


class ErrorResponse(BaseModel):
    detail: str = Field(..., description="Error description")
    error_code: str = Field(..., description="Machine-readable error code")
    timestamp: datetime = Field(default_factory=datetime.now, description="Error timestamp")


class HealthResponse(BaseModel):
    status: str = Field(..., description="Service health status")
    timestamp: datetime = Field(default_factory=datetime.now)
    accounts_count: int = Field(..., description="Number of accounts in system")
    transactions_processed: int = Field(..., description="Total transactions processed")