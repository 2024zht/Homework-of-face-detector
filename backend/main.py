"""FastAPI main application"""
import os, sys

# Ensure backend directory is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from config import STATIC_DIR, PORT, HOST
from database import init_db, async_session
from routes import auth, qrcode, checkin, admin as admin_routes


async def auto_checkout_loop():
    """Background task: auto sign-out expired check-ins every 5 minutes."""
    while True:
        try:
            async with async_session() as db:
                count = await checkin.auto_checkout_expired(db)
                if count > 0:
                    print(f"[AutoCheckout] Signed out {count} expired check-in(s)")
        except Exception as e:
            print(f"[AutoCheckout] Error: {e}")
        await asyncio.sleep(300)  # 5 minutes


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB. Shutdown: cleanup."""
    await init_db()
    print(f"[Server] Database initialized, admin user ready")
    print(f"[Server] Face model will load on first request")
    task = asyncio.create_task(auto_checkout_loop())
    yield
    task.cancel()


app = FastAPI(
    title="Lab Check-in System",
    description="Face recognition check-in/out system with location verification",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(auth.router)
app.include_router(qrcode.router)
app.include_router(checkin.router)
app.include_router(admin_routes.router)

# Static files (QR codes, photos)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Frontend pages
FRONTEND_DIR = os.path.join(os.path.dirname(STATIC_DIR), "frontend")
# Mount frontend static assets (CSS, JS)
app.mount("/frontend", StaticFiles(directory=FRONTEND_DIR), name="frontend")


@app.get("/")
async def root():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


@app.get("/checkin.html")
async def checkin_page():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


@app.get("/admin.html")
async def admin_page():
    return FileResponse(os.path.join(FRONTEND_DIR, "admin.html"))


@app.get("/login.html")
async def login_page():
    return FileResponse(os.path.join(FRONTEND_DIR, "login.html"))


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "lab-checkin"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)
