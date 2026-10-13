with open("app/main.py", "r") as f:
    content = f.read()

if "CORSMiddleware" not in content:
    cors_str = """
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
"""
    content = content.replace("app.include_router(pipeline.router)", cors_str + "\napp.include_router(pipeline.router)")
    with open("app/main.py", "w") as f:
        f.write(content)
