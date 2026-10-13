import re

with open("frontend/src/pages/Dashboard.tsx", "r") as f:
    code = f.read()

# Add controls.dispose() to the cleanup function
if "controls.dispose();" not in code:
    code = code.replace(
        "window.removeEventListener('resize', onResize);",
        "window.removeEventListener('resize', onResize);\n        controls.dispose();"
    )

with open("frontend/src/pages/Dashboard.tsx", "w") as f:
    f.write(code)

