import { useState, useEffect } from 'react';
import { apiFetch } from '../lib/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell
} from 'recharts';
import {
  TrendingUp,
  TrendingDown,
  Users,
  DollarSign,
  FileText,
  AlertCircle,
  ArrowUpRight,
  ArrowDownRight,
  Minus,
  Activity,
  HeartPulse
} from 'lucide-react';

interface ExecutiveSummary {
  total_visits: number;
  unique_patients: number;
  total_charges: number;
  total_payments: number;
  uncompensated_visits: number;
  year: number;
}

interface FPLData {
  label: string;
  value: number;
}

interface VisitTrend {
  label: string;
  value: number;
}

interface YoYMetrics {
  visits: number;
  patients: number;
  charges: number;
  charity_care: number;
}

interface YoYComparison {
  current_year: number;
  last_year: number;
  current: YoYMetrics;
  previous: YoYMetrics;
}

interface DiagnosisData {
  label: string;
  value: number;
}

interface PayorData {
  label: string;
  value: number;
}

const EMERALD_COLORS = [
  '#059669',
  '#10b981',
  '#34d399',
  '#047857',
  '#6ee7b7',
  '#065f46',
];

export default function AnalyticsExecutive() {
  const [summary, setSummary] = useState<ExecutiveSummary | null>(null);
  const [fplData, setFplData] = useState<FPLData[]>([]);
  const [visitTrends, setVisitTrends] = useState<VisitTrend[]>([]);
  const [yoyData, setYoyData] = useState<YoYComparison | null>(null);
  const [diagnosisData, setDiagnosisData] = useState<DiagnosisData[]>([]);
  const [payorData, setPayorData] = useState<PayorData[]>([]);
  const [selectedPeriod, setSelectedPeriod] = useState<string>('all');
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    fetchAnalytics();
  }, [selectedPeriod]);

  const fetchAnalytics = async () => {
    setIsLoading(true);
    try {

      // Fetch all analytics in parallel
      const [summaryRes, fpl, trends, yoy, diagnoses, payors] = await Promise.all([
        apiFetch(`/api/analytics/summary?time_period=${selectedPeriod}`),
        apiFetch(`/api/analytics/fpl-distribution?time_period=${selectedPeriod}`).then(r => r.json()),
        apiFetch(`/api/analytics/visit-trends?time_period=${selectedPeriod}`).then(r => r.json()),
        apiFetch('/api/analytics/yoy-comparison').then(r => r.json()),
        apiFetch(`/api/analytics/top-diagnoses?time_period=${selectedPeriod}&limit=5`).then(r => r.json()),
        apiFetch(`/api/analytics/payor-distribution?time_period=${selectedPeriod}`).then(r => r.json()),
      ]);

      if (summaryRes.ok) {
        const data = await summaryRes.json();
        setSummary(data.summary);
      }

      if (fpl.success) setFplData(fpl.data);
      if (trends.success) setVisitTrends(trends.data);
      if (yoy.success) setYoyData(yoy);
      if (diagnoses.success) setDiagnosisData(diagnoses.data);
      if (payors.success) setPayorData(payors.data);

    } catch (error) {
      console.error('Failed to load analytics:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const getPeriodLabel = (period: string): string => {
    const labels: { [key: string]: string } = {
      'week': 'Last 7 Days',
      'month': 'Last 30 Days',
      'quarter': 'Last 90 Days',
      'ytd': 'Year to Date',
      'all': 'All Time'
    };
    return labels[period] || period;
  };

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }).format(value);
  };

  const formatNumber = (value: number) => {
    return new Intl.NumberFormat('en-US').format(value);
  };

  const getTrendIcon = (change: number) => {
    if (change > 0) return <ArrowUpRight className="w-4 h-4 text-green-600" />;
    if (change < 0) return <ArrowDownRight className="w-4 h-4 text-red-600" />;
    return <Minus className="w-4 h-4 text-slate-400" />;
  };

  const getTrendColor = (change: number) => {
    if (change > 0) return 'text-green-600';
    if (change < 0) return 'text-red-600';
    return 'text-slate-600';
  };

  const collectionRate = summary
    ? (summary.total_payments / summary.total_charges * 100)
    : 0;

  const uncompensatedRate = summary
    ? (summary.uncompensated_visits / summary.total_visits * 100)
    : 0;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-12 h-12 border-4 border-emerald-600 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-xl font-bold text-slate-900">Analytics Dashboard</h1>
          <p className="text-xs text-slate-600 mt-1">
            {getPeriodLabel(selectedPeriod)} Performance Overview
          </p>
        </div>

        {/* Period Selector */}
        <select
          value={selectedPeriod}
          onChange={(e) => setSelectedPeriod(e.target.value)}
          className="px-3 py-1.5 text-sm border border-slate-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
        >
          <option value="month">Last 30 Days</option>
          <option value="quarter">Last 90 Days</option>
          <option value="ytd">Year to Date</option>
          <option value="all">All Time</option>
        </select>
      </div>

      {/* Key Metrics - Top Row */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Visits */}
        <Card>
          <CardContent className="pt-4 pb-4">
            <div>
              <p className="text-sm font-bold text-slate-900 mb-1.5">Total Visits</p>
              <p className="text-xl text-slate-900 mb-1.5">
                {summary ? formatNumber(summary.total_visits) : '—'}
              </p>
              <p className="text-xs text-slate-500">
                {getPeriodLabel(selectedPeriod)}
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Unique Patients */}
        <Card>
          <CardContent className="pt-4 pb-4">
            <div>
              <p className="text-sm font-bold text-slate-900 mb-1.5">Unique Patients</p>
              <p className="text-xl text-slate-900 mb-1.5">
                {summary ? formatNumber(summary.unique_patients) : '—'}
              </p>
              <p className="text-xs text-slate-500">
                Individuals served
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Total Charges */}
        <Card>
          <CardContent className="pt-4 pb-4">
            <div>
              <p className="text-sm font-bold text-slate-900 mb-1.5">Total Charges</p>
              <p className="text-xl text-slate-900 mb-1.5">
                {summary ? formatCurrency(summary.total_charges) : '—'}
              </p>
              <p className="text-[10px] text-slate-500 mt-1">
                Billed amount
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Collection Rate */}
        <Card>
          <CardContent className="pt-4 pb-4">
            <div>
              <p className="text-sm font-bold text-slate-900 mb-1.5">Collection Rate</p>
              <p className="text-xl text-slate-900 mb-1.5">
                {collectionRate.toFixed(1)}%
              </p>
              <p className="text-xs text-slate-500">
                {summary ? formatCurrency(summary.total_payments) : '—'} collected
              </p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Key Insights */}
      <Card>
        <CardHeader className="py-3 px-5">
          <CardTitle className="text-base">Key Insights</CardTitle>
        </CardHeader>
        <CardContent className="px-5 pb-4">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
            <div className="p-3 bg-emerald-50 rounded-lg border border-emerald-200">
              <p className="text-xs font-medium text-emerald-900">Average Visit Value</p>
              <p className="text-xl font-bold text-emerald-700 mt-1">
                {summary ? formatCurrency(summary.total_charges / summary.total_visits) : '—'}
              </p>
              <p className="text-[10px] text-emerald-600 mt-0.5">Per patient encounter</p>
            </div>

            <div className="p-3 bg-emerald-50 rounded-lg border border-emerald-200">
              <p className="text-xs font-medium text-emerald-900">Visits Per Patient</p>
              <p className="text-xl font-bold text-emerald-700 mt-1">
                {summary ? (summary.total_visits / summary.unique_patients).toFixed(1) : '—'}
              </p>
              <p className="text-[10px] text-emerald-600 mt-0.5">Average encounters</p>
            </div>

            <div className="p-3 bg-emerald-50 rounded-lg border border-emerald-200">
              <p className="text-xs font-medium text-emerald-900">Payment Rate</p>
              <p className="text-xl font-bold text-emerald-700 mt-1">
                {summary ? formatCurrency(summary.total_payments / summary.total_visits) : '—'}
              </p>
              <p className="text-[10px] text-emerald-600 mt-0.5">Average collected per visit</p>
            </div>

            <div className="p-3 bg-rose-50 rounded-lg border border-rose-200">
              <div className="flex items-center gap-1.5 mb-1">
                <AlertCircle className="w-3 h-3 text-rose-700" />
                <p className="text-xs font-medium text-rose-900">Uncompensated Care</p>
              </div>
              <div className="flex items-baseline gap-2">
                <p className="text-xl font-bold text-rose-700">
                  {summary ? formatNumber(summary.uncompensated_visits) : '—'}
                </p>
                <p className="text-sm font-bold text-rose-600">
                  ({uncompensatedRate.toFixed(1)}%)
                </p>
              </div>
              <p className="text-[10px] text-rose-600 mt-0.5">
                {summary ? formatCurrency(summary.total_charges - summary.total_payments) : '—'} uncollected
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* FPL Distribution & Charity Tiers */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Income Distribution</CardTitle>
            <CardDescription>Patient household income ranges</CardDescription>
          </CardHeader>
          <CardContent className="pt-6">
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={fplData} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#d1fae5" />
                <XAxis type="number" />
                <YAxis dataKey="label" type="category" width={120} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#ecfdf5',
                    border: '1px solid #10b981',
                    borderRadius: '8px'
                  }}
                />
                <Bar dataKey="value" radius={[0, 8, 8, 0]}>
                  {fplData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={EMERALD_COLORS[index % EMERALD_COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Visit Trends</CardTitle>
            <CardDescription>Monthly visit volume over time</CardDescription>
          </CardHeader>
          <CardContent className="pt-6">
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={visitTrends}>
                <CartesianGrid strokeDasharray="3 3" stroke="#d1fae5" />
                <XAxis dataKey="label" style={{ fontSize: '11px' }} angle={-35} textAnchor="end" height={60} />
                <YAxis style={{ fontSize: '11px' }} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#ecfdf5',
                    border: '1px solid #10b981',
                    borderRadius: '8px'
                  }}
                />
                <Line
                  type="monotone"
                  dataKey="value"
                  name="Visits"
                  stroke="#059669"
                  strokeWidth={2}
                  dot={{ fill: '#059669', r: 4 }}
                  activeDot={{ r: 6 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      {/* Top Diagnoses & Payor Distribution */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <CardHeader className="py-3 px-5">
            <CardTitle className="text-base">Top 5 Diagnosis Codes (ICD-10)</CardTitle>
            <CardDescription className="text-sm">Most common primary diagnoses</CardDescription>
          </CardHeader>
          <CardContent className="px-5 pb-4">
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={diagnosisData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#d1fae5" />
                <XAxis dataKey="label" angle={-45} textAnchor="end" height={80} style={{ fontSize: '11px' }} />
                <YAxis style={{ fontSize: '11px' }} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#ecfdf5',
                    border: '1px solid #10b981',
                    borderRadius: '8px',
                    fontSize: '12px'
                  }}
                />
                <Bar dataKey="value" name="Patient Count" radius={[6, 6, 0, 0]}>
                  {diagnosisData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={EMERALD_COLORS[index % EMERALD_COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="py-3 px-5">
            <CardTitle className="text-base">Primary Insurance Distribution</CardTitle>
            <CardDescription className="text-sm">Patients by insurance type</CardDescription>
          </CardHeader>
          <CardContent className="px-5 pb-4">
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={payorData} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#d1fae5" />
                <XAxis type="number" style={{ fontSize: '11px' }} />
                <YAxis dataKey="label" type="category" width={100} style={{ fontSize: '11px' }} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#ecfdf5',
                    border: '1px solid #10b981',
                    borderRadius: '8px',
                    fontSize: '12px'
                  }}
                />
                <Bar dataKey="value" name="Patient Count" radius={[0, 6, 6, 0]}>
                  {payorData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={EMERALD_COLORS[index % EMERALD_COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
