import 'ag-grid-community/styles/ag-grid.css'
import 'ag-grid-community/styles/ag-theme-quartz.css'

import { AgGridReact } from 'ag-grid-react'
import { useMemo } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import type { ColDef, ValueFormatterParams } from 'ag-grid-community'

import CollapsibleCard from '@/components/CollapsibleCard'
import { useExportPapers } from '@/hooks/useExportPapers'
import { getErrorMessage } from '@/services/apiError'
import type { CompareFlowResult } from '@/hooks/useComparePapers'
import type { ComparisonTableRow } from '@/types/comparison'

function truncate(text: string | null, maxLength: number): string {
  if (!text) return '—'
  return text.length > maxLength ? `${text.slice(0, maxLength).trimEnd()}…` : text
}

function BulletList({ items }: { items: string[] }) {
  if (items.length === 0) return <p className="text-sm italic text-slate-400">None identified.</p>
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

function Fact({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3">
      <dt className="text-xs font-medium text-slate-400">{label}</dt>
      <dd className="mt-0.5 text-sm text-slate-800">{value || '—'}</dd>
    </div>
  )
}

export default function ComparisonPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const exportMutation = useExportPapers()

  // Populated by SearchPage's "Compare Selected" flow (useComparePapers) via
  // navigate('/compare', { state }) -- no persistence, so this page has
  // nothing to show if opened directly, same pattern as /paper/:id.
  const result = location.state as CompareFlowResult | undefined

  const rowData = useMemo<ComparisonTableRow[]>(() => result?.comparison.comparison_table ?? [], [result])

  const columnDefs = useMemo<ColDef<ComparisonTableRow>[]>(
    () => [
      {
        headerName: 'Title',
        field: 'title',
        flex: 2,
        minWidth: 220,
        wrapText: true,
        autoHeight: true,
        cellClass: 'font-medium text-slate-900 leading-snug py-2',
      },
      { headerName: 'Electrolyte', field: 'electrolyte', flex: 1.2, minWidth: 160 },
      { headerName: 'Salt', field: 'salt', flex: 1, minWidth: 110 },
      { headerName: 'Additives', field: 'additive', flex: 1, minWidth: 110 },
      { headerName: 'Cathode', field: 'cathode', flex: 1, minWidth: 110 },
      { headerName: 'Anode', field: 'anode', flex: 1, minWidth: 110 },
      { headerName: 'Voltage Window', field: 'voltage_window', flex: 1, minWidth: 130 },
      { headerName: 'Temperature', field: 'temperature', flex: 1, minWidth: 110 },
      { headerName: 'Cycle Condition', field: 'cycle_condition', flex: 1.2, minWidth: 140 },
      {
        headerName: 'Main Finding',
        field: 'main_finding',
        flex: 1.5,
        minWidth: 200,
        wrapText: true,
        autoHeight: true,
        valueFormatter: (params: ValueFormatterParams<ComparisonTableRow>) => truncate(params.value ?? null, 140),
      },
      {
        headerName: 'Advantages',
        field: 'advantages',
        flex: 1.5,
        minWidth: 180,
        wrapText: true,
        autoHeight: true,
      },
      {
        headerName: 'Limitations',
        field: 'limitations',
        flex: 1.5,
        minWidth: 180,
        wrapText: true,
        autoHeight: true,
      },
    ],
    [],
  )

  const handleExport = () => {
    if (result) exportMutation.mutate(result.papers)
  }

  return (
    <section className="space-y-6">
      <button onClick={() => navigate(-1)} className="text-sm text-slate-500 transition hover:text-slate-900">
        ← Back to search
      </button>

      {!result ? (
        <div className="rounded-xl border border-slate-200 bg-white p-6 text-sm text-slate-500">
          <p>No comparison to show.</p>
          <p className="mt-1">Select papers on the search page and click "Compare Selected" to see one here.</p>
        </div>
      ) : (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h1 className="text-2xl font-semibold tracking-tight">Paper Comparison</h1>
              <p className="mt-1 text-sm text-slate-500">
                {result.comparison.paper_count} paper{result.comparison.paper_count === 1 ? '' : 's'} compared
              </p>
            </div>
            <button
              type="button"
              onClick={handleExport}
              disabled={exportMutation.isPending}
              className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {exportMutation.isPending ? 'Exporting…' : 'Export to Excel'}
            </button>
          </div>

          {exportMutation.isError && (
            <p className="text-sm text-red-600">
              {getErrorMessage(exportMutation.error, 'Export failed. Please try again.')}
            </p>
          )}

          <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <Fact label="Most Common Cathode" value={result.comparison.most_common_cathode} />
            <Fact label="Most Common Anode" value={result.comparison.most_common_anode} />
            <Fact label="Research Trend" value={result.comparison.research_trend} />
            <Fact label="Research Gap" value={result.comparison.research_gap} />
            <Fact label="Potential Future Direction" value={result.comparison.potential_future_direction} />
          </dl>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <CollapsibleCard title="Common Experimental Conditions" defaultOpen>
              <BulletList items={result.comparison.common_experimental_conditions} />
            </CollapsibleCard>
            <CollapsibleCard title="Differences" defaultOpen>
              <BulletList items={result.comparison.differences} />
            </CollapsibleCard>
            <CollapsibleCard title="Frequently Used Electrolytes">
              <BulletList items={result.comparison.frequently_used_electrolytes} />
            </CollapsibleCard>
            <CollapsibleCard title="Frequently Used Additives">
              <BulletList items={result.comparison.frequently_used_additives} />
            </CollapsibleCard>
          </div>

          <div className="space-y-2">
            <h2 className="text-sm font-semibold text-slate-700">Comparison Table</h2>
            <div className="ag-theme-quartz h-[60vh] w-full rounded-xl border border-slate-200 bg-white p-2 shadow-sm">
              <AgGridReact<ComparisonTableRow>
                rowData={rowData}
                columnDefs={columnDefs}
                animateRows
                defaultColDef={{ resizable: true, sortable: true }}
              />
            </div>
          </div>
        </>
      )}
    </section>
  )
}
