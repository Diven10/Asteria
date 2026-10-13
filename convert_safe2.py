import re

with open("asteria_landing.html", "r") as f:
    html = f.read()

# Extract from <body> to </body>
body_match = re.search(r'<body[^>]*>(.*?)</body>', html, re.DOTALL)
if body_match:
    body_content = body_match.group(1)
else:
    body_content = html

# Remove all script tags
body_content = re.sub(r'<script\b[^>]*>.*?</script>', '', body_content, flags=re.DOTALL)

# Escape quotes and backticks
body_content = body_content.replace('`', '\\`').replace('$', '\\$')

# Change <button> to Link around button for routing
body_content = body_content.replace(
    '<button class="bg-starlight text-white font-bold py-5 px-12 rounded-full btn-glow tracking-widest uppercase text-lg mt-4">',
    '<a href="/dashboard"><button class="bg-starlight text-white font-bold py-5 px-12 rounded-full btn-glow tracking-widest uppercase text-lg mt-4">'
).replace('</button>\n    </section>', '</button></a>\n    </section>')
body_content = body_content.replace(
    '<button class="bg-starlight text-white font-bold py-4 px-8 rounded-full btn-glow tracking-wide uppercase text-sm">\n                    Launch Pipeline',
    '<a href="/dashboard"><button class="bg-starlight text-white font-bold py-4 px-8 rounded-full btn-glow tracking-wide uppercase text-sm">\n                    Launch Pipeline'
).replace('Launch Pipeline\n                </button>', 'Launch Pipeline\n                </button></a>')

# Add smooth CSS transition inline to the animated path to fix lag!
body_content = body_content.replace(
    'id="svg-progress" class="text-starlight drop-shadow-[0_0_15px_rgba(75,123,245,0.8)]"',
    'id="svg-progress" class="text-starlight drop-shadow-[0_0_15px_rgba(75,123,245,0.8)]" style="transition: stroke-dashoffset 0.1s linear;"'
)


tsx_code = f"""
import React, {{ useEffect, useRef }} from 'react';
import './Landing.css';

const Landing = () => {{
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {{
    const container = document.getElementById('pipeline-container');
    const path = document.getElementById('svg-progress') as any;
    const basePath = document.getElementById('svg-base') as any;
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
                (text as any).style.textShadow = '0 0 10px rgba(255,255,255,0.5)';
            }} else {{
                if (isMagenta) {{
                    circle.classList.remove('bg-magenta/30', 'border-magenta', 'text-white', 'shadow-[0_0_30px_#B3589A]', 'scale-110');
                }} else {{
                    circle.classList.remove('bg-starlight/30', 'border-starlight', 'text-white', 'shadow-[0_0_30px_#4B7BF5]', 'scale-110');
                }}
                circle.classList.add('bg-black/30', 'border-white/20', 'text-white/30');
                text.classList.remove('text-white');
                text.classList.add('text-white/30');
                (text as any).style.textShadow = 'none';
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
        
        const logo = document.getElementById('nav-logo');
        if (logo) {{
            if (window.scrollY > window.innerHeight * 0.7) {{
                logo.classList.remove('opacity-0');
            }} else {{
                logo.classList.add('opacity-0');
            }}
        }}
    }};

    document.addEventListener('scroll', onScroll, {{ passive: true }});
    
    setTimeout(() => {{
        buildSVGPath();
    }}, 100);

    return () => {{
      window.removeEventListener('resize', buildSVGPath);
      document.removeEventListener('scroll', onScroll);
    }};
  }}, []);

  return (
    <div 
        ref={{containerRef}} 
        className="bg-hero min-h-screen flex flex-col font-sans antialiased text-[#E2E8F0]"
        dangerouslySetInnerHTML={{{{ __html: `{body_content}` }}}}
    />
  );
}};

export default Landing;
"""

with open("frontend/src/pages/Landing.tsx", "w") as f:
    f.write(tsx_code)
