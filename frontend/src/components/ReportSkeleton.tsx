/** Placeholder shapes that hold the layout while a report loads (no layout jump when it arrives). */
export function ReportSkeleton() {
  return (
    <div className="space-y-4" role="status" aria-busy="true" aria-label="Loading report…">
      <div className="rounded-2xl border border-border bg-card p-5 sm:p-7">
        <div className="h-3 w-40 animate-pulse rounded bg-muted" />
        <div className="mt-3 h-9 w-72 max-w-full animate-pulse rounded-lg bg-muted" />
        <div className="mt-4 flex gap-2">
          <div className="h-6 w-28 animate-pulse rounded-full bg-muted" />
          <div className="h-6 w-36 animate-pulse rounded-full bg-muted" />
        </div>
      </div>
      <div className="flex gap-2 py-2">
        {[120, 130, 100, 130, 90].map((w, i) => (
          <div key={i} className="h-11 animate-pulse rounded-lg bg-muted" style={{ width: w }} />
        ))}
      </div>
      <div className="rounded-2xl border border-border bg-card p-5 sm:p-7">
        <div className="h-3 w-24 animate-pulse rounded bg-muted" />
        <div className="mt-3 space-y-2">
          <div className="h-4 w-full animate-pulse rounded bg-muted" />
          <div className="h-4 w-11/12 animate-pulse rounded bg-muted" />
          <div className="h-4 w-3/4 animate-pulse rounded bg-muted" />
        </div>
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        {[0, 1, 2].map((i) => (
          <div key={i} className="h-28 animate-pulse rounded-xl bg-muted" />
        ))}
      </div>
    </div>
  )
}
