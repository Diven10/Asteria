import re

with open("app/main.py", "r") as f:
    code = f.read()

addition = """
from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse, tags=["frontend"])
async def render_landing(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/dashboard", response_class=HTMLResponse, tags=["frontend"])
async def render_dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})
"""

code = code + "\n" + addition

with open("app/main.py", "w") as f:
    f.write(code)
