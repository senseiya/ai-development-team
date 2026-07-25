"""Task Manager - FastAPI application entry point."""
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from src.core.config import settings
from src.models.database import init_db
from src.api.routes import router as task_router

app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION)


@app.on_event("startup")
def on_startup():
    """Initialize database on application startup."""
    init_db()


app.include_router(task_router)

# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def index():
    """Serve the main HTML page."""
    return FileResponse("src/templates/index.html")


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )