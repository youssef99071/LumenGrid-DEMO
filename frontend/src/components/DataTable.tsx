import type { RecordingRow } from '../api'
import './DataTable.css'

interface DataTableProps {
  rows: RecordingRow[]
}

export function DataTable({ rows }: DataTableProps) {
  return (
    <section className="table-panel">
      <h2>Current recording</h2>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Timestamp</th>
              <th>MatchRate</th>
              <th>RSRP</th>
              <th>RSRQ</th>
              <th>Actual</th>
              <th>Predicted</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={6} className="empty">
                  Run a simulation to populate the 60-second recording table.
                </td>
              </tr>
            ) : (
              rows.map((r, i) => (
                <tr key={`${r.timestamp}-${i}`} className={r.correct ? 'ok' : 'bad'}>
                  <td>{new Date(r.timestamp).toLocaleTimeString()}</td>
                  <td>{r.match_rate}</td>
                  <td>{r.rsrp}</td>
                  <td>{r.rsrq}</td>
                  <td>{r.actual_traffic.replace('_', ' ')}</td>
                  <td>{r.predicted_traffic.replace('_', ' ')}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  )
}
