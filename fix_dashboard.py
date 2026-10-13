import re

with open("frontend/src/pages/Dashboard.tsx", "r") as f:
    code = f.read()

# Add OrbitControls import if not present
if "OrbitControls" not in code or "three/examples/jsm/controls/OrbitControls.js" not in code:
    code = code.replace(
        "import * as THREE from 'three';",
        "import * as THREE from 'three';\n// @ts-ignore\nimport { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';"
    )

# Remove the old broken import if any
code = re.sub(r"import \{ OrbitControls \} from 'three/examples/jsm/controls/OrbitControls';\n", "", code)

# Restore devicePixelRatio for HD crispness
code = code.replace(
    'renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5)); // Capped for performance',
    'renderer.setPixelRatio(window.devicePixelRatio); // Restored for high definition Retina'
)
code = code.replace(
    'renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));',
    'renderer.setPixelRatio(window.devicePixelRatio);'
)

# Insert OrbitControls setup after renderer
controls_setup = """
    // OrbitControls
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.enablePan = false;
    controls.minDistance = 5;
    controls.maxDistance = 30;
"""

if "new OrbitControls(" not in code:
    code = code.replace(
        "renderer.setSize(window.innerWidth, window.innerHeight);",
        "renderer.setSize(window.innerWidth, window.innerHeight);" + controls_setup
    )

# Add controls.update() in the animation loop
if "controls.update();" not in code:
    code = code.replace(
        "renderer.render(scene, camera);",
        "controls.update();\n      renderer.render(scene, camera);"
    )

with open("frontend/src/pages/Dashboard.tsx", "w") as f:
    f.write(code)

