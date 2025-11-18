import { useState } from 'react';
import Login from './pages/Login';
import UploadValidation from './pages/UploadValidation';

export default function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  const handleLogin = () => {
    setIsAuthenticated(true);
  };

  const handleLogout = () => {
    setIsAuthenticated(false);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100">
      {!isAuthenticated ? (
        <Login onLogin={handleLogin} />
      ) : (
        <UploadValidation onLogout={handleLogout} />
      )}
    </div>
  );
}
