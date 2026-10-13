import re

with open("frontend/src/pages/Landing.tsx", "r") as f:
    content = f.read()

# Replace HTML comments with JSX comments
# Note: This is inside the return statement, so `{/* ... */}` works.
# However, if it's outside the return statement, it should be just `//` or `/* ... */`.
# Let's just find where the return statement starts.
return_idx = content.find("return (")
if return_idx != -1:
    before = content[:return_idx]
    after = content[return_idx:]
    after = re.sub(r'<!--(.*?)-->', r'{/*\1*/}', after, flags=re.DOTALL)
    content = before + after

with open("frontend/src/pages/Landing.tsx", "w") as f:
    f.write(content)
