from fastapi import FastAPI

from app.core.config import settings

from app.api import pipeline
from app.api import dashboard

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="ASTERIA — AI-enabled exoplanet detection from noisy astronomical light curves.",
)


from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(pipeline.router)
app.include_router(dashboard.router)

@app.get("/health", tags=["system"]) 
def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}
    

from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse, tags=["frontend"])
async def render_landing(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.get("/select", response_class=HTMLResponse, tags=["frontend"])
async def render_select(request: Request):
    return templates.TemplateResponse(request=request, name="select.html")

@app.get("/dashboard", response_class=HTMLResponse, tags=["frontend"])
async def render_dashboard(request: Request):
    return templates.TemplateResponse(request=request, name="dashboard.html")
