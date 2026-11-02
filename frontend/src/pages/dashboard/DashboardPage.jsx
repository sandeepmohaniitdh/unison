import { Navigate } from 'react-router'
import { useAuth } from '../../auth/AuthContext'
import StudentDashboard from './StudentDashboard'
import TeacherDashboard from './TeacherDashboard'

// Everyone lands on their own role's dashboard (Figma 05, 07 and 10).
export default function DashboardPage() {
  const { user } = useAuth()
  if (user.role === 'admin') return <Navigate to="/admin" replace />
  return user.role === 'teacher' ? <TeacherDashboard /> : <StudentDashboard />
}
