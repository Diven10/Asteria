import os
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

from app.contracts.models import ClassifiedCandidate
from app.planet_properties.estimator import PlanetProperties
from app.validation.rules import ValidationResult
from app.explainability.shap_wrapper import ShapExplanation
from app.ranking.ops import OPSResult

def generate_scientific_report(
    candidate: ClassifiedCandidate,
    props: PlanetProperties,
    ops_result: OPSResult,
    validation_results: ValidationResult,
    shap_explain: ShapExplanation,
    output_dir: str = "/tmp",
    filename: str | None = None
) -> str:
    """
    Generates a deterministic scientific PDF report for a candidate, including all
    parameters, model versions, validation, SHAP, and disclaimers.
    """
    os.makedirs(output_dir, exist_ok=True)
    if filename is None:
        filename = f"ASTERIA_Report_{candidate.candidate.target_id.replace(' ', '_')}.pdf"
    filepath = os.path.join(output_dir, filename)

    doc = SimpleDocTemplate(filepath, pagesize=letter)
    styles = getSampleStyleSheet()

    # Custom styles
    title_style = styles['Heading1']
    subtitle_style = styles['Heading2']
    normal_style = styles['Normal']
    bold_style = ParagraphStyle(name='NormalBold', parent=styles['Normal'], fontName='Helvetica-Bold')
    italic_style = ParagraphStyle(name='NormalItalic', parent=styles['Normal'], fontName='Helvetica-Oblique')

    story = []

    # 1. Title
    story.append(Paragraph(f"ASTERIA Scientific Report", title_style))
    story.append(Paragraph(f"Target: {candidate.candidate.target_id}", subtitle_style))
    story.append(Spacer(1, 12))

    # 2. Mission & Provenance
    story.append(Paragraph("Data Provenance & Mission", subtitle_style))
    story.append(Paragraph(f"<b>Mission:</b> {candidate.candidate.mission.value}", normal_style))
    sector = candidate.candidate.metadata.get("sector")
    if sector is not None:
        story.append(Paragraph(f"<b>Sector/Quarter:</b> {sector}", normal_style))
    story.append(Paragraph(f"<b>Light Curve ID:</b> {candidate.candidate.light_curve_id}", normal_style))
    story.append(Spacer(1, 12))

    # 3. Stellar Parameters
    story.append(Paragraph("Stellar Parameters", subtitle_style))
    teff = f"{candidate.candidate.stellar_teff_k:.1f} K" if candidate.candidate.stellar_teff_k else "Unavailable"
    rad = f"{candidate.candidate.stellar_radius_solar:.3f} R_solar" if candidate.candidate.stellar_radius_solar else "Unavailable"
    mass = f"{candidate.candidate.stellar_mass_solar:.3f} M_solar" if candidate.candidate.stellar_mass_solar else "Unavailable"
    story.append(Paragraph(f"<b>Effective Temperature (Teff):</b> {teff}", normal_style))
    story.append(Paragraph(f"<b>Stellar Radius:</b> {rad}", normal_style))
    story.append(Paragraph(f"<b>Stellar Mass:</b> {mass}", normal_style))
    story.append(Spacer(1, 12))

    # 4. BLS Transit Parameters
    story.append(Paragraph("BLS Detection Parameters", subtitle_style))
    snr = f"{candidate.candidate.snr:.2f}" if candidate.candidate.snr else "Unavailable"
    bls_power = f"{candidate.candidate.bls_power:.2f}" if candidate.candidate.bls_power else "Unavailable"
    duration = f"{candidate.candidate.duration_hours:.2f} hours" if candidate.candidate.duration_hours else "Unavailable"
    story.append(Paragraph(f"<b>Period:</b> {candidate.candidate.period_days:.5f} days", normal_style))
    story.append(Paragraph(f"<b>Epoch:</b> {candidate.candidate.epoch_btjd:.5f} BTJD", normal_style))
    story.append(Paragraph(f"<b>Duration:</b> {duration}", normal_style))
    story.append(Paragraph(f"<b>Depth:</b> {candidate.candidate.depth:.6f}", normal_style))
    story.append(Paragraph(f"<b>Transit Count:</b> {candidate.candidate.transit_count}", normal_style))
    story.append(Paragraph(f"<b>BLS Power:</b> {bls_power}", normal_style))
    story.append(Paragraph(f"<b>Signal-to-Noise Ratio (SNR):</b> {snr}", normal_style))
    story.append(Spacer(1, 12))

    # 5. Planetary Properties
    story.append(Paragraph("Planetary Property Estimation", subtitle_style))
    p_rad = f"{props.radius_earth:.2f} R_earth" if props.radius_earth else "Unavailable"
    sma = f"{props.semi_major_axis_au:.4f} AU" if props.semi_major_axis_au else "Unavailable"
    eq_temp = f"{props.equilibrium_temperature_k:.1f} K" if props.equilibrium_temperature_k else "Unavailable"
    flux = f"{props.insolation_flux_earth:.2f} S_earth" if props.insolation_flux_earth else "Unavailable"

    story.append(Paragraph(f"<b>Radius:</b> {p_rad}", normal_style))
    story.append(Paragraph(f"<b>Semi-Major Axis:</b> {sma}", normal_style))
    story.append(Paragraph(f"<b>Equilibrium Temperature:</b> {eq_temp}", normal_style))
    story.append(Paragraph(f"<b>Insolation Flux:</b> {flux}", normal_style))
    story.append(Paragraph(f"<b>Size Classification:</b> {props.size_class}", normal_style))
    story.append(Paragraph(f"<b>Habitable Zone Proxy:</b> {'Yes' if props.habitable_zone_proxy else 'No'}", normal_style))
    story.append(Spacer(1, 12))

    # 6. ML Classification
    story.append(Paragraph("Machine Learning Classification", subtitle_style))
    story.append(Paragraph(f"<b>Model Name:</b> {candidate.model_name}", normal_style))
    story.append(Paragraph(f"<b>Model Version:</b> {candidate.model_version}", normal_style))
    story.append(Paragraph(f"<b>Feature Schema Version:</b> {candidate.feature_schema_version}", normal_style))
    story.append(Paragraph(f"<b>Raw Planet Probability:</b> {candidate.planet_probability:.4f}", normal_style))
    story.append(Spacer(1, 12))

    # 7. False Positive Validation
    story.append(Paragraph("False-Positive Validation", subtitle_style))
    story.append(Paragraph(f"<b>Astrophysically Valid:</b> {'Yes' if validation_results.is_valid_astrophysically else 'No'}", bold_style))
    story.append(Paragraph(f"<b>Fused Confidence:</b> {validation_results.fused_probability:.4f}", normal_style))

    val_data = [["Rule", "Passed", "Missing Data", "Reason"]]
    for rule in validation_results.rules:
        val_data.append([
            rule.rule_name,
            "Yes" if rule.passed else "No",
            "Yes" if rule.is_missing_data else "No",
            rule.reason
        ])

    if len(val_data) > 1:
        t = Table(val_data, colWidths=[100, 50, 70, 250])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.grey),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0,0), (-1,0), 6),
            ('BACKGROUND', (0,1), (-1,-1), colors.beige),
            ('GRID', (0,0), (-1,-1), 1, colors.black),
            ('FONTSIZE', (0,0), (-1,-1), 8)
        ]))
        story.append(Spacer(1, 6))
        story.append(t)
    story.append(Spacer(1, 12))

    # 8. OPS Score
    story.append(Paragraph("Observation Priority Score (OPS)", subtitle_style))
    story.append(Paragraph(f"<b>Total Score:</b> {ops_result.total_score:.1f} / 100", bold_style))
    story.append(Paragraph(f"- Confidence Score: {ops_result.breakdown.confidence_score:.1f}", normal_style))
    story.append(Paragraph(f"- SNR Score: {ops_result.breakdown.snr_score:.1f}", normal_style))
    story.append(Paragraph(f"- Radius Score: {ops_result.breakdown.radius_score:.1f}", normal_style))
    story.append(Paragraph(f"- Host-Star Score: {ops_result.breakdown.host_star_score:.1f}", normal_style))
    if ops_result.breakdown.fp_penalty_applied:
        story.append(Paragraph(f"- <b>Penalty Applied:</b> False-Positive Risk", normal_style))
    story.append(Spacer(1, 12))

    # 9. Explainability (SHAP)
    story.append(Paragraph("Explainability (SHAP)", subtitle_style))
    if not shap_explain.is_valid:
        story.append(Paragraph(f"<b>SHAP Unavailable:</b> {shap_explain.error_message}", normal_style))
    else:
        base_val_str = f"{shap_explain.base_value:.4f}" if shap_explain.base_value is not None else "N/A"
        pred_val_str = f"{shap_explain.predicted_value:.4f}" if shap_explain.predicted_value is not None else "N/A"
        story.append(Paragraph(f"<b>Base Value:</b> {base_val_str}", normal_style))
        story.append(Paragraph(f"<b>Predicted Value:</b> {pred_val_str}", normal_style))
        story.append(Spacer(1, 6))

        shap_data = [["Feature", "Contribution"]]
        # Sort by absolute contribution magnitude
        sorted_feats = sorted(
            shap_explain.feature_contributions.items(),
            key=lambda x: abs(x[1]),
            reverse=True
        )
        for k, v in sorted_feats[:10]: # Top 10 features
            shap_data.append([k, f"{v:.4f}"])

        t2 = Table(shap_data, colWidths=[200, 100])
        t2.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.grey),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('GRID', (0,0), (-1,-1), 1, colors.black),
            ('FONTSIZE', (0,0), (-1,-1), 8)
        ]))
        story.append(t2)

    story.append(Spacer(1, 20))

    # 10. Disclaimer
    story.append(Paragraph("Scientific Disclaimer", subtitle_style))
    disclaimer = (
        "This report is generated by the ASTERIA automated pipeline. "
        "Detection and property estimations are based on heuristic checks, "
        "uncalibrated XGBoost classification, and engineering assumptions. "
        "Missing catalog values were gracefully handled without fabrication. "
        "Model predictions should be treated as synthetic readiness tests "
        "unless explicitly trained on validated astronomical data."
    )
    story.append(Paragraph(disclaimer, italic_style))

    doc.build(story)
    return filepath
