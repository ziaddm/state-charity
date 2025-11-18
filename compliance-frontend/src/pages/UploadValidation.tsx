import { useState, useCallback } from 'react';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Alert, AlertDescription } from '../components/ui/alert';
import { Building2, Upload, FileText, CheckCircle2, XCircle, AlertCircle, LogOut } from 'lucide-react';
import { Badge } from '../components/ui/badge';

interface UploadValidationProps {
  onLogout: () => void;
}

interface ValidationResult {
  id: string;
  fileName: string;
  tenant: string;
  state: string;
  status: 'ready' | 'errors' | 'warnings';
  errorCount: number;
  warningCount: number;
  totalRecords: number;
  validRecords: number;
  errors?: Array<{
    code: string;
    field: string;
    row: number;
    message: string;
  }>;
  warnings?: Array<{
    code: string;
    field: string;
    row: number;
    message: string;
  }>;
  uploadedAt: Date;
}

export default function UploadValidation({ onLogout }: UploadValidationProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [selectedTenant, setSelectedTenant] = useState('');
  const [selectedState, setSelectedState] = useState('NJ');
  const [results, setResults] = useState<ValidationResult[]>([]);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const validateFile = (file: File): ValidationResult => {
    const validExtensions = ['.csv', '.xlsx', '.xls'];
    const fileExtension = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();

    // Mock validation - replace with actual API call
    if (!validExtensions.includes(fileExtension)) {
      return {
        id: Math.random().toString(36).substring(7),
        fileName: file.name,
        tenant: selectedTenant,
        state: selectedState,
        status: 'errors',
        errorCount: 1,
        warningCount: 0,
        totalRecords: 0,
        validRecords: 0,
        errors: [{
          code: 'E000',
          field: 'file',
          row: 0,
          message: `Invalid file format. Accepted: ${validExtensions.join(', ')}`
        }],
        uploadedAt: new Date()
      };
    }

    // Simulate validation results
    const random = Math.random();
    const totalRecords = Math.floor(Math.random() * 500 + 100);

    if (random > 0.6) {
      // Pass with no errors
      const warningCount = Math.floor(Math.random() * 5);
      return {
        id: Math.random().toString(36).substring(7),
        fileName: file.name,
        tenant: selectedTenant,
        state: selectedState,
        status: warningCount > 0 ? 'warnings' : 'ready',
        errorCount: 0,
        warningCount,
        totalRecords,
        validRecords: totalRecords,
        warnings: warningCount > 0 ? [
          { code: 'W004', field: 'payor_source', row: 8, message: 'Invalid enum value' },
          { code: 'W100', field: 'visit_date', row: 15, message: 'Cross-field violation' }
        ] : undefined,
        uploadedAt: new Date()
      };
    } else {
      // Errors found
      const errorCount = Math.floor(Math.random() * 10 + 1);
      const warningCount = Math.floor(Math.random() * 3);
      return {
        id: Math.random().toString(36).substring(7),
        fileName: file.name,
        tenant: selectedTenant,
        state: selectedState,
        status: 'errors',
        errorCount,
        warningCount,
        totalRecords,
        validRecords: totalRecords - errorCount,
        errors: [
          { code: 'E001', field: 'patient_id', row: 5, message: 'Required field is empty' },
          { code: 'E002', field: 'last_name', row: 12, message: 'Field exceeds maximum length' }
        ],
        warnings: warningCount > 0 ? [
          { code: 'W004', field: 'payor_source', row: 8, message: 'Invalid enum value' }
        ] : undefined,
        uploadedAt: new Date()
      };
    }
  };

  const processFiles = async (files: File[]) => {
    if (!selectedTenant) {
      alert('Please select a healthcare facility');
      return;
    }

    setIsUploading(true);

    // Simulate upload delay
    await new Promise(resolve => setTimeout(resolve, 2000));

    const newResults = files.map(file => validateFile(file));
    setResults(prev => [...newResults, ...prev]);
    setIsUploading(false);
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);

    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) {
      processFiles(files);
    }
  }, [selectedTenant]);

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    if (files.length > 0) {
      processFiles(files);
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'ready':
        return <CheckCircle2 className="w-5 h-5 text-green-600" />;
      case 'warnings':
        return <AlertCircle className="w-5 h-5 text-amber-600" />;
      case 'errors':
        return <XCircle className="w-5 h-5 text-red-600" />;
      default:
        return null;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'ready':
        return 'bg-green-50 border-green-200';
      case 'warnings':
        return 'bg-amber-50 border-amber-200';
      case 'errors':
        return 'bg-red-50 border-red-200';
      default:
        return '';
    }
  };

  const stats = {
    total: results.length,
    passed: results.filter(r => r.status === 'ready').length,
    warnings: results.filter(r => r.status === 'warnings').length,
    errors: results.filter(r => r.status === 'errors').length
  };

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="bg-white border-b border-slate-200 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="flex items-center justify-center w-10 h-10 bg-blue-600 rounded-lg">
                <Building2 className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-xl font-bold text-slate-900">Compliance Analytics</h1>
                <p className="text-sm text-slate-600">Charity Care Validation Portal</p>
              </div>
            </div>
            <Button
              variant="outline"
              onClick={onLogout}
              className="border-slate-300"
            >
              <LogOut className="w-4 h-4 mr-2" />
              Sign Out
            </Button>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Stats */}
        {results.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-slate-600">Total Files</p>
                    <p className="text-2xl font-bold text-slate-900 mt-1">{stats.total}</p>
                  </div>
                  <FileText className="w-8 h-8 text-slate-400" />
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-slate-600">Passed</p>
                    <p className="text-2xl font-bold text-green-600 mt-1">{stats.passed}</p>
                  </div>
                  <CheckCircle2 className="w-8 h-8 text-green-400" />
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-slate-600">Warnings</p>
                    <p className="text-2xl font-bold text-amber-600 mt-1">{stats.warnings}</p>
                  </div>
                  <AlertCircle className="w-8 h-8 text-amber-400" />
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-slate-600">Errors</p>
                    <p className="text-2xl font-bold text-red-600 mt-1">{stats.errors}</p>
                  </div>
                  <XCircle className="w-8 h-8 text-red-400" />
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Upload Configuration */}
        <Card className="mb-8">
          <CardHeader>
            <CardTitle>Configuration</CardTitle>
            <CardDescription>
              Select your facility and target state before uploading
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  Healthcare Facility
                </label>
                <select
                  value={selectedTenant}
                  onChange={(e) => setSelectedTenant(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">Select facility...</option>
                  <option value="hospital_a">Hospital A</option>
                  <option value="hospital_b">Hospital B</option>
                  <option value="clinic_c">Clinic C</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  Target State
                </label>
                <select
                  value={selectedState}
                  onChange={(e) => setSelectedState(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="NJ">New Jersey</option>
                  <option value="NY" disabled>New York (Coming Soon)</option>
                  <option value="PA" disabled>Pennsylvania (Coming Soon)</option>
                </select>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Upload Area */}
        <Card className="mb-8">
          <CardHeader>
            <CardTitle>Upload Charity Care Files</CardTitle>
            <CardDescription>
              Upload your charity care documentation files for validation. Accepted formats: CSV, Excel
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              className={`border-2 border-dashed rounded-lg p-12 text-center transition-all ${
                isDragging
                  ? 'border-blue-500 bg-blue-50'
                  : 'border-slate-300 bg-slate-50 hover:border-slate-400'
              }`}
            >
              {isUploading ? (
                <div className="flex flex-col items-center gap-4">
                  <div className="w-12 h-12 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
                  <p className="text-slate-600">Validating files...</p>
                </div>
              ) : (
                <>
                  <Upload className="w-12 h-12 text-slate-400 mx-auto mb-4" />
                  <p className="text-lg text-slate-700 mb-2">
                    Drag and drop files here, or click to browse
                  </p>
                  <p className="text-sm text-slate-500 mb-6">
                    Maximum file size: 10MB
                  </p>
                  <label htmlFor="file-upload">
                    <Button type="button" className="bg-blue-600 hover:bg-blue-700" asChild>
                      <span>
                        <FileText className="w-4 h-4 mr-2" />
                        Select Files
                      </span>
                    </Button>
                  </label>
                  <input
                    id="file-upload"
                    type="file"
                    multiple
                    onChange={handleFileInput}
                    className="hidden"
                    accept=".csv,.xlsx,.xls"
                  />
                </>
              )}
            </div>

            <Alert className="mt-4 border-blue-200 bg-blue-50">
              <AlertCircle className="h-4 w-4 text-blue-600" />
              <AlertDescription className="text-sm text-blue-800">
                <strong>Fail Open Philosophy:</strong> Errors block submission, warnings allow submission with acknowledgment. We trust your data and operators.
              </AlertDescription>
            </Alert>
          </CardContent>
        </Card>

        {/* Results Section */}
        {results.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>Validation Results</CardTitle>
              <CardDescription>
                Review the validation status of your submitted files
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {results.map((result) => (
                <div
                  key={result.id}
                  className={`border rounded-lg p-4 ${getStatusColor(result.status)}`}
                >
                  <div className="flex items-start gap-4">
                    <div className="mt-0.5">{getStatusIcon(result.status)}</div>
                    <div className="flex-1">
                      <div className="flex items-start justify-between mb-2">
                        <div>
                          <p className="font-medium text-slate-900">{result.fileName}</p>
                          <p className="text-sm text-slate-600">
                            {result.tenant} • {result.state} • {result.uploadedAt.toLocaleString()}
                          </p>
                        </div>
                        <Badge
                          variant={result.status === 'ready' ? 'default' : 'secondary'}
                          className={
                            result.status === 'ready'
                              ? 'bg-green-600'
                              : result.status === 'warnings'
                              ? 'bg-amber-600'
                              : 'bg-red-600'
                          }
                        >
                          {result.status.toUpperCase()}
                        </Badge>
                      </div>
                      <div className="grid grid-cols-3 gap-4 mb-3">
                        <div>
                          <p className="text-xs text-slate-600">Total Records</p>
                          <p className="text-sm font-semibold text-slate-900">{result.totalRecords}</p>
                        </div>
                        <div>
                          <p className="text-xs text-slate-600">Valid Records</p>
                          <p className="text-sm font-semibold text-green-600">{result.validRecords}</p>
                        </div>
                        <div>
                          <p className="text-xs text-slate-600">Issues</p>
                          <p className="text-sm font-semibold text-red-600">
                            {result.errorCount} errors, {result.warningCount} warnings
                          </p>
                        </div>
                      </div>
                      {result.errors && result.errors.length > 0 && (
                        <div className="mb-2">
                          <p className="text-sm font-semibold text-red-800 mb-1">Errors:</p>
                          <ul className="space-y-1">
                            {result.errors.slice(0, 3).map((error, idx) => (
                              <li key={idx} className="text-sm text-slate-700 flex items-start gap-2">
                                <span className="text-red-600 font-mono text-xs">[{error.code}]</span>
                                <span>{error.field} (row {error.row}): {error.message}</span>
                              </li>
                            ))}
                          </ul>
                          {result.errors.length > 3 && (
                            <p className="text-xs text-slate-600 mt-1">
                              ... and {result.errors.length - 3} more errors
                            </p>
                          )}
                        </div>
                      )}
                      {result.warnings && result.warnings.length > 0 && (
                        <div>
                          <p className="text-sm font-semibold text-amber-800 mb-1">Warnings:</p>
                          <ul className="space-y-1">
                            {result.warnings.slice(0, 2).map((warning, idx) => (
                              <li key={idx} className="text-sm text-slate-700 flex items-start gap-2">
                                <span className="text-amber-600 font-mono text-xs">[{warning.code}]</span>
                                <span>{warning.field} (row {warning.row}): {warning.message}</span>
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
