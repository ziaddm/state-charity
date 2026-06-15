import { useState, useCallback, useEffect, useRef } from 'react';
import { apiFetch, downloadFile } from '../lib/api';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import {
  HeartPulse, Upload, FileText, CheckCircle2, XCircle, AlertCircle,
  LogOut, Trash2, BarChart3, ChevronDown, ChevronRight, Download, FileDown, Clock
} from 'lucide-react';
import { Badge } from '../components/ui/badge';
import AnalyticsExecutive from './AnalyticsExecutive';
import SubmissionHistory from './History';

interface UploadValidationProps {
  onLogout: () => void;
}

interface ValidationError {
  code: string;
  field: string;
  row: number;
  message: string;
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
  errors?: ValidationError[];
  uploadedAt: string;
}

type FilterMode = 'all' | 'passed' | 'errors';

const STORAGE_KEY = 'validation_results';

const isPassedStatus = (status: string) =>
  status === 'ready' || status === 'uploading' || status === 'completed' || status === 'validating';

export default function UploadValidation({ onLogout }: UploadValidationProps) {
  const [activeTab, setActiveTab] = useState<'upload' | 'analytics' | 'history'>('upload');
  const [isDragging, setIsDragging] = useState(false);
  const [filter, setFilter] = useState<FilterMode>('all');
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());
  const [results, setResults] = useState<ValidationResult[]>(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      return stored ? JSON.parse(stored) : [];
    } catch {
      return [];
    }
  });

  const hasLoadedRef = useRef(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Persist to localStorage
  useEffect(() => {
    if (hasLoadedRef.current) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(results));
    } else {
      hasLoadedRef.current = true;
    }
  }, [results]);

  // Auto-expand error rows, keep passed rows collapsed
  useEffect(() => {
    setExpandedRows(prev => {
      const next = new Set(prev);
      results.forEach(r => {
        if (r.status === 'errors' && !next.has(r.id)) {
          next.add(r.id);
        }
      });
      return next;
    });
  }, [results]);

  const toggleRow = (id: string) => {
    setExpandedRows(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const pollStatus = async (runId: string) => {
    try {
      const response = await apiFetch(`/api/validation/status/${runId}`);
      if (response.ok) {
        const data = await response.json();
        setResults(prev => prev.map(result =>
          result.id === runId
            ? {
                ...result,
                status: data.status || result.status,
                ingestionStatus: data.ingestion_status,
                recordsIngested: data.records_ingested,
                errorCount: data.error_count || result.errorCount,
                totalRecords: data.total_records || result.totalRecords
              }
            : result
        ));
      } else {
        // Stop polling on auth failure or server error to prevent infinite requests
        if (response.status === 401 || response.status >= 500) {
          setResults(prev => prev.map(r =>
            r.id === runId
              ? { ...r, status: r.status === 'uploading' ? 'ready' as const : r.status, ingestionStatus: 'failed' }
              : r
          ));
        }
        console.error(`Polling returned ${response.status} for run ${runId}`);
      }
    } catch (error) {
      console.error(`Failed to poll status for ${runId}:`, error);
    }
  };

  useEffect(() => {
    const incompleteResults = results.filter(r => {
      if (!r.id || r.id.startsWith('temp-')) return false;
      return r.status === 'uploading' || r.status === 'ready' ||
             r.ingestionStatus === 'in_progress' || r.ingestionStatus === 'pending';
    });

    if (incompleteResults.length > 0) {
      pollingIntervalRef.current = setInterval(() => {
        incompleteResults.forEach(result => pollStatus(result.id));
      }, 2000);
    } else {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }
    }

    return () => {
      if (pollingIntervalRef.current) clearInterval(pollingIntervalRef.current);
    };
  }, [results]);

  const validateFile = async (file: File): Promise<ValidationResult> => {
    const startTime = Date.now();
    const formData = new FormData();
    formData.append('file', file);

    const response = await apiFetch('/api/validation/upload', {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      let message = `Upload failed (${response.status})`;
      try {
        const error = await response.json();
        message = error.error || error.detail || message;
      } catch { /* non-JSON body (e.g. 502 gateway HTML) — keep the status-code message */ }
      throw new Error(message);
    }

    const data = await response.json();
    const processingTime = (Date.now() - startTime) / 1000;

    let status: ValidationResult['status'] = 'ready';
    if (data.error_count > 0 || data.status === 'errors') {
      status = 'errors';
    } else {
      status = data.status || 'ready';
    }

    return {
      id: data.run_id,
      fileName: file.name,
      tenant: '',
      state: '',
      status,
      ingestionStatus: data.ingestion_status,
      errorCount: data.error_count || 0,
      totalRecords: data.total_records || 0,
      validRecords: (data.total_records || 0) - (data.error_count || 0),
      recordsIngested: data.records_ingested,
      processingTimeSeconds: Math.round(processingTime * 100) / 100,
      errors: data.errors || [],
      uploadedAt: new Date().toLocaleString(),
    };
  };

  const deleteResult = (resultId: string) => {
    setResults(prev => prev.filter(r => r.id !== resultId));
    setExpandedRows(prev => { const n = new Set(prev); n.delete(resultId); return n; });
  };

  const processFiles = async (files: File[]) => {
    const placeholders: ValidationResult[] = files.map((file, index) => ({
      id: `temp-${Date.now()}-${index}`,
      fileName: file.name,
      tenant: '',
      state: '',
      status: 'validating',
      ingestionStatus: undefined,
      errorCount: 0,
      totalRecords: 0,
      validRecords: 0,
      uploadedAt: new Date().toLocaleString(),
    }));

    setResults(prev => [...placeholders, ...prev]);

    await Promise.all(files.map(async (file, index) => {
      try {
        const result = await validateFile(file);
        setResults(prev => prev.map(r => r.id === placeholders[index].id ? result : r));
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : 'Upload failed';
        setResults(prev => prev.map(r =>
          r.id === placeholders[index].id
            ? { ...r, status: 'errors' as const, errorCount: 1, errors: [{ code: 'UPLOAD_ERROR', field: 'File', row: 0, message: errorMessage }] }
            : r
        ));
      }
    }));
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) processFiles(files);
  }, []);

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    if (files.length > 0) {
      processFiles(files);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const exportSummary = () => {
    const header = 'File Name,Status,Total Records,Valid Records,Errors,Records Ingested,Processing Time (s),Uploaded At';
    const rows = results.map(r => [
      `"${r.fileName}"`,
      r.status,
      r.totalRecords,
      r.validRecords,
      r.errorCount,
      r.recordsIngested ?? '',
      r.processingTimeSeconds ?? '',
      `"${r.uploadedAt}"`
    ].join(','));
    const csv = [header, ...rows].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `charitycare-session-${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const stats = {
    total: results.length,
    passed: results.filter(r => isPassedStatus(r.status)).length,
    errors: results.filter(r => r.status === 'errors').length,
  };

  const hasErrors = stats.errors > 0;

  const filteredResults = results.filter(r => {
    if (filter === 'passed') return isPassedStatus(r.status);
    if (filter === 'errors') return r.status === 'errors';
    return true;
  });

  const getStatusIcon = (status: string, size = 'w-4 h-4') => {
    switch (status) {
      case 'validating':
        return <div className={`${size} border-2 border-emerald-600 border-t-transparent rounded-full animate-spin`} />;
      case 'ready':
      case 'completed':
        return <CheckCircle2 className={`${size} text-emerald-600`} />;
      case 'uploading':
        return <div className={`${size} border-2 border-purple-600 border-t-transparent rounded-full animate-spin`} />;
      case 'errors':
        return <XCircle className={`${size} text-rose-600`} />;
      default:
        return null;
    }
  };

  const navItems = [
    { id: 'upload' as const, label: 'Upload', icon: Upload },
    { id: 'history' as const, label: 'History', icon: Clock },
    { id: 'analytics' as const, label: 'Analytics', icon: BarChart3 },
  ];

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Sidebar */}
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
          <Button variant="outline" onClick={onLogout} className="w-full border-slate-300 hover:bg-slate-50">
            <LogOut className="w-4 h-4 mr-2" />
            Sign Out
          </Button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="ml-64 p-6">
        <div className="max-w-5xl mx-auto">
          {activeTab === 'history' ? (
            <SubmissionHistory />
          ) : activeTab === 'upload' ? (
            <div className="space-y-6">

              {/* ── SECTION 1: UPLOAD ── */}
              <div>
                <h1 className="text-2xl font-bold text-slate-900 mb-1">File Upload</h1>
                <p className="text-sm text-slate-500">Drag and drop one or more files to validate and submit</p>
              </div>

              {/* Stat Cards */}
              <div className="grid grid-cols-3 gap-4">
                <div className="bg-white rounded-xl p-4 border border-slate-200 shadow-sm">
                  <div className="flex items-center gap-2 mb-2">
                    <FileText className="w-4 h-4 text-slate-500" />
                    <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">Total Files</p>
                  </div>
                  <p className="text-3xl font-bold text-slate-900">{stats.total}</p>
                </div>

                <div className="bg-emerald-50 rounded-xl p-4 border border-emerald-200 shadow-sm">
                  <div className="flex items-center gap-2 mb-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                    <p className="text-xs font-medium text-emerald-700 uppercase tracking-wide">Passed</p>
                  </div>
                  <p className="text-3xl font-bold text-emerald-900">{stats.passed}</p>
                </div>

                <div className={`rounded-xl p-4 border shadow-sm ${
                  hasErrors
                    ? 'bg-rose-600 border-rose-700'
                    : 'bg-white border-slate-200'
                }`}>
                  <div className="flex items-center gap-2 mb-2">
                    <XCircle className={`w-4 h-4 ${hasErrors ? 'text-white' : 'text-slate-400'}`} />
                    <p className={`text-xs font-medium uppercase tracking-wide ${hasErrors ? 'text-rose-100' : 'text-slate-500'}`}>
                      Errors
                    </p>
                  </div>
                  <p className={`text-3xl font-bold ${hasErrors ? 'text-white' : 'text-slate-900'}`}>
                    {stats.errors}
                  </p>
                  {hasErrors && (
                    <p className="text-xs text-rose-200 mt-1">Action required</p>
                  )}
                </div>
              </div>

              {/* Dropzone */}
              <div
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                className={`border-2 border-dashed rounded-2xl p-10 text-center transition-all ${
                  isDragging
                    ? 'border-emerald-400 bg-emerald-50 scale-[1.01]'
                    : 'border-slate-300 bg-white hover:border-emerald-300 hover:bg-emerald-50/30'
                }`}
              >
                <div className="w-14 h-14 bg-gradient-to-br from-emerald-100 to-teal-100 rounded-2xl flex items-center justify-center mx-auto mb-4">
                  <Upload className="w-7 h-7 text-emerald-600" />
                </div>
                <p className="text-base font-semibold text-slate-900 mb-1">
                  Drop files here, or browse
                </p>
                <p className="text-sm text-slate-500 mb-6">CSV, Excel (.xlsx, .xls) — multiple files supported</p>
                <label htmlFor="file-upload">
                  <Button
                    type="button"
                    className="bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-700 hover:to-teal-700 shadow-md shadow-emerald-500/20"
                    asChild
                  >
                    <span>
                      <FileText className="w-4 h-4 mr-2" />
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

              {/* ── VISUAL DIVIDER ── */}
              {results.length > 0 && (
                <div className="flex items-center gap-4 pt-2">
                  <div className="flex-1 h-px bg-slate-200" />
                  <span className="text-xs font-semibold text-slate-400 uppercase tracking-widest">Session Results</span>
                  <div className="flex-1 h-px bg-slate-200" />
                </div>
              )}

              {/* ── SECTION 2: RESULTS ── */}
              {results.length > 0 && (
                <div className="space-y-4">

                  {/* Blocked Banner */}
                  {hasErrors && (
                    <div className="flex items-center gap-3 px-4 py-3 bg-rose-50 border border-rose-300 rounded-xl">
                      <AlertCircle className="w-5 h-5 text-rose-600 flex-shrink-0" />
                      <div className="flex-1">
                        <p className="text-sm font-bold text-rose-900">
                          {stats.errors} file{stats.errors !== 1 ? 's' : ''} require attention
                        </p>
                        <p className="text-xs text-rose-700">
                          No data will be submitted until all errors are resolved.
                        </p>
                      </div>
                    </div>
                  )}

                  {/* Results Header */}
                  <div className="flex items-center justify-between">
                    {/* Filter Tabs */}
                    <div className="flex items-center gap-1 bg-white border border-slate-200 rounded-lg p-1 shadow-sm">
                      {(['all', 'passed', 'errors'] as FilterMode[]).map(f => (
                        <button
                          key={f}
                          onClick={() => setFilter(f)}
                          className={`px-3 py-1.5 text-xs font-semibold rounded-md transition-colors capitalize ${
                            filter === f
                              ? 'bg-emerald-600 text-white shadow-sm'
                              : 'text-slate-500 hover:text-slate-800 hover:bg-slate-50'
                          }`}
                        >
                          {f === 'all' ? `All (${stats.total})` : f === 'passed' ? `Passed (${stats.passed})` : `Errors (${stats.errors})`}
                        </button>
                      ))}
                    </div>

                    {/* Export Summary */}
                    <Button
                      onClick={exportSummary}
                      disabled={hasErrors}
                      className="bg-emerald-600 hover:bg-emerald-700 text-white disabled:opacity-40 disabled:cursor-not-allowed text-sm"
                    >
                      <FileDown className="w-4 h-4 mr-2" />
                      Export Summary
                    </Button>
                  </div>

                  {/* Result Rows */}
                  <div className="space-y-2">
                    {filteredResults.map((result) => {
                      const isError = result.status === 'errors';
                      const isExpanded = expandedRows.has(result.id);
                      const isPassed = isPassedStatus(result.status);

                      return (
                        <div
                          key={result.id}
                          className={`rounded-xl border overflow-hidden shadow-sm transition-all ${
                            isError
                              ? 'border-rose-300 border-l-4 border-l-rose-600'
                              : 'border-slate-200'
                          }`}
                        >
                          {/* Row Header — always visible, clickable to expand */}
                          <div
                            className={`flex items-center gap-3 px-4 py-3 cursor-pointer transition-colors ${
                              isError ? 'bg-rose-50 hover:bg-rose-100' : 'bg-white hover:bg-slate-50'
                            }`}
                            onClick={() => toggleRow(result.id)}
                          >
                            <div className="flex-shrink-0">
                              {getStatusIcon(result.status)}
                            </div>

                            <div className="flex-1 min-w-0">
                              <p className={`text-sm font-semibold truncate ${isError ? 'text-rose-900' : 'text-slate-900'}`}>
                                {result.fileName}
                              </p>
                              <p className="text-xs text-slate-500">
                                {result.uploadedAt}
                                {result.processingTimeSeconds && <> · {result.processingTimeSeconds}s</>}
                                {' · '}{result.totalRecords} records
                              </p>
                            </div>

                            <div className="flex items-center gap-2 flex-shrink-0">
                              {isError && (
                                <span className="text-xs font-bold text-rose-700 bg-rose-100 px-2 py-0.5 rounded-full">
                                  {result.errorCount} error{result.errorCount !== 1 ? 's' : ''}
                                </span>
                              )}
                              {isPassed && result.recordsIngested !== undefined && result.status === 'completed' && (
                                <span className="text-xs text-emerald-700 bg-emerald-100 px-2 py-0.5 rounded-full font-medium">
                                  {result.recordsIngested} ingested
                                </span>
                              )}
                              <Badge
                                className={`text-[10px] uppercase tracking-wide ${
                                  isError ? 'bg-rose-600 hover:bg-rose-700' :
                                  result.status === 'validating' ? 'bg-slate-500 hover:bg-slate-600' :
                                  result.status === 'uploading' ? 'bg-purple-600 hover:bg-purple-700' :
                                  'bg-emerald-600 hover:bg-emerald-700'
                                }`}
                              >
                                {result.status}
                              </Badge>
                              {isExpanded
                                ? <ChevronDown className="w-4 h-4 text-slate-400" />
                                : <ChevronRight className="w-4 h-4 text-slate-400" />
                              }
                              <button
                                onClick={(e) => { e.stopPropagation(); deleteResult(result.id); }}
                                className="text-slate-300 hover:text-rose-500 transition-colors ml-1"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                              </button>
                            </div>
                          </div>

                          {/* Expanded Content */}
                          {isExpanded && (
                            <div className={`px-4 pb-4 pt-2 border-t ${isError ? 'bg-rose-50 border-rose-200' : 'bg-slate-50 border-slate-100'}`}>

                              {/* Stats row */}
                              <div className="grid grid-cols-3 gap-3 mb-4">
                                <div className="bg-white rounded-lg p-3 border border-slate-200">
                                  <p className="text-[10px] text-slate-500 uppercase tracking-wide mb-0.5">Total Records</p>
                                  <p className="text-lg font-bold text-slate-900">{result.totalRecords}</p>
                                </div>
                                <div className="bg-white rounded-lg p-3 border border-slate-200">
                                  <p className="text-[10px] text-slate-500 uppercase tracking-wide mb-0.5">Valid</p>
                                  <p className="text-lg font-bold text-emerald-700">{result.validRecords}</p>
                                </div>
                                <div className="bg-white rounded-lg p-3 border border-slate-200">
                                  <p className="text-[10px] text-slate-500 uppercase tracking-wide mb-0.5">Errors</p>
                                  <p className={`text-lg font-bold ${result.errorCount > 0 ? 'text-rose-700' : 'text-slate-900'}`}>
                                    {result.errorCount === 0 ? 'None' : result.errorCount}
                                  </p>
                                </div>
                              </div>

                              {/* Action buttons for passed files */}
                              {isPassed && result.errorCount === 0 && (
                                <div className="flex gap-2 mb-4">
                                  <button
                                    onClick={() => downloadFile(`/api/validation/download/${result.id}`)}
                                    className="inline-flex items-center gap-1.5 px-3 py-2 bg-emerald-600 text-white text-xs font-semibold rounded-lg hover:bg-emerald-700 transition-colors shadow-sm"
                                  >
                                    <Download className="w-3.5 h-3.5" />
                                    Download File
                                  </button>
                                  <button
                                    onClick={() => downloadFile(`/api/validation/download/${result.id}/report`)}
                                    className="inline-flex items-center gap-1.5 px-3 py-2 bg-slate-700 text-white text-xs font-semibold rounded-lg hover:bg-slate-800 transition-colors shadow-sm"
                                  >
                                    <FileText className="w-3.5 h-3.5" />
                                    Report
                                  </button>
                                </div>
                              )}

                              {/* Ingestion status */}
                              {result.status === 'uploading' || result.ingestionStatus === 'in_progress' ? (
                                <div className="flex items-center gap-2 p-3 bg-purple-50 border border-purple-200 rounded-lg mb-3">
                                  <div className="w-3.5 h-3.5 border-2 border-purple-600 border-t-transparent rounded-full animate-spin flex-shrink-0" />
                                  <p className="text-xs font-semibold text-purple-900">Uploading to analytics database…</p>
                                </div>
                              ) : result.status === 'completed' && result.recordsIngested !== undefined ? (
                                <div className="flex items-center gap-2 p-3 bg-emerald-50 border border-emerald-200 rounded-lg mb-3">
                                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 flex-shrink-0" />
                                  <p className="text-xs text-emerald-800">
                                    {result.recordsIngested > 0
                                      ? <><strong>{result.recordsIngested}</strong> new records added to analytics database{result.totalRecords - result.recordsIngested > 0 && <> · {result.totalRecords - result.recordsIngested} duplicates skipped</>}</>
                                      : <>All {result.totalRecords} records already exist in the database</>
                                    }
                                  </p>
                                </div>
                              ) : null}

                              {/* Error table */}
                              {isError && result.errors && result.errors.length > 0 && (
                                <div>
                                  <p className="text-xs font-bold text-rose-800 mb-2 uppercase tracking-wide">
                                    Validation Errors — fix all issues and resubmit
                                  </p>
                                  <div className="rounded-lg border border-rose-200 overflow-hidden">
                                    <table className="w-full text-xs">
                                      <thead>
                                        <tr className="bg-rose-100 text-rose-800">
                                          <th className="text-left px-3 py-2 font-semibold w-16">Row</th>
                                          <th className="text-left px-3 py-2 font-semibold w-28">Field</th>
                                          <th className="text-left px-3 py-2 font-semibold w-20">Code</th>
                                          <th className="text-left px-3 py-2 font-semibold">Issue</th>
                                        </tr>
                                      </thead>
                                      <tbody>
                                        {result.errors.map((err, idx) => (
                                          <tr key={idx} className={`border-t border-rose-100 ${idx % 2 === 0 ? 'bg-white' : 'bg-rose-50/40'}`}>
                                            <td className="px-3 py-2 font-mono text-slate-600">{err.row || '—'}</td>
                                            <td className="px-3 py-2 font-medium text-slate-800">{err.field}</td>
                                            <td className="px-3 py-2 font-mono text-rose-700">{err.code}</td>
                                            <td className="px-3 py-2 text-slate-700">{err.message}</td>
                                          </tr>
                                        ))}
                                      </tbody>
                                    </table>
                                  </div>
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
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
