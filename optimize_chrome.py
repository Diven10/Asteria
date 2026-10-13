import re

# 1. Fix Landing.tsx (Remove drop shadow from SVG, add will-change)
with open("frontend/src/pages/Landing.tsx", "r") as f:
    landing = f.read()

# Replace the filter: drop-shadow and add will-change
landing = landing.replace(
    'style="filter: drop-shadow(0px 0px 15px rgba(75,123,245,0.8)); transition: stroke-dashoffset 0.1s ease-out;"',
    'style="will-change: stroke-dashoffset; transition: stroke-dashoffset 0.1s ease-out;"'
)
# Make the stroke slightly thicker to compensate for the lost glow, and use a brighter color if needed
landing = landing.replace('stroke-width="14"', 'stroke-width="16"')

with open("frontend/src/pages/Landing.tsx", "w") as f:
    f.write(landing)

# 2. Fix Dashboard.tsx (Clamp devicePixelRatio, reduce polygon count)
with open("frontend/src/pages/Dashboard.tsx", "r") as f:
    dash = f.read()

dash = dash.replace(
    'renderer.setPixelRatio(window.devicePixelRatio);',
    'renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5)); // Capped for performance'
)
dash = dash.replace(
    'new THREE.SphereGeometry(3, 64, 64)',
    'new THREE.SphereGeometry(3, 32, 32)'
)
dash = dash.replace(
    'new THREE.SphereGeometry(3.1, 64, 64)',
    'new THREE.SphereGeometry(3.1, 32, 32)'
)

with open("frontend/src/pages/Dashboard.tsx", "w") as f:
    f.write(dash)

