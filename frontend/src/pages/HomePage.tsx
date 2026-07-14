import LoadingSpinner from '@/components/LoadingSpinner'
import { useHealthCheck } from '@/hooks/useHealthCheck'

export default function HomePage() {
  const { data, isLoading, isError } = useHealthCheck()

  return (
    <section className="space-y-4">
      <h1 className="text-2xl font-semibold">Dashboard</h1>
      <p className="text-slate-600">
        Paper search, organization, and summarization are not implemented yet — this page only
        proves the frontend and backend are wired together end to end.
      </p>

      <div className="rounded-lg border border-slate-200 bg-white p-4">
        <h2 className="mb-2 text-sm font-medium text-slate-500">Backend status</h2>
        {isLoading && <LoadingSpinner />}
        {isError && <p className="text-red-600">Could not reach the backend API.</p>}
        {data && (
          <p className="text-emerald-600">
            {data.app_name} is {data.status} ({data.environment})
          </p>
        )}
      </div>
    </section>
  )
}
