import { BrowserRouter, Navigate, Route, Routes } from 'react-router'
import { AuthProvider, useAuth } from './auth/AuthContext'
import { Loading, ToastProvider } from './components'
import ErrorBoundary from './components/ErrorBoundary'
import { homeFor } from './components/navigation'
import RequireAuth from './layouts/RequireAuth'
import { AdminAuditLogPage, AdminCoursesPage, AdminDepartmentsPage, AdminSettingsPage, AdminUserPage, AdminUsersPage } from './pages/admin/AdminPages'
import AdminOverview from './pages/admin/AdminOverview'
import ComponentsPage from './pages/ComponentsPage'
import CourseManagePage from './pages/courses/CourseManagePage'
import CoursePage from './pages/courses/CoursePage'
import JoinRequestsPage from './pages/courses/JoinRequestsPage'
import MyCoursesPage from './pages/courses/MyCoursesPage'
import DashboardPage from './pages/dashboard/DashboardPage'
import NotificationsPage from './pages/notifications/NotificationsPage'
import ChangePasswordPage from './pages/profile/PasswordForm'
import ProfilePage from './pages/profile/ProfilePage'
import AboutPage from './pages/public/AboutPage'
import { ForgotPasswordPage, ResetPasswordPage, VerifyEmailPage } from './pages/public/AccountLinkPages'
import CataloguePage from './pages/public/CataloguePage'
import InvitationPage from './pages/public/InvitationPage'
import LoginPage from './pages/public/LoginPage'
import NotFoundPage from './pages/public/NotFoundPage'
import ReviewPage from './pages/reviews/ReviewPage'
import AssignmentPage from './pages/teams/AssignmentPage'
import TeamWorkspacePage from './pages/teams/TeamWorkspacePage'

// "/" is the catalogue for visitors and the dashboard for logged-in users.
function Home() {
  const { user, status } = useAuth()
  if (status === 'loading') return <Loading />
  return status === 'in' ? <Navigate to={homeFor(user.role)} replace /> : <Navigate to="/catalogue" replace />
}

const signedIn = (page, roles) => <RequireAuth roles={roles}>{page}</RequireAuth>
const STAFF = ['teacher', 'admin']
const ADMIN = ['admin']

// Every page of the site. Paths match the links the backend puts in emails and
// notifications (/teams/12, /courses/3/manage, /invitations/<token>, /reset-password ...).
export default function App() {
  return (
    <ErrorBoundary>
    <BrowserRouter>
      <AuthProvider>
        <ToastProvider>
          <Routes>
            <Route path="/" element={<Home />} />
            {/* Public pages */}
            <Route path="/catalogue" element={<CataloguePage />} />
            <Route path="/about" element={<AboutPage />} />
            <Route path="/login" element={<LoginPage mode="login" />} />
            <Route path="/signup" element={<LoginPage mode="signup" />} />
            <Route path="/forgot-password" element={<ForgotPasswordPage />} />
            <Route path="/reset-password" element={<ResetPasswordPage />} />
            <Route path="/verify-email" element={<VerifyEmailPage />} />
            <Route path="/invitations/:token" element={<InvitationPage />} />
            <Route path="/invitations" element={<InvitationPage />} />
            <Route path="/courses/:courseId" element={<CoursePage />} />

            {/* Signed-in pages */}
            <Route path="/change-password" element={signedIn(<ChangePasswordPage />)} />
            <Route path="/dashboard" element={signedIn(<DashboardPage />)} />
            <Route path="/courses" element={signedIn(<MyCoursesPage />)} />
            <Route path="/courses/:courseId/manage" element={signedIn(<CourseManagePage />, STAFF)} />
            <Route path="/join-requests" element={signedIn(<JoinRequestsPage />, STAFF)} />
            <Route path="/assignments/:assignmentId" element={signedIn(<AssignmentPage />)} />
            <Route path="/assignments/:assignmentId/review" element={signedIn(<ReviewPage />, STAFF)} />
            <Route path="/teams/:teamId" element={signedIn(<TeamWorkspacePage />)} />
            <Route path="/teams/:teamId/marks" element={signedIn(<TeamWorkspacePage />)} />
            <Route path="/notifications" element={signedIn(<NotificationsPage />)} />
            <Route path="/profile" element={signedIn(<ProfilePage />)} />

            {/* Admin pages */}
            <Route path="/admin" element={signedIn(<AdminOverview />, ADMIN)} />
            <Route path="/admin/users" element={signedIn(<AdminUsersPage />, ADMIN)} />
            <Route path="/admin/users/:userId" element={signedIn(<AdminUserPage />, ADMIN)} />
            <Route path="/admin/courses" element={signedIn(<AdminCoursesPage />, ADMIN)} />
            <Route path="/admin/departments" element={signedIn(<AdminDepartmentsPage />, ADMIN)} />
            <Route path="/admin/audit-log" element={signedIn(<AdminAuditLogPage />, ADMIN)} />
            <Route path="/admin/settings" element={signedIn(<AdminSettingsPage />, ADMIN)} />

            {/* Shared components with the design's demo data, for checking against Figma */}
            <Route path="/dev/components" element={<ComponentsPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </ToastProvider>
      </AuthProvider>
    </BrowserRouter>
    </ErrorBoundary>
  )
}
