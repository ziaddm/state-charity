import { useState, useEffect, useRef } from 'react';
import { apiFetch } from '../lib/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer
} from 'recharts';
import { TrendingUp, Calendar, DollarSign, Users, Upload } from 'lucide-react';

interface MetricOption {
  field: string;
  label: string;
  type: string;
  aggregations: string[];
}

interface AnalyticsDataPoint {
  label: string;
  value: number;
  count: number;
  secondary_label?: string;
}

interface AnalyticsResponse {
  success: boolean;
  data: AnalyticsDataPoint[];
  chart_type: string;
  primary_metric: string;
  secondary_metric?: string;
  time_period: string;
  date_range: {
    start: string;
    end: string;
  };
}

interface AnalyticsSummary {
  total_visits: number;
  unique_patients: number;
  total_charges: number;
  total_payments: number;
  uncompensated_visits: number;
  year: number;
}

const COLORS = ['#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#14b8a6', '#f97316'];

export default function Analytics() {
  const [metrics, setMetrics] = useState<MetricOption[]>([]);
  const [timePeriod, setTimePeriod] = useState<string>('month');
  const [primaryMetric, setPrimaryMetric] = useState<string>('record_id');
  const [secondaryMetric, setSecondaryMetric] = useState<string>('');
  const [analyticsData, setAnalyticsData] = useState<AnalyticsResponse | null>(null);
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadMessage, setUploadMessage] = useState<string>('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Load available metrics
  useEffect(() => {
    const fetchMetrics = async () => {
      try {
        const response = await apiFetch('/api/analytics/metrics');

        if (response.ok) {
          const data = await response.json();
          setMetrics(data);
        }
      } catch (error) {
        console.error('Failed to load metrics:', error);
      }
    };

    fetchMetrics();
  }, []);

  // Load summary
  useEffect(() => {
    const fetchSummary = async () => {
      try {
        const response = await apiFetch('/api/analytics/summary');

        if (response.ok) {
          const data = await response.json();
          setSummary(data.summary);
        }
      } catch (error) {
        console.error('Failed to load summary:', error);
      }
    };

    fetchSummary();
  }, []);

  // Query analytics data
  useEffect(() => {
    if (!primaryMetric) return;

    const fetchAnalytics = async () => {
      setIsLoading(true);
      try {
        const response = await apiFetch('/api/analytics/query', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            time_period: timePeriod,
            primary_metric: primaryMetric,
            secondary_metric: secondaryMetric || undefined
          })
        });

        if (response.ok) {
          const data = await response.json();
          setAnalyticsData(data);
        }
      } catch (error) {
        console.error('Failed to load analytics:', error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchAnalytics();
  }, [timePeriod, primaryMetric, secondaryMetric]);

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    setUploadMessage('');

    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await apiFetch('/api/analytics/upload', {
        method: 'POST',
        body: formData
      });

      const result = await response.json();

      if (response.ok) {
        setUploadMessage(`Success! ${result.records_ingested} records ingested.`);
        // Refresh summary and analytics data
        window.location.reload();
      } else {
        setUploadMessage(`Upload failed: ${result.detail || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Upload error:', error);
      setUploadMessage('Upload failed: Network error');
    } finally {
      setIsUploading(false);
      // Reset file input
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }).format(value);
  };

  const renderChart = () => {
    if (!analyticsData || !analyticsData.data || analyticsData.data.length === 0) {
      return (
        <div className="flex items-center justify-center h-64">
          <p className="text-slate-500">No data available for the selected criteria</p>
        </div>
      );
    }

    const chartData = analyticsData.data.map(d => ({
      name: d.label,
      value: d.value,
      count: d.count,
      secondaryLabel: d.secondary_label
    }));

    if (analyticsData.chart_type === 'line') {
      return (
        <ResponsiveContainer width="100%" height={400}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Line type="monotone" dataKey="value" stroke="#3b82f6" name="Count" />
          </LineChart>
        </ResponsiveContainer>
      );
    } else if (analyticsData.chart_type === 'pie') {
      return (
        <ResponsiveContainer width="100%" height={400}>
          <PieChart>
            <Pie
              data={chartData}
              dataKey="value"
              nameKey="name"
              cx="50%"
              cy="50%"
              outerRadius={120}
              fill="#3b82f6"
              label
            >
              {chartData.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
              ))}
            </Pie>
            <Tooltip />
            <Legend />
          </PieChart>
        </ResponsiveContainer>
      );
    } else {
      // Bar chart (default)
      return (
        <ResponsiveContainer width="100%" height={400}>
          <BarChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Bar dataKey="value" fill="#3b82f6" name="Count" />
          </BarChart>
        </ResponsiveContainer>
      );
    }
  };

  return (
    <div className="space-y-6">
      {/* Upload Section */}
      <Card>
        <CardHeader>
          <CardTitle>Upload Data for Analytics</CardTitle>
          <CardDescription>
            Upload CSV files directly to populate analytics data
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-4">
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv"
              onChange={handleFileUpload}
              className="hidden"
            />
            <Button
              onClick={() => fileInputRef.current?.click()}
              disabled={isUploading}
              className="flex items-center gap-2"
            >
              <Upload className="w-4 h-4" />
              {isUploading ? 'Uploading...' : 'Upload CSV'}
            </Button>
            {uploadMessage && (
              <p className={`text-sm ${uploadMessage.startsWith('Success') ? 'text-green-600' : 'text-red-600'}`}>
                {uploadMessage}
              </p>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Summary Cards */}
      {summary && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-slate-600">Total Visits</p>
                  <p className="text-2xl font-bold text-slate-900 mt-1">{summary.total_visits.toLocaleString()}</p>
                  <p className="text-xs text-slate-500 mt-1">YTD {summary.year}</p>
                </div>
                <TrendingUp className="w-8 h-8 text-blue-500" />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-slate-600">Unique Patients</p>
                  <p className="text-2xl font-bold text-slate-900 mt-1">{summary.unique_patients.toLocaleString()}</p>
                  <p className="text-xs text-slate-500 mt-1">YTD {summary.year}</p>
                </div>
                <Users className="w-8 h-8 text-green-500" />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-slate-600">Total Charges</p>
                  <p className="text-2xl font-bold text-slate-900 mt-1">{formatCurrency(summary.total_charges)}</p>
                  <p className="text-xs text-slate-500 mt-1">YTD {summary.year}</p>
                </div>
                <DollarSign className="w-8 h-8 text-purple-500" />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-slate-600">Uncompensated Care</p>
                  <p className="text-2xl font-bold text-slate-900 mt-1">{summary.uncompensated_visits.toLocaleString()}</p>
                  <p className="text-xs text-slate-500 mt-1">YTD {summary.year}</p>
                </div>
                <Calendar className="w-8 h-8 text-amber-500" />
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Chart Configuration */}
      <Card>
        <CardHeader>
          <CardTitle>Data Visualization</CardTitle>
          <CardDescription>
            Select time period and metrics to visualize your data
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
            {/* Time Period Selector */}
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">
                Time Period
              </label>
              <select
                value={timePeriod}
                onChange={(e) => setTimePeriod(e.target.value)}
                className="w-full px-3 py-2 border border-slate-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="week">Last 7 Days</option>
                <option value="month">Last 30 Days</option>
                <option value="quarter">Last 90 Days</option>
                <option value="ytd">Year to Date</option>
                <option value="all">All Time</option>
              </select>
            </div>

            {/* Primary Metric Selector */}
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">
                Primary Metric
              </label>
              <select
                value={primaryMetric}
                onChange={(e) => setPrimaryMetric(e.target.value)}
                className="w-full px-3 py-2 border border-slate-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {metrics.map(m => (
                  <option key={m.field} value={m.field}>{m.label}</option>
                ))}
              </select>
            </div>

            {/* Secondary Metric Selector */}
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">
                Secondary Metric (Optional)
              </label>
              <select
                value={secondaryMetric}
                onChange={(e) => setSecondaryMetric(e.target.value)}
                className="w-full px-3 py-2 border border-slate-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">None</option>
                {metrics
                  .filter(m => m.field !== primaryMetric && m.type === 'categorical')
                  .map(m => (
                    <option key={m.field} value={m.field}>{m.label}</option>
                  ))}
              </select>
            </div>
          </div>

          {/* Chart Display */}
          {isLoading ? (
            <div className="flex items-center justify-center h-64">
              <div className="w-12 h-12 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
            </div>
          ) : (
            renderChart()
          )}

          {analyticsData && (
            <div className="mt-4 p-4 bg-slate-50 rounded-lg border border-slate-200">
              <p className="text-sm text-slate-600">
                Showing data from <span className="font-semibold">{new Date(analyticsData.date_range.start).toLocaleDateString()}</span> to <span className="font-semibold">{new Date(analyticsData.date_range.end).toLocaleDateString()}</span>
              </p>
              <p className="text-sm text-slate-600 mt-1">
                Chart Type: <span className="font-semibold">{analyticsData.chart_type.replace('_', ' ')}</span> •
                Data Points: <span className="font-semibold">{analyticsData.data.length}</span>
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
