import re

with open("frontend/src/pages/Landing.tsx", "r") as f:
    content = f.read()

# Fix the self-closing tag issue
content = content.replace("</path>", "")
content = content.replace("</img>", "")
content = content.replace("</stop>", "")

# Fix other JSX properties
content = content.replace("stroke-linejoin", "strokeLinejoin")
content = content.replace("stroke-miterlimit", "strokeMiterlimit")
content = content.replace("stroke-opacity", "strokeOpacity")

with open("frontend/src/pages/Landing.tsx", "w") as f:
    f.write(content)
