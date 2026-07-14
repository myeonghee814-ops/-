import { useLocation, useNavigate, useParams } from 'react-router-dom'

import type { PaperResult } from '@/types/paper'

export default function PaperDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const location = useLocation()

  // Search results aren't persisted yet (see docs/ARCHITECTURE.md), so
  // there's no GET /paper/:id backend endpoint to fetch from. The row the
  // user clicked is passed via router state instead.
  const paper = (location.state as { paper?: PaperResult } | undefined)?.paper

  return (
    <section className="space-y-4">
      <button
        onClick={() => navigate(-1)}
        className="text-sm text-slate-500 transition hover:text-slate-900"
      >
        ← Back to search
      </button>

      {!paper ? (
        <div className="rounded-xl border border-slate-200 bg-white p-6 text-sm text-slate-500">
          <p>No details available for paper "{id}".</p>
          <p className="mt-1">Open this page from a search result to see its contents.</p>
        </div>
      ) : (
        <article className="space-y-4 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h1 className="text-xl font-semibold text-slate-900">{paper.title}</h1>

          <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-slate-500">
            {paper.journal && <span>{paper.journal}</span>}
            {paper.year && <span>{paper.year}</span>}
            <span>{(paper.citation_count ?? 0).toLocaleString()} citations</span>
            {paper.doi && <span className="font-mono">DOI: {paper.doi}</span>}
          </div>

          {paper.authors.length > 0 && <p className="text-sm text-slate-600">{paper.authors.join(', ')}</p>}

          {paper.abstract && <p className="leading-relaxed text-slate-700">{paper.abstract}</p>}

          {paper.pdf_url && (
            <a
              href={paper.pdf_url}
              target="_blank"
              rel="noreferrer"
              className="inline-block text-sm font-medium text-slate-900 underline underline-offset-2 hover:text-slate-600"
            >
              View PDF ↗
            </a>
          )}
        </article>
      )}
    </section>
  )
}
