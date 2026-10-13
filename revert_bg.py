import sys

with open('asteria_landing.html', 'r') as f:
    content = f.read()

# Remove bg-space/95 from Architecture
content = content.replace(
    '<section id="architecture" class="min-h-screen flex flex-col justify-center py-24 px-6 md:px-20 bg-space/95 border-t border-white/5">',
    '<section id="architecture" class="min-h-screen flex flex-col justify-center py-24 px-6 md:px-20 border-t border-white/5">'
)

# Remove bg-space from CTA
content = content.replace(
    '<section class="min-h-screen flex flex-col justify-center items-center py-32 px-6 text-center bg-space">',
    '<section class="min-h-screen flex flex-col justify-center items-center py-32 px-6 text-center">'
)

with open('asteria_landing.html', 'w') as f:
    f.write(content)
