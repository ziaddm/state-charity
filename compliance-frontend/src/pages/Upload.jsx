import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Upload as UploadIcon, FileText, AlertCircle } from 'lucide-react';

export default function Upload() {
  const [file, setFile] = useState(null);
  const [tenant, setTenant] = useState('');
  const [state, setState] = useState('NJ');
  const [isDragging, setIsDragging] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile) {
      setFile(droppedFile);
    }
  };

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0];
    if (selectedFile) {
      setFile(selectedFile);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsLoading(true);

    // TODO: Implement API call to FastAPI backend
    // For now, simulate a delay
    setTimeout(() => {
      setIsLoading(false);
      navigate('/results/mock-report-id');
    }, 2000);
  };

  return (
    <div className="mx-auto max-w-4xl">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Upload & Validate</h1>
        <p className="mt-2 text-gray-600">
          Upload your compliance data file for validation against state-mandated schemas
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* File Upload Area */}
        <div className="rounded-lg border-2 border-dashed border-gray-300 bg-white p-8">
          <div
            className={`rounded-lg transition-colors ${
              isDragging ? 'bg-blue-50' : 'bg-gray-50'
            }`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
          >
            <label htmlFor="file-upload" className="block cursor-pointer p-12 text-center">
              {file ? (
                <div className="flex flex-col items-center">
                  <FileText className="h-16 w-16 text-blue-600" />
                  <p className="mt-4 text-lg font-medium text-gray-900">{file.name}</p>
                  <p className="mt-1 text-sm text-gray-500">
                    {(file.size / 1024).toFixed(2)} KB
                  </p>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.preventDefault();
                      setFile(null);
                    }}
                    className="mt-4 text-sm text-red-600 hover:text-red-700"
                  >
                    Remove file
                  </button>
                </div>
              ) : (
                <div className="flex flex-col items-center">
                  <UploadIcon className="h-16 w-16 text-gray-400" />
                  <p className="mt-4 text-lg font-medium text-gray-900">
                    Drop your file here, or click to browse
                  </p>
                  <p className="mt-1 text-sm text-gray-500">CSV or Excel files accepted</p>
                </div>
              )}
              <input
                id="file-upload"
                name="file-upload"
                type="file"
                accept=".csv,.xlsx,.xls"
                className="sr-only"
                onChange={handleFileChange}
              />
            </label>
          </div>
        </div>

        {/* Configuration Options */}
        <div className="rounded-lg border border-gray-200 bg-white p-6">
          <h3 className="mb-4 text-lg font-semibold text-gray-900">Configuration</h3>

          <div className="grid grid-cols-2 gap-6">
            {/* Tenant Selection */}
            <div>
              <label htmlFor="tenant" className="block text-sm font-medium text-gray-700">
                Healthcare Facility
              </label>
              <select
                id="tenant"
                value={tenant}
                onChange={(e) => setTenant(e.target.value)}
                required
                className="mt-1 block w-full rounded-md border border-gray-300 bg-white px-3 py-2 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              >
                <option value="">Select facility...</option>
                <option value="hospital_a">Hospital A</option>
                <option value="hospital_b">Hospital B</option>
                <option value="clinic_c">Clinic C</option>
              </select>
            </div>

            {/* State Selection */}
            <div>
              <label htmlFor="state" className="block text-sm font-medium text-gray-700">
                Target State
              </label>
              <select
                id="state"
                value={state}
                onChange={(e) => setState(e.target.value)}
                required
                className="mt-1 block w-full rounded-md border border-gray-300 bg-white px-3 py-2 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              >
                <option value="NJ">New Jersey</option>
                <option value="NY" disabled>
                  New York (Coming Soon)
                </option>
                <option value="PA" disabled>
                  Pennsylvania (Coming Soon)
                </option>
              </select>
            </div>
          </div>
        </div>

        {/* Info Box */}
        <div className="flex items-start rounded-lg border border-blue-200 bg-blue-50 p-4">
          <AlertCircle className="mr-3 h-5 w-5 flex-shrink-0 text-blue-600" />
          <div className="text-sm text-blue-900">
            <p className="font-medium">Validation Philosophy</p>
            <p className="mt-1">
              We use a "fail open" approach - errors block submission, but warnings allow
              submission with acknowledgment. Trust your data and operators.
            </p>
          </div>
        </div>

        {/* Submit Button */}
        <div className="flex justify-end">
          <button
            type="submit"
            disabled={!file || !tenant || isLoading}
            className="flex items-center rounded-lg bg-blue-600 px-6 py-3 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isLoading ? (
              <>
                <svg
                  className="mr-2 h-5 w-5 animate-spin text-white"
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  ></circle>
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  ></path>
                </svg>
                Validating...
              </>
            ) : (
              <>
                <FileText className="mr-2 h-5 w-5" />
                Generate Report
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
