import { useParams } from 'react-router-dom';
import { CheckCircle, XCircle, AlertTriangle, Download, FileText } from 'lucide-react';

// Mock data - will be replaced with API call
const mockResults = {
  status: 'errors', // 'ready', 'errors', 'failed'
  errors: [
    {
      code: 'E001',
      severity: 'error',
      type: 'required_missing',
      field: 'patient_id',
      row: 5,
      message: 'Required field is empty',
      action: 'Add missing required field value',
    },
    {
      code: 'E002',
      severity: 'error',
      type: 'too_long',
      field: 'last_name',
      row: 12,
      message: 'Field exceeds maximum length',
      value: 'ThisIsAVeryLongLastNameThatExceedsLimit',
      action: 'Truncate or abbreviate field value',
    },
  ],
  warnings: [
    {
      code: 'W004',
      severity: 'warning',
      type: 'invalid_enum',
      field: 'payor_source',
      row: 8,
      message: 'Value not in expected enum list',
      value: 'XX',
      action: 'Verify if this is a new valid code from state',
    },
    {
      code: 'W100',
      severity: 'warning',
      type: 'cross_field_violation',
      field: 'visit_date',
      row: 15,
      message: 'Visit date before birth date by 1 day',
      action: 'Verify dates, might be timezone/typo',
    },
  ],
  totalRecords: 500,
  validRecords: 498,
};

export default function Results() {
  const { reportId } = useParams();
  const results = mockResults; // Replace with API call

  const hasErrors = results.errors && results.errors.length > 0;
  const hasWarnings = results.warnings && results.warnings.length > 0;

  return (
    <div className="mx-auto max-w-6xl">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Validation Results</h1>
        <p className="mt-2 text-sm text-gray-600">Report ID: {reportId}</p>
      </div>

      {/* Status Banner */}
      {hasErrors ? (
        <div className="mb-6 flex items-start rounded-lg border border-red-200 bg-red-50 p-4">
          <XCircle className="mr-3 h-6 w-6 flex-shrink-0 text-red-600" />
          <div>
            <h3 className="text-lg font-semibold text-red-900">
              Validation Failed - {results.errors.length} Error{results.errors.length !== 1 ? 's' : ''} Found
            </h3>
            <p className="mt-1 text-sm text-red-700">
              Please fix all errors before submission
            </p>
          </div>
        </div>
      ) : (
        <div className="mb-6 flex items-start rounded-lg border border-green-200 bg-green-50 p-4">
          <CheckCircle className="mr-3 h-6 w-6 flex-shrink-0 text-green-600" />
          <div>
            <h3 className="text-lg font-semibold text-green-900">Validation Passed</h3>
            <p className="mt-1 text-sm text-green-700">
              {hasWarnings
                ? `${results.warnings.length} warning(s) found - Review recommended but submission allowed`
                : 'All records validated successfully'}
            </p>
          </div>
        </div>
      )}

      {/* Summary Stats */}
      <div className="mb-6 grid grid-cols-3 gap-4">
        <div className="rounded-lg border border-gray-200 bg-white p-6">
          <p className="text-sm font-medium text-gray-600">Total Records</p>
          <p className="mt-2 text-3xl font-bold text-gray-900">{results.totalRecords}</p>
        </div>
        <div className="rounded-lg border border-gray-200 bg-white p-6">
          <p className="text-sm font-medium text-gray-600">Valid Records</p>
          <p className="mt-2 text-3xl font-bold text-green-600">{results.validRecords}</p>
        </div>
        <div className="rounded-lg border border-gray-200 bg-white p-6">
          <p className="text-sm font-medium text-gray-600">Issues Found</p>
          <p className="mt-2 text-3xl font-bold text-red-600">
            {results.errors.length + results.warnings.length}
          </p>
        </div>
      </div>

      {/* Errors Table */}
      {hasErrors && (
        <div className="mb-6 overflow-hidden rounded-lg border border-gray-200 bg-white">
          <div className="border-b border-gray-200 bg-gray-50 px-6 py-4">
            <h2 className="flex items-center text-lg font-semibold text-red-900">
              <XCircle className="mr-2 h-5 w-5" />
              Errors ({results.errors.length})
            </h2>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Code
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Field
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Row
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Message
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Action
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 bg-white">
                {results.errors.map((error, index) => (
                  <tr key={index} className="hover:bg-gray-50">
                    <td className="whitespace-nowrap px-6 py-4 text-sm font-medium text-red-600">
                      {error.code}
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-900">
                      {error.field}
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-500">
                      {error.row}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-900">{error.message}</td>
                    <td className="px-6 py-4 text-sm text-gray-600">{error.action}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Warnings Table */}
      {hasWarnings && (
        <div className="mb-6 overflow-hidden rounded-lg border border-gray-200 bg-white">
          <div className="border-b border-gray-200 bg-gray-50 px-6 py-4">
            <h2 className="flex items-center text-lg font-semibold text-yellow-900">
              <AlertTriangle className="mr-2 h-5 w-5" />
              Warnings ({results.warnings.length})
            </h2>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Code
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Field
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Row
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Message
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Action
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 bg-white">
                {results.warnings.map((warning, index) => (
                  <tr key={index} className="hover:bg-gray-50">
                    <td className="whitespace-nowrap px-6 py-4 text-sm font-medium text-yellow-600">
                      {warning.code}
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-900">
                      {warning.field}
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-500">
                      {warning.row}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-900">{warning.message}</td>
                    <td className="px-6 py-4 text-sm text-gray-600">{warning.action}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="flex justify-between">
        <button
          type="button"
          className="flex items-center rounded-lg border border-gray-300 bg-white px-6 py-3 text-sm font-semibold text-gray-700 shadow-sm hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
        >
          <FileText className="mr-2 h-5 w-5" />
          Download Validation Report
        </button>

        {!hasErrors && (
          <button
            type="button"
            className="flex items-center rounded-lg bg-blue-600 px-6 py-3 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
          >
            <Download className="mr-2 h-5 w-5" />
            Download Compliant Output File
          </button>
        )}
      </div>
    </div>
  );
}
