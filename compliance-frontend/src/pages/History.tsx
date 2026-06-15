import { useState, useEffect } from 'react';
import { apiFetch, downloadFile } from '../lib/api';
import { CheckCircle2, XCircle, AlertCircle, Download, FileText, RefreshCw, Search, ChevronDown, ChevronRight } from 'lucide-react';
import { Badge } from '../components/ui/badge';

interface HistoryRun {
  id: string;
  filename: string;
  status: string;
  ingestion_status: string | null;
  records_ingested: number;
  error_count: number;
  warning_count: number;
  record_count: number;
  valid_count: number;
  has_submission_file: boolean;
  started_at: string | null;
  completed_at: string | null;
  created_at: string | null;
}

type StatusFilter = 'all' | 'completed' | 'errors';

export default function SubmissionHistory() {
  const [runs, setRuns] = useState<HistoryRun[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());

  const fetchRuns = async () => {
    setIsLoading(true);
    setFetchError(null);
    try {
      const res = await apiFetch('/api/validation/runs');
      if (res.ok) {
        const data = await res.json();
        setRuns(data.runs || []);
      } else {
        setFetchError(res.status === 401 ? 'Session expired — please sign out and sign back in.' : `Failed to load history (${res.status})`);
      }
    } catch (err) {
      setFetchError('Network error — check your connection and try again.');
      console.error('Failed to fetch runs:', err);
    } finally {
      setIsLoading(false);
    }
  };


  useEffect(() => {
    fetchRuns();
  }, []);

  const toggleRow = (id: string) => {
    setExpandedRows(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const formatDate = (iso: string | null) => {
    if (!iso) return '—';
    return new Date(iso).toLocaleString(undefined, {
      month: 'short', day: 'numeric', year: 'numeric',
      hour: '2-digit', minute: '2-digit'
    });
  };

  const isPassedStatus = (status: string) =>
    status === 'ready' || status === 'completed' || status === 'uploading' || status === 'validating';

  const filtered = runs.filter(r => {
    const matchesSearch = !search || r.filename?.toLowerCase().includes(search.toLowerCase());
    const matchesStatus =
      statusFilter === 'all' ||
      (statusFilter === 'completed' && isPassedStatus(r.status)) ||
      (statusFilter === 'errors' && r.status === 'errors');
    return matchesSearch && matchesStatus;
  });

  const stats = {
    total: runs.length,
    passed: runs.filter(r => isPassedStatus(r.status)).length,
    errors: runs.filter(r => r.status === 'errors').length,
    totalIngested: runs.reduce((sum, r) => sum + (r.records_ingested || 0), 0),
  };

  const getStatusBadge = (run: HistoryRun) => {
    const isError = run.status === 'errors';
    const isPassed = isPassedStatus(run.status);

    return (
      <Badge className={`text-[10px] uppercase tracking-wide ${
        isError ? 'bg-rose-600 hover:bg-rose-700' :
        isPassed ? 'bg-emerald-600 hover:bg-emerald-700' :
        'bg-slate-500 hover:bg-slate-600'
      }`}>
        {run.status}
      </Badge>
    );
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 mb-1">Submission History</h1>
          <p className="text-sm text-slate-500">All file submissions for your facility</p>
        </div>
        <button
          onClick={fetchRuns}
          disabled={isLoading}
          className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-slate-600 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors shadow-sm disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-4 gap-4">
        <div className="bg-white rounded-xl p-4 border border-slate-200 shadow-sm">
          <p className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-1">Total Submissions</p>
          <p className="text-3xl font-bold text-slate-900">{stats.total}</p>
        </div>
        <div className="bg-emerald-50 rounded-xl p-4 border border-emerald-200 shadow-sm">
          <p className="text-xs font-medium text-emerald-700 uppercase tracking-wide mb-1">Passed</p>
          <p className="text-3xl font-bold text-emerald-900">{stats.passed}</p>
        </div>
        <div className={`rounded-xl p-4 border shadow-sm ${stats.errors > 0 ? 'bg-rose-600 border-rose-700' : 'bg-white border-slate-200'}`}>
          <p className={`text-xs font-medium uppercase tracking-wide mb-1 ${stats.errors > 0 ? 'text-rose-100' : 'text-slate-500'}`}>
            Failed
          </p>
          <p className={`text-3xl font-bold ${stats.errors > 0 ? 'text-white' : 'text-slate-900'}`}>{stats.errors}</p>
        </div>
        <div className="bg-white rounded-xl p-4 border border-slate-200 shadow-sm">
          <p className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-1">Records Ingested</p>
          <p className="text-3xl font-bold text-slate-900">{stats.totalIngested.toLocaleString()}</p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            type="text"
            placeholder="Search by filename…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full pl-9 pr-3 py-2 text-sm border border-slate-200 rounded-lg bg-white shadow-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
          />
        </div>
        <div className="flex items-center gap-1 bg-white border border-slate-200 rounded-lg p-1 shadow-sm">
          {(['all', 'completed', 'errors'] as StatusFilter[]).map(f => (
            <button
              key={f}
              onClick={() => setStatusFilter(f)}
              className={`px-3 py-1.5 text-xs font-semibold rounded-md transition-colors capitalize ${
                statusFilter === f
                  ? 'bg-emerald-600 text-white shadow-sm'
                  : 'text-slate-500 hover:text-slate-800 hover:bg-slate-50'
              }`}
            >
              {f === 'all' ? `All (${stats.total})` : f === 'completed' ? `Passed (${stats.passed})` : `Failed (${stats.errors})`}
            </button>
          ))}
        </div>
      </div>

      {/* Error banner */}
      {fetchError && (
        <div className="flex items-center gap-3 px-4 py-3 bg-rose-50 border border-rose-300 rounded-xl">
          <XCircle className="w-4 h-4 text-rose-600 flex-shrink-0" />
          <p className="text-sm text-rose-800">{fetchError}</p>
        </div>
      )}

      {/* Table */}
      {isLoading ? (
        <div className="flex items-center justify-center h-48">
          <div className="w-10 h-10 border-4 border-emerald-600 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-48 text-slate-400">
          <FileText className="w-10 h-10 mb-3" />
          <p className="text-sm font-medium">No submissions found</p>
          <p className="text-xs mt-1">{runs.length > 0 ? 'Try adjusting the filter or search' : 'Upload a file to get started'}</p>
        </div>
      ) : (
        <div className="space-y-2">
          {filtered.map(run => {
            const isError = run.status === 'errors';
            const isPassed = isPassedStatus(run.status);
            const isExpanded = expandedRows.has(run.id);

            return (
              <div
                key={run.id}
                className={`rounded-xl border overflow-hidden shadow-sm ${
                  isError ? 'border-rose-300 border-l-4 border-l-rose-600' : 'border-slate-200'
                }`}
              >
                {/* Row */}
                <button
                  className={`w-full flex items-center gap-4 px-4 py-3 text-left transition-colors ${
                    isError ? 'bg-rose-50 hover:bg-rose-100' : 'bg-white hover:bg-slate-50'
                  }`}
                  onClick={() => toggleRow(run.id)}
                >
                  <div className="flex-shrink-0">
                    {isError
                      ? <XCircle className="w-4 h-4 text-rose-600" />
                      : isPassed
                      ? <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                      : <AlertCircle className="w-4 h-4 text-slate-400" />
                    }
                  </div>

                  <div className="flex-1 min-w-0">
                    <p className={`text-sm font-semibold truncate ${isError ? 'text-rose-900' : 'text-slate-900'}`}>
                      {run.filename || 'Unknown file'}
                    </p>
                    <p className="text-xs text-slate-500">{formatDate(run.created_at)}</p>
                  </div>

                  <div className="flex items-center gap-6 flex-shrink-0 text-right">
                    <div className="hidden md:block">
                      <p className="text-[10px] text-slate-400 uppercase tracking-wide">Records</p>
                      <p className="text-sm font-semibold text-slate-700">{run.record_count || '—'}</p>
                    </div>
                    <div className="hidden md:block">
                      <p className="text-[10px] text-slate-400 uppercase tracking-wide">Ingested</p>
                      <p className="text-sm font-semibold text-emerald-700">{isPassed ? run.records_ingested : '—'}</p>
                    </div>
                    <div className="hidden md:block">
                      <p className="text-[10px] text-slate-400 uppercase tracking-wide">Errors</p>
                      <p className={`text-sm font-semibold ${isError ? 'text-rose-700' : 'text-slate-500'}`}>
                        {isError ? run.error_count : 'None'}
                      </p>
                    </div>
                    {getStatusBadge(run)}
                    {isExpanded
                      ? <ChevronDown className="w-4 h-4 text-slate-400" />
                      : <ChevronRight className="w-4 h-4 text-slate-400" />
                    }
                  </div>
                </button>

                {/* Expanded detail */}
                {isExpanded && (
                  <div className={`px-4 pb-4 pt-3 border-t ${isError ? 'bg-rose-50 border-rose-200' : 'bg-slate-50 border-slate-100'}`}>
                    <div className="grid grid-cols-4 gap-3 mb-4">
                      <div className="bg-white rounded-lg p-3 border border-slate-200">
                        <p className="text-[10px] text-slate-500 uppercase tracking-wide mb-0.5">Total Records</p>
                        <p className="text-xl font-bold text-slate-900">{run.record_count || '—'}</p>
                      </div>
                      <div className="bg-white rounded-lg p-3 border border-slate-200">
                        <p className="text-[10px] text-slate-500 uppercase tracking-wide mb-0.5">Valid</p>
                        <p className="text-xl font-bold text-emerald-700">{run.valid_count || (run.record_count - run.error_count) || '—'}</p>
                      </div>
                      <div className="bg-white rounded-lg p-3 border border-slate-200">
                        <p className="text-[10px] text-slate-500 uppercase tracking-wide mb-0.5">Errors</p>
                        <p className={`text-xl font-bold ${run.error_count > 0 ? 'text-rose-700' : 'text-slate-500'}`}>
                          {run.error_count > 0 ? run.error_count : 'None'}
                        </p>
                      </div>
                      <div className="bg-white rounded-lg p-3 border border-slate-200">
                        <p className="text-[10px] text-slate-500 uppercase tracking-wide mb-0.5">Records Ingested</p>
                        <p className="text-xl font-bold text-slate-900">{isPassed ? run.records_ingested : '—'}</p>
                      </div>
                    </div>

                    {/* Ingestion status pill */}
                    {isPassed && (
                      <div className="flex items-center gap-2 mb-4">
                        <span className={`text-xs px-2.5 py-1 rounded-full font-medium ${
                          run.ingestion_status === 'completed' ? 'bg-emerald-100 text-emerald-800' :
                          run.ingestion_status === 'in_progress' ? 'bg-purple-100 text-purple-800' :
                          run.ingestion_status === 'failed' ? 'bg-rose-100 text-rose-800' :
                          'bg-slate-100 text-slate-600'
                        }`}>
                          DB: {run.ingestion_status || 'pending'}
                        </span>
                        <span className="text-xs text-slate-400">
                          Submitted {formatDate(run.created_at)}
                          {run.completed_at && ` · Completed ${formatDate(run.completed_at)}`}
                        </span>
                      </div>
                    )}

                    {/* Actions */}
                    {isPassed && run.has_submission_file && (
                      <div className="flex gap-2">
                        <button
                          onClick={() => downloadFile(`/api/validation/download/${run.id}`)}
                          className="inline-flex items-center gap-1.5 px-3 py-2 bg-emerald-600 text-white text-xs font-semibold rounded-lg hover:bg-emerald-700 transition-colors shadow-sm"
                        >
                          <Download className="w-3.5 h-3.5" />
                          Download File
                        </button>
                        <button
                          onClick={() => downloadFile(`/api/validation/download/${run.id}/report`)}
                          className="inline-flex items-center gap-1.5 px-3 py-2 bg-slate-700 text-white text-xs font-semibold rounded-lg hover:bg-slate-800 transition-colors shadow-sm"
                        >
                          <FileText className="w-3.5 h-3.5" />
                          Report Bundle
                        </button>
                      </div>
                    )}

                    {isError && (
                      <div className="mt-2 p-3 bg-rose-100 border border-rose-200 rounded-lg">
                        <p className="text-xs font-bold text-rose-900 mb-1">
                          This submission was rejected — {run.error_count} error{run.error_count !== 1 ? 's' : ''} found
                        </p>
                        <p className="text-xs text-rose-700">
                          No data was ingested. Re-upload the corrected file from the Upload tab.
                        </p>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
