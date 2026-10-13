import sys

with open('asteria_landing.html', 'r') as f:
    content = f.read()

# Fix the SVG path by adding pathLength="100"
old_path = '<path id="svg-progress" d="M 30 10 L 70 10 C 85 10, 85 50, 70 50 L 30 50 C 15 50, 15 90, 30 90 L 70 90" stroke="url(#line-gradient)" stroke-width="6" fill="none" stroke-linecap="round" vector-effect="non-scaling-stroke" style="filter: drop-shadow(0px 0px 8px rgba(75,123,245,0.6));" />'
new_path = '<path id="svg-progress" d="M 30 10 L 70 10 C 85 10, 85 50, 70 50 L 30 50 C 15 50, 15 90, 30 90 L 70 90" stroke="url(#line-gradient)" stroke-width="6" fill="none" stroke-linecap="round" vector-effect="non-scaling-stroke" style="filter: drop-shadow(0px 0px 8px rgba(75,123,245,0.6));" pathLength="100" />'

content = content.replace(old_path, new_path)

# Fix the JS logic
old_js = """            // Initialize SVG Path length for drawing animation
            const pathLength = path.getTotalLength();
            path.style.strokeDasharray = pathLength;
            path.style.strokeDashoffset = pathLength;"""

new_js = """            // Use normalized pathLength=100 to prevent browser scaling bugs (dashed line artifact)
            path.style.strokeDasharray = "100 105"; // 100 dash, 105 gap (gap slightly larger to prevent tail bleed)
            path.style.strokeDashoffset = "100";"""

content = content.replace(old_js, new_js)

old_draw = """                // Draw the SVG line perfectly with no stutter
                path.style.strokeDashoffset = pathLength * (1 - progress);"""

new_draw = """                // Draw the SVG line perfectly with no stutter (0 to 100)
                path.style.strokeDashoffset = 100 - (progress * 100);"""

content = content.replace(old_draw, new_draw)

with open('asteria_landing.html', 'w') as f:
    f.write(content)
