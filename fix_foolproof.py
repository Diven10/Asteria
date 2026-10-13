import sys
import re

with open('asteria_landing.html', 'r') as f:
    content = f.read()

# Replace the SVG definition
svg_old_regex = r'<svg class="absolute inset-0 w-full h-full -z-10" viewBox="0 0 100 100" preserveAspectRatio="none">.*?</svg>'
svg_new = """<svg id="pipeline-svg" class="absolute inset-0 w-full h-full -z-10">
                        <defs>
                            <linearGradient id="line-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
                                <stop offset="0%" stop-color="#4B7BF5" />
                                <stop offset="100%" stop-color="#B3589A" />
                            </linearGradient>
                        </defs>
                        <!-- Base track (dim) -->
                        <path id="svg-base" stroke="rgba(255,255,255,0.1)" stroke-width="2" fill="none" stroke-linecap="round" />
                        <!-- Animated progress line -->
                        <path id="svg-progress" stroke="url(#line-gradient)" stroke-width="6" fill="none" stroke-linecap="round" style="filter: drop-shadow(0px 0px 8px rgba(75,123,245,0.6)); transition: none;" />
                    </svg>"""
content = re.sub(svg_old_regex, svg_new, content, flags=re.DOTALL)

# Replace the entire script tag content
script_regex = r'<script>\s+document\.addEventListener\("DOMContentLoaded", \(\) => \{.*?updatePipeline\(\);\n        \}\);\n    </script>'
script_new = """<script>
        document.addEventListener("DOMContentLoaded", () => {
            const container = document.getElementById('pipeline-container');
            const path = document.getElementById('svg-progress');
            const basePath = document.getElementById('svg-base');
            const steps = document.querySelectorAll('.pipeline-step');
            
            if(!container || !path || !steps.length) return;

            let pathLength = 0;
            
            // This function completely bypasses browser scaling bugs by manually drawing the SVG 
            // in exact physical pixels that precisely match your screen size.
            function buildSVGPath() {
                const w = container.offsetWidth;
                const h = container.offsetHeight;
                
                const svg = document.getElementById('pipeline-svg');
                svg.setAttribute('viewBox', `0 0 ${w} ${h}`);
                
                // Absolute positions matching the 30% / 70% left and 10% / 50% / 90% top CSS
                const x1 = w * 0.3;
                const x2 = w * 0.7;
                const y1 = h * 0.1;
                const y2 = h * 0.5;
                const y3 = h * 0.9;
                
                // Curve radius to make a perfect semi-circle snake bend
                const dx = (y2 - y1) * 0.6;
                
                // Draw: Line right -> Curve down & left -> Line left -> Curve down & right -> Line right
                const d = `M ${x1} ${y1} L ${x2} ${y1} C ${x2 + dx} ${y1}, ${x2 + dx} ${y2}, ${x2} ${y2} L ${x1} ${y2} C ${x1 - dx} ${y2}, ${x1 - dx} ${y3}, ${x1} ${y3} L ${x2} ${y3}`;
                
                basePath.setAttribute('d', d);
                path.setAttribute('d', d);
                
                pathLength = path.getTotalLength();
                // Add a small buffer to the gap so it doesn't wrap around
                path.style.strokeDasharray = `${pathLength} ${pathLength + 50}`; 
                path.style.strokeDashoffset = pathLength;
                
                updatePipeline();
            }

            let ticking = false;

            const updatePipeline = () => {
                const rect = container.getBoundingClientRect();
                const windowHeight = window.innerHeight;
                
                let progress = 0;
                if (rect.top <= 0) {
                    const scrolled = -rect.top;
                    const totalScrollable = rect.height - windowHeight;
                    progress = Math.min(1, Math.max(0, scrolled / totalScrollable)); // 0.0 to 1.0
                }
                
                // Exact pixel offset means absolutely zero dashing artifacts
                path.style.strokeDashoffset = pathLength - (progress * pathLength);
                
                const thresholds = [0, 0.20, 0.45, 0.55, 0.80, 0.99];
                
                steps.forEach((step, index) => {
                    const circle = step.querySelector('.step-circle');
                    const text = step.querySelector('.step-text');
                    const isMagenta = index >= 3; 
                    
                    if (progress >= thresholds[index]) {
                        if (isMagenta) {
                            circle.classList.add('bg-magenta', 'border-magenta', 'text-white', 'shadow-[0_0_20px_#B3589A]', 'scale-110');
                            circle.classList.remove('bg-space', 'border-white/20', 'text-white/30');
                        } else {
                            circle.classList.add('bg-starlight', 'border-starlight', 'text-space', 'shadow-[0_0_20px_#4B7BF5]', 'scale-110');
                            circle.classList.remove('bg-space', 'border-white/20', 'text-white/30');
                        }
                        text.classList.add('text-white');
                        text.classList.remove('text-white/30');
                        text.style.textShadow = '0 0 10px rgba(255,255,255,0.5)';
                    } else {
                        if (isMagenta) {
                            circle.classList.remove('bg-magenta', 'border-magenta', 'text-white', 'shadow-[0_0_20px_#B3589A]', 'scale-110');
                        } else {
                            circle.classList.remove('bg-starlight', 'border-starlight', 'text-space', 'shadow-[0_0_20px_#4B7BF5]', 'scale-110');
                        }
                        circle.classList.add('bg-space', 'border-white/20', 'text-white/30');
                        text.classList.remove('text-white');
                        text.classList.add('text-white/30');
                        text.style.textShadow = 'none';
                    }
                });
            };

            window.addEventListener('resize', () => {
                buildSVGPath();
            });

            document.addEventListener('scroll', () => {
                if (!ticking) {
                    window.requestAnimationFrame(() => {
                        updatePipeline();
                        ticking = false;
                    });
                    ticking = true;
                }
            });
            
            // Build the SVG geometry precisely for this screen size on load
            buildSVGPath();
        });
    </script>"""

content = re.sub(script_regex, script_new, content, flags=re.DOTALL)

with open('asteria_landing.html', 'w') as f:
    f.write(content)
