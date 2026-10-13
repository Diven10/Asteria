import sys
import re

with open('asteria_landing.html', 'r') as f:
    content = f.read()

# 1. Nav Logo - ensure it has the correct ID and opacity toggle
nav_original = '<div class="font-display font-bold text-2xl text-white tracking-widest glow-text">ASTERIA</div>'
nav_new = '<div id="nav-logo" class="font-display font-bold text-2xl text-white tracking-widest glow-text opacity-0 transition-opacity duration-500">ASTERIA</div>'
content = content.replace(nav_original, nav_new)

# 2. Sections to 100% height (min-h-screen flex flex-col justify-center)
content = content.replace(
    '<section id="mission" class="py-24 px-6 md:px-20 bg-space/80">',
    '<section id="mission" class="min-h-screen flex flex-col justify-center py-24 px-6 md:px-20 bg-space/80">'
)

content = content.replace(
    '<section id="architecture" class="py-24 px-6 md:px-20">',
    '<section id="architecture" class="min-h-screen flex flex-col justify-center py-24 px-6 md:px-20 bg-space/95 border-t border-white/5">' # Added a background so hero doesn't bleed messily
)

# Revert CTA to just be fullscreen without the extra galaxy background I previously added
cta_regex = r'<section class="min-h-screen flex flex-col justify-center items-center py-32 px-6 text-center[^>]*>'
cta_new = '<section class="min-h-screen flex flex-col justify-center items-center py-32 px-6 text-center bg-space">'
content = re.sub(cta_regex, cta_new, content)

# 3. Pipeline Line Thickness and Circle Pass-through
# Ensure thickness is 14
content = content.replace('stroke-width="6"', 'stroke-width="14"')

# Ensure the circles have transparent backgrounds so the thick line visibly passes THROUGH them
# First, remove solid bg-space from HTML
content = content.replace('bg-space border-2 border-white/20', 'bg-black/30 backdrop-blur-md border-2 border-white/20')
# Second, in JS, replace bg-space with bg-black/30 so it doesn't revert to solid
content = content.replace('circle.classList.add(\'bg-space\',', 'circle.classList.add(\'bg-black/30\',')
content = content.replace('circle.classList.remove(\'bg-space\',', 'circle.classList.remove(\'bg-black/30\',')

with open('asteria_landing.html', 'w') as f:
    f.write(content)
