import { useState } from 'react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card } from '../components/ui/card';
import { HeartPulse, ArrowRight } from 'lucide-react';

interface LoginProps {
  onLogin: () => void;
}

export default function Login({ onLogin }: LoginProps) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);

    try {
      const response = await fetch('http://localhost:8000/api/auth/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email, password }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Login failed');
      }

      const data = await response.json();

      // Store token in localStorage
      localStorage.setItem('token', data.token);
      localStorage.setItem('userId', data.user_id);
      localStorage.setItem('email', data.email);
      localStorage.setItem('role', data.role);
      if (data.must_change_password) {
        localStorage.setItem('must_change_password', 'true');
      }

      // Call the onLogin callback to update app state
      onLogin();
    } catch (error) {
      alert(`Login failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex">
      {/* Left Side - Branding with Geometric Background */}
      <div className="hidden lg:flex lg:w-1/2 bg-gradient-to-br from-emerald-600 via-teal-600 to-cyan-600 p-12 flex-col justify-between relative overflow-hidden">
        {/* Geometric Shapes */}
        <div className="absolute inset-0">
          {/* Large Circle - Top Right */}
          <div className="absolute -top-20 -right-20 w-80 h-80 bg-white/10 rounded-full"></div>

          {/* Medium Circle - Bottom Left */}
          <div className="absolute -bottom-16 -left-16 w-64 h-64 bg-white/10 rounded-full"></div>

          {/* Small Circle - Middle */}
          <div className="absolute top-1/2 left-1/3 w-32 h-32 bg-white/5 rounded-full"></div>

          {/* Square - Top Left */}
          <div className="absolute top-40 left-20 w-24 h-24 bg-white/10 rotate-12 rounded-lg"></div>

          {/* Rectangle - Bottom Right */}
          <div className="absolute bottom-32 right-32 w-40 h-24 bg-white/10 -rotate-12 rounded-lg"></div>

          {/* Triangle - Using border trick */}
          <div className="absolute top-1/3 right-1/4 w-0 h-0 border-l-[50px] border-l-transparent border-r-[50px] border-r-transparent border-b-[80px] border-b-white/10"></div>
        </div>

        {/* Logo at top */}
        <div className="relative z-10">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-14 h-14 bg-white/20 backdrop-blur-sm rounded-2xl flex items-center justify-center">
              <HeartPulse className="w-8 h-8 text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white">CharityCare</h1>
              <p className="text-emerald-100 text-sm">Compliance Portal</p>
            </div>
          </div>
        </div>

        {/* Copyright at bottom */}
        <p className="text-emerald-100 text-sm relative z-10">© 2025 CharityCare Portal</p>
      </div>

      {/* Right Side - Login Form */}
      <div className="flex-1 flex items-center justify-center p-8 bg-slate-50">
        <div className="w-full max-w-md">
          <div className="lg:hidden mb-8 text-center">
            <div className="inline-flex items-center justify-center w-16 h-16 bg-gradient-to-br from-emerald-600 to-cyan-600 rounded-2xl mb-4">
              <HeartPulse className="w-8 h-8 text-white" />
            </div>
            <h1 className="text-2xl font-bold text-slate-900 mb-2">CharityCare Portal</h1>
          </div>

          <div className="mb-8">
            <h2 className="text-3xl font-bold text-slate-900 mb-2">Welcome</h2>
            <p className="text-slate-600">Sign in to access the portal</p>
          </div>

          <Card className="border-0 shadow-lg">
            <form onSubmit={handleSubmit} className="p-8 space-y-6">
              <div className="space-y-2">
                <Label htmlFor="email" className="text-slate-700">Email Address</Label>
                <Input
                  id="email"
                  type="email"
                  placeholder="name@clinic.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  className="h-12 border-slate-300 focus:border-emerald-500 focus:ring-emerald-500"
                />
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label htmlFor="password" className="text-slate-700">Password</Label>
                </div>
                <Input
                  id="password"
                  type="password"
                  placeholder="Enter your password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  className="h-12 border-slate-300 focus:border-emerald-500 focus:ring-emerald-500"
                />
              </div>

              <Button
                type="submit"
                className="w-full h-12 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-700 hover:to-teal-700 shadow-lg shadow-emerald-500/30"
                disabled={isLoading}
              >
                {isLoading ? (
                  <div className="flex items-center gap-2">
                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    Signing in...
                  </div>
                ) : (
                  <div className="flex items-center gap-2">
                    Sign In
                    <ArrowRight className="w-4 h-4" />
                  </div>
                )}
              </Button>
            </form>
          </Card>

          <p className="text-center text-slate-500 text-sm mt-6">
            Need assistance? Contact your system administrator.
          </p>
        </div>
      </div>
    </div>
  );
}
