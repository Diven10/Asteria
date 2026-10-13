import sys

with open("app/api/dashboard.py", "a") as f:
    f.write("""
from fastapi.responses import StreamingResponse

@router.post("/export/lightcurve/csv")
def export_lightcurve_csv(lc: LightCurve):
    \"\"\"Exports a LightCurve to a CSV file.\"\"\"
    try:
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        if lc.flux_error is not None:
            writer.writerow(["time", "flux", "flux_error"])
            for t, f, e in zip(lc.time, lc.flux, lc.flux_error):
                writer.writerow([t, f, e])
        else:
            writer.writerow(["time", "flux"])
            for t, f in zip(lc.time, lc.flux):
                writer.writerow([t, f])
                
        output.seek(0)
        
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=lightcurve_{lc.target_id}.csv"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
""")
