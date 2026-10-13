import re

def convert_html_to_jsx(html):
    # Quick and dirty conversion for HTML to JSX
    jsx = html
    # Convert class to className
    jsx = re.sub(r'\bclass=', 'className=', jsx)
    # Convert SVG styling that uses dashes
    jsx = re.sub(r'stroke-dasharray', 'strokeDasharray', jsx)
    jsx = re.sub(r'stroke-dashoffset', 'strokeDashoffset', jsx)
    jsx = re.sub(r'stroke-width', 'strokeWidth', jsx)
    jsx = re.sub(r'stroke-linecap', 'strokeLinecap', jsx)
    # Self close tags that need it
    jsx = re.sub(r'<img([^>]+)(?<!/)>', r'<img\1 />', jsx)
    jsx = re.sub(r'<path([^>]+)(?<!/)>', r'<path\1 />', jsx)
    jsx = re.sub(r'<stop([^>]+)(?<!/)>', r'<stop\1 />', jsx)
    jsx = re.sub(r'stroke-color', 'strokeColor', jsx)
    jsx = re.sub(r'stop-color', 'stopColor', jsx)
    jsx = re.sub(r'vector-effect', 'vectorEffect', jsx)
    
    # Handle style="filter: drop-shadow(...)"
    # A bit complicated, but we'll try: style="filter: drop-shadow(0px 0px 15px rgba(75,123,245,0.8)); transition: none;"
    # Actually, let's just manually replace known style tags.
    jsx = jsx.replace('style="filter: drop-shadow(0px 0px 15px rgba(75,123,245,0.8)); transition: none;"', "style={{filter: 'drop-shadow(0px 0px 15px rgba(75,123,245,0.8))', transition: 'none'}}")
    jsx = jsx.replace('style="filter: drop-shadow(0px 0px 8px rgba(75,123,245,0.6)); transition: none;"', "style={{filter: 'drop-shadow(0px 0px 8px rgba(75,123,245,0.6))', transition: 'none'}}")
    jsx = jsx.replace('style="background-image: linear-gradient', "style={{backgroundImage: 'linear-gradient")
    
    # Simple fix for that one remaining style attribute in Landing page
    jsx = re.sub(r'style="([^"]+)"', r'style={{\1}}', jsx) # Very naive, but we only have a few styles

    return jsx

# --- LANDING PAGE ---
with open('asteria_landing.html', 'r') as f:
    landing_html = f.read()

# Extract styles
styles_match = re.search(r'<style>(.*?)</style>', landing_html, re.DOTALL)
landing_styles = styles_match.group(1) if styles_match else ""

# Extract body
body_match = re.search(r'<body[^>]*>(.*?)<script>', landing_html, re.DOTALL)
if not body_match:
    body_match = re.search(r'<body[^>]*>(.*?)</body>', landing_html, re.DOTALL)
    
landing_body = body_match.group(1)
landing_jsx = convert_html_to_jsx(landing_body)

# Wrap in a component
# For the Landing page, we also need the SVG logic in a useEffect
landing_component = f"""
import React, {{ useEffect, useRef }} from 'react';
import {{ Link }} from 'react-router-dom';
import './Landing.css';

const Landing = () => {{
  const containerRef = useRef(null);
  const pathRef = useRef(null);
  const basePathRef = useRef(null);
  const stepsRef = useRef([]);

  useEffect(() => {{
    const container = containerRef.current;
    const path = pathRef.current;
    const basePath = basePathRef.current;
    const steps = document.querySelectorAll('.pipeline-step');
    let pathLength = 0;
    
    if(!container || !path || !steps.length) return;

    function buildSVGPath() {{
        const w = container.offsetWidth;
        const h = container.offsetHeight;
        
        const svg = document.getElementById('pipeline-svg');
        if (svg) svg.setAttribute('viewBox', `0 0 ${{w}} ${{h}}`);
        
        const x1 = w * 0.3;
        const x2 = w * 0.7;
        const y1 = h * 0.1;
        const y2 = h * 0.5;
        const y3 = h * 0.9;
        
        const dx = (y2 - y1) * 0.6;
        const d = `M ${{x1}} ${{y1}} L ${{x2}} ${{y1}} C ${{x2 + dx}} ${{y1}}, ${{x2 + dx}} ${{y2}}, ${{x2}} ${{y2}} L ${{x1}} ${{y2}} C ${{x1 - dx}} ${{y2}}, ${{x1 - dx}} ${{y3}}, ${{x1}} ${{y3}} L ${{x2}} ${{y3}}`;
        
        if (basePath) basePath.setAttribute('d', d);
        if (path) path.setAttribute('d', d);
        
        pathLength = path.getTotalLength();
        path.style.strokeDasharray = `${{pathLength}} ${{pathLength + 50}}`; 
        path.style.strokeDashoffset = pathLength;
        
        updatePipeline();
    }}

    let ticking = false;

    const updatePipeline = () => {{
        const rect = container.getBoundingClientRect();
        const windowHeight = window.innerHeight;
        
        let progress = 0;
        if (rect.top <= 0) {{
            const scrolled = -rect.top;
            const totalScrollable = rect.height - windowHeight;
            progress = Math.min(1, Math.max(0, scrolled / totalScrollable));
        }}
        
        path.style.strokeDashoffset = pathLength - (progress * pathLength);
        
        const thresholds = [0, 0.20, 0.45, 0.55, 0.80, 0.99];
        
        steps.forEach((step, index) => {{
            const circle = step.querySelector('.step-circle');
            const text = step.querySelector('.step-text');
            const isMagenta = index >= 3; 
            
            if (progress >= thresholds[index]) {{
                if (isMagenta) {{
                    circle.classList.add('bg-magenta/30', 'border-magenta', 'text-white', 'shadow-[0_0_30px_#B3589A]', 'scale-110');
                    circle.classList.remove('bg-black/30', 'border-white/20', 'text-white/30');
                }} else {{
                    circle.classList.add('bg-starlight/30', 'border-starlight', 'text-white', 'shadow-[0_0_30px_#4B7BF5]', 'scale-110');
                    circle.classList.remove('bg-black/30', 'border-white/20', 'text-white/30');
                }}
                text.classList.add('text-white');
                text.classList.remove('text-white/30');
                text.style.textShadow = '0 0 10px rgba(255,255,255,0.5)';
            }} else {{
                if (isMagenta) {{
                    circle.classList.remove('bg-magenta/30', 'border-magenta', 'text-white', 'shadow-[0_0_30px_#B3589A]', 'scale-110');
                }} else {{
                    circle.classList.remove('bg-starlight/30', 'border-starlight', 'text-white', 'shadow-[0_0_30px_#4B7BF5]', 'scale-110');
                }}
                circle.classList.add('bg-black/30', 'border-white/20', 'text-white/30');
                text.classList.remove('text-white');
                text.classList.add('text-white/30');
                text.style.textShadow = 'none';
            }}
        }});
    }};

    window.addEventListener('resize', buildSVGPath);

    const onScroll = () => {{
        if (!ticking) {{
            window.requestAnimationFrame(() => {{
                updatePipeline();
                ticking = false;
            }});
            ticking = true;
        }}
        
        // Nav logo
        const logo = document.getElementById('nav-logo');
        if (logo) {{
            if (window.scrollY > window.innerHeight * 0.7) {{
                logo.classList.remove('opacity-0');
            }} else {{
                logo.classList.add('opacity-0');
            }}
        }}
    }};

    document.addEventListener('scroll', onScroll);
    buildSVGPath();

    return () => {{
      window.removeEventListener('resize', buildSVGPath);
      document.removeEventListener('scroll', onScroll);
    }};
  }}, []);

  return (
    <div className="bg-hero min-h-screen flex flex-col font-sans antialiased text-[#E2E8F0]">
        {landing_jsx.replace('id="pipeline-container"', 'id="pipeline-container" ref={containerRef}').replace('id="svg-progress"', 'id="svg-progress" ref={pathRef}').replace('id="svg-base"', 'id="svg-base" ref={basePathRef}').replace('<button className="bg-starlight text-white font-bold py-5 px-12 rounded-full btn-glow tracking-widest uppercase text-lg mt-4">\n            Access ML Dashboard\n        </button>', '<Link to="/dashboard"><button className="bg-starlight text-white font-bold py-5 px-12 rounded-full btn-glow tracking-widest uppercase text-lg mt-4">\n            Access ML Dashboard\n        </button></Link>').replace('<button className="bg-starlight text-white font-bold py-4 px-8 rounded-full btn-glow tracking-wide uppercase text-sm">\n                    Launch Pipeline\n                </button>', '<Link to="/dashboard"><button className="bg-starlight text-white font-bold py-4 px-8 rounded-full btn-glow tracking-wide uppercase text-sm">\n                    Launch Pipeline\n                </button></Link>')}
    </div>
  );
}};

export default Landing;
"""

with open('frontend/src/pages/Landing.tsx', 'w') as f:
    f.write(landing_component)

with open('frontend/src/pages/Landing.css', 'w') as f:
    f.write(landing_styles)
