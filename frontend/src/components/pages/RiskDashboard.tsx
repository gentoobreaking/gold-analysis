import type React from "react";
import { useEffect, useState, useCallback } from "react";
import {
  fetchRiskSample,
  type RiskSampleResponse,
  type CorrelationMatrix,
} from "@services/api";

const FACTOR_LABELS: Record<string, string> = {
  DXY: "美元指數 DXY",
  REAL_YIELD: "實質利率",
  BTC: "比特幣 BTC",
  SPX: "美股 SPX",
};

// 將相關係數 [-1,1] 對應到紅(負)-白(0)-綠(正)色階
function corrColor(v: number): string {
  if (Number.isNaN(v)) return "#3a3f4b";
  // 正相關 -> 偏綠；負相關 -> 偏紅
  const t = Math.max(-1, Math.min(1, v));
  if (t >= 0) {
    const g = Math.round(70 + 150 * t);
    return `rgb(${Math.round(70 - 40 * t)}, ${g}, ${Math.round(90 - 30 * t)})`;
  }
  const a = -t;
  const r = Math.round(70 + 160 * a);
  return `rgb(${r}, ${Math.round(80 - 40 * a)}, ${Math.round(90 - 30 * a)})`;
}

const Heatmap: React.FC<{ cm: CorrelationMatrix }> = ({ cm }) => {
  const { assets, matrix } = cm;
  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ borderCollapse: "collapse", fontSize: 12 }}>
        <thead>
          <tr>
            <th style={{ padding: 4 }} />
            {assets.map((a) => (
              <th key={a} style={{ padding: 4, color: "#cbd5e1" }}>
                {a}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {assets.map((rowA, i) => (
            <tr key={rowA}>
              <td style={{ padding: 4, color: "#cbd5e1" }}>{rowA}</td>
              {assets.map((colA, j) => {
                const v = matrix[i]?.[j];
                return (
                  <td
                    key={colA}
                    title={`${rowA} vs ${colA}: ${Number.isNaN(v as number) ? "n/a" : (v as number).toFixed(2)}`}
                    style={{
                      width: 56,
                      height: 36,
                      textAlign: "center",
                      color: "#0b0f17",
                      fontWeight: 600,
                      background: corrColor(v as number),
                      border: "1px solid #1f2430",
                    }}
                  >
                    {Number.isNaN(v as number) ? "–" : (v as number).toFixed(2)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

const FactorBars: React.FC<{ exposure: Record<string, number> }> = ({
  exposure,
}) => {
  const entries = Object.entries(exposure).filter(([k]) => !k.startsWith("_"));
  const maxAbs = Math.max(0.001, ...entries.map(([, v]) => Math.abs(v)));
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {entries.length === 0 && (
        <span style={{ color: "#94a3b8" }}>無因子曝險資料</span>
      )}
      {entries.map(([k, v]) => (
        <div key={k} style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ width: 120, color: "#cbd5e1" }}>
            {FACTOR_LABELS[k] ?? k}
          </span>
          <div
            style={{
              position: "relative",
              flex: 1,
              height: 18,
              background: "#1f2430",
              borderRadius: 4,
            }}
          >
            <div
              style={{
                position: "absolute",
                left: "50%",
                top: 0,
                width: `${(Math.abs(v) / maxAbs) * 50}%`,
                height: "100%",
                background: v >= 0 ? "#22c55e" : "#ef4444",
                transform: v >= 0 ? "translateX(0)" : "translateX(-100%)",
                borderRadius: 4,
              }}
            />
            <div
              style={{
                position: "absolute",
                left: "50%",
                top: -2,
                width: 1,
                height: 22,
                background: "#64748b",
              }}
            />
          </div>
          <span
            style={{
              width: 56,
              textAlign: "right",
              color: v >= 0 ? "#22c55e" : "#ef4444",
              fontVariantNumeric: "tabular-nums",
            }}
          >
            {v >= 0 ? "+" : ""}
            {v.toFixed(3)}
          </span>
        </div>
      ))}
    </div>
  );
};

const Card: React.FC<{ title: string; children: React.ReactNode }> = ({
  title,
  children,
}) => (
  <div
    style={{
      background: "#11151f",
      border: "1px solid #1f2430",
      borderRadius: 10,
      padding: 16,
      marginBottom: 16,
    }}
  >
    <h3 style={{ margin: "0 0 12px", color: "#e2e8f0", fontSize: 15 }}>
      {title}
    </h3>
    {children}
  </div>
);

const RiskDashboard: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sample, setSample] = useState<RiskSampleResponse | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchRiskSample();
      setSample(data);
    } catch (e: any) {
      setError(e?.message || "載入風險樣本失敗");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div style={{ padding: 24, maxWidth: 900, margin: "0 auto" }}>
      <h2 style={{ color: "#e2e8f0" }}>投資組合風險儀表板 (T064)</h2>
      <p style={{ color: "#94a3b8", marginTop: 0 }}>
        跨資產相關性熱圖與因子曝險。GOLD 採真實歷史收盤價； DXY / 實質利率 / BTC
        / SPX 為示範用合成因子。
      </p>

      {loading && <p style={{ color: "#94a3b8" }}>載入中…</p>}
      {error && (
        <div
          style={{
            background: "#3b1d1d",
            color: "#fca5a5",
            padding: 12,
            borderRadius: 8,
          }}
        >
          {error}
        </div>
      )}

      {sample && (
        <>
          <Card title="跨資產相關性矩陣">
            <Heatmap cm={sample.correlation} />
            {!sample.correlation.valid && (
              <p style={{ color: "#fbbf24", fontSize: 12 }}>
                ⚠ {sample.note || "資料不足，部分相關性無法計算"}
              </p>
            )}
          </Card>

          <Card title="因子曝險 (Gold 對各因子 beta)">
            <FactorBars exposure={sample.factor_exposure} />
            {sample.factor_exposure._r2 !== undefined && (
              <p style={{ color: "#64748b", fontSize: 12, marginTop: 8 }}>
                回歸 R² = {sample.factor_exposure._r2.toFixed(3)}
              </p>
            )}
          </Card>

          {sample.note && (
            <p style={{ color: "#64748b", fontSize: 12 }}>{sample.note}</p>
          )}
        </>
      )}
    </div>
  );
};

export default RiskDashboard;
