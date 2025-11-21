import { useState, useEffect } from 'react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { LogOut, UserPlus } from 'lucide-react';

interface Tenant {
  id: string;
  name: string;
}

interface AdminDashboardProps {
  onLogout: () => void;
}

export default function AdminDashboard({ onLogout }: AdminDashboardProps) {
  const [email, setEmail] = useState('');
  const [role, setRole] = useState('user');
  const [tenantId, setTenantId] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [messageType, setMessageType] = useState<'success' | 'error'>('success');
  const [tenants, setTenants] = useState<Tenant[]>([]);

  // Load tenants on mount
  useEffect(() => {
    const loadTenants = async () => {
      try {
        const token = localStorage.getItem('token');
        const response = await fetch('http://localhost:8000/api/validation/tenants', {
          headers: {
            'Authorization': `Bearer ${token}`,
          },
        });

        if (response.ok) {
          const data = await response.json();
          setTenants(data.tenants || []);
          // Auto-select first tenant
          if (data.tenants && data.tenants.length > 0) {
            setTenantId(data.tenants[0].id);
          }
        }
      } catch (error) {
        console.error('Failed to load tenants:', error);
      }
    };

    loadTenants();
  }, []);

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setMessage('');

    try {
      const token = localStorage.getItem('token');

      const response = await fetch('http://localhost:8000/api/auth/create-user', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({ email, role, tenant_id: tenantId }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to create user');
      }

      const data = await response.json();
      setMessageType('success');
      setMessage(`User created: ${data.email}. Temp password sent to their email.`);
      setEmail('');
      setRole('user');
      setTenantId('');
    } catch (error) {
      setMessageType('error');
      setMessage(`Error: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <div className="bg-white border-b border-slate-200">
        <div className="max-w-6xl mx-auto px-4 py-4 flex justify-between items-center">
          <h1 className="text-2xl font-bold text-slate-900">Admin Dashboard</h1>
          <Button
            onClick={onLogout}
            variant="outline"
            className="flex items-center gap-2"
          >
            <LogOut className="w-4 h-4" />
            Logout
          </Button>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-6xl mx-auto px-4 py-8">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          {/* Create User Card */}
          <Card className="border-slate-200 shadow-lg">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <UserPlus className="w-5 h-5 text-blue-600" />
                Create New User
              </CardTitle>
              <CardDescription>
                Create a new account for a clinic or staff member
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleCreateUser} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="email">Email Address</Label>
                  <Input
                    id="email"
                    type="email"
                    placeholder="clinic@example.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    className="border-slate-300"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="role">Role</Label>
                  <select
                    id="role"
                    value={role}
                    onChange={(e) => setRole(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="user">User</option>
                    <option value="admin">Admin</option>
                  </select>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="tenantId">Healthcare Facility</Label>
                  <select
                    id="tenantId"
                    value={tenantId}
                    onChange={(e) => setTenantId(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    required
                  >
                    <option value="">Select a facility...</option>
                    {tenants.map((tenant) => (
                      <option key={tenant.id} value={tenant.id}>
                        {tenant.name}
                      </option>
                    ))}
                  </select>
                </div>

                {message && (
                  <div
                    className={`p-3 rounded-md text-sm ${
                      messageType === 'success'
                        ? 'bg-green-50 text-green-800 border border-green-200'
                        : 'bg-red-50 text-red-800 border border-red-200'
                    }`}
                  >
                    {message}
                  </div>
                )}

                <Button
                  type="submit"
                  className="w-full bg-blue-600 hover:bg-blue-700"
                  disabled={isLoading}
                >
                  {isLoading ? 'Creating...' : 'Create User'}
                </Button>
              </form>
            </CardContent>
          </Card>

          {/* Info Card */}
          <Card className="border-slate-200 shadow-lg">
            <CardHeader>
              <CardTitle>How It Works</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-sm text-slate-600">
              <div>
                <h3 className="font-semibold text-slate-900 mb-2">User Creation Process</h3>
                <ol className="list-decimal list-inside space-y-2">
                  <li>Enter the clinic/user email address</li>
                  <li>Select their role (User or Admin)</li>
                  <li>Select the healthcare facility they belong to</li>
                  <li>Click "Create User"</li>
                  <li>A temporary password will be sent to their email</li>
                  <li>User logs in and must change password on first login</li>
                </ol>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
