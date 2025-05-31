from fastapi import FastAPI, HTTPException, Request
from models import TransactionRequest, TransactionResponse
from services import process_transaction

app = FastAPI()

@app.post("/transactions", response_model=TransactionResponse, status_code=201)
async def create_transaction(request: TransactionRequest):
    try:
        result = await process_transaction(request)
        return result
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))