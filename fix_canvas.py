import re

with open("frontend/src/pages/Dashboard.tsx", "r") as f:
    code = f.read()

# Fix the React strict mode double-canvas bug
code = code.replace(
    'mountRef.current?.appendChild(renderer.domElement);',
    'const currentMount = mountRef.current;\n    if (currentMount) currentMount.innerHTML = ""; // Clear any ghost canvases\n    currentMount?.appendChild(renderer.domElement);'
)

code = code.replace(
    'mountRef.current?.removeChild(renderer.domElement);',
    'currentMount?.removeChild(renderer.domElement);'
)

# And fix the Chart.js strict mode bug just in case!
code = code.replace(
    'const ctx = chartRef.current.getContext(\'2d\');',
    'if (chartInstance.current) chartInstance.current.destroy(); // Clear old chart\n    const ctx = chartRef.current.getContext(\'2d\');'
)

with open("frontend/src/pages/Dashboard.tsx", "w") as f:
    f.write(code)

