import { Link } from 'react-router-dom';
import { FileText, CheckCircle, XCircle, Clock } from 'lucide-react';

// Mock data - will be replaced with API call
const mockHistory = [
  {
    id: 'report-001',
    filename: 'charity_care_q1_2024.csv',
    tenant: 'Hospital A',
    state: 'NJ',
    status: 'ready',
    timestamp: '2024-11-18T10:30:00Z',
    errors: 0,
    warnings: 5,
  },
  {
    id: 'report-002',
    filename: 'charity_care_q2_2024.xlsx',
    tenant: 'Hospital B',
    state: 'NJ',
    status: 'errors',
    timestamp: '2024-11-17T15:45:00Z',
    errors: 12,
    warnings: 3,
  },
  {
    id: 'report-003',
    filename: 'patient_data_nov.csv',
    tenant: 'Clinic C',
    state: 'NJ',
    status: 'ready',
    timestamp: '2024-11-16T09:15:00Z',
    errors: 0,
    warnings: 0,
  },
];

export default function History() {
  const formatDate = (isoString) => {
    const date = new Date(isoString);
    return new Intl.DateTimeFormat('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(date);
  };

  const getStatusBadge = (status, errors, warnings) => {
    if (status === 'ready' && errors === 0) {
      return (
        <span className="inline-flex items-center rounded-full bg-green-100 px-3 py-1 text-xs font-medium text-green-800">
          <CheckCircle className="mr-1 h-3 w-3" />
          Passed
        </span>
      );
    } else if (status === 'errors' || errors > 0) {
      return (
        <span className="inline-flex items-center rounded-full bg-red-100 px-3 py-1 text-xs font-medium text-red-800">
          <XCircle className="mr-1 h-3 w-3" />
          Failed
        </span>
      );
    } else {
      return (
        <span className="inline-flex items-center rounded-full bg-gray-100 px-3 py-1 text-xs font-medium text-gray-800">
          <Clock className="mr-1 h-3 w-3" />
          Processing
        </span>
      );
    }
  };

  return (
    <div className="mx-auto max-w-6xl">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Validation History</h1>
        <p className="mt-2 text-gray-600">View past validation reports and their results</p>
      </div>

      {/* History Table */}
      <div className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                File
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                Facility
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                State
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                Status
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                Issues
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                Date
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200 bg-white">
            {mockHistory.map((report) => (
              <tr key={report.id} className="hover:bg-gray-50">
                <td className="whitespace-nowrap px-6 py-4">
                  <div className="flex items-center">
                    <FileText className="mr-3 h-5 w-5 text-gray-400" />
                    <span className="text-sm font-medium text-gray-900">{report.filename}</span>
                  </div>
                </td>
                <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-900">
                  {report.tenant}
                </td>
                <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-500">
                  {report.state}
                </td>
                <td className="whitespace-nowrap px-6 py-4">
                  {getStatusBadge(report.status, report.errors, report.warnings)}
                </td>
                <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-900">
                  {report.errors > 0 && (
                    <span className="mr-3 text-red-600">{report.errors} errors</span>
                  )}
                  {report.warnings > 0 && (
                    <span className="text-yellow-600">{report.warnings} warnings</span>
                  )}
                  {report.errors === 0 && report.warnings === 0 && (
                    <span className="text-green-600">No issues</span>
                  )}
                </td>
                <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-500">
                  {formatDate(report.timestamp)}
                </td>
                <td className="whitespace-nowrap px-6 py-4 text-sm font-medium">
                  <Link
                    to={`/results/${report.id}`}
                    className="text-blue-600 hover:text-blue-900"
                  >
                    View Details
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Empty State - show if no history */}
      {mockHistory.length === 0 && (
        <div className="rounded-lg border border-gray-200 bg-white p-12 text-center">
          <FileText className="mx-auto h-12 w-12 text-gray-400" />
          <h3 className="mt-4 text-lg font-medium text-gray-900">No validation history</h3>
          <p className="mt-2 text-sm text-gray-500">
            Upload your first file to get started with compliance validation
          </p>
          <Link
            to="/upload"
            className="mt-6 inline-flex items-center rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700"
          >
            Upload File
          </Link>
        </div>
      )}
    </div>
  );
}
