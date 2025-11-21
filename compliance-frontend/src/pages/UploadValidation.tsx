import { useState, useCallback, useEffect, useRef } from 'react';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Alert, AlertDescription } from '../components/ui/alert';
import { Building2, Upload, FileText, CheckCircle2, XCircle, AlertCircle, LogOut, Trash2 } from 'lucide-react';
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
  processingTimeSeconds?: number;
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
  uploadedAt: string;
}

const STORAGE_KEY = 'validation_results';

export default function UploadValidation({ onLogout }: UploadValidationProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [selectedTenant, setSelectedTenant] = useState('');
  const [selectedState, setSelectedState] = useState('NJ');
  const [results, setResults] = useState<ValidationResult[]>(() => {
    // Load from localStorage on initial state initialization
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      return stored ? JSON.parse(stored) : [];
    } catch (error) {
      console.error('Failed to load validation results:', error);
      return [];
    }
  });

  const hasLoadedRef = useRef(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Save results to localStorage whenever they change (but skip initial load)
  useEffect(() => {
    if (hasLoadedRef.current) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(results));
    } else {
      hasLoadedRef.current = true;
    }
  }, [results]);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const validateFile = async (file: File): Promise<ValidationResult> => {
    const token = localStorage.getItem('token');
    const startTime = Date.now();

    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch('http://localhost:8000/api/validation/upload', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
      },
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Upload failed');
    }

    const data = await response.json();
    const processingTime = (Date.now() - startTime) / 1000; // Convert to seconds

    // Determine status based on error count
    let status: 'ready' | 'errors' | 'warnings' = 'ready';
    if (data.error_count > 0) {
      status = 'errors';
    } else if (data.warning_count > 0) {
      status = 'warnings';
    }

    return {
      id: data.run_id,
      fileName: file.name,
      tenant: selectedTenant,
      state: selectedState,
      status: status,
      errorCount: data.error_count || 0,
      warningCount: data.warning_count || 0,
      totalRecords: data.total_records || 0,
      validRecords: data.total_records - data.error_count || 0,
      processingTimeSeconds: Math.round(processingTime * 100) / 100, // Round to 2 decimals
      errors: data.errors || [],
      warnings: data.warnings || [],
      uploadedAt: new Date().toLocaleString(),
    };
  };

  const deleteResult = (resultId: string) => {
    setResults(prev => prev.filter(r => r.id !== resultId));
  };

  const processFiles = async (files: File[]) => {
    if (!selectedTenant) {
      alert('Please select a healthcare facility');
      return;
    }

    setIsUploading(true);

    try {
      const newResults = await Promise.all(files.map(validateFile));
      setResults(prev => [...newResults, ...prev]);
    } catch (error) {
      alert(`Upload failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setIsUploading(false);
    }
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
      // Reset the input so the same file can be selected again
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
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
                  <option value="acme_health">Acme Health</option>
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
                    ref={fileInputRef}
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
          </CardContent>
        </Card>

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
                            {result.tenant} • {result.state} • {result.uploadedAt}
                            {result.processingTimeSeconds && (
                              <> • {result.processingTimeSeconds}s</>
                            )}
                          </p>
                        </div>
                        <div className="flex items-center gap-2">
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
                          <button
                            onClick={() => deleteResult(result.id)}
                            className="text-slate-400 hover:text-red-600 transition-colors"
                            title="Delete this result"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
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
                          {result.errorCount === 0 && result.warningCount === 0 ? (
                            <p className="text-sm font-semibold text-slate-900">No issues</p>
                          ) : (
                            <p className="text-sm font-semibold text-red-600">
                              {result.errorCount} errors, {result.warningCount} warnings
                            </p>
                          )}
                        </div>
                      </div>

                      <div className="flex gap-2 mb-3">
                        {result.status === 'ready' && (
                          <>
                            <a
                              href={`http://localhost:8000/api/validation/download/${result.id}?token=${localStorage.getItem('token')}`}
                              className="text-sm px-3 py-1 bg-blue-100 text-blue-700 rounded hover:bg-blue-200"
                              download
                            >
                              Download File
                            </a>
                            <a
                              href={`http://localhost:8000/api/validation/download/${result.id}/report?token=${localStorage.getItem('token')}`}
                              className="text-sm px-3 py-1 bg-slate-100 text-slate-700 rounded hover:bg-slate-200"
                              download
                            >
                              Report
                            </a>
                          </>
                        )}
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
