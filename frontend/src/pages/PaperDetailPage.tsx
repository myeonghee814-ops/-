import { useLocation, useNavigate, useParams } from 'react-router-dom'

import CollapsibleCard from '@/components/CollapsibleCard'
import LoadingSpinner from '@/components/LoadingSpinner'
import { useAnalyzePaper } from '@/hooks/useAnalyzePaper'
import { getErrorMessage } from '@/services/apiError'
import type { PaperAnalysis } from '@/types/analysis'
import type { PaperResult } from '@/types/paper'

function NotAnalyzedYet({ message }: { message: string }) {
  return <p className="text-sm italic text-slate-400">{message}</p>
}

function BulletList({ items, emptyMessage }: { items: string[]; emptyMessage: string }) {
  if (items.length === 0) return <NotAnalyzedYet message={emptyMessage} />
  return (
    <ul className="space-y-1.5 text-sm text-slate-700">
      {items.map((item) => (
        <li key={item} className="flex gap-2">
          <span className="text-slate-400">•</span>
          <span>{item}</span>
        </li>
      ))}
    </ul>
  )
}

// One label:value pair within an ExperimentalGroup. "—" for fields the
// model didn't find in the text, consistent with how every other
// AI-derived surface in the app treats missing data (never fabricated).
function Field({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-1 text-sm">
      <dt className="text-slate-500">{label}</dt>
      <dd className="text-right text-slate-800">{value || '—'}</dd>
    </div>
  )
}

function ExperimentalGroup({ title, fields }: { title: string; fields: [string, string | null][] }) {
  return (
    <div>
      <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-400">{title}</h3>
      <dl className="mt-1 divide-y divide-slate-100">
        {fields.map(([label, value]) => (
          <Field key={label} label={label} value={value} />
        ))}
      </dl>
    </div>
  )
}

export default function PaperDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const location = useLocation()
  const analyzeMutation = useAnalyzePaper()

  // Search results aren't persisted yet (see docs/ARCHITECTURE.md), so
  // there's no GET /paper/:id backend endpoint to fetch from. The row the
  // user clicked is passed via router state instead.
  const paper = (location.state as { paper?: PaperResult } | undefined)?.paper
  const analysis: PaperAnalysis | undefined = analyzeMutation.data

  const handleAnalyze = () => {
    if (!paper?.abstract) return
    analyzeMutation.mutate({ title: paper.title, abstract: paper.abstract })
  }

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
        <div className="space-y-6">
          {/* Basic Information: always visible, never collapsed -- this is
              how a researcher confirms they're looking at the right paper. */}
          <header className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <h1 className="text-xl font-semibold text-slate-900 sm:text-2xl">{paper.title}</h1>
              {analysis?.battery_system && (
                <span className="shrink-0 rounded-full bg-slate-900 px-3 py-1 text-xs font-medium text-white">
                  {analysis.battery_system}
                </span>
              )}
            </div>

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

            <div className="mt-4 flex flex-wrap items-center gap-4">
              {paper.pdf_url && (
                <a
                  href={paper.pdf_url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-sm font-medium text-slate-900 underline underline-offset-2 hover:text-slate-600"
                >
                  View PDF ↗
                </a>
              )}

              {!analysis && (
                <button
                  type="button"
                  onClick={handleAnalyze}
                  disabled={!paper.abstract || analyzeMutation.isPending}
                  title={paper.abstract ? undefined : 'No abstract available to analyze'}
                  className="inline-flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-1.5 text-sm font-medium text-white transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {analyzeMutation.isPending && <LoadingSpinner />}
                  {analyzeMutation.isPending ? 'Analyzing…' : 'Analyze This Paper'}
                </button>
              )}
            </div>

            {analyzeMutation.isError && (
              <p className="mt-2 text-sm text-red-600">
                {getErrorMessage(analyzeMutation.error, 'Analysis failed. Please try again.')}
              </p>
            )}
          </header>

          <CollapsibleCard title="Abstract" defaultOpen>
            {paper.abstract ? (
              <p className="leading-relaxed text-slate-700">{paper.abstract}</p>
            ) : (
              <NotAnalyzedYet message="No abstract available." />
            )}
          </CollapsibleCard>

          {/* One card covering electrolyte/cell/electrochemical fields
              together (not three separate cards) so the whole experimental
              setup is scannable in one place, in well under 30 seconds. */}
          <CollapsibleCard title="Experimental Conditions" defaultOpen>
            {!analysis ? (
              <NotAnalyzedYet message="Click “Analyze This Paper” above to extract experimental conditions." />
            ) : (
              <div className="grid grid-cols-1 gap-x-8 gap-y-4 sm:grid-cols-3">
                <ExperimentalGroup
                  title="Electrolyte Composition"
                  fields={[
                    ['Electrolyte', analysis.electrolyte],
                    ['Salt', analysis.salt],
                    ['Solvent', analysis.solvent],
                    ['Additives', analysis.additive],
                  ]}
                />
                <ExperimentalGroup
                  title="Cell Configuration"
                  fields={[
                    ['Cathode', analysis.cathode],
                    ['Anode', analysis.anode],
                    ['Separator', analysis.separator],
                    ['Cell Type', analysis.cell_type],
                  ]}
                />
                <ExperimentalGroup
                  title="Electrochemical Evaluation"
                  fields={[
                    ['Voltage Window', analysis.voltage_window],
                    ['Temperature', analysis.temperature],
                    ['Formation', analysis.formation_protocol],
                    ['Cycle Condition', analysis.cycle_condition],
                    ['Rate Capability', analysis.rate_capability],
                  ]}
                />
              </div>
            )}
          </CollapsibleCard>

          <CollapsibleCard title="Key Experimental Results" defaultOpen>
            {!analysis ? (
              <NotAnalyzedYet message="Not summarized yet." />
            ) : (
              <BulletList items={analysis.main_findings} emptyMessage="No findings extracted." />
            )}
          </CollapsibleCard>

          <CollapsibleCard title="Advantages">
            {!analysis ? (
              <NotAnalyzedYet message="Not summarized yet." />
            ) : (
              <BulletList items={analysis.advantages} emptyMessage="No advantages extracted." />
            )}
          </CollapsibleCard>

          <CollapsibleCard title="Limitations">
            {!analysis ? (
              <NotAnalyzedYet message="Not summarized yet." />
            ) : (
              <BulletList items={analysis.limitations} emptyMessage="No limitations extracted." />
            )}
          </CollapsibleCard>

          <CollapsibleCard title="AI Summary">
            {!analysis ? (
              <NotAnalyzedYet message="Not summarized yet." />
            ) : (
              <div className="space-y-4">
                <div>
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-400">Main Contribution</h3>
                  <p className="mt-1 text-sm text-slate-700">{analysis.innovation || '—'}</p>
                </div>
                <div>
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-400">Future Work</h3>
                  <div className="mt-1">
                    <BulletList items={analysis.future_work} emptyMessage="No future work suggested." />
                  </div>
                </div>
              </div>
            )}
          </CollapsibleCard>
        </div>
      )}
    </section>
  )
}
