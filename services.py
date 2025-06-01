import uuid
from datetime import datetime
from zoneinfo import ZoneInfo
from decimal import Decimal
from fastapi import HTTPException
import structlog

from models import TransactionRequest, TransactionResponse, TransactionType
from repositories import AccountRepository, IdempotencyRepository

# Configure structured logging
logger = structlog.get_logger()


class TransactionService:
    def __init__(self, account_repo: AccountRepository, idempotency_repo: IdempotencyRepository):
        self.account_repo = account_repo
        self.idempotency_repo = idempotency_repo
    
    async def process_transaction(self, request: TransactionRequest) -> TransactionResponse:
        """Process a financial transaction with idempotency support."""
        
        logger.info(
            "Processing transaction",
            idempotency_key=request.idempotencyKey,
            account_id=request.accountId,
            amount=str(request.amount),
            type=request.type.value
        )
        
        # Check idempotency first
        existing_transaction = await self.idempotency_repo.get_transaction(request.idempotencyKey)
        if existing_transaction:
            logger.info(
                "Returning existing transaction due to idempotency",
                idempotency_key=request.idempotencyKey,
                transaction_id=existing_transaction.transactionId
            )
            return existing_transaction
        
        # Validate account existence
        if not await self.account_repo.account_exists(request.accountId):
            logger.warning(
                "Account not found",
                account_id=request.accountId,
                idempotency_key=request.idempotencyKey
            )
            raise HTTPException(
                status_code=404, 
                detail="Account not found"
            )
        
        # Process transaction with account lock
        if hasattr(self.account_repo, 'get_lock'):
            lock = self.account_repo.get_lock(request.accountId)
        else:
            # Fallback for repositories without locks
            import asyncio
            lock = asyncio.Lock()
        
        async with lock:
            current_balance = await self.account_repo.get_balance(request.accountId)
            
            # Calculate new balance based on transaction type
            if request.type == TransactionType.debit:
                new_balance = await self._process_debit(
                    request, current_balance, request.accountId
                )
            elif request.type == TransactionType.credit:
                new_balance = await self._process_credit(
                    request, current_balance, request.accountId
                )
            else:
                logger.error(
                    "Invalid transaction type",
                    type=request.type,
                    idempotency_key=request.idempotencyKey
                )
                raise HTTPException(
                    status_code=400, 
                    detail="Invalid transaction type"
                )
            
            # Update account balance
            await self.account_repo.update_balance(request.accountId, new_balance)
            
            # Create response
            response = TransactionResponse(
                transactionId=str(uuid.uuid4()),
                status="processed",
                balance=new_balance,
                timestamp=datetime.now(ZoneInfo("America/Sao_Paulo"))
            )
            
            # Store for idempotency
            await self.idempotency_repo.store_transaction(request.idempotencyKey, response)
            
            logger.info(
                "Transaction processed successfully",
                transaction_id=response.transactionId,
                account_id=request.accountId,
                new_balance=str(new_balance),
                idempotency_key=request.idempotencyKey
            )
            
            return response
    
    async def _process_debit(
        self, 
        request: TransactionRequest, 
        current_balance: Decimal, 
        account_id: str
    ) -> Decimal:
        """Process debit transaction."""
        debit_amount = abs(request.amount)  # Ensure positive for calculation
        
        if current_balance < debit_amount:
            logger.warning(
                "Insufficient funds for debit",
                account_id=account_id,
                current_balance=str(current_balance),
                requested_amount=str(debit_amount),
                idempotency_key=request.idempotencyKey
            )
            raise HTTPException(
                status_code=400, 
                detail="Insufficient funds"
            )
        
        new_balance = current_balance - debit_amount
        
        logger.debug(
            "Debit processed",
            account_id=account_id,
            debit_amount=str(debit_amount),
            old_balance=str(current_balance),
            new_balance=str(new_balance)
        )
        
        return new_balance
    
    async def _process_credit(
        self, 
        request: TransactionRequest, 
        current_balance: Decimal, 
        account_id: str
    ) -> Decimal:
        """Process credit transaction."""
        credit_amount = abs(request.amount)  # Ensure positive for calculation
        new_balance = current_balance + credit_amount
        
        logger.debug(
            "Credit processed",
            account_id=account_id,
            credit_amount=str(credit_amount),
            old_balance=str(current_balance),
            new_balance=str(new_balance)
        )
        
        return new_balance


# Factory function for dependency injection
def get_transaction_service(
    account_repo: AccountRepository,
    idempotency_repo: IdempotencyRepository
) -> TransactionService:
    return TransactionService(account_repo, idempotency_repo)