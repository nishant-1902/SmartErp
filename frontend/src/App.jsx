import { lazy, Suspense } from 'react'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import LoadingSpinner from './components/LoadingSpinner.jsx'
import { AuthProvider } from './context/AuthContext.jsx'
import { ToastProvider } from './context/ToastContext.jsx'
import { ProtectedRoute, RoleRoute } from './components/ProtectedRoute.jsx'

const AuthLayout = lazy(() => import('./layouts/AuthLayout.jsx'))
const MainLayout = lazy(() => import('./layouts/MainLayout.jsx'))
const Forbidden = lazy(() => import('./pages/Forbidden.jsx'))
const Home = lazy(() => import('./pages/Home.jsx'))
const Employees = lazy(() => import('./pages/Employees.jsx'))
const EmployeeProfile = lazy(() => import('./pages/EmployeeProfile.jsx'))
const Departments = lazy(() => import('./pages/Departments.jsx'))
const Products = lazy(() => import('./pages/Products.jsx'))
const ProductDetail = lazy(() => import('./pages/ProductDetail.jsx'))
const Inventory = lazy(() => import('./pages/Inventory.jsx'))
const StockMovements = lazy(() => import('./pages/StockMovements.jsx'))
const Users = lazy(() => import('./pages/Users.jsx'))
const Profile = lazy(() => import('./pages/Profile.jsx'))
const Settings = lazy(() => import('./pages/Settings.jsx'))
const AuditLogs = lazy(() => import('./pages/AuditLogs.jsx'))
const ForgotPassword = lazy(() => import('./pages/ForgotPassword.jsx'))
const ResetPassword = lazy(() => import('./pages/ResetPassword.jsx'))
const Login = lazy(() => import('./pages/Login.jsx'))
const NotFound = lazy(() => import('./pages/NotFound.jsx'))

const employeeDirectoryRoles = [
  'super_admin',
  'hr_manager',
  'inventory_manager',
  'purchase_manager',
  'sales_manager',
]

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
                <Route path="/forgot-password" element={<ForgotPassword />} />
                <Route path="/reset-password" element={<ResetPassword />} />
              </Route>
              <Route element={<ProtectedRoute />}>
                <Route path="/403" element={<Forbidden />} />
                <Route element={<MainLayout />}>
                  <Route index element={<Home />} />
                  <Route
                    element={<RoleRoute permission="own-profile:read" />}
                    path="profile"
                  >
                    <Route index element={<Profile />} />
                  </Route>
                  <Route
                    element={<RoleRoute permission="own-password:change" />}
                    path="settings"
                  >
                    <Route index element={<Settings />} />
                  </Route>
                  <Route
                    element={<RoleRoute permission="users:manage" />}
                    path="users"
                  >
                    <Route index element={<Users />} />
                  </Route>
                  <Route
                    element={<RoleRoute permission="audit:read" />}
                    path="audit-logs"
                  >
                    <Route index element={<AuditLogs />} />
                  </Route>
                  <Route
                    element={
                      <RoleRoute
                        permission="employees:read"
                        roles={employeeDirectoryRoles}
                      />
                    }
                    path="employees"
                  >
                    <Route index element={<Employees />} />
                    <Route path=":employeeId" element={<EmployeeProfile />} />
                  </Route>
                  <Route
                    element={<RoleRoute permission="departments:read" />}
                    path="departments"
                  >
                    <Route index element={<Departments />} />
                  </Route>
                  <Route
                    element={<RoleRoute permission="products:read" />}
                    path="products"
                  >
                    <Route index element={<Products />} />
                    <Route
                      element={<RoleRoute permission="stock:read" />}
                      path=":productId"
                    >
                      <Route index element={<ProductDetail />} />
                    </Route>
                  </Route>
                  <Route
                    element={<RoleRoute permission="stock:read" />}
                    path="inventory"
                  >
                    <Route index element={<Inventory />} />
                  </Route>
                  <Route
                    element={<RoleRoute permission="stock:read" />}
                    path="stock-movements"
                  >
                    <Route index element={<StockMovements />} />
                  </Route>
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
