import uuid
from fastapi import FastAPI, Request, HTTPException, Depends
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address
from loguru import logger
from opentracing import Span, tag
from app.api.endpoints import user, auth, transcription
from app.core.config import settings
from app.core.tracing import init_jaeger_tracer

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

# Loguru configuration
logger.add("logs/app.log", rotation="1 day", retention="10 days", level="INFO")

# Initialize Jaeger tracer
tracer = init_jaeger_tracer("audio-summarizer")

# Middleware to assign a unique UUID to each request for tracking
class RequestUUIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request.state.uuid = str(uuid.uuid4())
        response = await call_next(request)
        return response

app.add_middleware(RequestUUIDMiddleware)

# Middleware to log each request and response
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"Request UUID: {request.state.uuid} | Path: {request.url.path} | Method: {request.method}")
    response = await call_next(request)
    logger.info(f"Request UUID: {request.state.uuid} | Response Status: {response.status_code}")
    return response

# Global exception handler
@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    logger.error(f"Request UUID: {request.state.uuid} | Error: {exc.detail}")
    return {"detail": exc.detail}

@app.on_event("startup")
async def startup_event():
    logger.info("Starting up the application...")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down the application...")
    tracer.close()

@app.get("/", tags=["root"])
async def read_root():
    return {"message": "Welcome to the Audio Summarizer API!"}

# Include the API routers
app.include_router(user.router, prefix="/users", tags=["users"])
app.include_router(auth.router, prefix="/auth", tags=["authentication"])
app.include_router(transcription.router, prefix="/transcription", tags=["transcription"])
