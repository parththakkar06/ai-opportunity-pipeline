import { DATA_MODES, type DataMode } from './worstCase'

const LABELS: Record<DataMode, string> = { demo: 'Demo data', worst: 'Worst case', empty: 'Empty', one: 'One' }

/** Dev-only segmented control for the break-ui review. Plain chrome, not part of the design under test. */
export function DataToggle({ mode }: { mode: DataMode }) {
  const set = (m: DataMode) => {
    const params = new URLSearchParams(window.location.search)
    if (m === 'demo') params.delete('data')
    else params.set('data', m)
    window.location.search = params.toString()
  }
  return (
    <div
      role="group"
      aria-label="Dev data"
      style={{ position: 'fixed', bottom: 12, left: '50%', transform: 'translateX(-50%)', zIndex: 70, display: 'flex', flexWrap: 'wrap', justifyContent: 'center', maxWidth: 'calc(100vw - 16px)', gap: 2, padding: 3, background: '#e5e5e5', borderRadius: 8, font: '12px system-ui' }}
    >
      {DATA_MODES.map((m) => (
        <button
          key={m}
          type="button"
          aria-pressed={mode === m}
          onClick={() => set(m)}
          style={{ padding: '4px 8px', whiteSpace: 'nowrap', borderRadius: 6, border: 0, background: mode === m ? '#fff' : 'transparent', color: '#111', cursor: 'pointer' }}
        >
          {LABELS[m]}
        </button>
      ))}
    </div>
  )
}
