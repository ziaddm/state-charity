import { useState, useEffect } from 'react';
import Login from './pages/Login';
import AdminDashboard from './pages/AdminDashboard';
import UploadValidation from './pages/UploadValidation';
import ChangePassword from './pages/ChangePassword';

export default function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [userRole, setUserRole] = useState<string>('');
  const [mustChangePassword, setMustChangePassword] = useState(false);

  // Check if user is already logged in
  useEffect(() => {
    const token = localStorage.getItem('token');
    const role = localStorage.getItem('role');
    if (token && role) {
      setIsAuthenticated(true);
      setUserRole(role);
    }
  }, []);

  const handleLogin = () => {
    const role = localStorage.getItem('role');
    const mustChange = localStorage.getItem('must_change_password') === 'true';
    setUserRole(role || '');
    setMustChangePassword(mustChange);
    setIsAuthenticated(true);
  };

  const handlePasswordChanged = () => {
    localStorage.removeItem('must_change_password');
    setMustChangePassword(false);
  };

  const handleLogout = () => {
    // Clear all auth data
    localStorage.removeItem('token');
    localStorage.removeItem('userId');
    localStorage.removeItem('email');
    localStorage.removeItem('role');
    localStorage.removeItem('must_change_password');
    setIsAuthenticated(false);
    setUserRole('');
    setMustChangePassword(false);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100">
      {!isAuthenticated ? (
        <Login onLogin={handleLogin} />
      ) : mustChangePassword ? (
        <ChangePassword onPasswordChanged={handlePasswordChanged} />
      ) : userRole === 'admin' ? (
        <AdminDashboard onLogout={handleLogout} />
      ) : (
        <UploadValidation onLogout={handleLogout} />
      )}
    </div>
  );
}
