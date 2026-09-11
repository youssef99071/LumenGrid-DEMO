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
        <h3>📶 Live 5G Signal Disruption</h3>
        <p className="chart-sub">Signal drops when vehicles block the radio waves between towers</p>
        <div className="chart-box">
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={matchSeries}>
              <CartesianGrid stroke="rgba(0,212,255,0.08)" strokeDasharray="3 3" />
              <XAxis dataKey="t" tick={{ fill: '#8888aa', fontSize: 11 }} unit="s" />
              <YAxis domain={[0, 100]} tick={{ fill: '#8888aa', fontSize: 11 }} />
              <Tooltip
                contentStyle={{ background: '#16162a', border: '1px solid rgba(0,212,255,0.25)', borderRadius: 8 }}
              />
              <Line
                type="monotone"
                dataKey="match_rate"
                stroke="#00d4ff"
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
                name="Signal strength"
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="chart-block">
        <h3>🎯 AI Certainty — What's happening?</h3>
        <p className="chart-sub">How confident the AI is in each traffic state right now</p>
        <div className="chart-box">
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={confData}>
              <CartesianGrid stroke="rgba(0,212,255,0.08)" strokeDasharray="3 3" />
              <XAxis dataKey="name" tick={{ fill: '#8888aa', fontSize: 11 }} />
              <YAxis domain={[0, 100]} tick={{ fill: '#8888aa', fontSize: 11 }} />
              <Tooltip
                contentStyle={{ background: '#16162a', border: '1px solid rgba(0,212,255,0.25)', borderRadius: 8 }}
              />
              <Bar dataKey="value" fill="#ff2d78" radius={[4, 4, 0, 0]} name="Confidence %" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="chart-block wide">
        <h3>
          {hasComparison
            ? '📊 Scenario Comparison — Clear road vs. Traffic jam'
            : '📈 AI Track Record — Detection Accuracy Over Time'}
        </h3>
        <p className="chart-sub">
          {hasComparison
            ? 'How the 5G signal pattern differs across traffic scenarios'
            : 'How accurately the AI has been detecting traffic states'}
        </p>
        <div className="chart-box">
          <ResponsiveContainer width="100%" height={200}>
            {hasComparison ? (
              <LineChart data={comparison}>
                <CartesianGrid stroke="rgba(0,212,255,0.08)" strokeDasharray="3 3" />
                <XAxis dataKey="t" tick={{ fill: '#8888aa', fontSize: 11 }} unit="s" />
                <YAxis domain={[0, 100]} tick={{ fill: '#8888aa', fontSize: 11 }} />
                <Tooltip
                  contentStyle={{ background: '#16162a', border: '1px solid rgba(0,212,255,0.25)', borderRadius: 8 }}
                />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="NORMAL"
                  stroke="#00d4ff"
                  strokeWidth={2}
                  dot={false}
                  name="Normal flow"
                />
                <Line
                  type="monotone"
                  dataKey="TRAFFIC_JAM"
                  stroke="#ff2d78"
                  strokeWidth={2}
                  dot={false}
                  name="Traffic jam"
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
                <CartesianGrid stroke="rgba(0,212,255,0.08)" strokeDasharray="3 3" />
                <XAxis dataKey="label" tick={{ fill: '#8888aa', fontSize: 11 }} />
                <YAxis domain={[0, 100]} tick={{ fill: '#8888aa', fontSize: 11 }} />
                <Tooltip
                  contentStyle={{ background: '#16162a', border: '1px solid rgba(0,212,255,0.25)', borderRadius: 8 }}
                />
                <Line type="monotone" dataKey="accuracy" stroke="#00d4ff" strokeWidth={2} dot />
              </LineChart>
            )}
          </ResponsiveContainer>
        </div>
      </div>
    </section>
  )
}

