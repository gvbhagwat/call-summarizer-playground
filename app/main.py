import logging
import uuid
from fastapi import FastAPI, Request, HTTPException, Depends
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.api.endpoints import user, auth, transcription
from app.db.session import SessionLocal
from app.core.config import settings

# Setup structured logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [%(request_uuid)s] %(message)s")
logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0",
)

app.state.limiter = limiter
app.add_exception_handler(HTTPException, limiter.http_exception_handler)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this in production!
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency to get logger with request UUID
def get_logger(request: Request):
    custom_logger = logging.LoggerAdapter(logger, {"request_uuid": request.state.uuid})
    return custom_logger

# Include the API routers
app.include_router(user.router, prefix="/users", tags=["users"])
app.include_router(auth.router, prefix="/auth", tags=["authentication"])
app.include_router(transcription.router, prefix="/transcription", tags=["transcription"])

@app.on_event("startup")
async def startup_event():
    logger.info("Starting up the application...")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down the application...")

@app.get("/", tags=["root"])
async def read_root():
    return {"message": "Welcome to the Audio Summarizer API!"}

# Middleware to assign a unique UUID to each request for tracking
class RequestUUIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request.state.uuid = str(uuid.uuid4())
        response = await call_next(request)
        return response

app.add_middleware(RequestUUIDMiddleware)

# Middleware to log each request and response
@app.middleware("http")
async def log_requests(request: Request, call_next, logger: logging.LoggerAdapter = Depends(get_logger)):
    logger.info(f"Path: {request.url.path} | Method: {request.method}")
    response = await call_next(request)
    logger.info(f"Response Status: {response.status_code}")
    return response

# Global exception handler
@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException, logger: logging.LoggerAdapter = Depends(get_logger)):
    logger.error(f"Error: {exc.detail}")
    return {"detail": exc.detail}
