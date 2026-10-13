import sys
import re

with open('asteria_landing.html', 'r') as f:
    content = f.read()

# 1. Navbar Logo
content = content.replace(
    '<div class="font-display text-2xl font-bold tracking-widest text-white">ASTERIA</div>',
    '<div id="nav-logo" class="font-display text-2xl font-bold tracking-widest text-white opacity-0 transition-opacity duration-500">ASTERIA</div>'
)

# 2. Add scroll listener for Navbar Logo
nav_script = """
    <script>
        document.addEventListener('scroll', () => {
            const logo = document.getElementById('nav-logo');
            if (logo) {
                if (window.scrollY > window.innerHeight * 0.7) {
                    logo.classList.remove('opacity-0');
                } else {
                    logo.classList.add('opacity-0');
                }
            }
        });
    </script>
</body>
"""
content = content.replace('</body>', nav_script)

# 3. Min-h-screen for all sections
content = content.replace(
    '<section class="py-24 px-6 md:px-20 bg-space relative">',
    '<section class="min-h-screen flex flex-col justify-center py-24 px-6 md:px-20 bg-space relative">'
)

content = content.replace(
    '<section class="py-24 px-6 md:px-20 bg-space border-t border-white/5">',
    '<section class="min-h-screen flex flex-col justify-center py-24 px-6 md:px-20 bg-space border-t border-white/5">'
)

content = content.replace(
    '<section class="py-32 px-6 text-center">',
    '<section class="min-h-screen flex flex-col justify-center items-center py-32 px-6 text-center bg-space border-t border-white/5" style="background-image: linear-gradient(to bottom, rgba(10,11,20,1) 0%, rgba(10,11,20,0.5) 50%, rgba(10,11,20,1) 100%), url(\'https://www.nasa.gov/wp-content/uploads/2026/09/m101-lg.jpg\'); background-size: cover; background-position: center; background-attachment: fixed;">'
)

# 4. Pipeline Line Thickness
content = content.replace(
    '<path id="svg-base" stroke="rgba(255,255,255,0.1)" stroke-width="2"',
    '<path id="svg-base" stroke="rgba(255,255,255,0.1)" stroke-width="6"'
)

content = content.replace(
    '<path id="svg-progress" stroke="url(#line-gradient)" stroke-width="6" fill="none" stroke-linecap="round" style="filter: drop-shadow(0px 0px 8px rgba(75,123,245,0.6)); transition: none;" />',
    '<path id="svg-progress" stroke="url(#line-gradient)" stroke-width="14" fill="none" stroke-linecap="round" style="filter: drop-shadow(0px 0px 15px rgba(75,123,245,0.8)); transition: none;" />'
)

# 5. Pipeline Circle transparency so the thick line visibly passes THROUGH it
content = content.replace('bg-space border-2 border-white/20', 'bg-black/40 backdrop-blur-sm border-2 border-white/20')

# Update the JS class toggles for the circles
old_js = """                        if (isMagenta) {
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
                    }"""

new_js = """                        if (isMagenta) {
                            circle.classList.add('bg-magenta/30', 'border-magenta', 'text-white', 'shadow-[0_0_30px_#B3589A]', 'scale-110');
                            circle.classList.remove('bg-black/40', 'border-white/20', 'text-white/30');
                        } else {
                            circle.classList.add('bg-starlight/30', 'border-starlight', 'text-white', 'shadow-[0_0_30px_#4B7BF5]', 'scale-110');
                            circle.classList.remove('bg-black/40', 'border-white/20', 'text-white/30');
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
                        circle.classList.add('bg-black/40', 'border-white/20', 'text-white/30');
                        text.classList.remove('text-white');
                        text.classList.add('text-white/30');
                        text.style.textShadow = 'none';
                    }"""

content = content.replace(old_js, new_js)

with open('asteria_landing.html', 'w') as f:
    f.write(content)

