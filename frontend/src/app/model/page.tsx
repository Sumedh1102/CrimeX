"use client";

import { ChartCard } from "@/components/charts/ChartCard";
import { HBars } from "@/components/charts/charts";
import { Card, DataTable, Dl, ErrorNote, Loading } from "@/components/ui/primitives";
import { useModelCard } from "@/lib/api";
import { CHROME, SERIES } from "@/lib/colors";
import { fmtDateTime, fmtNum, fmtPct } from "@/lib/format";
import type { ProbabilityMetrics } from "@/lib/types";
import { CartesianGrid, ComposedChart, Line, ResponsiveContainer, Scatter, Tooltip, XAxis, YAxis } from "recharts";

const MODEL_LABELS: Record<string, string> = {
  xgboost_calibrated: "XGBoost (calibrated) · deployed",
  xgboost_raw: "XGBoost (uncalibrated)",
  random_forest_calibrated: "Random Forest (calibrated)",
  historical_rate_baseline: "Historical-rate baseline",
  crs_explainable: "Explainable CRS (score)",
  crs_components_logistic: "Logistic fit on CRS components",
  blended_score: "Blended score",
};

export default function ModelPage() {
  const { data, error } = useModelCard();
  if (error) return <div className="p-3 sm:p-5"><ErrorNote error={error} /></div>;
  if (!data) return <Loading />;
  const md = data.metadata;
  const test = data.metrics.test;
  const val = data.metrics.validation;
  const names = Object.keys(test);
  const rel = data.metrics.reliability.test;
  const splits = md.splits as Record<string, { origins?: number; first_window_start?: string; last_window_end?: string } | string>;
  return (
    <div className="space-y-4 p-3 sm:p-5">
      <Card title="Model card" subtitle={`${md.model_version} · trained ${fmtDateTime(md.trained_at)} UTC · ${md.data_label}`}>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <Dl
            items={[
              ["Classification target", md.target.classification],
              ["Regression target", md.target.regression],
              ["Training data", md.training_dataset_version],
              ["Feature set", md.feature_version],
              ["Deployed", MODEL_LABELS[md.model_selection.deployed]],
              ["Selection note", md.model_selection.note],
            ]}
          />
          <Dl
            items={(["train", "validation", "test"] as const).map((k) => {
              const s = splits[k];
              return [
                k[0].toUpperCase() + k.slice(1),
                typeof s === "object" && s ? `${s.first_window_start} → ${s.last_window_end} (${s.origins} weekly windows)` : String(s),
              ] as [string, string];
            }).concat([
              ["Split rule", "Chronological; windows straddling a boundary are dropped"],
              ["Calibration", "Isotonic, fitted on the validation period"],
            ])}
          />
        </div>
      </Card>

      <Card title="Held-out test period: model comparison" subtitle="PR-AUC is the headline metric (the event is rare). Scores (CRS, blended) get ranking metrics only.">
        <DataTable
          rows={names}
          rowKey={(n) => n}
          columns={[
            { key: "m", header: "Model", render: (n) => <span className={n === "xgboost_calibrated" ? "font-semibold text-ink" : ""}>{MODEL_LABELS[n] ?? n}</span> },
            { key: "pr", header: "PR-AUC", render: (n) => fmtNum(test[n].pr_auc, 3), align: "right" },
            { key: "prv", header: "PR-AUC (val)", render: (n) => fmtNum(val[n]?.pr_auc, 3), align: "right" },
            { key: "roc", header: "ROC-AUC", render: (n) => fmtNum(test[n].roc_auc, 3), align: "right" },
            { key: "brier", header: "Brier", render: (n) => (test[n].brier !== undefined ? test[n].brier!.toFixed(4) : "–"), align: "right" },
            { key: "ece", header: "ECE", render: (n) => (test[n].ece !== undefined ? test[n].ece!.toFixed(4) : "–"), align: "right" },
            { key: "f1", header: "P / R / F1", render: (n) => (test[n].f1 !== undefined ? `${fmtNum(test[n].precision, 2)} / ${fmtNum(test[n].recall, 2)} / ${fmtNum(test[n].f1, 2)}` : "–"), align: "right" },
            { key: "topk", header: `Top-${Math.round(md.top_k_fraction * 100)}% capture`, render: (n) => fmtPct(test[n].top_k.capture_rate), align: "right" },
            { key: "pai", header: "PAI", render: (n) => fmtNum(test[n].top_k.pai, 2), align: "right" },
          ]}
        />
        <p className="mt-3 text-[11px] leading-snug text-muted">
          Top-K capture: share of test-period incidents that fell in the {test.xgboost_calibrated.top_k.k_zones} highest-ranked zones of
          each (week, crime type, band); an oracle that knew the outcomes would capture {fmtPct(test.xgboost_calibrated.top_k.oracle_capture_rate)}.
          Counts: XGBoost Poisson MAE {fmtNum(data.metrics.test_counts.xgboost_poisson.mae, 4)} / RMSE {fmtNum(data.metrics.test_counts.xgboost_poisson.rmse, 4)} vs baseline{" "}
          {fmtNum(data.metrics.test_counts.historical_rate_baseline.mae, 4)} / {fmtNum(data.metrics.test_counts.historical_rate_baseline.rmse, 4)}.
          All metrics are on synthetic demonstration data and say nothing about real-world performance.
        </p>
      </Card>

      <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
        <ChartCard
          title="Calibration on the test period"
          subtitle="Observed event rate vs mean predicted probability, 10 quantile bins (diagonal = perfect)"
          table={{
            columns: [{ key: "p", header: "Mean predicted", align: "right" }, { key: "o", header: "Observed", align: "right" }, { key: "n", header: "Rows", align: "right" }],
            rows: rel.map((b) => ({ p: fmtPct(b.mean_predicted), o: fmtPct(b.observed_rate), n: b.n.toLocaleString("en-IN") })),
          }}
        >
          <div style={{ height: 260 }}>
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={rel.map((b) => ({ x: b.mean_predicted, y: b.observed_rate, d: b.mean_predicted }))} margin={{ top: 8, right: 12, bottom: 4, left: -8 }}>
                <CartesianGrid stroke={CHROME.grid} />
                <XAxis type="number" dataKey="x" domain={[0, "dataMax"]} tick={{ fill: CHROME.muted, fontSize: 11 }} tickFormatter={(v) => fmtPct(v)} stroke={CHROME.baseline} />
                <YAxis type="number" domain={[0, "dataMax"]} tick={{ fill: CHROME.muted, fontSize: 11 }} tickFormatter={(v) => fmtPct(v)} stroke={CHROME.baseline} width={48} />
                <Tooltip formatter={(v) => fmtPct(Number(v))} contentStyle={{ background: CHROME.surface, border: "1px solid rgba(255,255,255,0.18)", fontSize: 11 }} />
                <Line dataKey="d" name="perfect calibration" stroke={CHROME.muted} strokeWidth={1} dot={false} isAnimationActive={false} />
                <Scatter dataKey="y" name="observed" fill={SERIES.primary} line={{ stroke: SERIES.primary, strokeWidth: 2 }} isAnimationActive={false} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </ChartCard>
        <ChartCard
          title="What the model relies on"
          subtitle="Mean |SHAP| on a test sample (log-odds), top 12 inputs"
          table={{
            columns: [{ key: "f", header: "Input" }, { key: "s", header: "Mean |SHAP|", align: "right" }],
            rows: md.mean_abs_shap_test_sample.map((r) => ({ f: r.label, s: r.mean_abs_shap.toFixed(4) })),
          }}
        >
          <HBars rows={md.mean_abs_shap_test_sample.slice(0, 12).map((r) => ({ key: r.feature, label: r.label, value: r.mean_abs_shap }))} format={(v) => v.toFixed(3)} />
        </ChartCard>
      </div>

      <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
        <Card title="Per crime type (test period)" subtitle="Deployed model vs the explainable score">
          <DataTable
            rows={Object.entries(data.metrics.test_per_crime_type)}
            rowKey={([k]) => k}
            columns={[
              { key: "c", header: "Crime type", render: ([k]) => k },
              { key: "b", header: "Base rate", render: ([, m]) => fmtPct(m.base_rate), align: "right" },
              { key: "x", header: "XGB PR-AUC", render: ([, m]) => fmtNum(m.xgboost_calibrated.pr_auc, 3), align: "right" },
              { key: "br", header: "XGB Brier", render: ([, m]) => m.xgboost_calibrated.brier?.toFixed(4) ?? "–", align: "right" },
              { key: "c2", header: "CRS PR-AUC", render: ([, m]) => fmtNum(m.crs_explainable.pr_auc, 3), align: "right" },
              { key: "tk", header: "XGB top-K", render: ([k]) => fmtPct((test.xgboost_calibrated as ProbabilityMetrics).top_k.per_crime_type[k]), align: "right" },
            ]}
          />
        </Card>
        <Card title="Explainable score weights" subtitle="Configured design weights vs a logistic fit on the same seven signals (not applied automatically)">
          <DataTable<string>
            rows={Object.keys(md.crs_weights_configured)}
            rowKey={(k) => k}
            columns={[
              { key: "k", header: "Signal", render: (k) => k },
              { key: "c", header: "Configured", render: (k) => md.crs_weights_configured[k].toFixed(2), align: "right" },
              {
                key: "s",
                header: "Logistic fit (normalised)",
                render: (k) => md.crs_weights_suggested_by_logistic_fit[k]?.toFixed(2) ?? "–",
                align: "right",
              },
            ]}
          />
          <p className="mt-3 text-[11px] leading-snug text-muted">
            Recency half-lives tuned on validation (days):{" "}
            {Object.entries(md.recency_half_life_tuning).map(([k, v]) => `${k} ${v.chosen}`).join(" · ")}.
          </p>
        </Card>
      </div>
      <p className="text-[11px] text-muted">{data.limitation_statement}</p>
    </div>
  );
}
