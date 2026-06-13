import { useState, useCallback, useEffect, useRef } from 'react';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Alert, AlertDescription } from '../components/ui/alert';
import { HeartPulse, Upload, FileText, CheckCircle2, XCircle, AlertCircle, LogOut, Trash2, BarChart3, Home, ShieldCheck } from 'lucide-react';
import { Badge } from '../components/ui/badge';
import AnalyticsExecutive from './AnalyticsExecutive';

interface UploadValidationProps {
  onLogout: () => void;
}

interface ValidationResult {
  id: string;
  fileName: string;
  tenant: string;
  state: string;
  status: 'validating' | 'ready' | 'uploading' | 'completed' | 'errors';
  ingestionStatus?: 'pending' | 'in_progress' | 'completed' | 'failed';
  errorCount: number;
  totalRecords: number;
  validRecords: number;
  recordsIngested?: number;
  processingTimeSeconds?: number;
  errors?: Array<{
    code: string;
    field: string;
    row: number;
    message: string;
  }>;
  uploadedAt: string;
}

const STORAGE_KEY = 'validation_results';

export default function UploadValidation({ onLogout }: UploadValidationProps) {
  const [activeTab, setActiveTab] = useState<'upload' | 'analytics'>('upload');
  const [isDragging, setIsDragging] = useState(false);
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
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);

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

  // Poll status for active uploads
  const pollStatus = async (runId: string) => {
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`http://localhost:8000/api/validation/status/${runId}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });

      if (response.ok) {
        const data = await response.json();
        console.log(`Poll response for ${runId}:`, data);

        setResults(prev => prev.map(result => {
          if (result.id === runId) {
            const updated = {
              ...result,
              status: data.status || result.status,
              ingestionStatus: data.ingestion_status,
              recordsIngested: data.records_ingested,
              errorCount: data.error_count || result.errorCount,
              totalRecords: data.total_records || result.totalRecords
            };
            console.log(`Updated ${runId}:`, {
              oldStatus: result.status,
              newStatus: updated.status,
              oldIngestion: result.ingestionStatus,
              newIngestion: updated.ingestionStatus,
              recordsIngested: updated.recordsIngested
            });
            return updated;
          }
          return result;
        }));
      } else {
        console.error(`Poll failed for ${runId}: ${response.status}`);
      }
    } catch (error) {
      console.error(`Failed to poll status for ${runId}:`, error);
    }
  };

  // Start polling for incomplete uploads
  useEffect(() => {
    const incompleteResults = results.filter(r => {
      // Don't poll temp IDs (placeholders still validating)
      if (!r.id || r.id.startsWith('temp-')) return false;

      // Poll if status is uploading or if ingestion is in progress
      return r.status === 'uploading' ||
             r.status === 'ready' ||
             r.ingestionStatus === 'in_progress' ||
             r.ingestionStatus === 'pending';
    });

    if (incompleteResults.length > 0) {
      console.log('Starting polling for:', incompleteResults.map(r => ({ id: r.id, status: r.status, ingestionStatus: r.ingestionStatus })));

      // Poll every 2 seconds
      pollingIntervalRef.current = setInterval(() => {
        incompleteResults.forEach(result => {
          console.log(`Polling ${result.id} - current status: ${result.status}, ingestion: ${result.ingestionStatus}`);
          pollStatus(result.id);
        });
      }, 2000);
    } else {
      // Stop polling when everything is complete
      if (pollingIntervalRef.current) {
        console.log('Stopping polling - all uploads complete');
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }
    }

    // Cleanup on unmount
    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
      }
    };
  }, [results]);

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

    console.log('Backend response:', data);

    // Map backend status to frontend status
    let status: 'validating' | 'ready' | 'uploading' | 'completed' | 'errors' = 'ready';

    // CRITICAL: Check error_count first, then use backend status
    if (data.error_count > 0) {
      status = 'errors';
      console.log(`File has ${data.error_count} errors - setting status to 'errors'`);
    } else if (data.status === 'errors') {
      // Backend explicitly said errors even if error_count is 0
      status = 'errors';
      console.log('Backend status is errors - setting status to errors');
    } else {
      status = data.status || 'ready'; // Use backend status (ready/uploading/completed)
      console.log(`No errors - using backend status: ${status}`);
    }

    const result = {
      id: data.run_id,
      fileName: file.name,
      tenant: selectedTenant,
      state: selectedState,
      status: status,
      ingestionStatus: data.ingestion_status,
      errorCount: data.error_count || 0,
      totalRecords: data.total_records || 0,
      validRecords: (data.total_records || 0) - (data.error_count || 0),
      recordsIngested: data.records_ingested,
      processingTimeSeconds: Math.round(processingTime * 100) / 100, // Round to 2 decimals,
      errors: data.errors || [],
      uploadedAt: new Date().toLocaleString(),
    };

    console.log('Mapped result:', result);
    return result;
  };

  const deleteResult = (resultId: string) => {
    setResults(prev => prev.filter(r => r.id !== resultId));
  };

  const processFiles = async (files: File[]) => {
    if (!selectedTenant) {
      alert('Please select a healthcare facility');
      return;
    }

    // Create placeholder cards IMMEDIATELY for each file
    const placeholders: ValidationResult[] = files.map((file, index) => ({
      id: `temp-${Date.now()}-${index}`, // Temporary ID
      fileName: file.name,
      tenant: selectedTenant,
      state: selectedState,
      status: 'validating',
      ingestionStatus: undefined,
      errorCount: 0,
      totalRecords: 0,
      validRecords: 0,
      uploadedAt: new Date().toLocaleString(),
    }));

    // Add placeholder cards to UI immediately
    setResults(prev => [...placeholders, ...prev]);

    // Process each file individually and update its card
    files.forEach(async (file, index) => {
      try {
        const result = await validateFile(file);

        // Replace the placeholder with the actual result
        setResults(prev => prev.map(r =>
          r.id === placeholders[index].id ? result : r
        ));
      } catch (error) {
        // Update placeholder to show error with actual error message
        const errorMessage = error instanceof Error ? error.message : 'Upload failed';
        setResults(prev => prev.map(r =>
          r.id === placeholders[index].id
            ? {
                ...r,
                status: 'errors' as const,
                errorCount: 1,
                errors: [{
                  code: 'UPLOAD_ERROR',
                  field: 'File',
                  row: 0,
                  message: errorMessage
                }]
              }
            : r
        ));
        console.error(`Upload failed for ${file.name}:`, error);
      }
    });
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
      case 'validating':
        return <div className="w-5 h-5 border-2 border-emerald-600 border-t-transparent rounded-full animate-spin" />;
      case 'ready':
        return <CheckCircle2 className="w-5 h-5 text-emerald-600" />;
      case 'uploading':
        return <div className="w-5 h-5 border-2 border-purple-600 border-t-transparent rounded-full animate-spin" />;
      case 'completed':
        return <CheckCircle2 className="w-5 h-5 text-emerald-600" />;
      case 'errors':
        return <XCircle className="w-5 h-5 text-rose-600" />;
      default:
        return null;
    }
  };

  const stats = {
    total: results.length,
    passed: results.filter(r => r.status === 'ready' || r.status === 'uploading' || r.status === 'completed').length,
    errors: results.filter(r => r.status === 'errors').length
  };

  const navItems = [
    { id: 'upload' as const, label: 'Upload', icon: Upload },
    { id: 'analytics' as const, label: 'Analytics', icon: BarChart3 },
  ];

  return (
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
              <p className="text-xs text-slate-500">Portal</p>
            </div>
          </div>
        </div>

        <nav className="flex-1 p-4">
          <div className="space-y-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => setActiveTab(item.id)}
                  className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all ${
                    isActive
                      ? 'bg-gradient-to-r from-emerald-50 to-teal-50 text-emerald-700'
                      : 'text-slate-600 hover:bg-slate-50'
                  }`}
                >
                  <Icon className="w-5 h-5" />
                  <span className="font-medium">{item.label}</span>
                </button>
              );
            })}
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
      <main className="ml-64 p-6">
        <div className="max-w-7xl mx-auto">
          {activeTab === 'upload' ? (
            <div className="space-y-5">
              <div>
                <h1 className="text-2xl font-bold text-slate-900 mb-2">File Upload</h1>
              </div>

              {/* Stats */}
              {results.length > 0 && (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  <div className="bg-white rounded-xl p-4 border border-slate-200">
                    <div className="flex items-center justify-between mb-3">
                      <div className="w-9 h-9 bg-slate-100 rounded-lg flex items-center justify-center">
                        <FileText className="w-5 h-5 text-slate-600" />
                      </div>
                    </div>
                    <p className="text-xs text-slate-600 mb-1">Total Files</p>
                    <p className="text-2xl font-bold text-slate-900">{stats.total}</p>
                  </div>

                  <div className="bg-gradient-to-br from-emerald-50 to-teal-50 rounded-xl p-4 border border-emerald-200">
                    <div className="flex items-center justify-between mb-3">
                      <div className="w-9 h-9 bg-emerald-100 rounded-lg flex items-center justify-center">
                        <CheckCircle2 className="w-5 h-5 text-emerald-600" />
                      </div>
                    </div>
                    <p className="text-xs text-emerald-700 mb-1">Passed</p>
                    <p className="text-2xl font-bold text-emerald-900">{stats.passed}</p>
                  </div>

                  <div className="bg-gradient-to-br from-rose-50 to-red-50 rounded-xl p-4 border border-rose-200">
                    <div className="flex items-center justify-between mb-3">
                      <div className="w-9 h-9 bg-rose-100 rounded-lg flex items-center justify-center">
                        <XCircle className="w-5 h-5 text-rose-600" />
                      </div>
                    </div>
                    <p className="text-xs text-rose-700 mb-1">Errors</p>
                    <p className="text-2xl font-bold text-rose-900">{stats.errors}</p>
                  </div>
                </div>
              )}

              {/* Configuration */}
              <Card className="border-slate-200 rounded-xl shadow-sm">
                <CardHeader className="bg-gradient-to-r from-slate-50 to-slate-100/50 py-3 px-5">
                  <CardTitle className="text-slate-900 text-base">Configuration</CardTitle>
                  <CardDescription className="text-slate-600 text-sm">
                    Select your facility and target state before uploading
                  </CardDescription>
                </CardHeader>
                <CardContent className="p-4">
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-medium text-slate-700 mb-1.5">
                        Healthcare Facility
                      </label>
                      <select
                        value={selectedTenant}
                        onChange={(e) => setSelectedTenant(e.target.value)}
                        className="w-full px-2.5 py-1.5 text-sm border border-slate-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
                      >
                        <option value="">Select facility...</option>
                        <option value="acme_health">Acme Health</option>
                        <option value="jfk_hackensack">JFK Hackensack Meridian Health</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-slate-700 mb-1.5">
                        Target State
                      </label>
                      <select
                        value={selectedState}
                        onChange={(e) => setSelectedState(e.target.value)}
                        className="w-full px-2.5 py-1.5 text-sm border border-slate-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
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
              <Card className="border-slate-200 rounded-xl overflow-hidden shadow-sm">
                <CardHeader className="bg-gradient-to-r from-slate-50 to-slate-100/50 py-3 px-5">
                  <CardTitle className="text-slate-900 text-base">Upload Files</CardTitle>
                  <CardDescription className="text-slate-600 text-sm">
                    Accepted formats: CSV, Excel (.xlsx, .xls)
                  </CardDescription>
                </CardHeader>
                <CardContent className="p-4">
                  <div
                    onDragOver={handleDragOver}
                    onDragLeave={handleDragLeave}
                    onDrop={handleDrop}
                    className={`border-2 border-dashed rounded-xl p-8 text-center transition-all ${
                      isDragging
                        ? 'border-emerald-400 bg-emerald-50/50 scale-[1.02]'
                        : 'border-slate-300 bg-white hover:border-slate-400'
                    }`}
                  >
                    <div className="w-12 h-12 bg-gradient-to-br from-emerald-100 to-teal-100 rounded-xl flex items-center justify-center mx-auto mb-4">
                      <Upload className="w-6 h-6 text-emerald-600" />
                    </div>
                    <p className="text-base font-medium text-slate-900 mb-1.5">
                      Drop your files here, or browse
                    </p>
                    <p className="text-xs text-slate-500 mb-6">
                      Support for multiple file upload
                    </p>
                    <label htmlFor="file-upload">
                      <Button type="button" className="bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-700 hover:to-teal-700 shadow-lg shadow-emerald-500/20 text-sm py-2 px-4" asChild>
                        <span>
                          <FileText className="w-3.5 h-3.5 mr-2" />
                          Choose Files
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
                  </div>
                </CardContent>
              </Card>

              {/* Results Section */}
              {results.length > 0 && (
                <Card className="border-slate-200 rounded-xl shadow-sm">
                  <CardHeader className="bg-gradient-to-r from-slate-50 to-slate-100/50 py-3 px-5">
                    <CardTitle className="text-slate-900 text-base">Validation Results</CardTitle>
                    <CardDescription className="text-slate-600 text-sm">
                      Review the status of your submitted files
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="p-4 space-y-2.5">
                    {results.map((result) => (
                      <div
                        key={result.id}
                        className={`rounded-lg p-3.5 border transition-all hover:shadow-md ${
                          result.status === 'validating' || result.status === 'ready' || result.status === 'uploading' || result.status === 'completed'
                            ? 'bg-gradient-to-r from-emerald-50 to-teal-50 border-emerald-200'
                            : 'bg-gradient-to-r from-rose-50 to-red-50 border-rose-200'
                        }`}
                      >
                  <div className="flex items-start gap-3">
                    <div className="mt-0.5">{getStatusIcon(result.status)}</div>
                    <div className="flex-1">
                      <div className="flex items-start justify-between mb-1.5">
                        <div>
                          <p className="font-medium text-slate-900 text-sm">{result.fileName}</p>
                          <p className="text-xs text-slate-600">
                            {result.tenant} • {result.state} • {result.uploadedAt}
                            {result.processingTimeSeconds && (
                              <> • {result.processingTimeSeconds}s</>
                            )}
                          </p>
                        </div>
                        <div className="flex items-center gap-2">
                          <Badge
                            className={`shrink-0 text-xs ${
                              result.status === 'validating' || result.status === 'ready' || result.status === 'uploading' || result.status === 'completed'
                                ? 'bg-emerald-600 hover:bg-emerald-700'
                                : 'bg-rose-600 hover:bg-rose-700'
                            }`}
                          >
                            {result.status.toUpperCase()}
                          </Badge>
                          <button
                            onClick={() => deleteResult(result.id)}
                            className="text-slate-400 hover:text-rose-600 transition-colors"
                            title="Delete this result"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>
                      <div className="grid grid-cols-3 gap-3 mb-2">
                        <div>
                          <p className="text-[10px] text-slate-600 uppercase tracking-wide">Total Records</p>
                          <p className="text-sm font-semibold text-slate-900">{result.totalRecords}</p>
                        </div>
                        <div>
                          <p className="text-[10px] text-slate-600 uppercase tracking-wide">Valid Records</p>
                          <p className="text-sm font-semibold text-slate-900">{result.validRecords}</p>
                        </div>
                        <div>
                          <p className="text-[10px] text-slate-600 uppercase tracking-wide">Errors</p>
                          {result.errorCount === 0 ? (
                            <p className="text-sm font-semibold text-slate-900">None</p>
                          ) : (
                            <p className="text-sm font-semibold text-rose-600">
                              {result.errorCount}
                            </p>
                          )}
                        </div>
                      </div>

                      {(result.status === 'ready' || result.status === 'uploading' || result.status === 'completed') && result.errorCount === 0 && (
                        <div className="flex gap-1.5 mb-2">
                          <a
                            href={`http://localhost:8000/api/validation/download/${result.id}?token=${localStorage.getItem('token')}`}
                            className="text-xs px-2.5 py-1 bg-slate-100 text-slate-700 rounded hover:bg-slate-200 transition-colors border border-slate-300"
                            download
                          >
                            Download File
                          </a>
                          <a
                            href={`http://localhost:8000/api/validation/download/${result.id}/report?token=${localStorage.getItem('token')}`}
                            className="text-xs px-2.5 py-1 bg-slate-100 text-slate-700 rounded hover:bg-slate-200 transition-colors border border-slate-300"
                            download
                          >
                            Report
                          </a>
                        </div>
                      )}

                      {/* Ingestion Status - show during uploading phase */}
                      {(result.status === 'uploading' || result.ingestionStatus === 'in_progress') && (
                        <div className="mb-2 p-2 rounded border bg-purple-50 border-purple-200">
                          <div className="flex items-center gap-1.5">
                            <div className="w-3.5 h-3.5 border-2 border-purple-600 border-t-transparent rounded-full animate-spin flex-shrink-0" />
                            <p className="text-xs font-semibold text-purple-900">
                              Uploading to Analytics Database...
                            </p>
                          </div>
                        </div>
                      )}

                      {/* Ingestion Status - Only show when completed */}
                      {result.status === 'completed' && result.errorCount === 0 && result.recordsIngested !== undefined && (
                        <div className="mb-2 p-2 rounded border bg-slate-50 border-slate-200">
                          {result.recordsIngested > 0 ? (
                            <div className="flex items-start gap-1.5">
                              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 mt-0.5 flex-shrink-0" />
                              <div>
                                <p className="text-xs font-semibold text-emerald-800">
                                  Success
                                </p>
                                <p className="text-[10px] text-slate-700 mt-0.5">
                                  {result.recordsIngested === result.totalRecords ? (
                                    <>All {result.recordsIngested} records added to analytics database</>
                                  ) : (
                                    <>
                                      ✓ {result.recordsIngested} new records added
                                      {result.totalRecords - result.recordsIngested > 0 && (
                                        <> • {result.totalRecords - result.recordsIngested} duplicates skipped</>
                                      )}
                                    </>
                                  )}
                                </p>
                              </div>
                            </div>
                          ) : (
                            <div className="flex items-start gap-1.5">
                              <AlertCircle className="w-3.5 h-3.5 text-amber-600 mt-0.5 flex-shrink-0" />
                              <div>
                                <p className="text-xs font-semibold text-amber-800">
                                  No New Records
                                </p>
                                <p className="text-[10px] text-slate-700 mt-0.5">
                                  All {result.totalRecords} records already exist in the database
                                </p>
                              </div>
                            </div>
                          )}
                        </div>
                      )}

                      {result.errors && result.errors.length > 0 && (
                        <div className="mb-1.5">
                          <div className="mb-2 p-2 rounded border bg-rose-50 border-rose-200">
                            <p className="text-xs font-semibold text-rose-900 mb-0.5">
                              ✗ Validation Failed - File Rejected
                            </p>
                            <p className="text-[10px] text-rose-700">
                              This file contains {result.errorCount} error{result.errorCount !== 1 ? 's' : ''} and has been rejected. No data was uploaded or ingested. Please fix all errors and resubmit.
                            </p>
                          </div>
                          <p className="text-xs font-semibold text-rose-800 mb-1">Errors Found:</p>
                          <ul className="space-y-0.5">
                            {result.errors.slice(0, 3).map((error, idx) => (
                              <li key={idx} className="text-xs text-slate-700 flex items-start gap-1.5">
                                <span className="text-rose-600 font-mono text-[10px]">[{error.code}]</span>
                                <span>{error.field} (row {error.row}): {error.message}</span>
                              </li>
                            ))}
                          </ul>
                          {result.errors.length > 3 && (
                            <p className="text-[10px] text-slate-600 mt-0.5">
                              ... and {result.errors.length - 3} more errors
                            </p>
                          )}
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
          ) : (
            <AnalyticsExecutive />
          )}
        </div>
      </main>
    </div>
  );
}
