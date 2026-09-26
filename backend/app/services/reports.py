"""Printable HTML briefs for a station or a zone (save as PDF from the browser).

Every figure comes from the same service functions as the JSON API. Each report carries
the time window, the model and dataset versions, the synthetic-data label and the
limitation statement.
"""

from __future__ import annotations

from html import escape
from typing import Any

from backend.app.services import analytics as svc
from backend.app.services import intelligence as intel
from backend.app.services.store import DataStore
from ml.config import LIMITATION_STATEMENT

CSS = """
:root { color-scheme: light; }
body { font: 13px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif; color: #1a1d23;
       max-width: 900px; margin: 24px auto; padding: 0 16px; }
h1 { font-size: 20px; margin: 0 0 4px; } h2 { font-size: 15px; margin: 22px 0 8px;
     border-bottom: 1px solid #d5d9e0; padding-bottom: 4px; }
.meta { color: #5a6270; font-size: 12px; }
.banner { background: #fff4d6; border: 1px solid #e6c56b; padding: 8px 10px;
          border-radius: 4px; margin: 12px 0; font-weight: 600; }
.limit { background: #eef2f7; border-left: 3px solid #5a6270; padding: 8px 10px;
         margin: 16px 0; }
table { border-collapse: collapse; width: 100%; font-size: 12px; }
th, td { text-align: left; padding: 4px 6px; border-bottom: 1px solid #e3e6eb; }
th { background: #f4f6f9; } td.num { text-align: right; font-variant-numeric: tabular-nums; }
.kpis { display: flex; flex-wrap: wrap; gap: 8px; }
.kpi { border: 1px solid #d5d9e0; border-radius: 4px; padding: 6px 10px; min-width: 120px; }
.kpi b { display: block; font-size: 18px; }
footer { margin-top: 28px; color: #5a6270; font-size: 11px; }
@media print { body { margin: 0; } .noprint { display: none; } }
"""


def _table(rows: list[dict[str, Any]], cols: list[tuple[str, str]]) -> str:
    if not rows:
        return "<p class='meta'>None.</p>"
    head = "".join(f"<th>{escape(label)}</th>" for _, label in cols)
    body = []
    for r in rows:
        cells = []
        for key, _ in cols:
            v = r.get(key)
            num = isinstance(v, int | float) and not isinstance(v, bool)
            if isinstance(v, float):
                v = f"{v:.3f}" if abs(v) < 1 else f"{v:.1f}"
            cells.append(
                f"<td{' class=num' if num else ''}>{escape('' if v is None else str(v))}</td>"
            )
        body.append("<tr>" + "".join(cells) + "</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def _page(title: str, subtitle: str, store: DataStore, body: str) -> str:
    v = svc.versions(store)
    w = svc.window(store)
    label = store.dataset_manifest["data_label"]
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title><style>{CSS}</style></head><body>
<h1>{escape(title)}</h1>
<div class="meta">{escape(subtitle)} · Forecast window {escape(w["start"][:10])} to
{escape(w["end"][:10])} (exclusive) · Generated {escape(v["generated_at"])}</div>
<div class="banner">{escape(label)}: all incidents, stations and zones in this report are
synthetic demonstration data, not real police records or official boundaries.</div>
<p class="noprint meta">Use your browser's Print command to save this report as a PDF.</p>
{body}
<div class="limit">{escape(LIMITATION_STATEMENT)}</div>
<footer>Model {escape(v["model_version"])} · training dataset
{escape(v["training_dataset_version"])} · input dataset {escape(v["input_dataset_version"])}
· features {escape(v["feature_version"])}. Risk scores (CRS, final risk) are composite
indicators, not probabilities; only the calibrated probability is a probability.</footer>
</body></html>"""


def station_report(store: DataStore, station_id: str) -> str:
    d = intel.station_detail(store, station_id)
    st = d["station"]
    k = d["kpis"]
    kpis = "".join(
        f"<div class='kpi'><b>{k[key]}</b>{escape(name)}</div>"
        for key, name in (
            ("zones", "Zones"),
            ("high_risk_zones", "High-risk zones"),
            ("active_hotspots", "Active hotspots"),
            ("emerging_hotspots", "Emerging hotspots"),
            ("current_anomalies", "Surge alerts"),
            ("incidents_4w", "Incidents, last 4 weeks"),
        )
    )
    lifecycle = [{"stage": s, "count": n} for s, n in d["lifecycle"].items() if n]
    body = f"""
<h2>Summary</h2><div class="kpis">{kpis}</div>
<h2>Attention priorities (highest blended risk)</h2>
{
        _table(
            d["top_attention"],
            [
                ("zone_id", "Zone"),
                ("label", "Crime type"),
                ("band", "Band"),
                ("final_risk", "Final risk"),
                ("risk_band", "Risk band"),
                ("probability", "Calibrated probability"),
                ("confidence", "Confidence"),
                ("hotspot_state", "Hotspot state"),
            ],
        )
    }
<h2>Surge alerts</h2>
{
        _table(
            d["alerts"],
            [
                ("zone_id", "Zone"),
                ("label", "Crime type"),
                ("current_count", "Last week"),
                ("baseline_mean", "52-week mean"),
                ("z_score", "z"),
            ],
        )
    }
<h2>Hotspot lifecycle (zone × crime type pairs)</h2>
{_table(lifecycle, [("stage", "Stage"), ("count", "Pairs")])}
<h2>Crime mix</h2>
{
        _table(
            d["crime_mix"],
            [
                ("label", "Crime type"),
                ("incidents_52w", "Last 52 weeks"),
                ("incidents_4w", "Last 4 weeks"),
            ],
        )
    }
<p class="meta">{escape(d["boundary_note"])}</p>"""
    return _page(f"Station brief: {st['name']}", st["station_id"], store, body)


def zone_report(store: DataStore, zone_id: str, crime_type: str, band: str) -> str:
    d = svc.zone_detail(store, zone_id, crime_type, band)
    lc = intel.zone_lifecycle(store, zone_id, crime_type)
    pm = intel.zone_patterns(store, zone_id, crime_type)
    p = d["prediction"]
    hs = d["hotspot_state"]
    body = f"""
<h2>Forecast</h2>
<p><b>Event:</b> {escape(p["event_definition"])}.</p>
{
        _table(
            [p],
            [
                ("probability", "Calibrated probability"),
                ("confidence", "Confidence"),
                ("crs", "Risk score (CRS)"),
                ("final_risk", "Final risk"),
                ("risk_band", "Risk band"),
                ("expected_count", "Expected count"),
            ],
        )
    }
<h2>Risk score components</h2>
{
        _table(
            p["components"],
            [
                ("code", "Code"),
                ("name", "Component"),
                ("value", "Value (0-1)"),
                ("weight", "Weight"),
                ("contribution", "Points"),
            ],
        )
    }
<h2>Why (from the formula components)</h2>
<ul>{
        "".join(f"<li>{escape(r['text'])}</li>" for r in p["reasons"])
        or "<li>No component stands out.</li>"
    }</ul>
<h2>Model drivers (SHAP)</h2>
{
        _table(
            p["shap"]["top"],
            [
                ("label", "Feature"),
                ("value", "Value"),
                ("shap_log_odds", "SHAP (log-odds)"),
                ("direction", "Effect"),
            ],
        )
    }
<h2>Hotspot state and lifecycle</h2>
<p>{escape(hs["state"])}: {escape(hs["description"])} Current lifecycle stage:
<b>{escape(str(lc["current_stage"]))}</b> for {lc["steps_in_stage"]} step(s).</p>
{
        _table(
            lc["timeline"],
            [
                ("period_end", "Period end"),
                ("state", "State"),
                ("stage", "Stage"),
                ("gi_z_last", "Gi* z"),
            ],
        )
    }
<h2>Similar past patterns</h2>
<p class="meta">{escape(pm["note"])}</p>
{
        _table(
            pm["analogs"],
            [
                ("context_start", "Pattern start"),
                ("outcome_start", "Following window"),
                ("outcome_count", "Incidents in following window"),
                ("similarity", "Similarity"),
            ],
        )
    }"""
    title = f"Zone brief: {zone_id} · {d['crime_label']}"
    sub = f"{d['band_label']} · station {d['zone']['station_id']}"
    return _page(title, sub, store, body)
