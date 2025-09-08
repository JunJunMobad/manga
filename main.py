"""
FastAPI backend for mobile app with Firebase Auth and Firestore
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
from app.routes import notifications, manga, admin
from app.services.firebase_service import initialize_firebase
from app.services.cron_service import cron_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize Firebase and start cron jobs on startup"""
    print("🚀 Starting Manga Notification API...")
    initialize_firebase()
    
    cron_service.start_scheduler()
    
    print("✅ Application startup completed successfully!")
    yield
    
    print("🛑 Application shutting down...")
    cron_service.stop_scheduler()


app = FastAPI(
    title="Manga Notification API",
    description="FastAPI backend for manga subscription notifications with Firebase Auth",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
app.include_router(manga.router, prefix="/manga", tags=["manga"])
app.include_router(admin.router, prefix="/admin", tags=["admin"])


@app.get("/")
async def root():
    """Health check endpoint"""
    return {"message": "Manga Notification API is running"}


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )