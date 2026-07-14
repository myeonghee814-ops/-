import { Route, Routes } from 'react-router-dom'

import MainLayout from './layouts/MainLayout'
import NotFoundPage from './pages/NotFoundPage'
import PaperDetailPage from './pages/PaperDetailPage'
import SearchPage from './pages/SearchPage'

export default function App() {
  return (
    <Routes>
      <Route element={<MainLayout />}>
        <Route index element={<SearchPage />} />
        <Route path="paper/:id" element={<PaperDetailPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}
