import { useState, useEffect, useRef, useCallback } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import { apiFetch } from './lib/api';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import Login from './pages/Login';
import UploadValidation from './pages/UploadValidation';
import AdminDashboard from './pages/AdminDashboard';
import ChangePassword from './pages/ChangePassword';
import { Clock, LogOut } from 'lucide-react';

// ---------------------------------------------------------------------------
// Inactivity timeout — HIPAA §164.312(a)(2)(iii)
// ---------------------------------------------------------------------------
const WARN_AFTER_MS  = 13 * 60 * 1000; // show warning at 13 min
const LOGOUT_AFTER_MS = 15 * 60 * 1000; // force logout at 15 min
const WARNING_DURATION_S = (LOGOUT_AFTER_MS - WARN_AFTER_MS) / 1000; // 120 s

// Reissue the session cookie every 10 minutes while the user is signed in,
// so an actively working user never hits the token's fixed expiry. Idle users
// are logged out by the inactivity monitor long before the token matters.
const SESSION_REFRESH_MS = 10 * 60 * 1000;

function SessionKeepAlive() {
  const { user } = useAuth();

  useEffect(() => {
    if (!user) return;
    const id = setInterval(() => {
      apiFetch('/api/auth/refresh', { method: 'POST' }).catch(() => {});
    }, SESSION_REFRESH_MS);
    return () => clearInterval(id);
  }, [user]);

  return null;
}

function InactivityMonitor() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const warnTimer   = useRef<ReturnType<typeof setTimeout> | null>(null);
  const logoutTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const tickRef     = useRef<ReturnType<typeof setInterval> | null>(null);
  const [showWarning, setShowWarning] = useState(false);
  const [secondsLeft, setSecondsLeft] = useState(WARNING_DURATION_S);

  const clearAll = () => {
    if (warnTimer.current)   clearTimeout(warnTimer.current);
    if (logoutTimer.current) clearTimeout(logoutTimer.current);
    if (tickRef.current)     clearInterval(tickRef.current);
  };

  const doLogout = useCallback(async () => {
    clearAll();
    setShowWarning(false);
    await logout();
    navigate('/login', { replace: true });
  }, [logout, navigate]);

  const reset = useCallback(() => {
    clearAll();
    setShowWarning(false);
    setSecondsLeft(WARNING_DURATION_S);

    warnTimer.current = setTimeout(() => {
      setShowWarning(true);
      setSecondsLeft(WARNING_DURATION_S);
      tickRef.current = setInterval(() => {
        setSecondsLeft(s => (s <= 1 ? 0 : s - 1));
      }, 1000);
    }, WARN_AFTER_MS);

    logoutTimer.current = setTimeout(doLogout, LOGOUT_AFTER_MS);
  }, [doLogout]);

  useEffect(() => {
    if (!user) return;
    const events = ['mousemove', 'mousedown', 'keydown', 'touchstart', 'scroll'] as const;
    events.forEach(e => window.addEventListener(e, reset, { passive: true }));
    reset();
    return () => {
      events.forEach(e => window.removeEventListener(e, reset));
      clearAll();
    };
  }, [user, reset]);

  if (!user || !showWarning) return null;

  const mins = Math.floor(secondsLeft / 60);
  const secs = String(secondsLeft % 60).padStart(2, '0');

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-2xl p-8 max-w-md w-full mx-4">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 bg-amber-100 rounded-full flex items-center justify-center flex-shrink-0">
            <Clock className="w-5 h-5 text-amber-600" />
          </div>
          <h2 className="text-lg font-semibold text-slate-900">Session Expiring Soon</h2>
        </div>
        <p className="text-slate-600 mb-2">
          Your session will end automatically due to inactivity in:
        </p>
        <div className="text-5xl font-bold text-amber-600 text-center my-5 tabular-nums">
          {mins}:{secs}
        </div>
        <p className="text-sm text-slate-500 mb-6 text-center">
          Any unsaved work may be lost.
        </p>
        <div className="flex gap-3">
          <button
            onClick={reset}
            className="flex-1 py-2.5 px-4 bg-emerald-600 text-white font-semibold rounded-lg hover:bg-emerald-700 transition-colors"
          >
            Stay Logged In
          </button>
          <button
            onClick={doLogout}
            className="flex items-center justify-center gap-2 py-2.5 px-4 bg-white text-slate-700 font-semibold rounded-lg border border-slate-200 hover:bg-slate-50 transition-colors"
          >
            <LogOut className="w-4 h-4" />
            Log Out
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Route guards
// ---------------------------------------------------------------------------
function ProtectedRoute({ children, adminOnly = false }: { children: React.ReactNode; adminOnly?: boolean }) {
  const { user, isLoading } = useAuth();

  if (isLoading) return <Spinner />;
  if (!user) return <Navigate to="/login" replace />;
  if (user.must_change_password) return <Navigate to="/change-password" replace />;
  if (adminOnly && user.role !== 'admin') return <Navigate to="/upload" replace />;

  return <>{children}</>;
}

function Spinner() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50">
      <div className="w-10 h-10 border-4 border-emerald-600 border-t-transparent rounded-full animate-spin" />
    </div>
  );
}

// ---------------------------------------------------------------------------
// App shell — routes + inactivity monitor
// ---------------------------------------------------------------------------
function AppShell() {
  const { user, isLoading, login, logout, refreshUser } = useAuth();

  if (isLoading) return <Spinner />;

  return (
    <>
      <InactivityMonitor />
      <SessionKeepAlive />
      <Routes>
        <Route
          path="/login"
          element={
            user && !user.must_change_password
              ? <Navigate to={user.role === 'admin' ? '/admin' : '/upload'} replace />
              : <Login onLogin={login} />
          }
        />
        <Route
          path="/change-password"
          element={
            !user
              ? <Navigate to="/login" replace />
              : <ChangePassword onPasswordChanged={refreshUser} />
          }
        />
        <Route
          path="/upload"
          element={
            <ProtectedRoute>
              <UploadValidation onLogout={logout} />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin"
          element={
            <ProtectedRoute adminOnly>
              <AdminDashboard onLogout={logout} />
            </ProtectedRoute>
          }
        />
        <Route
          path="*"
          element={
            <Navigate
              to={!user ? '/login' : user.role === 'admin' ? '/admin' : '/upload'}
              replace
            />
          }
        />
      </Routes>
    </>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100">
          <AppShell />
        </div>
      </AuthProvider>
    </BrowserRouter>
  );
}
