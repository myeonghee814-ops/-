import { useLocation, useNavigate, useParams } from 'react-router-dom'

import CollapsibleCard from '@/components/CollapsibleCard'
import type { PaperResult } from '@/types/paper'

const EXPERIMENTAL_FIELDS = [
  'Electrolyte',
  'Cathode',
  'Anode',
  'Separator',
  'Cell Type',
  'Voltage Window',
  'Temperature',
  'Cycling Condition',
] as const

// Not-yet-analyzed placeholder shown in every "quick summary" section below.
// These fields depend on the LLM summarization feature, which is not
// implemented yet — see backend/prompts/ and docs/ARCHITECTURE.md.
function NotAnalyzedYet({ message, className = '' }: { message: string; className?: string }) {
  return <p className={`text-sm italic text-slate-400 ${className}`}>{message}</p>
}

export default function PaperDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const location = useLocation()

  // Search results aren't persisted yet (see docs/ARCHITECTURE.md), so
  // there's no GET /paper/:id backend endpoint to fetch from. The row the
  // user clicked is passed via router state instead.
  const paper = (location.state as { paper?: PaperResult } | undefined)?.paper

  return (
    <section className="space-y-6">
      <button onClick={() => navigate(-1)} className="text-sm text-slate-500 transition hover:text-slate-900">
        ← Back to search
      </button>

      {!paper ? (
        <div className="rounded-xl border border-slate-200 bg-white p-6 text-sm text-slate-500">
          <p>No details available for paper "{id}".</p>
          <p className="mt-1">Open this page from a search result to see its contents.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)] lg:items-start">
          {/* Left: paper information */}
          <div className="space-y-6">
            <header className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
              <h1 className="text-xl font-semibold text-slate-900 sm:text-2xl">{paper.title}</h1>

              {paper.authors.length > 0 && <p className="mt-2 text-sm text-slate-600">{paper.authors.join(', ')}</p>}

              <dl className="mt-4 flex flex-wrap gap-x-6 gap-y-1 text-sm text-slate-500">
                {paper.journal && (
                  <div>
                    <dt className="inline text-slate-400">Journal </dt>
                    <dd className="inline">{paper.journal}</dd>
                  </div>
                )}
                {paper.year && (
                  <div>
                    <dt className="inline text-slate-400">Year </dt>
                    <dd className="inline">{paper.year}</dd>
                  </div>
                )}
                <div>
                  <dt className="inline text-slate-400">Citations </dt>
                  <dd className="inline">{(paper.citation_count ?? 0).toLocaleString()}</dd>
                </div>
                {paper.doi && (
                  <div>
                    <dt className="inline text-slate-400">DOI </dt>
                    <dd className="inline font-mono">{paper.doi}</dd>
                  </div>
                )}
              </dl>

              {paper.pdf_url && (
                <a
                  href={paper.pdf_url}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-4 inline-block text-sm font-medium text-slate-900 underline underline-offset-2 hover:text-slate-600"
                >
                  View PDF ↗
                </a>
              )}
            </header>

            <CollapsibleCard title="Abstract" defaultOpen>
              {paper.abstract ? (
                <p className="leading-relaxed text-slate-700">{paper.abstract}</p>
              ) : (
                <NotAnalyzedYet message="No abstract available." />
              )}
            </CollapsibleCard>
          </div>

          {/* Right: quick summary */}
          <div className="space-y-4">
            <h2 className="px-1 text-xs font-semibold uppercase tracking-wide text-slate-400">Quick Summary</h2>

            <CollapsibleCard title="Keywords" defaultOpen>
              <NotAnalyzedYet message="Automated keyword extraction hasn't run for this paper yet." />
            </CollapsibleCard>

            <CollapsibleCard title="Experimental Conditions" defaultOpen>
              <dl className="divide-y divide-slate-100 text-sm">
                {EXPERIMENTAL_FIELDS.map((field) => (
                  <div key={field} className="flex items-center justify-between gap-4 py-1.5">
                    <dt className="text-slate-500">{field}</dt>
                    <dd className="text-slate-400">—</dd>
                  </div>
                ))}
              </dl>
              <NotAnalyzedYet message="Not extracted yet." className="mt-3" />
            </CollapsibleCard>

            <CollapsibleCard title="Main Findings" defaultOpen>
              <NotAnalyzedYet message="Not summarized yet." />
            </CollapsibleCard>

            <CollapsibleCard title="Advantages">
              <NotAnalyzedYet message="Not summarized yet." />
            </CollapsibleCard>

            <CollapsibleCard title="Limitations">
              <NotAnalyzedYet message="Not summarized yet." />
            </CollapsibleCard>

            <CollapsibleCard title="Future Work">
              <NotAnalyzedYet message="Not summarized yet." />
            </CollapsibleCard>
          </div>
        </div>
      )}
    </section>
  )
}
