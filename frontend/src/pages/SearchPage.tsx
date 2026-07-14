import 'ag-grid-community/styles/ag-grid.css'
import 'ag-grid-community/styles/ag-theme-quartz.css'

import { AgGridReact } from 'ag-grid-react'
import { useCallback, useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import type { ColDef, RowClickedEvent, ValueFormatterParams } from 'ag-grid-community'

import LoadingSpinner from '@/components/LoadingSpinner'
import { useSearchPapers } from '@/hooks/useSearchPapers'
import type { PaperResult, SearchParams } from '@/types/paper'

type GridRow = PaperResult & { _id: string }

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

export default function SearchPage() {
  const navigate = useNavigate()

  const [keyword, setKeyword] = useState('')
  const [yearFrom, setYearFrom] = useState<number | ''>('')
  const [yearTo, setYearTo] = useState<number | ''>('')
  const [limit, setLimit] = useState(20)
  const [formError, setFormError] = useState<string | null>(null)
  const [submittedQuery, setSubmittedQuery] = useState<SearchParams | null>(null)

  const { data, isFetching, isError, error } = useSearchPapers(submittedQuery)

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
      (data?.results ?? []).map((paper, index) => ({
        ...paper,
        _id: paper.doi ? `doi-${encodeURIComponent(paper.doi)}` : `idx-${index}`,
      })),
    [data],
  )

  const columnDefs = useMemo<ColDef<GridRow>[]>(
    () => [
      {
        headerName: 'Title',
        field: 'title',
        flex: 2,
        minWidth: 240,
        wrapText: true,
        autoHeight: true,
        cellClass: 'font-medium text-slate-900 leading-snug py-2',
      },
      {
        headerName: 'Journal',
        field: 'journal',
        flex: 1,
        minWidth: 140,
        valueFormatter: (params: ValueFormatterParams<GridRow>) => params.value ?? '—',
      },
      { headerName: 'Year', field: 'year', width: 100 },
      {
        headerName: 'Citations',
        field: 'citation_count',
        width: 120,
        valueFormatter: (params: ValueFormatterParams<GridRow>) => (params.value ?? 0).toLocaleString(),
      },
      {
        headerName: 'DOI',
        field: 'doi',
        flex: 1,
        minWidth: 160,
        cellClass: 'font-mono text-xs text-slate-500',
        valueFormatter: (params: ValueFormatterParams<GridRow>) => params.value ?? '—',
      },
      {
        headerName: 'Abstract Preview',
        field: 'abstract',
        flex: 2,
        minWidth: 260,
        valueFormatter: (params: ValueFormatterParams<GridRow>) => truncate(params.value ?? null, 140),
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
          <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3 text-sm text-slate-500">
            {data ? (
              <span>
                {data.count} result{data.count === 1 ? '' : 's'} via {formatSourceName(data.source)}
              </span>
            ) : (
              <span>&nbsp;</span>
            )}
            {isFetching && <LoadingSpinner />}
          </div>

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
