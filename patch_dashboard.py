import re

with open("templates/dashboard.html", "r") as f:
    html = f.read()

# Add IDs to the HTML elements so we can update them via JS
html = html.replace('11.4 R<sub class="text-xs">⊕</sub> (Jupiter-like)', '<span id="val-radius">11.4 R</span><sub class="text-xs">⊕</sub>')
html = html.replace('>4.12 Days<', ' id="val-period">>4.12 Days<')
html = html.replace('>12,400 ppm<', ' id="val-depth">>12,400 ppm<')
html = html.replace('>1,240 K<', ' id="val-temp">>1,240 K<')
html = html.replace('>94.2%<', ' id="val-confidence">>94.2%<')
html = html.replace('>CONFIRMED CANDIDATE<', ' id="val-verdict">>CONFIRMED CANDIDATE<')
html = html.replace('SYSTEM NOTE: Running ASTERIA-Untrained-Estimator', 'SYSTEM NOTE: <span id="val-model">Running ASTERIA-Untrained-Estimator</span>')

js_addition = """
        // --- REAL API INTEGRATION ---
        async function fetchRealData() {
            try {
                // 1. Ingest
                const res = await fetch("/dashboard/ingest", {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({target: "TIC 261136679", mission: "TESS", sector_or_quarter: 1})
                });
                if(!res.ok) throw new Error("Ingest failed");
                const lc = await res.json();

                // 2. Preprocess
                const res2 = await fetch("/dashboard/preprocess", {
                    method: "POST", headers: {"Content-Type": "application/json"},
                    body: JSON.stringify(lc)
                });
                const preprocessed = await res2.json();

                // 3. Detect
                const res3 = await fetch("/dashboard/detect", {
                    method: "POST", headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({light_curve: preprocessed, min_period: 1.0, max_period: 10.0})
                });
                const candidates = await res3.json();

                if(candidates && candidates.length > 0) {
                    const best = candidates[0];

                    // 4. Classify
                    const res4 = await fetch("/dashboard/classify", {
                        method: "POST", headers: {"Content-Type": "application/json"},
                        body: JSON.stringify(best)
                    });
                    const classified = await res4.json();

                    // Update UI
                    document.getElementById('val-period').innerText = best.period_days.toFixed(2) + " Days";
                    document.getElementById('val-depth').innerText = (best.depth * 1000000).toFixed(0) + " ppm";
                    document.getElementById('val-confidence').innerText = (classified.planet_probability * 100).toFixed(1) + "%";
                    document.getElementById('val-verdict').innerText = classified.prediction.replace('_', ' ').toUpperCase();
                    
                    let modelNote = "Running " + classified.model_name;
                    if(classified.metadata && classified.metadata.is_synthetic_prediction) {
                        modelNote += " (SYNTHETIC)";
                    } else {
                        modelNote += " (REAL)";
                    }
                    document.getElementById('val-model').innerText = modelNote;

                    // Downsample curve for Chart.js
                    const filteredTime = preprocessed.time.filter((_, i) => i % 10 === 0);
                    const filteredFlux = preprocessed.flux.filter((_, i) => i % 10 === 0);

                    window.asteriaChart.data.labels = filteredTime;
                    window.asteriaChart.data.datasets[0].data = filteredFlux;
                    window.asteriaChart.update();
                }

            } catch(e) {
                console.warn("Falling back to synthetic data due to error: ", e);
            }
        }
"""

# Find the end of Chart.js initialization and append fetch logic
chart_init_end = "});"
html = html.replace('});\n\n    </script>', '});\n\n        window.asteriaChart = Chart.instances[Object.keys(Chart.instances)[0]];' + js_addition + '\n        fetchRealData();\n    </script>')

# In Chart.js initialization, we need to make sure we assign it to a variable or let Chart.instances be used.
html = html.replace('new Chart(ctx, {', 'window.asteriaChart = new Chart(ctx, {')

with open("templates/dashboard.html", "w") as f:
    f.write(html)

