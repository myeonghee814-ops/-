import 'ag-grid-community/styles/ag-grid.css'
import 'ag-grid-community/styles/ag-theme-quartz.css'

import { AgGridReact } from 'ag-grid-react'
import { useCallback, useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import type { ColDef, RowClickedEvent, SelectionChangedEvent, ValueFormatterParams } from 'ag-grid-community'

import LoadingSpinner from '@/components/LoadingSpinner'
import { useAnalyzePapers } from '@/hooks/useAnalyzePapers'
import { useComparePapers } from '@/hooks/useComparePapers'
import { useExportPapers } from '@/hooks/useExportPapers'
import { useSearchPapers } from '@/hooks/useSearchPapers'
import { getErrorMessage } from '@/services/apiError'
import type { PaperAnalysis } from '@/types/analysis'
import type { PaperResult, SearchParams } from '@/types/paper'

// Analysis-derived fields, filled in only after "Analyze Results" runs.
// Kept separate from PaperResult (raw search metadata) since they come from
// a different, opt-in step -- see the "Analyze Results" button below.
type GridRow = PaperResult & {
  _id: string
  battery_system: string | null
  electrolyte: string | null
  main_contribution: string | null
}

const PAPER_LIMIT_OPTIONS = [10, 20, 50, 100]
const EARLIEST_YEAR = 1990
const CURRENT_YEAR = new Date().getFullYear()
const YEAR_OPTIONS = Array.from({ length: CURRENT_YEAR - EARLIEST_YEAR + 1 }, (_, i) => CURRENT_YEAR - i)

function truncate(text: string | null, maxLength: number): string {
  if (!text) return '—'
  return text.length > maxLength ? `${text.slice(0, maxLength).trimEnd()}…` : text
}

function formatSourceName(source: string): string {
  return source === 'semantic_scholar' ? 'Semantic Scholar' : 'OpenAlex'
}

// Doi-based ids are stable; index-based ids are only unique *within one
// result set*, so any state keyed by this id (analysisByRowId below) must
// be reset whenever a new search replaces the result set -- otherwise a
// new paper landing on the same index as an old one would inherit its
// stale analysis.
function getRowId(paper: PaperResult, index: number): string {
  return paper.doi ? `doi-${encodeURIComponent(paper.doi)}` : `idx-${index}`
}

export default function SearchPage() {
  const navigate = useNavigate()

  const [keyword, setKeyword] = useState('')
  const [yearFrom, setYearFrom] = useState<number | ''>('')
  const [yearTo, setYearTo] = useState<number | ''>('')
  const [limit, setLimit] = useState(20)
  const [formError, setFormError] = useState<string | null>(null)
  const [submittedQuery, setSubmittedQuery] = useState<SearchParams | null>(null)
  const [selectedRows, setSelectedRows] = useState<GridRow[]>([])
  const [analysisByRowId, setAnalysisByRowId] = useState<Record<string, PaperAnalysis | null>>({})

  const { data, isFetching, isError, error } = useSearchPapers(submittedQuery)
  const exportMutation = useExportPapers()
  const analyzeMutation = useAnalyzePapers()
  const compareMutation = useComparePapers()

  const handleSearch = useCallback(
    (event: FormEvent) => {
      event.preventDefault()

      const trimmedKeyword = keyword.trim()
      if (!trimmedKeyword) {
        setFormError('Enter a keyword to search.')
        return
      }
      if (yearFrom !== '' && yearTo !== '' && yearFrom > yearTo) {
        setFormError('"From" year must not be after "To" year.')
        return
      }

      setFormError(null)
      setAnalysisByRowId({})
      setSubmittedQuery({
        keyword: trimmedKeyword,
        yearFrom: yearFrom === '' ? undefined : yearFrom,
        yearTo: yearTo === '' ? undefined : yearTo,
        limit,
      })
    },
    [keyword, yearFrom, yearTo, limit],
  )

  const rowData = useMemo<GridRow[]>(
    () =>
      (data?.results ?? []).map((paper, index) => {
        const _id = getRowId(paper, index)
        const analysis = analysisByRowId[_id]
        return {
          ...paper,
          _id,
          battery_system: analysis?.battery_system ?? null,
          electrolyte: analysis?.electrolyte ?? null,
          main_contribution: analysis?.innovation ?? null,
        }
      }),
    [data, analysisByRowId],
  )

  const columnDefs = useMemo<ColDef<GridRow>[]>(
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
      {
        headerName: 'Journal',
        field: 'journal',
        flex: 1,
        minWidth: 130,
        valueFormatter: (params: ValueFormatterParams<GridRow>) => params.value ?? '—',
      },
      { headerName: 'Year', field: 'year', width: 90 },
      {
        headerName: 'Citation Count',
        field: 'citation_count',
        width: 130,
        valueFormatter: (params: ValueFormatterParams<GridRow>) => (params.value ?? 0).toLocaleString(),
      },
      {
        headerName: 'Battery System',
        field: 'battery_system',
        flex: 1,
        minWidth: 130,
        valueFormatter: (params: ValueFormatterParams<GridRow>) => params.value ?? '—',
      },
      {
        headerName: 'Electrolyte',
        field: 'electrolyte',
        flex: 1.5,
        minWidth: 200,
        valueFormatter: (params: ValueFormatterParams<GridRow>) => truncate(params.value ?? null, 80),
      },
      {
        headerName: 'Main Contribution',
        field: 'main_contribution',
        flex: 2,
        minWidth: 260,
        wrapText: true,
        autoHeight: true,
        valueFormatter: (params: ValueFormatterParams<GridRow>) => truncate(params.value ?? null, 160),
      },
    ],
    [],
  )

  const handleRowClicked = useCallback(
    (event: RowClickedEvent<GridRow>) => {
      if (!event.data) return
      navigate(`/paper/${event.data._id}`, { state: { paper: event.data } })
    },
    [navigate],
  )

  const handleSelectionChanged = useCallback((event: SelectionChangedEvent<GridRow>) => {
    setSelectedRows(event.api.getSelectedRows())
  }, [])

  const handleExport = useCallback(() => {
    const papers: PaperResult[] = selectedRows.map(
      ({ _id, battery_system, electrolyte, main_contribution, ...paper }) => paper,
    )
    exportMutation.mutate(papers)
  }, [selectedRows, exportMutation])

  const handleAnalyzeResults = useCallback(() => {
    const papers = data?.results ?? []
    analyzeMutation.mutate(papers, {
      onSuccess: (results) => {
        setAnalysisByRowId((previous) => {
          const next = { ...previous }
          papers.forEach((paper, index) => {
            next[getRowId(paper, index)] = results[index]
          })
          return next
        })
      },
    })
  }, [data, analyzeMutation])

  const handleCompare = useCallback(() => {
    const papers: PaperResult[] = selectedRows.map(
      ({ _id, battery_system, electrolyte, main_contribution, ...paper }) => paper,
    )
    compareMutation.mutate(papers, {
      onSuccess: (result) => {
        navigate('/compare', { state: result })
      },
    })
  }, [selectedRows, compareMutation, navigate])

  return (
    <section className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">Search battery literature</h1>
        <p className="text-sm text-slate-500">
          Searches Semantic Scholar first, automatically falling back to OpenAlex if it's unavailable.
        </p>
      </div>

      <form onSubmit={handleSearch} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5">
        <div className="flex flex-col gap-4 md:flex-row md:items-end md:gap-3">
          <div className="flex-1">
            <label htmlFor="keyword" className="mb-1 block text-xs font-medium text-slate-500">
              Keyword
            </label>
            <input
              id="keyword"
              type="text"
              value={keyword}
              onChange={(event) => setKeyword(event.target.value)}
              placeholder="e.g. solid electrolyte interphase"
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
            />
          </div>

          <div className="flex gap-3">
            <div>
              <label htmlFor="year-from" className="mb-1 block text-xs font-medium text-slate-500">
                From
              </label>
              <select
                id="year-from"
                value={yearFrom}
                onChange={(event) => setYearFrom(event.target.value ? Number(event.target.value) : '')}
                className="rounded-lg border border-slate-300 px-2 py-2 text-sm text-slate-900 focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
              >
                <option value="">Any</option>
                {YEAR_OPTIONS.map((year) => (
                  <option key={year} value={year}>
                    {year}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="year-to" className="mb-1 block text-xs font-medium text-slate-500">
                To
              </label>
              <select
                id="year-to"
                value={yearTo}
                onChange={(event) => setYearTo(event.target.value ? Number(event.target.value) : '')}
                className="rounded-lg border border-slate-300 px-2 py-2 text-sm text-slate-900 focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
              >
                <option value="">Any</option>
                {YEAR_OPTIONS.map((year) => (
                  <option key={year} value={year}>
                    {year}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label htmlFor="limit" className="mb-1 block text-xs font-medium text-slate-500">
              Papers
            </label>
            <select
              id="limit"
              value={limit}
              onChange={(event) => setLimit(Number(event.target.value))}
              className="rounded-lg border border-slate-300 px-2 py-2 text-sm text-slate-900 focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
            >
              {PAPER_LIMIT_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </div>

          <button
            type="submit"
            disabled={isFetching}
            className="rounded-lg bg-slate-900 px-5 py-2 text-sm font-medium text-white transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isFetching ? 'Searching…' : 'Search'}
          </button>
        </div>

        {formError && <p className="mt-3 text-sm text-red-600">{formError}</p>}
      </form>

      {submittedQuery === null && (
        <div className="rounded-xl border border-dashed border-slate-300 p-10 text-center text-sm text-slate-400">
          Enter a keyword and click Search to see results.
        </div>
      )}

      {submittedQuery !== null && (
        <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 px-4 py-3 text-sm text-slate-500">
            <div className="flex items-center gap-2">
              {data && (
                <span>
                  {data.count} result{data.count === 1 ? '' : 's'} via {formatSourceName(data.source)}
                </span>
              )}
              {selectedRows.length > 0 && (
                <span className="text-slate-400">· {selectedRows.length} selected</span>
              )}
            </div>
            <div className="flex flex-wrap items-center gap-3">
              {(isFetching || analyzeMutation.isPending || compareMutation.isPending) && <LoadingSpinner />}
              <button
                type="button"
                onClick={handleAnalyzeResults}
                disabled={!data || data.results.length === 0 || analyzeMutation.isPending}
                className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {analyzeMutation.isPending ? 'Analyzing…' : 'Analyze Results'}
              </button>
              <button
                type="button"
                onClick={handleCompare}
                disabled={selectedRows.length === 0 || compareMutation.isPending}
                className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {compareMutation.isPending ? 'Comparing…' : `Compare Selected (${selectedRows.length})`}
              </button>
              <button
                type="button"
                onClick={handleExport}
                disabled={selectedRows.length === 0 || exportMutation.isPending}
                className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {exportMutation.isPending ? 'Exporting…' : `Export Selected (${selectedRows.length})`}
              </button>
            </div>
          </div>

          {exportMutation.isError && (
            <div className="border-b border-slate-100 px-4 py-2 text-xs text-red-600">
              Export failed. Please try again.
            </div>
          )}
          {analyzeMutation.isError && (
            <div className="border-b border-slate-100 px-4 py-2 text-xs text-red-600">
              {getErrorMessage(analyzeMutation.error, 'Analysis failed. Please try again.')}
            </div>
          )}
          {compareMutation.isError && (
            <div className="border-b border-slate-100 px-4 py-2 text-xs text-red-600">
              {getErrorMessage(compareMutation.error, 'Comparison failed. Please try again.')}
            </div>
          )}

          {isError && (
            <div className="p-6 text-sm text-red-600">
              Search failed: {error instanceof Error ? error.message : 'please try again.'}
            </div>
          )}

          {!isError && data && data.results.length === 0 && (
            <div className="p-6 text-sm text-slate-500">No papers found for this query.</div>
          )}

          {!isError && data && data.results.length > 0 && (
            <div className="ag-theme-quartz h-[65vh] w-full p-2">
              <AgGridReact<GridRow>
                rowData={rowData}
                columnDefs={columnDefs}
                onRowClicked={handleRowClicked}
                onSelectionChanged={handleSelectionChanged}
                rowSelection={{ mode: 'multiRow', checkboxes: true, headerCheckbox: true }}
                rowStyle={{ cursor: 'pointer' }}
                animateRows
                defaultColDef={{ resizable: true, sortable: true }}
              />
            </div>
          )}

          {!isError && !data && isFetching && (
            <div className="flex items-center justify-center gap-2 p-10 text-sm text-slate-500">
              <LoadingSpinner />
              Searching…
            </div>
          )}
        </div>
      )}
    </section>
  )
}
