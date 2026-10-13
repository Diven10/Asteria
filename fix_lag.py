import re

# 1. Fix index.css (Remove background-attachment: fixed)
with open("frontend/src/index.css", "r") as f:
    css = f.read()

css = css.replace("background-attachment: fixed;", "")
# Add a new class for the fixed background layer
if ".fixed-bg" not in css:
    css += """
.fixed-bg {
    position: fixed;
    top: 0;
    left: 0;
    width: 100vw;
    height: 100vh;
    z-index: -1;
    background-image: url('https://www.nasa.gov/wp-content/uploads/2026/10/stsci-01m3cbk3t6srkp4q7wv9cgfgw9.jpg');
    background-size: cover;
    background-position: center;
    background-repeat: no-repeat;
    will-change: transform;
}
"""
with open("frontend/src/index.css", "w") as f:
    f.write(css)

# 2. Fix Landing.tsx (Use the fixed background div, optimize loop)
with open("frontend/src/pages/Landing.tsx", "r") as f:
    landing = f.read()

# Replace bg-hero on the main container with the new fixed-bg div
landing = landing.replace(
    'className="bg-hero min-h-screen flex flex-col font-sans antialiased text-[#E2E8F0]"',
    'className="min-h-screen flex flex-col font-sans antialiased text-[#E2E8F0]"'
)
landing = landing.replace(
    '<div \n        ref={containerRef}',
    '<div className="fixed-bg"></div>\n    <div \n        ref={containerRef}'
)

# Optimize the SVG progress path to use GPU compositing
landing = landing.replace(
    'style="will-change: stroke-dashoffset; transition: stroke-dashoffset 0.1s ease-out;"',
    'style="will-change: stroke-dashoffset, transform; transition: stroke-dashoffset 0.1s linear;"'
)

# Optimize the updatePipeline loop to cache the DOM queries
# We'll inject a slightly smarter loop inside the JS block
optimized_js = """
    const stepsData = Array.from(steps).map(step => ({
        step,
        circle: step.querySelector('.step-circle'),
        text: step.querySelector('.step-text'),
        isActive: false
    }));

    const updatePipeline = () => {
        const rect = container.getBoundingClientRect();
        const windowHeight = window.innerHeight;
        
        let progress = 0;
        if (rect.top <= 0) {
            const scrolled = -rect.top;
            const totalScrollable = rect.height - windowHeight;
            progress = Math.min(1, Math.max(0, scrolled / totalScrollable));
        }
        
        path.style.strokeDashoffset = pathLength - (progress * pathLength);
        
        const thresholds = [0, 0.20, 0.45, 0.55, 0.80, 0.99];
        
        stepsData.forEach((data, index) => {
            const { circle, text } = data;
            const isMagenta = index >= 3; 
            const shouldBeActive = progress >= thresholds[index];
            
            if (data.isActive !== shouldBeActive) {
                data.isActive = shouldBeActive;
                if (shouldBeActive) {
                    if (isMagenta) {
                        circle.classList.add('bg-magenta/30', 'border-magenta', 'text-white', 'shadow-[0_0_30px_#B3589A]', 'scale-110');
                        circle.classList.remove('bg-black/30', 'border-white/20', 'text-white/30');
                    } else {
                        circle.classList.add('bg-starlight/30', 'border-starlight', 'text-white', 'shadow-[0_0_30px_#4B7BF5]', 'scale-110');
                        circle.classList.remove('bg-black/30', 'border-white/20', 'text-white/30');
                    }
                    text.classList.add('text-white');
                    text.classList.remove('text-white/30');
                    text.style.textShadow = '0 0 10px rgba(255,255,255,0.5)';
                } else {
                    if (isMagenta) {
                        circle.classList.remove('bg-magenta/30', 'border-magenta', 'text-white', 'shadow-[0_0_30px_#B3589A]', 'scale-110');
                    } else {
                        circle.classList.remove('bg-starlight/30', 'border-starlight', 'text-white', 'shadow-[0_0_30px_#4B7BF5]', 'scale-110');
                    }
                    circle.classList.add('bg-black/30', 'border-white/20', 'text-white/30');
                    text.classList.remove('text-white');
                    text.classList.add('text-white/30');
                    text.style.textShadow = 'none';
                }
            }
        });
    };
"""

# We need to replace the old updatePipeline and steps logic
old_js_pattern = re.compile(r'const updatePipeline = \(\) => \{.*?\};\n', re.DOTALL)
landing = old_js_pattern.sub("", landing) # Remove the old one first

# Now find where to insert it (right before `window.addEventListener('resize'`)
landing = landing.replace("window.addEventListener('resize', buildSVGPath);", optimized_js + "\n    window.addEventListener('resize', buildSVGPath);")


with open("frontend/src/pages/Landing.tsx", "w") as f:
    f.write(landing)

