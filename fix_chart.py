import re

with open("frontend/src/pages/Dashboard.tsx", "r") as f:
    code = f.read()

# Replace the double destroy logic with a single clean setup
new_chart_init = """
    if (!chartRef.current) return;
    if (chartInstance.current) {
        chartInstance.current.destroy();
        chartInstance.current = null;
    }
    const ctx = chartRef.current.getContext('2d');
    if (!ctx) return;

    chartInstance.current = new Chart(ctx, {
"""

# We need to regex out the messy block between `if (!chartRef.current) return;` and `chartInstance.current = new Chart`
code = re.sub(
    r"if \(\!chartRef\.current\) return;.*?chartInstance\.current = new Chart\(ctx, \{",
    new_chart_init.strip(),
    code,
    flags=re.DOTALL
)

with open("frontend/src/pages/Dashboard.tsx", "w") as f:
    f.write(code)

