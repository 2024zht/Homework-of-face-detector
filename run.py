"""Launch the check-in system"""
import os, sys

# Load .env file before anything else
_env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(_env_path):
    with open(_env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

BACKEND_DIR = os.path.join(os.path.dirname(__file__), "backend")
os.chdir(BACKEND_DIR)
sys.path.insert(0, BACKEND_DIR)

if __name__ == "__main__":
    from config import PORT
    print("Starting Lab Check-in System...")
    print(f"Backend: {BACKEND_DIR}")
    print(f"Open http://localhost:{PORT} in your browser")
    print("Mobile QR scan requires cpolar tunnel or local network access")

    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=True, log_level="info")
