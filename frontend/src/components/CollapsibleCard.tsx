import { useId, useState } from 'react'
import type { ReactNode } from 'react'

interface CollapsibleCardProps {
  title: string
  defaultOpen?: boolean
  children: ReactNode
}

export default function CollapsibleCard({ title, defaultOpen = false, children }: CollapsibleCardProps) {
  const [open, setOpen] = useState(defaultOpen)
  const contentId = useId()

  return (
    <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        aria-controls={contentId}
        className="flex w-full items-center justify-between px-5 py-3 text-left text-sm font-medium text-slate-900 transition hover:bg-slate-50"
      >
        {title}
        <svg
          className={`h-4 w-4 shrink-0 text-slate-400 transition-transform ${open ? 'rotate-180' : ''}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
          aria-hidden="true"
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {open && (
        <div id={contentId} className="border-t border-slate-100 px-5 py-4">
          {children}
        </div>
      )}
    </div>
  )
}
