import re

with open("app/main.py", "r") as f:
    code = f.read()

code = code.replace(
    'return templates.TemplateResponse("index.html", {"request": request})',
    'return templates.TemplateResponse(request=request, name="index.html")'
)

code = code.replace(
    'return templates.TemplateResponse("dashboard.html", {"request": request})',
    'return templates.TemplateResponse(request=request, name="dashboard.html")'
)

with open("app/main.py", "w") as f:
    f.write(code)

