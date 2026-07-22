/** Loading placeholder shown while a paper is being extracted/summarized. */
export function PaperDetailSkeleton() {
  return (
    <div className="animate-pulse space-y-6">
      <div className="rounded-2xl border border-border bg-card p-6">
        <div className="h-7 w-2/3 rounded-md bg-black/[0.06]" />
        <div className="mt-3 h-4 w-1/3 rounded-md bg-black/[0.05]" />
        <div className="mt-5 h-4 w-full rounded-md bg-black/[0.05]" />
        <div className="mt-2 h-4 w-5/6 rounded-md bg-black/[0.05]" />
      </div>
      {[0, 1, 2].map((i) => (
        <div key={i} className="rounded-2xl border border-border bg-card p-6">
          <div className="h-4 w-24 rounded-md bg-black/[0.06]" />
          <div className="mt-4 h-4 w-full rounded-md bg-black/[0.05]" />
          <div className="mt-2 h-4 w-full rounded-md bg-black/[0.05]" />
          <div className="mt-2 h-4 w-2/3 rounded-md bg-black/[0.05]" />
        </div>
      ))}
    </div>
  );
}
