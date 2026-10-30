import { lazy, Suspense } from 'react'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import LoadingSpinner from './components/LoadingSpinner.jsx'
import { AuthProvider } from './context/AuthContext.jsx'
import { ToastProvider } from './context/ToastContext.jsx'
import { ProtectedRoute } from './components/ProtectedRoute.jsx'

const AuthLayout = lazy(() => import('./layouts/AuthLayout.jsx'))
const MainLayout = lazy(() => import('./layouts/MainLayout.jsx'))
const Forbidden = lazy(() => import('./pages/Forbidden.jsx'))
const Home = lazy(() => import('./pages/Home.jsx'))
const Login = lazy(() => import('./pages/Login.jsx'))
const NotFound = lazy(() => import('./pages/NotFound.jsx'))

/**
 * Declares the lazy-loaded public and authenticated application routes.
 *
 * @returns {JSX.Element}
 */
function App() {
  return (
    <BrowserRouter
      future={{
        v7_relativeSplatPath: true,
        v7_startTransition: true,
      }}
    >
      <AuthProvider>
        <ToastProvider>
          <Suspense
            fallback={
              <div className="min-vh-100 d-grid place-items-center text-center">
                <LoadingSpinner label="Loading application" />
              </div>
            }
          >
            <Routes>
              <Route element={<AuthLayout />}>
                <Route path="/login" element={<Login />} />
              </Route>
              <Route element={<ProtectedRoute />}>
                <Route path="/403" element={<Forbidden />} />
                <Route element={<MainLayout />}>
                  <Route index element={<Home />} />
                  <Route path="*" element={<NotFound />} />
                </Route>
              </Route>
            </Routes>
          </Suspense>
        </ToastProvider>
      </AuthProvider>
    </BrowserRouter>
  )
}

export default App
