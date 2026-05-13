"""
VestaCode Design Report Generator
===================================
Generates a print-ready HTML "Design Report" for client presentations.

Usage:
    GET /project/{project_id}/report → HTML page optimised for print.
"""

from backend.core.bim_state import BIMProjectState
from datetime import datetime, timezone


def generate_report_html(project: BIMProjectState) -> str:
    """Build a self-contained HTML design report from a BIMProjectState."""

    elements = project.elements or []
    furniture = [e for e in elements if e.type == "furniture"]
    walls = [e for e in elements if e.type == "wall"]
    doors = [e for e in elements if e.type == "door"]
    windows = [e for e in elements if e.type == "window"]

    # Compliance
    compliance_log = None
    spatial_log = None
    for log in reversed(project.compliance_logs or []):
        if log.get("agent") == "spatial_engine" and not spatial_log:
            spatial_log = log
        elif "is_compliant" in log and not compliance_log:
            compliance_log = log

    flow_score = spatial_log.get("flow_score", "—") if spatial_log else "—"
    is_compliant = compliance_log.get("is_compliant", None) if compliance_log else None
    compliance_summary = compliance_log.get("summary", "") if compliance_log else "Not audited yet."
    compliance_class = "pass" if is_compliant else ("fail" if is_compliant is False else "pending")

    # Style
    style = project.style_profile or {}
    theme = style.get("theme", "Custom")
    wall_color = style.get("wall_color") or style.get("palette", {}).get("wall_color", "#F5F5F0")
    floor_mat = style.get("floor_material") or style.get("palette", {}).get("floor_material", "—")
    lighting = style.get("lighting_mood") or style.get("palette", {}).get("lighting_mood", "—")

    # Furniture table rows
    furniture_rows = ""
    total_cost = 0.0
    for f in furniture:
        meta = f.metadata or {}
        name = meta.get("item_type", "Item")
        sourced = meta.get("sourced_product", {})
        vendor = sourced.get("vendor", "—")
        price = sourced.get("price", meta.get("cost", 0))
        url = sourced.get("product_url", "#")
        stock = sourced.get("stock_status", "—")
        total_cost += float(price or 0)
        furniture_rows += f"""
        <tr>
            <td>{name}</td>
            <td>{vendor}</td>
            <td>${price:,.0f}</td>
            <td>{stock}</td>
            <td><a href="{url}" target="_blank" rel="noopener">View →</a></td>
        </tr>"""

    now = datetime.now(timezone.utc).strftime("%B %d, %Y")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>VestaCode — Design Report: {project.name}</title>
<meta name="viewport" content="width=device-width, initial-scale=1" />
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap" rel="stylesheet" />
<style>
  :root {{
    --bg: #0e0e12;
    --surface: #16161e;
    --border: rgba(255,255,255,0.08);
    --text: #f0eef5;
    --muted: rgba(255,255,255,0.45);
    --accent: #6d61ff;
    --success: #34d399;
    --warn: #fbbf24;
    --danger: #f87171;
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: 'Inter', sans-serif; background: var(--bg); color: var(--text); padding: 40px; line-height: 1.6; }}

  .report {{ max-width: 900px; margin: 0 auto; }}

  /* Header */
  .report-header {{ display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 48px; border-bottom: 1px solid var(--border); padding-bottom: 32px; }}
  .report-header h1 {{ font-size: 2rem; font-weight: 800; letter-spacing: -0.02em; }}
  .report-header .meta {{ color: var(--muted); font-size: 0.85rem; text-align: right; }}
  .report-header .meta strong {{ color: var(--accent); }}
  .logo {{ display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }}
  .logo-mark {{ width: 28px; height: 28px; background: var(--accent); border-radius: 6px; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 14px; }}
  .logo-text {{ font-weight: 800; font-size: 1.1rem; letter-spacing: 0.08em; }}
  .logo-text span {{ color: var(--accent); }}

  /* Summary */
  .summary-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 48px; }}
  .summary-card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 20px; text-align: center; }}
  .summary-card .val {{ font-size: 1.8rem; font-weight: 800; }}
  .summary-card .label {{ font-size: 0.75rem; color: var(--muted); margin-top: 4px; text-transform: uppercase; letter-spacing: 0.06em; }}

  /* Sections */
  .section {{ margin-bottom: 40px; }}
  .section h2 {{ font-size: 1.1rem; font-weight: 700; margin-bottom: 16px; display: flex; align-items: center; gap: 8px; }}
  .section h2 .icon {{ font-size: 1.2rem; }}

  /* Compliance badge */
  .compliance-badge {{ display: inline-flex; align-items: center; gap: 6px; padding: 6px 14px; border-radius: 20px; font-size: 0.8rem; font-weight: 700; }}
  .compliance-badge.pass {{ background: rgba(52,211,153,0.12); color: var(--success); border: 1px solid rgba(52,211,153,0.25); }}
  .compliance-badge.fail {{ background: rgba(248,113,113,0.12); color: var(--danger); border: 1px solid rgba(248,113,113,0.25); }}
  .compliance-badge.pending {{ background: rgba(255,255,255,0.05); color: var(--muted); border: 1px solid var(--border); }}
  .compliance-summary {{ color: var(--muted); font-size: 0.85rem; margin-top: 8px; }}

  /* Style DNA */
  .style-row {{ display: flex; align-items: center; gap: 16px; flex-wrap: wrap; }}
  .style-theme {{ font-size: 1rem; font-weight: 700; padding: 6px 16px; background: var(--surface); border: 1px solid var(--border); border-radius: 20px; }}
  .swatch {{ width: 28px; height: 28px; border-radius: 6px; border: 1px solid var(--border); }}
  .style-detail {{ color: var(--muted); font-size: 0.82rem; margin-top: 8px; }}

  /* Table */
  table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; }}
  th {{ text-align: left; padding: 10px 12px; border-bottom: 1px solid var(--border); color: var(--muted); font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.06em; }}
  td {{ padding: 10px 12px; border-bottom: 1px solid var(--border); }}
  tr:last-child td {{ border-bottom: none; }}
  a {{ color: var(--accent); text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}

  .total-row {{ display: flex; justify-content: flex-end; gap: 24px; padding: 12px 0; font-weight: 700; font-size: 1rem; border-top: 2px solid var(--accent); margin-top: 8px; }}

  /* Print */
  @media print {{
    body {{ background: #fff; color: #111; padding: 24px; }}
    .summary-card {{ border: 1px solid #ddd; }}
    .section h2 {{ color: #333; }}
    th {{ color: #666; }}
    td {{ border-color: #eee; }}
    a {{ color: #6d61ff; }}
  }}

  /* Score ring */
  .score-ring {{ display: inline-block; }}
</style>
</head>
<body>
<div class="report">

  <div class="report-header">
    <div>
      <div class="logo">
        <div class="logo-mark">V</div>
        <div class="logo-text">VESTA<span>CODE</span></div>
      </div>
      <h1>{project.name or "Untitled Project"}</h1>
      <p style="color: var(--muted); font-size: 0.85rem; margin-top: 4px;">
        {project.semantic_context or "AI-powered interior design report."}
      </p>
    </div>
    <div class="meta">
      <p>Generated <strong>{now}</strong></p>
      <p>Project ID: <code>{project.project_id[:12]}…</code></p>
      <p>Version {project.version}</p>
    </div>
  </div>

  <div class="summary-grid">
    <div class="summary-card">
      <div class="val">{len(project.rooms)}</div>
      <div class="label">Rooms</div>
    </div>
    <div class="summary-card">
      <div class="val">{len(furniture)}</div>
      <div class="label">Furniture</div>
    </div>
    <div class="summary-card">
      <div class="val" style="color: {'var(--success)' if isinstance(flow_score, int) and flow_score >= 80 else 'var(--warn)' if isinstance(flow_score, int) else 'var(--muted)'}">
        {flow_score}
      </div>
      <div class="label">Flow Score</div>
    </div>
    <div class="summary-card">
      <div class="val">${total_cost:,.0f}</div>
      <div class="label">Est. Budget</div>
    </div>
  </div>

  <div class="section">
    <h2><span class="icon">🛡️</span> Compliance Status</h2>
    <div class="compliance-badge {compliance_class}">
      {"✓ All Codes Passed" if is_compliant else "⚠ Issues Detected" if is_compliant is False else "⏳ Pending Audit"}
    </div>
    <p class="compliance-summary">{compliance_summary}</p>
  </div>

  <div class="section">
    <h2><span class="icon">🎨</span> Design DNA</h2>
    <div class="style-row">
      <span class="style-theme">{theme}</span>
      <div class="swatch" style="background: {wall_color}"></div>
      <div class="swatch" style="background: #2d2d2d"></div>
      <div class="swatch" style="background: #c4a882"></div>
      <div class="swatch" style="background: #6d61ff"></div>
    </div>
    <p class="style-detail">Floor: {floor_mat} · Lighting: {lighting}</p>
  </div>

  <div class="section">
    <h2><span class="icon">🛋️</span> Furniture Schedule</h2>
    <table>
      <thead>
        <tr><th>Item</th><th>Vendor</th><th>Price</th><th>Stock</th><th>Link</th></tr>
      </thead>
      <tbody>
        {furniture_rows}
      </tbody>
    </table>
    <div class="total-row">
      <span>Total Estimated Budget</span>
      <span>${total_cost:,.0f}</span>
    </div>
  </div>

  <div class="section">
    <h2><span class="icon">📐</span> Room Layout</h2>
    <table>
      <thead>
        <tr><th>Room</th><th>Dimensions</th></tr>
      </thead>
      <tbody>
        {"".join(f'<tr><td>{r.name}</td><td>Polygon: {len(r.polygon)} vertices</td></tr>' for r in (project.rooms or []))}
      </tbody>
    </table>
  </div>

  <div class="section" style="margin-top: 48px; padding-top: 24px; border-top: 1px solid var(--border); text-align: center; color: var(--muted); font-size: 0.78rem;">
    <p>Generated by VestaCode · AI-Powered BIM Design Platform</p>
    <p style="margin-top: 4px;">This report is auto-generated. Validate all dimensions before construction.</p>
  </div>

</div>
</body>
</html>"""

    return html
