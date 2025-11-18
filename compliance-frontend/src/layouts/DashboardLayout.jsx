import { Outlet, NavLink } from 'react-router-dom';
import { Upload, FileText, History } from 'lucide-react';

export default function DashboardLayout() {
  return (
    <div className="min-h-screen bg-gray-50">
      {/* Sidebar */}
      <aside className="fixed left-0 top-0 z-40 h-screen w-64 border-r border-gray-200 bg-white">
        <div className="flex h-full flex-col">
          {/* Logo */}
          <div className="flex h-16 items-center border-b border-gray-200 px-6">
            <FileText className="h-8 w-8 text-blue-600" />
            <span className="ml-3 text-xl font-bold text-gray-900">
              Compliance Analytics
            </span>
          </div>

          {/* Navigation */}
          <nav className="flex-1 space-y-1 px-3 py-4">
            <NavLink
              to="/upload"
              className={({ isActive }) =>
                `flex items-center rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-blue-50 text-blue-600'
                    : 'text-gray-700 hover:bg-gray-50 hover:text-gray-900'
                }`
              }
            >
              <Upload className="mr-3 h-5 w-5" />
              Upload & Validate
            </NavLink>

            <NavLink
              to="/history"
              className={({ isActive }) =>
                `flex items-center rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-blue-50 text-blue-600'
                    : 'text-gray-700 hover:bg-gray-50 hover:text-gray-900'
                }`
              }
            >
              <History className="mr-3 h-5 w-5" />
              History
            </NavLink>
          </nav>

          {/* Footer */}
          <div className="border-t border-gray-200 p-4">
            <p className="text-xs text-gray-500">
              v1.0.0 | Built with React & Tailwind
            </p>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="ml-64">
        <div className="p-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
