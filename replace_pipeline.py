import sys

with open('asteria_landing.html', 'r') as f:
    lines = f.readlines()

new_lines = """    <!-- SECTION 4: PIPELINE -->
    <!-- We make the container 400vh to create a long scrolling track -->
    <section id="pipeline-container" class="relative h-[400vh] bg-galaxy border-t border-b border-white/5">
        <div class="sticky top-0 h-screen flex flex-col justify-center px-4 md:px-20 w-full overflow-hidden">
            <div class="max-w-5xl mx-auto text-center w-full relative">
                <h2 class="font-display text-4xl md:text-5xl text-white font-bold mb-16 drop-shadow-lg">The 6-Step Pipeline</h2>
                
                <!-- Zig-Zag Grid Container -->
                <div class="relative w-full h-[50vh] md:h-[60vh] mx-auto">
                    <!-- SVG Background Line -->
                    <svg class="absolute inset-0 w-full h-full -z-10" viewBox="0 0 100 100" preserveAspectRatio="none">
                        <defs>
                            <linearGradient id="line-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
                                <stop offset="0%" stop-color="#4B7BF5" />
                                <stop offset="100%" stop-color="#B3589A" />
                            </linearGradient>
                            <filter id="glow">
                                <feGaussianBlur stdDeviation="2" result="coloredBlur"/>
                                <feMerge>
                                    <feMergeNode in="coloredBlur"/>
                                    <feMergeNode in="SourceGraphic"/>
                                </feMerge>
                            </filter>
                        </defs>
                        <!-- Base track (dim) -->
                        <path d="M 10 10 L 90 10 C 105 10, 105 50, 90 50 L 10 50 C -5 50, -5 90, 10 90 L 90 90" stroke="rgba(255,255,255,0.1)" stroke-width="0.5" fill="none" vector-effect="non-scaling-stroke" />
                        <!-- Animated progress line -->
                        <path id="svg-progress" d="M 10 10 L 90 10 C 105 10, 105 50, 90 50 L 10 50 C -5 50, -5 90, 10 90 L 90 90" stroke="url(#line-gradient)" stroke-width="4" fill="none" stroke-linecap="round" vector-effect="non-scaling-stroke" filter="url(#glow)" />
                    </svg>

                    <!-- Step 1: Top Left -->
                    <div class="pipeline-step absolute left-[10%] top-[10%] transform -translate-x-1/2 -translate-y-1/2 flex flex-col items-center">
                        <div class="step-circle w-12 h-12 md:w-16 md:h-16 rounded-full bg-space border-2 border-white/20 flex items-center justify-center text-white/30 font-bold transition-all duration-500 ease-out z-10 text-lg md:text-xl">1</div>
                        <span class="step-text text-white/30 font-semibold transition-all duration-500 ease-out tracking-wide mt-2 md:mt-4 absolute top-full md:text-lg">Ingest</span>
                    </div>

                    <!-- Step 2: Top Right -->
                    <div class="pipeline-step absolute left-[90%] top-[10%] transform -translate-x-1/2 -translate-y-1/2 flex flex-col items-center">
                        <div class="step-circle w-12 h-12 md:w-16 md:h-16 rounded-full bg-space border-2 border-white/20 flex items-center justify-center text-white/30 font-bold transition-all duration-500 ease-out z-10 text-lg md:text-xl">2</div>
                        <span class="step-text text-white/30 font-semibold transition-all duration-500 ease-out tracking-wide mt-2 md:mt-4 absolute top-full md:text-lg">Preprocess</span>
                    </div>

                    <!-- Step 3: Mid Right -->
                    <div class="pipeline-step absolute left-[90%] top-[50%] transform -translate-x-1/2 -translate-y-1/2 flex flex-col items-center">
                        <div class="step-circle w-12 h-12 md:w-16 md:h-16 rounded-full bg-space border-2 border-white/20 flex items-center justify-center text-white/30 font-bold transition-all duration-500 ease-out z-10 text-lg md:text-xl">3</div>
                        <span class="step-text text-white/30 font-semibold transition-all duration-500 ease-out tracking-wide mt-2 md:mt-4 absolute top-full md:text-lg">Detect</span>
                    </div>

                    <!-- Step 4: Mid Left -->
                    <div class="pipeline-step absolute left-[10%] top-[50%] transform -translate-x-1/2 -translate-y-1/2 flex flex-col items-center">
                        <div class="step-circle w-12 h-12 md:w-16 md:h-16 rounded-full bg-space border-2 border-white/20 flex items-center justify-center text-white/30 font-bold transition-all duration-500 ease-out z-10 text-lg md:text-xl">4</div>
                        <span class="step-text text-white/30 font-semibold transition-all duration-500 ease-out tracking-wide mt-2 md:mt-4 absolute top-full md:text-lg">Validate</span>
                    </div>

                    <!-- Step 5: Bottom Left -->
                    <div class="pipeline-step absolute left-[10%] top-[90%] transform -translate-x-1/2 -translate-y-1/2 flex flex-col items-center">
                        <div class="step-circle w-12 h-12 md:w-16 md:h-16 rounded-full bg-space border-2 border-white/20 flex items-center justify-center text-white/30 font-bold transition-all duration-500 ease-out z-10 text-lg md:text-xl">5</div>
                        <span class="step-text text-white/30 font-semibold transition-all duration-500 ease-out tracking-wide mt-2 md:mt-4 absolute top-full md:text-lg">Score</span>
                    </div>

                    <!-- Step 6: Bottom Right -->
                    <div class="pipeline-step absolute left-[90%] top-[90%] transform -translate-x-1/2 -translate-y-1/2 flex flex-col items-center">
                        <div class="step-circle w-12 h-12 md:w-16 md:h-16 rounded-full bg-space border-2 border-white/20 flex items-center justify-center text-white/30 font-bold transition-all duration-500 ease-out z-10 text-lg md:text-xl">6</div>
                        <span class="step-text text-white/30 font-semibold transition-all duration-500 ease-out tracking-wide mt-2 md:mt-4 absolute top-full md:text-lg">Report</span>
                    </div>
                </div>
            </div>
        </div>
    </section>

    <!-- Scroll Animation Script for SVG Pipeline -->
    <script>
        document.addEventListener("DOMContentLoaded", () => {
            const container = document.getElementById('pipeline-container');
            const path = document.getElementById('svg-progress');
            const steps = document.querySelectorAll('.pipeline-step');
            
            if(!container || !path || !steps.length) return;

            // Initialize SVG Path length for drawing animation
            const pathLength = path.getTotalLength();
            path.style.strokeDasharray = pathLength;
            path.style.strokeDashoffset = pathLength;

            document.addEventListener('scroll', () => {
                const rect = container.getBoundingClientRect();
                const windowHeight = window.innerHeight;
                
                let progress = 0;
                if (rect.top <= 0) {
                    const scrolled = -rect.top;
                    const totalScrollable = rect.height - windowHeight;
                    progress = Math.min(1, Math.max(0, scrolled / totalScrollable)); // 0.0 to 1.0
                }
                
                // Draw the SVG line smoothly
                path.style.strokeDashoffset = pathLength * (1 - progress);
                
                // Thresholds where the line naturally intersects each circle
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
            });
            
            window.dispatchEvent(new Event('scroll'));
        });
    </script>
"""

# Replace lines 188 to 288 (0-indexed 187 to 288)
out_lines = lines[:187] + [new_lines] + lines[288:]

with open('asteria_landing.html', 'w') as f:
    f.writelines(out_lines)
