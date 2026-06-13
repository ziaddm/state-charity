import { useState, useEffect } from 'react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { LogOut, UserPlus, HeartPulse, Building2, Upload, Trash2, Plus, X } from 'lucide-react';

interface Tenant {
  id: string;
  name: string;
  state_code?: string;
  created_at?: string;
}

interface UserStats {
  total_users: number;
  active_admins: number;
  active_users: number;
}

interface AdminDashboardProps {
  onLogout: () => void;
}

export default function AdminDashboard({ onLogout }: AdminDashboardProps) {
  const [activeTab, setActiveTab] = useState<'users' | 'tenants'>('users');
  const [showUserForm, setShowUserForm] = useState(false);
  const [showTenantForm, setShowTenantForm] = useState(false);

  // User creation state
  const [email, setEmail] = useState('');
  const [role, setRole] = useState('user');
  const [tenantId, setTenantId] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [messageType, setMessageType] = useState<'success' | 'error'>('success');
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [userStats, setUserStats] = useState<UserStats | null>(null);
  const [allUsers, setAllUsers] = useState<any[]>([]);

  // Tenant creation state
  const [tenantName, setTenantName] = useState('');
  const [stateCode, setStateCode] = useState('');
  const [yamlFile, setYamlFile] = useState<File | null>(null);
  const [tenantMessage, setTenantMessage] = useState('');
  const [tenantMessageType, setTenantMessageType] = useState<'success' | 'error'>('success');
  const [isTenantLoading, setIsTenantLoading] = useState(false);

  // US States list
  const US_STATES = [
    { code: 'AL', name: 'Alabama' },
    { code: 'AK', name: 'Alaska' },
    { code: 'AZ', name: 'Arizona' },
    { code: 'AR', name: 'Arkansas' },
    { code: 'CA', name: 'California' },
    { code: 'CO', name: 'Colorado' },
    { code: 'CT', name: 'Connecticut' },
    { code: 'DE', name: 'Delaware' },
    { code: 'FL', name: 'Florida' },
    { code: 'GA', name: 'Georgia' },
    { code: 'HI', name: 'Hawaii' },
    { code: 'ID', name: 'Idaho' },
    { code: 'IL', name: 'Illinois' },
    { code: 'IN', name: 'Indiana' },
    { code: 'IA', name: 'Iowa' },
    { code: 'KS', name: 'Kansas' },
    { code: 'KY', name: 'Kentucky' },
    { code: 'LA', name: 'Louisiana' },
    { code: 'ME', name: 'Maine' },
    { code: 'MD', name: 'Maryland' },
    { code: 'MA', name: 'Massachusetts' },
    { code: 'MI', name: 'Michigan' },
    { code: 'MN', name: 'Minnesota' },
    { code: 'MS', name: 'Mississippi' },
    { code: 'MO', name: 'Missouri' },
    { code: 'MT', name: 'Montana' },
    { code: 'NE', name: 'Nebraska' },
    { code: 'NV', name: 'Nevada' },
    { code: 'NH', name: 'New Hampshire' },
    { code: 'NJ', name: 'New Jersey' },
    { code: 'NM', name: 'New Mexico' },
    { code: 'NY', name: 'New York' },
    { code: 'NC', name: 'North Carolina' },
    { code: 'ND', name: 'North Dakota' },
    { code: 'OH', name: 'Ohio' },
    { code: 'OK', name: 'Oklahoma' },
    { code: 'OR', name: 'Oregon' },
    { code: 'PA', name: 'Pennsylvania' },
    { code: 'RI', name: 'Rhode Island' },
    { code: 'SC', name: 'South Carolina' },
    { code: 'SD', name: 'South Dakota' },
    { code: 'TN', name: 'Tennessee' },
    { code: 'TX', name: 'Texas' },
    { code: 'UT', name: 'Utah' },
    { code: 'VT', name: 'Vermont' },
    { code: 'VA', name: 'Virginia' },
    { code: 'WA', name: 'Washington' },
    { code: 'WV', name: 'West Virginia' },
    { code: 'WI', name: 'Wisconsin' },
    { code: 'WY', name: 'Wyoming' },
  ];

  // Load tenants and stats on mount
  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const token = localStorage.getItem('token');

      // Load tenants from admin endpoint
      const tenantsResponse = await fetch('http://localhost:8000/api/admin/tenants', {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (tenantsResponse.ok) {
        const data = await tenantsResponse.json();
        setTenants(data.tenants || []);
        // Auto-select first tenant
        if (data.tenants && data.tenants.length > 0 && !tenantId) {
          setTenantId(data.tenants[0].id);
        }
      }

      // Load all users
      const usersResponse = await fetch('http://localhost:8000/api/admin/users', {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (usersResponse.ok) {
        const data = await usersResponse.json();
        setAllUsers(data.users || []);
      }

      // Load user stats
      const statsResponse = await fetch('http://localhost:8000/api/auth/user-stats', {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (statsResponse.ok) {
        const stats = await statsResponse.json();
        setUserStats(stats);
      }
    } catch (error) {
      console.error('Failed to load data:', error);
    }
  };

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

      // Refresh all data
      await loadData();

      // Close form after 2 seconds
      setTimeout(() => {
        setShowUserForm(false);
        setMessage('');
      }, 2000);
    } catch (error) {
      setMessageType('error');
      setMessage(`Error: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCreateTenant = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsTenantLoading(true);
    setTenantMessage('');

    try {
      const token = localStorage.getItem('token');

      if (!yamlFile) {
        throw new Error('Please select a YAML configuration file');
      }

      const formData = new FormData();
      formData.append('tenant_name', tenantName);
      formData.append('state_code', stateCode.toUpperCase());
      formData.append('config_file', yamlFile);

      const response = await fetch('http://localhost:8000/api/admin/tenants', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
        body: formData,
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to create tenant');
      }

      const data = await response.json();
      setTenantMessageType('success');
      setTenantMessage(data.message || 'Tenant created successfully!');

      // Reset form
      setTenantName('');
      setStateCode('');
      setYamlFile(null);

      // Refresh tenant list
      await loadData();

      // Close form after 2 seconds
      setTimeout(() => {
        setShowTenantForm(false);
        setTenantMessage('');
      }, 2000);
    } catch (error) {
      setTenantMessageType('error');
      setTenantMessage(`Error: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setIsTenantLoading(false);
    }
  };

  const handleDeleteTenant = async (tenantId: string) => {
    if (!confirm('Are you sure you want to delete this tenant? This cannot be undone.')) {
      return;
    }

    try {
      const token = localStorage.getItem('token');

      const response = await fetch(`http://localhost:8000/api/admin/tenants/${tenantId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to delete tenant');
      }

      setTenantMessageType('success');
      setTenantMessage('Tenant deleted successfully');

      // Refresh tenant list
      await loadData();
    } catch (error) {
      setTenantMessageType('error');
      setTenantMessage(`Error: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  };

  return (
    <>
      <style>{`
        @keyframes fadeIn {
          from {
            opacity: 0;
          }
          to {
            opacity: 1;
          }
        }

        @keyframes scaleIn {
          from {
            opacity: 0;
            transform: scale(0.95);
          }
          to {
            opacity: 1;
            transform: scale(1);
          }
        }
      `}</style>

      <div className="min-h-screen bg-slate-50">
      {/* Sidebar Navigation */}
      <aside className="fixed inset-y-0 left-0 w-64 bg-white border-r border-slate-200 flex flex-col">
        <div className="p-6 border-b border-slate-200">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-gradient-to-br from-emerald-600 to-teal-600 rounded-xl flex items-center justify-center">
              <HeartPulse className="w-6 h-6 text-white" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-slate-900">CharityCare</h2>
              <p className="text-xs text-slate-500">Admin Portal</p>
            </div>
          </div>
        </div>

        <nav className="flex-1 p-4">
          <div className="space-y-1">
            <button
              onClick={() => setActiveTab('users')}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all ${
                activeTab === 'users'
                  ? 'bg-gradient-to-r from-emerald-50 to-teal-50 text-emerald-700'
                  : 'text-slate-600 hover:bg-slate-50'
              }`}
            >
              <UserPlus className="w-5 h-5" />
              <span className="font-medium">User Management</span>
            </button>
            <button
              onClick={() => setActiveTab('tenants')}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all ${
                activeTab === 'tenants'
                  ? 'bg-gradient-to-r from-emerald-50 to-teal-50 text-emerald-700'
                  : 'text-slate-600 hover:bg-slate-50'
              }`}
            >
              <Building2 className="w-5 h-5" />
              <span className="font-medium">Clinic Management</span>
            </button>
          </div>
        </nav>

        <div className="p-4 border-t border-slate-200">
          <Button
            variant="outline"
            onClick={onLogout}
            className="w-full border-slate-300 hover:bg-slate-50"
          >
            <LogOut className="w-4 h-4 mr-2" />
            Sign Out
          </Button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="ml-64 p-8">
        <div className="max-w-7xl mx-auto">
          <div className="mb-6">
            <h1 className="text-3xl font-bold text-slate-900 mb-2">Admin Dashboard</h1>
          </div>

          {/* Tab Content */}
          {activeTab === 'users' && (
            <div className="space-y-6">
              {/* Users List */}
              <Card className="border-slate-200 rounded-2xl shadow-sm">
                <CardHeader className="bg-gradient-to-r from-slate-50 to-slate-100/50">
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle className="text-slate-900">All Users</CardTitle>
                      <CardDescription className="text-slate-600">
                        Manage user accounts across all facilities
                      </CardDescription>
                    </div>
                    <Button
                      onClick={() => setShowUserForm(true)}
                      className="bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-700 hover:to-teal-700"
                    >
                      <Plus className="w-4 h-4 mr-2" />
                      Add User
                    </Button>
                  </div>
                </CardHeader>
                <CardContent className="p-0">
                  {allUsers.length === 0 ? (
                    <div className="text-center py-12 text-slate-500">
                      <UserPlus className="w-12 h-12 mx-auto mb-3 text-slate-300" />
                      <p>No users in the system yet</p>
                      <p className="text-sm mt-2">Click "Add User" to create your first user</p>
                    </div>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full">
                        <thead className="bg-slate-50 border-b border-slate-200">
                          <tr>
                            <th className="px-6 py-3 text-left text-xs font-medium text-slate-600 uppercase tracking-wider">
                              Email
                            </th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-slate-600 uppercase tracking-wider">
                              Role
                            </th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-slate-600 uppercase tracking-wider">
                              Facility
                            </th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-slate-600 uppercase tracking-wider">
                              Status
                            </th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-slate-600 uppercase tracking-wider">
                              Last Login
                            </th>
                          </tr>
                        </thead>
                        <tbody className="bg-white divide-y divide-slate-200">
                          {allUsers.map((user) => (
                            <tr key={user.id} className="hover:bg-slate-50 transition-colors">
                              <td className="px-6 py-4 whitespace-nowrap">
                                <div className="flex items-center">
                                  <div className="w-8 h-8 bg-slate-100 rounded-lg flex items-center justify-center mr-3">
                                    <UserPlus className="w-4 h-4 text-slate-600" />
                                  </div>
                                  <div className="text-sm font-medium text-slate-900">{user.email}</div>
                                </div>
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap">
                                <span className={`px-2 py-1 text-xs font-semibold rounded-full ${
                                  user.role === 'admin'
                                    ? 'bg-purple-100 text-purple-800'
                                    : 'bg-emerald-100 text-emerald-800'
                                }`}>
                                  {user.role}
                                </span>
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-600">
                                {user.tenant_name}
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap">
                                <div className="flex items-center gap-2">
                                  <span className={`w-2 h-2 rounded-full ${
                                    user.is_active ? 'bg-emerald-500' : 'bg-slate-300'
                                  }`} />
                                  <span className="text-sm text-slate-600">
                                    {user.is_active ? 'Active' : 'Inactive'}
                                  </span>
                                  {user.must_change_password && (
                                    <span className="text-xs text-amber-600 ml-2">(Password reset required)</span>
                                  )}
                                </div>
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-600">
                                {user.last_login
                                  ? new Date(user.last_login).toLocaleDateString()
                                  : 'Never'}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </CardContent>
              </Card>

            </div>
          )}

          {/* Tenant Management Tab */}
          {activeTab === 'tenants' && (
            <div className="space-y-6">
              {/* Clinics List */}
              <Card className="border-slate-200 rounded-2xl shadow-sm">
                <CardHeader className="bg-gradient-to-r from-slate-50 to-slate-100/50">
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle className="text-slate-900">All Clinics</CardTitle>
                      <CardDescription className="text-slate-600">
                        Manage healthcare facilities in the system
                      </CardDescription>
                    </div>
                    <Button
                      onClick={() => setShowTenantForm(true)}
                      className="bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-700 hover:to-teal-700"
                    >
                      <Plus className="w-4 h-4 mr-2" />
                      Add Clinic
                    </Button>
                  </div>
                </CardHeader>
                <CardContent className="p-6">
                  {tenants.length === 0 ? (
                    <div className="text-center py-8 text-slate-500">
                      <Building2 className="w-12 h-12 mx-auto mb-3 text-slate-300" />
                      <p>No clinics configured yet</p>
                      <p className="text-sm mt-2">Click "Add Clinic" to create your first clinic</p>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {tenants.map((tenant) => {
                        const userCount = allUsers.filter(u => u.tenant_id === tenant.id).length;
                        return (
                          <div
                            key={tenant.id}
                            className="flex items-center justify-between p-4 bg-slate-50 rounded-xl border border-slate-200 hover:border-slate-300 transition-all"
                          >
                            <div className="flex items-center gap-3">
                              <div className="w-10 h-10 bg-emerald-100 rounded-lg flex items-center justify-center">
                                <Building2 className="w-5 h-5 text-emerald-600" />
                              </div>
                              <div>
                                <p className="font-semibold text-slate-900">{tenant.name}</p>
                                <p className="text-sm text-slate-500">
                                  ID: {tenant.id} • State: {tenant.state_code || 'N/A'} • {userCount} user{userCount !== 1 ? 's' : ''}
                                </p>
                              </div>
                            </div>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleDeleteTenant(tenant.id)}
                              className="border-rose-300 text-rose-600 hover:bg-rose-50"
                            >
                              <Trash2 className="w-4 h-4" />
                            </Button>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          )}
        </div>
      </main>

      {/* Add User Modal */}
      {showUserForm && (
        <div
          className="fixed inset-0 bg-slate-900/30 backdrop-blur-sm flex items-center justify-center z-50 p-4 transition-all duration-300 ease-out"
          onClick={() => setShowUserForm(false)}
          style={{ animation: 'fadeIn 0.3s ease-out' }}
        >
          <div
            className="bg-white rounded-2xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto transition-all duration-300 ease-out transform"
            onClick={(e) => e.stopPropagation()}
            style={{ animation: 'scaleIn 0.3s ease-out' }}
          >
            <div className="sticky top-0 bg-gradient-to-r from-slate-50 to-slate-100/50 px-6 py-4 border-b border-slate-200 flex items-center justify-between">
              <div>
                <h2 className="text-xl font-bold text-slate-900 flex items-center gap-2">
                  <UserPlus className="w-5 h-5 text-emerald-600" />
                  Create New User
                </h2>
                <p className="text-sm text-slate-600 mt-1">Create a new account for a clinic or staff member</p>
              </div>
              <button
                onClick={() => setShowUserForm(false)}
                className="w-8 h-8 rounded-lg hover:bg-slate-200 flex items-center justify-center transition-colors"
              >
                <X className="w-5 h-5 text-slate-600" />
              </button>
            </div>
            <div className="p-6">
              <form onSubmit={handleCreateUser} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="email" className="text-slate-700">Email Address</Label>
                  <Input
                    id="email"
                    type="email"
                    placeholder="clinic@example.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    className="border-slate-300 focus:border-emerald-500 focus:ring-emerald-500"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="role" className="text-slate-700">Role</Label>
                  <select
                    id="role"
                    value={role}
                    onChange={(e) => setRole(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
                  >
                    <option value="user">User</option>
                    <option value="admin">Admin</option>
                  </select>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="tenantId" className="text-slate-700">Healthcare Facility</Label>
                  <select
                    id="tenantId"
                    value={tenantId}
                    onChange={(e) => setTenantId(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
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
                    className={`p-3 rounded-lg text-sm ${
                      messageType === 'success'
                        ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
                        : 'bg-rose-50 text-rose-800 border border-rose-200'
                    }`}
                  >
                    {message}
                  </div>
                )}

                <Button
                  type="submit"
                  className="w-full bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-700 hover:to-teal-700 shadow-lg shadow-emerald-500/20"
                  disabled={isLoading}
                >
                  {isLoading ? (
                    <div className="flex items-center gap-2">
                      <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      Creating...
                    </div>
                  ) : (
                    'Create User'
                  )}
                </Button>
              </form>
            </div>
          </div>
        </div>
      )}

      {/* Add Clinic Modal */}
      {showTenantForm && (
        <div
          className="fixed inset-0 bg-slate-900/30 backdrop-blur-sm flex items-center justify-center z-50 p-4 transition-all duration-300 ease-out"
          onClick={() => setShowTenantForm(false)}
          style={{ animation: 'fadeIn 0.3s ease-out' }}
        >
          <div
            className="bg-white rounded-2xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto transition-all duration-300 ease-out transform"
            onClick={(e) => e.stopPropagation()}
            style={{ animation: 'scaleIn 0.3s ease-out' }}
          >
            <div className="sticky top-0 bg-gradient-to-r from-slate-50 to-slate-100/50 px-6 py-4 border-b border-slate-200 flex items-center justify-between">
              <div>
                <h2 className="text-xl font-bold text-slate-900 flex items-center gap-2">
                  <Building2 className="w-5 h-5 text-emerald-600" />
                  Add New Clinic
                </h2>
                <p className="text-sm text-slate-600 mt-1">Create a new healthcare facility by uploading a YAML configuration file</p>
              </div>
              <button
                onClick={() => setShowTenantForm(false)}
                className="w-8 h-8 rounded-lg hover:bg-slate-200 flex items-center justify-center transition-colors"
              >
                <X className="w-5 h-5 text-slate-600" />
              </button>
            </div>
            <div className="p-6">
              <form onSubmit={handleCreateTenant} className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="tenantName" className="text-slate-700">Clinic Name</Label>
                    <Input
                      id="tenantName"
                      type="text"
                      placeholder="e.g., JFK Hackensack Health"
                      value={tenantName}
                      onChange={(e) => setTenantName(e.target.value)}
                      required
                      className="border-slate-300 focus:border-emerald-500 focus:ring-emerald-500"
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="stateCode" className="text-slate-700">State</Label>
                    <select
                      id="stateCode"
                      value={stateCode}
                      onChange={(e) => setStateCode(e.target.value)}
                      className="w-full px-3 py-2 border border-slate-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
                      required
                    >
                      <option value="">Select a state...</option>
                      {US_STATES.map((state) => (
                        <option key={state.code} value={state.code}>
                          {state.name} ({state.code})
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="yamlFile" className="text-slate-700">
                    Configuration File (YAML)
                  </Label>
                  <div className="relative">
                    <input
                      id="yamlFile"
                      type="file"
                      accept=".yaml,.yml"
                      onChange={(e) => setYamlFile(e.target.files?.[0] || null)}
                      required
                      className="w-full px-3 py-2 border border-slate-300 rounded-md text-sm file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-emerald-50 file:text-emerald-700 hover:file:bg-emerald-100"
                    />
                  </div>
                  {yamlFile && (
                    <p className="text-sm text-slate-600 flex items-center gap-2">
                      <Upload className="w-4 h-4 text-emerald-600" />
                      {yamlFile.name}
                    </p>
                  )}
                </div>

                {tenantMessage && (
                  <div
                    className={`p-3 rounded-lg text-sm ${
                      tenantMessageType === 'success'
                        ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
                        : 'bg-rose-50 text-rose-800 border border-rose-200'
                    }`}
                  >
                    {tenantMessage}
                  </div>
                )}

                <Button
                  type="submit"
                  className="w-full bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-700 hover:to-teal-700 shadow-lg shadow-emerald-500/20"
                  disabled={isTenantLoading}
                >
                  {isTenantLoading ? (
                    <div className="flex items-center gap-2">
                      <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      Creating Clinic...
                    </div>
                  ) : (
                    <>
                      <Building2 className="w-4 h-4 mr-2" />
                      Create Clinic
                    </>
                  )}
                </Button>
              </form>
            </div>
          </div>
        </div>
      )}
      </div>
    </>
  );
}
