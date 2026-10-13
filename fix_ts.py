with open("frontend/src/pages/Landing.tsx", "r") as f:
    content = f.read()

content = content.replace("useRef(null)", "useRef<any>(null)")
content = content.replace("useRef([])", "useRef<any>([])")

with open("frontend/src/pages/Landing.tsx", "w") as f:
    f.write(content)
