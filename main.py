from fastapi import FastAPI, HTTPException, Request, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import structlog
import time
from contextlib import asynccontextmanager

from models import TransactionRequest, TransactionResponse, ErrorResponse, HealthResponse
from services import TransactionService, get_transaction_service
from repositories import get_account_repository, get_idempotency_repository
from config import get_settings

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Rate limiting
limiter = Limiter(key_func=get_remote_address)

# Application lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Transaction API")
    yield
    # Shutdown
    logger.info("Shutting down Transaction API")

# Create FastAPI app
app = FastAPI(
    title="Transaction Processing API",
    description="High-performance API for processing financial transactions with idempotency support",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Add rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    
    # Log request
    logger.info(
        "Request started",
        method=request.method,
        url=str(request.url),
        client_ip=request.client.host if request.client else None
    )
    
    response = await call_next(request)
    
    # Log response
    process_time = time.time() - start_time
    logger.info(
        "Request completed",
        method=request.method,
        url=str(request.url),
        status_code=response.status_code,
        process_time=round(process_time, 4)
    )
    
    return response

# Dependency injection
def get_service(
    account_repo=Depends(get_account_repository),
    idempotency_repo=Depends(get_idempotency_repository)
) -> TransactionService:
    return get_transaction_service(account_repo, idempotency_repo)

# Health check endpoint
@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check",
    description="Check API health and get system statistics"
)
async def health_check(
    account_repo=Depends(get_account_repository),
    idempotency_repo=Depends(get_idempotency_repository)
):
    try:
        accounts_count = await account_repo.get_accounts_count()
        transactions_count = await idempotency_repo.get_transactions_count()
        
        return HealthResponse(
            status="healthy",
            accounts_count=accounts_count,
            transactions_processed=transactions_count
        )
    except Exception as e:
        logger.error("Health check failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Health check failed"
        )

# Main transaction endpoint
@app.post(
    "/transactions",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Process Transaction",
    description="Process a financial transaction (debit/credit) with idempotency support",
    responses={
        201: {"description": "Transaction processed successfully"},
        400: {"description": "Bad request - validation error or insufficient funds"},
        404: {"description": "Account not found"},
        429: {"description": "Rate limit exceeded"},
        500: {"description": "Internal server error"}
    }
)
@limiter.limit("30/minute")  # Rate limiting
async def create_transaction(
    request: Request,
    transaction_request: TransactionRequest,
    service: TransactionService = Depends(get_service)
):
    try:
        logger.info(
            "Transaction request received",
            idempotency_key=transaction_request.idempotencyKey,
            account_id=transaction_request.accountId
        )
        
        result = await service.process_transaction(transaction_request)
        
        logger.info(
            "Transaction request completed successfully",
            transaction_id=result.transactionId,
            idempotency_key=transaction_request.idempotencyKey
        )
        
        return result
        
    except HTTPException as e:
        logger.warning(
            "Transaction request failed with HTTP exception",
            status_code=e.status_code,
            detail=e.detail,
            idempotency_key=transaction_request.idempotencyKey
        )
        raise e
        
    except Exception as e:
        logger.error(
            "Transaction request failed with unexpected error",
            error=str(e),
            idempotency_key=transaction_request.idempotencyKey,
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )

# Global exception handler
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            detail=exc.detail,
            error_code=f"HTTP_{exc.status_code}"
        ).dict()
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(
        "Unhandled exception",
        error=str(exc),
        url=str(request.url),
        method=request.method,
        exc_info=True
    )
    
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            detail="Internal server error",
            error_code="INTERNAL_ERROR"
        ).dict()
    )

# Root endpoint
@app.get("/", include_in_schema=False)
async def root():
    return {"message": "Transaction Processing API", "docs": "/docs"}

if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )