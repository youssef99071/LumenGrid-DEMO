import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { MatchRatePoint } from '../api'
import './Charts.css'

export interface ComparisonPoint {
  t: number
  current?: number
  NORMAL?: number
  TRAFFIC_JAM?: number
  SLOW?: number
}

interface ChartsProps {
  matchSeries: MatchRatePoint[]
  comparison: ComparisonPoint[]
  probabilities: Record<string, number>
  accuracyHistory: { label: string; accuracy: number }[]
}

export function Charts({
  matchSeries,
  comparison,
  probabilities,
  accuracyHistory,
}: ChartsProps) {
  const confData = Object.entries(probabilities).map(([name, value]) => ({
    name: name.replace('_', ' '),
    value: Math.round(value * 100),
  }))

  const hasComparison =
    comparison.some((p) => p.NORMAL != null) && comparison.some((p) => p.TRAFFIC_JAM != null)

  return (
    <section className="charts-panel">
      <div className="chart-block">
        <h3>Match rate · 60s window</h3>
        <div className="chart-box">
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={matchSeries}>
              <CartesianGrid stroke="rgba(94,160,184,0.15)" strokeDasharray="3 3" />
              <XAxis dataKey="t" tick={{ fill: '#8aa8b5', fontSize: 11 }} unit="s" />
              <YAxis domain={[0, 100]} tick={{ fill: '#8aa8b5', fontSize: 11 }} />
              <Tooltip
                contentStyle={{ background: '#0b1f2a', border: '1px solid rgba(94,160,184,0.3)' }}
              />
              <Line
                type="monotone"
                dataKey="match_rate"
                stroke="#3ecf8e"
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="chart-block">
        <h3>Confidence bars</h3>
        <div className="chart-box">
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={confData}>
              <CartesianGrid stroke="rgba(94,160,184,0.15)" strokeDasharray="3 3" />
              <XAxis dataKey="name" tick={{ fill: '#8aa8b5', fontSize: 11 }} />
              <YAxis domain={[0, 100]} tick={{ fill: '#8aa8b5', fontSize: 11 }} />
              <Tooltip
                contentStyle={{ background: '#0b1f2a', border: '1px solid rgba(94,160,184,0.3)' }}
              />
              <Bar dataKey="value" fill="#5b8fa8" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="chart-block wide">
        <h3>
          {hasComparison
            ? 'What-If comparison · NORMAL vs TRAFFIC_JAM match rates'
            : 'Historical accuracy'}
        </h3>
        <div className="chart-box">
          <ResponsiveContainer width="100%" height={180}>
            {hasComparison ? (
              <LineChart data={comparison}>
                <CartesianGrid stroke="rgba(94,160,184,0.15)" strokeDasharray="3 3" />
                <XAxis dataKey="t" tick={{ fill: '#8aa8b5', fontSize: 11 }} unit="s" />
                <YAxis domain={[0, 100]} tick={{ fill: '#8aa8b5', fontSize: 11 }} />
                <Tooltip
                  contentStyle={{ background: '#0b1f2a', border: '1px solid rgba(94,160,184,0.3)' }}
                />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="NORMAL"
                  stroke="#3ecf8e"
                  strokeWidth={2}
                  dot={false}
                  name="NORMAL"
                />
                <Line
                  type="monotone"
                  dataKey="TRAFFIC_JAM"
                  stroke="#e07a5f"
                  strokeWidth={2}
                  dot={false}
                  name="TRAFFIC_JAM"
                />
                {comparison.some((p) => p.current != null) && (
                  <Line
                    type="monotone"
                    dataKey="current"
                    stroke="#f4c95f"
                    strokeWidth={2}
                    strokeDasharray="4 4"
                    dot={false}
                    name="Current run"
                  />
                )}
              </LineChart>
            ) : (
              <LineChart data={accuracyHistory}>
                <CartesianGrid stroke="rgba(94,160,184,0.15)" strokeDasharray="3 3" />
                <XAxis dataKey="label" tick={{ fill: '#8aa8b5', fontSize: 11 }} />
                <YAxis domain={[0, 100]} tick={{ fill: '#8aa8b5', fontSize: 11 }} />
                <Tooltip
                  contentStyle={{ background: '#0b1f2a', border: '1px solid rgba(94,160,184,0.3)' }}
                />
                <Line type="monotone" dataKey="accuracy" stroke="#f4c95f" strokeWidth={2} dot />
              </LineChart>
            )}
          </ResponsiveContainer>
        </div>
      </div>
    </section>
  )
}
