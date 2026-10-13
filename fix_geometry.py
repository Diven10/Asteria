with open("frontend/src/pages/Dashboard.tsx", "r") as f:
    code = f.read()

# Restore high definition geometry for the exoplanet blob
code = code.replace("new THREE.SphereGeometry(3, 32, 32)", "new THREE.SphereGeometry(3, 64, 64)")
code = code.replace("new THREE.SphereGeometry(3.1, 32, 32)", "new THREE.SphereGeometry(3.1, 64, 64)")

with open("frontend/src/pages/Dashboard.tsx", "w") as f:
    f.write(code)

