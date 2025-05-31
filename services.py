import uuid
from datetime import datetime
from zoneinfo import ZoneInfo   
from fastapi import HTTPException
from models import TransactionRequest, TransactionResponse
from storage import accounts, idempotency_store, account_locks


async def process_transaction(request: TransactionRequest) -> TransactionResponse:
    # Se a idempotencyKey já existe, retorna a resposta armazenada
    if request.idempotencyKey in idempotency_store:
        return idempotency_store[request.idempotencyKey]

    # Verifica se a conta existe
    if request.accountId not in accounts:
        raise HTTPException(status_code=404, detail="Account not found")

    # Lock por conta para evitar condições de corrida
    lock = account_locks[request.accountId]

    async with lock:
        current_balance = accounts[request.accountId]

        if request.type == "debit":
            if current_balance < abs(request.amount):
                raise HTTPException(status_code=400, detail="Insufficient funds")
            accounts[request.accountId] -= abs(request.amount)
        elif request.type == "credit":
            accounts[request.accountId] += abs(request.amount)
        else:
            raise HTTPException(status_code=400, detail="Invalid transaction type")

        # Criação da resposta
        response = TransactionResponse(
            transactionId=str(uuid.uuid4()),
            status="processed",
            balance=accounts[request.accountId],
            timestamp = datetime.now(ZoneInfo("America/Sao_Paulo"))
        )

        # Armazena para idempotência
        idempotency_store[request.idempotencyKey] = response

        return response