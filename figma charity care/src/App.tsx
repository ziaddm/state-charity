import { useState } from 'react';
import LoginPage from './components/LoginPage';
import UploadPage from './components/UploadPage';

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
        <LoginPage onLogin={handleLogin} />
      ) : (
        <UploadPage onLogout={handleLogout} />
      )}
    </div>
  );
}
