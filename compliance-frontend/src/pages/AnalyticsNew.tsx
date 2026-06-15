import { useState, useEffect } from 'react';
import { apiFetch } from '../lib/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Cell
} from 'recharts';
import { TrendingUp, TrendingDown, Users, DollarSign, HeartPulse, Activity } from 'lucide-react';

interface FPLData {
  label: string;
  value: number;
}

interface CharityTier {
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

const EMERALD_COLORS = {
  50: '#ecfdf5',
  100: '#d1fae5',
  200: '#a7f3d0',
  300: '#6ee7b7',
  400: '#34d399',
  500: '#10b981',
  600: '#059669',
  700: '#047857',
  800: '#065f46',
  900: '#064e3b',
};

const CHART_COLORS = [
  EMERALD_COLORS[600],
  EMERALD_COLORS[500],
  EMERALD_COLORS[400],
  EMERALD_COLORS[700],
  EMERALD_COLORS[300],
  EMERALD_COLORS[800],
];

const TIME_PERIODS = [
  { label: 'Week', value: 'week' },
  { label: 'Month', value: 'month' },
  { label: 'Quarter', value: 'quarter' },
  { label: 'YTD', value: 'ytd' },
  { label: 'All', value: 'all' },
];

export default function AnalyticsNew() {
  const [fplData, setFplData] = useState<FPLData[]>([]);
  const [charityTiers, setCharityTiers] = useState<CharityTier[]>([]);
  const [yoyData, setYoyData] = useState<YoYComparison | null>(null);
  const [diagnosisData, setDiagnosisData] = useState<DiagnosisData[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [timePeriod, setTimePeriod] = useState('all');

  useEffect(() => {
    loadAllAnalytics(timePeriod);
  }, [timePeriod]);

  const loadAllAnalytics = async (period: string) => {
    setIsLoading(true);

    try {
      const [fpl, tiers, yoy, diagnoses] = await Promise.all([
        apiFetch(`/api/analytics/fpl-distribution?time_period=${period}`).then(r => r.json()),
        apiFetch(`/api/analytics/charity-tiers?time_period=${period}`).then(r => r.json()),
        apiFetch('/api/analytics/yoy-comparison').then(r => r.json()),
        apiFetch(`/api/analytics/top-diagnoses?time_period=${period}`).then(r => r.json()),
      ]);

      if (fpl.success) setFplData(fpl.data);
      if (tiers.success) setCharityTiers(tiers.data);
      if (yoy.success) setYoyData(yoy);
      if (diagnoses.success) setDiagnosisData(diagnoses.data);
    } catch (error) {
      console.error('Failed to load analytics:', error);
    } finally {
      setIsLoading(false);
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

  const calculateChange = (current: number, previous: number) => {
    if (previous === 0) return 0;
    return ((current - previous) / previous) * 100;
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="w-16 h-16 border-4 border-emerald-600 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-emerald-50 via-white to-teal-50 p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="mb-8 flex items-end justify-between">
          <div>
            <h1 className="text-4xl font-bold text-slate-900 mb-2">Analytics Dashboard</h1>
            <p className="text-slate-600">Comprehensive charity care compliance insights</p>
          </div>
          <div className="flex items-center gap-1 bg-white border border-emerald-200 rounded-xl p-1 shadow-sm">
            {TIME_PERIODS.map(({ label, value }) => (
              <button
                key={value}
                onClick={() => setTimePeriod(value)}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  timePeriod === value
                    ? 'bg-emerald-600 text-white shadow-sm'
                    : 'text-slate-600 hover:text-emerald-700 hover:bg-emerald-50'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        {/* YoY Comparison Cards */}
        {yoyData && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <MetricCard
              title="Total Visits"
              current={yoyData.current.visits}
              previous={yoyData.previous.visits}
              icon={<Activity className="w-6 h-6" />}
              color="emerald"
            />
            <MetricCard
              title="Unique Patients"
              current={yoyData.current.patients}
              previous={yoyData.previous.patients}
              icon={<Users className="w-6 h-6" />}
              color="teal"
            />
            <MetricCard
              title="Total Charges"
              current={yoyData.current.charges}
              previous={yoyData.previous.charges}
              icon={<DollarSign className="w-6 h-6" />}
              color="green"
              isCurrency
            />
            <MetricCard
              title="Charity Care Cases"
              current={yoyData.current.charity_care}
              previous={yoyData.previous.charity_care}
              icon={<HeartPulse className="w-6 h-6" />}
              color="emerald"
            />
          </div>
        )}

        {/* Charts Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* FPL Distribution */}
          <Card className="shadow-lg border-emerald-100">
            <CardHeader className="bg-gradient-to-r from-emerald-50 to-teal-50">
              <CardTitle className="text-emerald-900">Federal Poverty Level Distribution</CardTitle>
              <CardDescription>Patient income levels relative to FPL thresholds</CardDescription>
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
                      <Cell key={`cell-${index}`} fill={CHART_COLORS[index % CHART_COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          {/* Charity Care Tiers */}
          <Card className="shadow-lg border-emerald-100">
            <CardHeader className="bg-gradient-to-r from-emerald-50 to-teal-50">
              <CardTitle className="text-emerald-900">Charity Care Discount Tiers</CardTitle>
              <CardDescription>Distribution of financial assistance levels</CardDescription>
            </CardHeader>
            <CardContent className="pt-6">
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={charityTiers} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke="#d1fae5" />
                  <XAxis type="number" />
                  <YAxis dataKey="label" type="category" width={160} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#ecfdf5',
                      border: '1px solid #10b981',
                      borderRadius: '8px'
                    }}
                  />
                  <Bar dataKey="value" radius={[0, 8, 8, 0]}>
                    {charityTiers.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={CHART_COLORS[index % CHART_COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          {/* Top Diagnoses */}
          <Card className="shadow-lg border-emerald-100 lg:col-span-2">
            <CardHeader className="bg-gradient-to-r from-emerald-50 to-teal-50">
              <CardTitle className="text-emerald-900">Top 10 Diagnosis Codes (ICD-10)</CardTitle>
              <CardDescription>Most common primary diagnoses in charity care population</CardDescription>
            </CardHeader>
            <CardContent className="pt-6">
              <ResponsiveContainer width="100%" height={400}>
                <BarChart data={diagnosisData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#d1fae5" />
                  <XAxis dataKey="label" angle={-45} textAnchor="end" height={100} />
                  <YAxis />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#ecfdf5',
                      border: '1px solid #10b981',
                      borderRadius: '8px'
                    }}
                  />
                  <Legend />
                  <Bar dataKey="value" name="Patient Count" radius={[8, 8, 0, 0]}>
                    {diagnosisData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={CHART_COLORS[index % CHART_COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

interface MetricCardProps {
  title: string;
  current: number;
  previous: number;
  icon: React.ReactNode;
  color: 'emerald' | 'teal' | 'green';
  isCurrency?: boolean;
}

function MetricCard({ title, current, previous, icon, color, isCurrency = false }: MetricCardProps) {
  const change = ((current - previous) / previous) * 100;
  const isPositive = change >= 0;

  const colorClasses = {
    emerald: 'from-emerald-500 to-emerald-600',
    teal: 'from-teal-500 to-teal-600',
    green: 'from-green-500 to-green-600',
  };

  const formatValue = (val: number) => {
    if (isCurrency) {
      return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: 0,
        maximumFractionDigits: 0
      }).format(val);
    }
    return val.toLocaleString();
  };

  return (
    <Card className="shadow-lg hover:shadow-xl transition-shadow border-emerald-100">
      <CardContent className="pt-6">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-sm font-medium text-slate-600 mb-1">{title}</p>
            <p className="text-3xl font-bold text-slate-900 mb-2">{formatValue(current)}</p>
            <div className="flex items-center gap-2">
              <div className={`flex items-center gap-1 px-2 py-1 rounded-full ${isPositive ? 'bg-emerald-100' : 'bg-red-100'}`}>
                {isPositive ? (
                  <TrendingUp className="w-3 h-3 text-emerald-600" />
                ) : (
                  <TrendingDown className="w-3 h-3 text-red-600" />
                )}
                <span className={`text-xs font-semibold ${isPositive ? 'text-emerald-700' : 'text-red-700'}`}>
                  {Math.abs(change).toFixed(1)}%
                </span>
              </div>
              <span className="text-xs text-slate-500">vs last year</span>
            </div>
          </div>
          <div className={`p-3 rounded-xl bg-gradient-to-br ${colorClasses[color]} text-white shadow-md`}>
            {icon}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
