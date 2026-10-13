with open("frontend/src/pages/Landing.tsx", "r") as f:
    content = f.read()

# Replace `return (` with `return ( <>`
content = content.replace(
    'return (\n    <div className="fixed-bg"></div>',
    'return (\n    <>\n    <div className="fixed-bg"></div>'
)

# We need to add the closing fragment tag `</>` right before the final `);`
# Let's find the end of the return statement.
content = content.replace(
    '    />\n  );\n};',
    '    />\n    </>\n  );\n};'
)

with open("frontend/src/pages/Landing.tsx", "w") as f:
    f.write(content)
