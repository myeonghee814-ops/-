import { Link, Outlet } from 'react-router-dom'

export default function MainLayout() {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="sticky top-0 z-10 border-b border-slate-200 bg-white/80 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 sm:px-6">
          <Link to="/" className="flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-md bg-slate-900 text-sm font-bold text-white">
              B
            </span>
            <span className="text-base font-semibold tracking-tight">BLIP</span>
          </Link>
          <span className="hidden text-sm text-slate-500 sm:block">
            Battery Literature Intelligence Platform
          </span>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 sm:py-8">
        <Outlet />
      </main>
    </div>
  )
}
