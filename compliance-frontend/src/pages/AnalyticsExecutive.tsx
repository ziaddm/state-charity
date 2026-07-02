import { useState, useEffect, ReactNode } from 'react';
import { apiFetch } from '../lib/api';
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
  Cell,
  LabelList,
} from 'recharts';
import { Table2, BarChart3 } from 'lucide-react';

// ---------------------------------------------------------------------------
// Chart color roles.
// Single-series marks use the brand emerald (3.77:1 on white — clears the 3:1
// mark floor). The income ramp is ORDINAL (ordered buckets → one hue, monotone
// lightness) and was machine-validated. Multi-series charts use the validated
// categorical palette (fixed slot order — the order IS the CVD-safety
// mechanism; worst adjacent pair ΔE 24.2). Aqua and yellow sit below 3:1 on
// white; the relief rule is satisfied by every card's table view.
// Text never wears series color.
// ---------------------------------------------------------------------------
const VIZ = {
  series: '#059669',        // emerald-600 — the one series hue
  ordinalRamp: ['#0fc08a', '#10a878', '#0c9067', '#087857', '#066047', '#054936', '#033325'],
  grid: '#e2e8f0',          // hairline solid, one step off the surface
  axisLine: '#cbd5e1',
  tickInk: '#64748b',       // muted text token for axis ticks
  labelInk: '#334155',      // secondary ink for direct labels
};

// Categorical slots 1–6, fixed order, never cycled
const CAT = ['#2a78d6', '#1baf7a', '#eda100', '#008300', '#4a3aa7', '#e34948'];

// Color follows the entity, never its rank: payors keep their slot no matter
// which period is selected or which payors are present.
const PAYOR_SERIES_ORDER = ['Medicaid', 'Medicare', 'Self-Pay', 'Uninsured', 'Commercial', 'Unknown'];
const payorColor = (name: string) => CAT[Math.max(0, PAYOR_SERIES_ORDER.indexOf(name)) % CAT.length];

interface ExecutiveSummary {
  total_visits: number;
  unique_patients: number;
  total_charges: number;
  total_payments: number;
  uncompensated_visits: number;
  year: number;
}

interface DataPoint {
  label: string;
  value: number;
}

interface FinancialPoint {
  label: string;
  charges: number;
  payments: number;
}

interface NewReturningPoint {
  label: string;
  new: number;
  returning: number;
}

type Row = Record<string, string | number>;

interface Column {
  key: string;
  header: string;
  numeric?: boolean;
  formatter?: (v: number) => string;
}

// ---------------------------------------------------------------------------
// Formatting — stat-tile values auto-compact; tables/axes stay exact
// ---------------------------------------------------------------------------
const fmtNumber = (v: number) => new Intl.NumberFormat('en-US').format(v);

const fmtCurrency = (v: number) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(v);

const fmtCompactCurrency = (v: number) =>
  Math.abs(v) >= 100_000
    ? new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', notation: 'compact', maximumFractionDigits: 1 }).format(v)
    : fmtCurrency(v);

const fmtMonth = (label: string) => {
  // "Jan 2024" → "Jan ’24"
  const m = /^(\w{3}) (\d{4})$/.exec(label);
  return m ? `${m[1]} ’${m[2].slice(2)}` : label;
};

// Y-axis ticks round to clean numbers (0 / 50 / 100…), ≤ 7 lines
const niceTicks = (max: number): number[] => {
  if (max <= 0) return [0, 1];
  const mag = Math.pow(10, Math.floor(Math.log10(max)));
  for (const m of [0.1, 0.2, 0.25, 0.5, 1, 2, 2.5, 5]) {
    const step = m * mag;
    const n = Math.ceil(max / step);
    if (n <= 6) return Array.from({ length: n + 1 }, (_, i) => Math.round(i * step * 100) / 100);
  }
  return [0, mag * 10];
};

// Attach a share column for single-series table views
const withShare = (data: DataPoint[]): Row[] => {
  const total = data.reduce((s, d) => s + d.value, 0);
  return data.map(d => ({ ...d, share: total > 0 ? (d.value / total) * 100 : 0 }));
};

const fmtShare = (v: number) => `${v.toFixed(1)}%`;

// ---------------------------------------------------------------------------
// Tooltips — surface background, hairline border; values lead (bold, primary
// ink), names follow in secondary ink. One tooltip lists every series at
// that X, keyed by a short stroke of the series color.
// ---------------------------------------------------------------------------
const tooltipShell = 'rounded-lg bg-white px-3 py-2 shadow-lg';
const tooltipBorder = { border: '1px solid rgba(11,11,11,0.10)' };

function VizTooltip({ active, payload, label, valueFormatter }: {
  active?: boolean;
  payload?: Array<{ value: number; payload: Row }>;
  label?: string;
  valueFormatter?: (v: number) => string;
}) {
  if (!active || !payload || payload.length === 0) return null;
  const point = payload[0];
  const fmt = valueFormatter ?? fmtNumber;
  const share = point.payload.share as number | undefined;
  return (
    <div className={tooltipShell} style={tooltipBorder}>
      <p className="text-sm font-semibold text-slate-900">{fmt(point.value)}</p>
      <p className="text-xs text-slate-500">
        {(point.payload.label as string) ?? label}
        {share !== undefined && ` · ${share.toFixed(1)}% of total`}
      </p>
    </div>
  );
}

function MultiTooltip({ active, payload, label, valueFormatter }: {
  active?: boolean;
  payload?: Array<{ value: number; name: string; color?: string }>;
  label?: string;
  valueFormatter?: (v: number) => string;
}) {
  if (!active || !payload || payload.length === 0) return null;
  const fmt = valueFormatter ?? fmtNumber;
  return (
    <div className={tooltipShell} style={tooltipBorder}>
      <p className="text-xs font-medium text-slate-500 mb-1">{fmtMonth(label ?? '')}</p>
      {[...payload].reverse().map(entry => (
        <div key={entry.name} className="flex items-center gap-2 py-0.5">
          <span className="inline-block w-3 h-0.5 rounded-full" style={{ background: entry.color }} />
          <span className="text-sm font-semibold text-slate-900">{fmt(entry.value)}</span>
          <span className="text-xs text-slate-500">{entry.name}</span>
        </div>
      ))}
    </div>
  );
}

// Legend — identity never rides on color alone; present for ≥ 2 series
function Legend({ items, shape }: { items: Array<{ name: string; color: string }>; shape: 'line' | 'rect' }) {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 pb-1">
      {items.map(item => (
        <span key={item.name} className="inline-flex items-center gap-1.5 text-xs text-slate-600">
          {shape === 'line'
            ? <span className="inline-block w-4 h-0.5 rounded-full" style={{ background: item.color }} />
            : <span className="inline-block w-2.5 h-2.5 rounded-sm" style={{ background: item.color }} />}
          {item.name}
        </span>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Chart card with a chart ⇄ table toggle. The table view is the always-
// reachable, WCAG-clean twin of every chart — tooltips enhance, never gate.
// ---------------------------------------------------------------------------
function ChartCard({ title, description, rows, columns, children }: {
  title: string;
  description: string;
  rows: Row[];
  columns: Column[];
  children: ReactNode;
}) {
  const [showTable, setShowTable] = useState(false);

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm">
      <div className="flex items-start justify-between px-5 pt-4 pb-1">
        <div>
          <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
          <p className="text-xs text-slate-500 mt-0.5">{description}</p>
        </div>
        {rows.length > 0 && (
          <button
            onClick={() => setShowTable(t => !t)}
            aria-label={showTable ? `Show ${title} as chart` : `Show ${title} as table`}
            title={showTable ? 'View as chart' : 'View as table'}
            className="p-1.5 rounded-md text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
          >
            {showTable ? <BarChart3 className="w-4 h-4" /> : <Table2 className="w-4 h-4" />}
          </button>
        )}
      </div>

      <div className="px-3 pb-4">
        {rows.length === 0 ? (
          <div className="flex items-center justify-center h-56 text-sm text-slate-400">
            No data for this period
          </div>
        ) : showTable ? (
          <div className="px-2 pt-2 max-h-72 overflow-y-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-slate-500 border-b border-slate-200">
                  {columns.map(c => (
                    <th key={c.key} className={`font-medium py-1.5 ${c.numeric ? 'text-right' : 'text-left'}`}>
                      {c.header}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="[font-variant-numeric:tabular-nums]">
                {rows.map((row, i) => (
                  <tr key={i} className="border-b border-slate-100 last:border-0">
                    {columns.map(c => (
                      <td key={c.key} className={`py-1.5 ${c.numeric ? 'text-right text-slate-900 font-medium' : 'text-slate-700'}`}>
                        {c.numeric
                          ? (c.formatter ?? fmtNumber)(Number(row[c.key] ?? 0))
                          : String(row[c.key] ?? '—')}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          children
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Horizontal category bars: thin marks (≤24px), 4px rounded data-end, square
// baseline, value at the tip in ink (so the number axis can stay silent).
// ---------------------------------------------------------------------------
function CategoryBars({ data, colorFor, labelWidth, valueFormatter }: {
  data: DataPoint[];
  colorFor: (index: number) => string;
  labelWidth: number;
  valueFormatter?: (v: number) => string;
}) {
  const fmt = valueFormatter ?? fmtNumber;
  const height = Math.max(180, data.length * 40 + 16);
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} layout="vertical" margin={{ top: 4, right: 56, left: 0, bottom: 0 }}>
        <XAxis type="number" hide />
        <YAxis
          dataKey="label"
          type="category"
          width={labelWidth}
          tickLine={false}
          axisLine={false}
          tick={{ fill: VIZ.tickInk, fontSize: 12 }}
        />
        <Tooltip cursor={{ fill: 'rgba(15,23,42,0.04)' }} content={<VizTooltip valueFormatter={fmt} />} />
        <Bar dataKey="value" barSize={18} radius={[0, 4, 4, 0]} isAnimationActive={false}>
          {data.map((entry, index) => (
            <Cell key={entry.label} fill={colorFor(index)} />
          ))}
          <LabelList
            dataKey="value"
            position="right"
            formatter={(v: unknown) => fmt(Number(v))}
            style={{ fill: VIZ.labelInk, fontSize: 11, fontWeight: 600 }}
          />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

// ---------------------------------------------------------------------------
// Stacked monthly columns: ≤20px columns, 1px surface stroke as the gap
// between touching segments, rounded cap on the top series only.
// ---------------------------------------------------------------------------
function StackedColumns({ data, series, height = 264 }: {
  data: Row[];
  series: Array<{ key: string; name: string; color: string }>;
  height?: number;
}) {
  const maxTotal = Math.max(0, ...data.map(row => series.reduce((s, sr) => s + Number(row[sr.key] ?? 0), 0)));
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 4 }}>
        <CartesianGrid vertical={false} stroke={VIZ.grid} />
        <XAxis
          dataKey="label"
          tickFormatter={fmtMonth}
          tick={{ fill: VIZ.tickInk, fontSize: 11 }}
          tickLine={false}
          axisLine={{ stroke: VIZ.axisLine }}
          interval="preserveStartEnd"
          minTickGap={24}
        />
        <YAxis
          allowDecimals={false}
          width={36}
          ticks={niceTicks(maxTotal)}
          domain={[0, (dataMax: number) => niceTicks(dataMax).slice(-1)[0]]}
          tick={{ fill: VIZ.tickInk, fontSize: 11 }}
          tickLine={false}
          axisLine={false}
        />
        <Tooltip cursor={{ fill: 'rgba(15,23,42,0.04)' }} content={<MultiTooltip />} />
        {series.map((s, i) => (
          <Bar
            key={s.key}
            dataKey={s.key}
            name={s.name}
            stackId="stack"
            fill={s.color}
            barSize={20}
            stroke="#ffffff"
            strokeWidth={1}
            radius={i === series.length - 1 ? [4, 4, 0, 0] : 0}
            isAnimationActive={false}
          />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}

// Direct label on the final point only — selective, never a number on every dot
function EndPointLabel(props: { x?: number; y?: number; index?: number; value?: number; dataLength: number }) {
  const { x, y, index, value, dataLength } = props;
  if (index !== dataLength - 1 || x === undefined || y === undefined) return null;
  return (
    <text x={x} y={y - 12} textAnchor="middle" fill={VIZ.labelInk} fontSize={11} fontWeight={600}>
      {fmtNumber(value ?? 0)}
    </text>
  );
}

// ---------------------------------------------------------------------------
// Stat tile: label · value (semibold, proportional figures) · context line
// ---------------------------------------------------------------------------
function StatTile({ label, value, context }: {
  label: string;
  value: string;
  context: string;
}) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm px-5 py-4">
      <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">{label}</p>
      <p className="text-3xl font-semibold text-slate-900 mt-1.5">{value}</p>
      <p className="text-xs text-slate-400 mt-1">{context}</p>
    </div>
  );
}

export default function AnalyticsExecutive() {
  const [summary, setSummary] = useState<ExecutiveSummary | null>(null);
  const [fplData, setFplData] = useState<DataPoint[]>([]);
  const [visitTrends, setVisitTrends] = useState<DataPoint[]>([]);
  const [diagnosisData, setDiagnosisData] = useState<DataPoint[]>([]);
  const [payorData, setPayorData] = useState<DataPoint[]>([]);
  const [financialData, setFinancialData] = useState<FinancialPoint[]>([]);
  const [payorMixData, setPayorMixData] = useState<Row[]>([]);
  const [payorMixSeries, setPayorMixSeries] = useState<string[]>([]);
  const [newReturningData, setNewReturningData] = useState<NewReturningPoint[]>([]);
  const [selectedPeriod, setSelectedPeriod] = useState<string>('all');
  const [isFetching, setIsFetching] = useState(true);
  const [hasLoadedOnce, setHasLoadedOnce] = useState(false);

  useEffect(() => {
    fetchAnalytics();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedPeriod]);

  const fetchAnalytics = async () => {
    setIsFetching(true);
    try {
      const [summaryRes, fpl, trends, diagnoses, payors, financial, payorMix, newReturning] = await Promise.all([
        apiFetch(`/api/analytics/summary?time_period=${selectedPeriod}`),
        apiFetch(`/api/analytics/fpl-distribution?time_period=${selectedPeriod}`).then(r => r.json()),
        apiFetch(`/api/analytics/visit-trends?time_period=${selectedPeriod}`).then(r => r.json()),
        apiFetch(`/api/analytics/top-diagnoses?time_period=${selectedPeriod}&limit=5`).then(r => r.json()),
        apiFetch(`/api/analytics/payor-distribution?time_period=${selectedPeriod}`).then(r => r.json()),
        apiFetch(`/api/analytics/financial-trends?time_period=${selectedPeriod}`).then(r => r.json()),
        apiFetch(`/api/analytics/payor-mix-trends?time_period=${selectedPeriod}`).then(r => r.json()),
        apiFetch(`/api/analytics/new-patient-trends?time_period=${selectedPeriod}`).then(r => r.json()),
      ]);

      if (summaryRes.ok) {
        const data = await summaryRes.json();
        setSummary(data.summary);
      }
      if (fpl.success) setFplData(fpl.data);
      if (trends.success) setVisitTrends(trends.data);
      if (diagnoses.success) setDiagnosisData(diagnoses.data);
      if (payors.success) setPayorData(payors.data);
      if (financial.success) setFinancialData(financial.data);
      if (payorMix.success) {
        setPayorMixData(payorMix.data);
        setPayorMixSeries(payorMix.series ?? []);
      }
      if (newReturning.success) setNewReturningData(newReturning.data);
    } catch (error) {
      console.error('Failed to load analytics:', error);
    } finally {
      setIsFetching(false);
      setHasLoadedOnce(true);
    }
  };

  const getPeriodLabel = (period: string): string => {
    const labels: { [key: string]: string } = {
      week: 'Last 7 Days',
      month: 'Last 30 Days',
      quarter: 'Last 90 Days',
      ytd: 'Year to Date',
      all: 'All Time',
    };
    return labels[period] || period;
  };

  const visitsPerPatient =
    summary && summary.unique_patients > 0 ? summary.total_visits / summary.unique_patients : null;

  const financialSeries = [
    { key: 'charges', name: 'Charges', color: CAT[0] },
    { key: 'payments', name: 'Payments', color: CAT[1] },
  ];
  const newReturningSeries = [
    { key: 'returning', name: 'Returning', color: CAT[1] },
    { key: 'new', name: 'New patients', color: CAT[0] },
  ];
  const payorMixChartSeries = payorMixSeries.map(name => ({ key: name, name, color: payorColor(name) }));
  const maxCharges = Math.max(0, ...financialData.map(d => Math.max(d.charges, d.payments)));

  if (!hasLoadedOnce) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-12 h-12 border-4 border-emerald-600 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* Header + filter row — one row, scopes everything below it */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-xl font-bold text-slate-900">Analytics</h1>
          <p className="text-xs text-slate-500 mt-1">{getPeriodLabel(selectedPeriod)} performance overview</p>
        </div>
        <select
          value={selectedPeriod}
          onChange={e => setSelectedPeriod(e.target.value)}
          className="px-3 py-1.5 text-sm border border-slate-300 rounded-lg bg-white shadow-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
        >
          <option value="month">Last 30 Days</option>
          <option value="quarter">Last 90 Days</option>
          <option value="ytd">Year to Date</option>
          <option value="all">All Time</option>
        </select>
      </div>

      {/* Refetch keeps the frame: previous render held at reduced opacity */}
      <div className={`space-y-5 transition-opacity duration-200 ${isFetching ? 'opacity-50 pointer-events-none' : ''}`}>

        {/* KPI row */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatTile
            label="Total visits"
            value={summary ? fmtNumber(summary.total_visits) : '—'}
            context={getPeriodLabel(selectedPeriod)}
          />
          <StatTile
            label="Unique patients"
            value={summary ? fmtNumber(summary.unique_patients) : '—'}
            context="Individuals served"
          />
          <StatTile
            label="Total charges"
            value={summary ? fmtCompactCurrency(summary.total_charges) : '—'}
            context="Billed amount"
          />
          <StatTile
            label="Visits per patient"
            value={visitsPerPatient !== null ? visitsPerPatient.toFixed(1) : '—'}
            context="Average encounters"
          />
        </div>

        {/* Charts */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <ChartCard
            title="Charges vs. payments"
            description="Monthly billed amount and payments received"
            rows={financialData as unknown as Row[]}
            columns={[
              { key: 'label', header: 'Month' },
              { key: 'charges', header: 'Charges', numeric: true, formatter: fmtCurrency },
              { key: 'payments', header: 'Payments', numeric: true, formatter: fmtCurrency },
            ]}
          >
            <Legend items={financialSeries} shape="line" />
            <ResponsiveContainer width="100%" height={264}>
              <LineChart data={financialData} margin={{ top: 8, right: 16, left: 8, bottom: 4 }}>
                <CartesianGrid vertical={false} stroke={VIZ.grid} />
                <XAxis
                  dataKey="label"
                  tickFormatter={fmtMonth}
                  tick={{ fill: VIZ.tickInk, fontSize: 11 }}
                  tickLine={false}
                  axisLine={{ stroke: VIZ.axisLine }}
                  interval="preserveStartEnd"
                  minTickGap={24}
                />
                <YAxis
                  width={52}
                  ticks={niceTicks(maxCharges)}
                  domain={[0, (dataMax: number) => niceTicks(dataMax).slice(-1)[0]]}
                  tickFormatter={(v: number) => fmtCompactCurrency(v)}
                  tick={{ fill: VIZ.tickInk, fontSize: 11 }}
                  tickLine={false}
                  axisLine={false}
                />
                <Tooltip
                  cursor={{ stroke: VIZ.axisLine, strokeWidth: 1 }}
                  content={<MultiTooltip valueFormatter={fmtCurrency} />}
                />
                {financialSeries.map(s => (
                  <Line
                    key={s.key}
                    type="monotone"
                    dataKey={s.key}
                    name={s.name}
                    stroke={s.color}
                    strokeWidth={2}
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    isAnimationActive={false}
                    dot={{ r: 3.5, fill: s.color, stroke: '#ffffff', strokeWidth: 2 }}
                    activeDot={{ r: 5, fill: s.color, stroke: '#ffffff', strokeWidth: 2 }}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </ChartCard>

          <ChartCard
            title="Payer mix over time"
            description="Monthly visits by payor source"
            rows={payorMixData}
            columns={[
              { key: 'label', header: 'Month' },
              ...payorMixSeries.map(s => ({ key: s, header: s, numeric: true })),
            ]}
          >
            <Legend items={payorMixChartSeries} shape="rect" />
            <StackedColumns data={payorMixData} series={payorMixChartSeries} />
          </ChartCard>

          <ChartCard
            title="New vs. returning patients"
            description="Monthly visit volume by patient status"
            rows={newReturningData as unknown as Row[]}
            columns={[
              { key: 'label', header: 'Month' },
              { key: 'new', header: 'New', numeric: true },
              { key: 'returning', header: 'Returning', numeric: true },
            ]}
          >
            <Legend items={[...newReturningSeries].reverse()} shape="rect" />
            <StackedColumns data={newReturningData as unknown as Row[]} series={newReturningSeries} />
          </ChartCard>

          <ChartCard
            title="Visit trends"
            description="Monthly visit volume over time"
            rows={withShare(visitTrends)}
            columns={[
              { key: 'label', header: 'Month' },
              { key: 'value', header: 'Visits', numeric: true },
              { key: 'share', header: 'Share', numeric: true, formatter: fmtShare },
            ]}
          >
            <ResponsiveContainer width="100%" height={264}>
              <LineChart data={visitTrends} margin={{ top: 24, right: 24, left: 0, bottom: 4 }}>
                <CartesianGrid vertical={false} stroke={VIZ.grid} />
                <XAxis
                  dataKey="label"
                  tickFormatter={fmtMonth}
                  tick={{ fill: VIZ.tickInk, fontSize: 11 }}
                  tickLine={false}
                  axisLine={{ stroke: VIZ.axisLine }}
                  interval="preserveStartEnd"
                  minTickGap={24}
                />
                <YAxis
                  allowDecimals={false}
                  width={36}
                  ticks={niceTicks(Math.max(0, ...visitTrends.map(d => d.value)))}
                  domain={[0, (dataMax: number) => niceTicks(dataMax).slice(-1)[0]]}
                  tick={{ fill: VIZ.tickInk, fontSize: 11 }}
                  tickLine={false}
                  axisLine={false}
                />
                <Tooltip
                  cursor={{ stroke: VIZ.axisLine, strokeWidth: 1 }}
                  content={<VizTooltip />}
                />
                <Line
                  type="monotone"
                  dataKey="value"
                  stroke={VIZ.series}
                  strokeWidth={2}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  isAnimationActive={false}
                  dot={{ r: 4, fill: VIZ.series, stroke: '#ffffff', strokeWidth: 2 }}
                  activeDot={{ r: 5.5, fill: VIZ.series, stroke: '#ffffff', strokeWidth: 2 }}
                >
                  <LabelList content={<EndPointLabel dataLength={visitTrends.length} />} />
                </Line>
              </LineChart>
            </ResponsiveContainer>
          </ChartCard>

          <ChartCard
            title="Income distribution"
            description="Patient household income ranges"
            rows={withShare(fplData)}
            columns={[
              { key: 'label', header: 'Category' },
              { key: 'value', header: 'Patients', numeric: true },
              { key: 'share', header: 'Share', numeric: true, formatter: fmtShare },
            ]}
          >
            {/* Ordered buckets → validated ordinal ramp, light→dark with income */}
            <CategoryBars
              data={fplData}
              colorFor={i => VIZ.ordinalRamp[Math.min(i, VIZ.ordinalRamp.length - 1)]}
              labelWidth={92}
            />
          </ChartCard>

          <ChartCard
            title="Top diagnosis codes"
            description="Most common primary diagnoses (ICD-10)"
            rows={withShare(diagnosisData)}
            columns={[
              { key: 'label', header: 'Code' },
              { key: 'value', header: 'Visits', numeric: true },
              { key: 'share', header: 'Share', numeric: true, formatter: fmtShare },
            ]}
          >
            {/* Nominal categories, one series → one color; length carries the value */}
            <CategoryBars data={diagnosisData} colorFor={() => VIZ.series} labelWidth={76} />
          </ChartCard>

          <ChartCard
            title="Insurance distribution"
            description="Patients by primary payor"
            rows={withShare(payorData)}
            columns={[
              { key: 'label', header: 'Payor' },
              { key: 'value', header: 'Patients', numeric: true },
              { key: 'share', header: 'Share', numeric: true, formatter: fmtShare },
            ]}
          >
            <CategoryBars data={withShare(payorData) as unknown as DataPoint[]} colorFor={() => VIZ.series} labelWidth={100} />
          </ChartCard>
        </div>
      </div>
    </div>
  );
}
