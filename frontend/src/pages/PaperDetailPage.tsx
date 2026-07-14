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

// One label:value pair, used across Experimental Conditions, Performance
// Summary and Original Metadata so every field reads consistently.
// "Unknown" (rather than a blank) is the fallback for AI-derived
// structured fields, per the Battery Snapshot spec extended to its
// siblings; callers can override for non-AI-derived data (e.g. DOI).
function Field({ label, value, fallback = 'Unknown' }: { label: string; value: string | null; fallback?: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-1 text-sm">
      <dt className="text-slate-500">{label}</dt>
      <dd className={value ? 'text-right text-slate-800' : 'text-right italic text-slate-400'}>
        {value || fallback}
      </dd>
    </div>
  )
}

function FieldGroup({ title, fields }: { title: string; fields: [string, string | null][] }) {
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

// A single stat tile within Battery Snapshot -- the "answer in 30 seconds"
// card, so values are visually larger/bolder than the dense Field rows
// used elsewhere on the page.
function SnapshotStat({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="rounded-lg border border-slate-100 bg-slate-50 px-4 py-3">
      <dt className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</dt>
      <dd className={`mt-1 text-sm font-semibold ${value ? 'text-slate-900' : 'text-slate-400'}`}>
        {value || 'Unknown'}
      </dd>
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
          <h1 className="text-xl font-semibold text-slate-900 sm:text-2xl">{paper.title}</h1>

          {/* 1. Battery Snapshot -- always visible, never collapsed. This is
              the single card a researcher should be able to read in a few
              seconds to know what the paper is about. */}
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Battery Snapshot</h2>
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

            <dl className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
              <SnapshotStat label="Battery System" value={analysis?.battery_system ?? null} />
              <SnapshotStat label="Cathode" value={analysis?.cathode ?? null} />
              <SnapshotStat label="Anode" value={analysis?.anode ?? null} />
              <SnapshotStat label="Electrolyte" value={analysis?.electrolyte ?? null} />
              <SnapshotStat label="Voltage Window" value={analysis?.voltage_window ?? null} />
              <SnapshotStat label="Temperature" value={analysis?.temperature ?? null} />
              <SnapshotStat label="Cycle Condition" value={analysis?.cycle_condition ?? null} />
            </dl>
          </div>

          {/* 2. Experimental Conditions */}
          <CollapsibleCard title="Experimental Conditions" defaultOpen>
            <div className="grid grid-cols-1 gap-x-8 gap-y-4 sm:grid-cols-3">
              <FieldGroup
                title="Electrolyte Composition"
                fields={[
                  ['Salt', analysis?.salt ?? null],
                  ['Salt Concentration', analysis?.salt_concentration ?? null],
                  ['Solvent', analysis?.solvent ?? null],
                  ['Solvent Ratio', analysis?.solvent_ratio ?? null],
                  ['Additives', analysis?.additive ?? null],
                  ['Electrolyte Amount', analysis?.electrolyte_amount ?? null],
                ]}
              />
              <FieldGroup
                title="Cell Configuration"
                fields={[
                  ['Separator', analysis?.separator ?? null],
                  ['Cell Type', analysis?.cell_type ?? null],
                  ['Loading', analysis?.loading ?? null],
                  ['N/P Ratio', analysis?.np_ratio ?? null],
                ]}
              />
              <FieldGroup
                title="Electrochemical Evaluation"
                fields={[
                  ['Formation Protocol', analysis?.formation_protocol ?? null],
                  ['Rate Capability', analysis?.rate_capability ?? null],
                  ['Temperature', analysis?.temperature ?? null],
                  ['Voltage Window', analysis?.voltage_window ?? null],
                  ['Cycle Condition', analysis?.cycle_condition ?? null],
                ]}
              />
            </div>
          </CollapsibleCard>

          {/* 3. Performance Summary */}
          <CollapsibleCard title="Performance Summary" defaultOpen>
            <dl className="grid grid-cols-1 gap-x-8 sm:grid-cols-2">
              <Field label="Initial Capacity" value={analysis?.initial_capacity ?? null} />
              <Field label="Capacity Retention" value={analysis?.capacity_retention ?? null} />
              <Field label="Cycle Life" value={analysis?.cycle_life ?? null} />
              <Field label="Coulombic Efficiency" value={analysis?.coulombic_efficiency ?? null} />
              <Field label="Rate Performance" value={analysis?.rate_performance ?? null} />
              <Field label="Main Performance Claim" value={analysis?.main_performance_claim ?? null} />
            </dl>
          </CollapsibleCard>

          {/* 4. AI Summary */}
          <CollapsibleCard title="AI Summary" defaultOpen>
            {!analysis ? (
              <NotAnalyzedYet message="Not summarized yet. Click “Analyze This Paper” above." />
            ) : (
              <div className="space-y-4">
                <div>
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-400">Main Contribution</h3>
                  <p className="mt-1 text-sm text-slate-700">{analysis.main_contribution || '—'}</p>
                </div>
                <div>
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-400">Innovation</h3>
                  <p className="mt-1 text-sm text-slate-700">{analysis.innovation || '—'}</p>
                </div>
                <div>
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-400">Advantages</h3>
                  <div className="mt-1">
                    <BulletList items={analysis.advantages} emptyMessage="No advantages extracted." />
                  </div>
                </div>
                <div>
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-400">Limitations</h3>
                  <div className="mt-1">
                    <BulletList items={analysis.limitations} emptyMessage="No limitations extracted." />
                  </div>
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

          {/* 5. Abstract */}
          <CollapsibleCard title="Abstract" defaultOpen>
            {paper.abstract ? (
              <p className="leading-relaxed text-slate-700">{paper.abstract}</p>
            ) : (
              <NotAnalyzedYet message="No abstract available." />
            )}
          </CollapsibleCard>

          {/* 6. Original Metadata -- bibliographic data, de-prioritized and
              collapsed by default since a researcher needs the science
              above far more urgently than the DOI. */}
          <CollapsibleCard title="Original Metadata">
            <dl className="divide-y divide-slate-100">
              <Field label="Authors" value={paper.authors.length > 0 ? paper.authors.join(', ') : null} fallback="—" />
              <Field label="Journal" value={paper.journal} fallback="—" />
              <Field label="Year" value={paper.year ? String(paper.year) : null} fallback="—" />
              <Field label="Citations" value={String(paper.citation_count ?? 0)} fallback="—" />
              <Field label="DOI" value={paper.doi} fallback="—" />
              <Field label="Published Date" value={paper.published_date} fallback="—" />
            </dl>
            {paper.pdf_url && (
              <a
                href={paper.pdf_url}
                target="_blank"
                rel="noreferrer"
                className="mt-3 inline-block text-sm font-medium text-slate-900 underline underline-offset-2 hover:text-slate-600"
              >
                View PDF ↗
              </a>
            )}
          </CollapsibleCard>
        </div>
      )}
    </section>
  )
}
