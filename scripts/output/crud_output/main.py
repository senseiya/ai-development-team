from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.api.routes import router as task_router
from app.core.database import engine

# Initialize FastAPI application
app = FastAPI(
    title="TaskMaster Pro",
    description="A fullstack task management CRUD application",
    version="1.0.0",
)

# Create database tables on startup
@app.on_event("startup")
async def startup_event():
    """
    Initializes the database schema upon application startup.
    """
    import app.models.task  # Ensure models are registered
    app.state.db_engine = engine
    app.state.db_engine.create_all(bind=engine)

# Mount static files for CSS and JS
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Set up Jinja2 templates directory
templates = Jinja2Templates(directory="app/templates")

# Include API routers
app.include_router(task_router, prefix="/api")

@app.get("/")
async def read_root(request):
    """
    Serves the main dashboard page.
    """
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/health")
async def health_check():
    """
    Health check endpoint for monitoring.
    """
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn

    # Run the application using uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )