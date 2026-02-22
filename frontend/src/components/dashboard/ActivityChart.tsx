// =============================================================================
// FGA CRM - Activity Pie Chart (Dashboard V2)
// =============================================================================

import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';
import type { ActivityByType } from '../../types';

// Labels FR par type
const TYPE_LABELS: Record<string, string> = {
  email: 'Email',
  call: 'Appel',
  meeting: 'Meeting',
  note: 'Note',
  linkedin: 'LinkedIn',
  task: 'Tache',
  audit: 'Audit',
};

// Couleurs par type
const TYPE_COLORS: Record<string, string> = {
  email: '#3b82f6',    // blue
  call: '#10b981',     // emerald
  meeting: '#8b5cf6',  // violet
  note: '#f59e0b',     // amber
  linkedin: '#0ea5e9', // sky
  task: '#f97316',     // orange
  audit: '#6366f1',    // indigo
};

interface ActivityChartProps {
  data: ActivityByType[];
}

// Tooltip custom
function CustomTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: { label: string; count: number } }> }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="bg-white border border-slate-200 shadow-lg rounded-lg px-3 py-2 text-sm">
      <p className="font-medium text-slate-700">{d.label}</p>
      <p className="text-slate-500">{d.count} activite{d.count > 1 ? 's' : ''}</p>
    </div>
  );
}

export default function ActivityChart({ data }: ActivityChartProps) {
  const chartData = data
    .filter((d) => d.count > 0)
    .map((d) => ({
      ...d,
      label: TYPE_LABELS[d.type] || d.type,
      color: TYPE_COLORS[d.type] || '#94a3b8',
    }));

  if (!chartData.length) {
    return (
      <div className="flex items-center justify-center h-full text-slate-400 text-sm">
        Aucune activite sur 30 jours
      </div>
    );
  }

  return (
    <div className="flex items-center gap-4 h-full">
      {/* Pie chart */}
      <div className="w-1/2 h-full">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={chartData}
              cx="50%"
              cy="50%"
              innerRadius="45%"
              outerRadius="80%"
              paddingAngle={2}
              dataKey="count"
            >
              {chartData.map((entry) => (
                <Cell key={entry.type} fill={entry.color} />
              ))}
            </Pie>
            <Tooltip content={<CustomTooltip />} />
          </PieChart>
        </ResponsiveContainer>
      </div>

      {/* Legende */}
      <div className="w-1/2 space-y-2">
        {chartData.map((entry) => (
          <div key={entry.type} className="flex items-center gap-2 text-sm">
            <span
              className="w-2.5 h-2.5 rounded-full flex-shrink-0"
              style={{ backgroundColor: entry.color }}
            />
            <span className="text-slate-600 flex-1">{entry.label}</span>
            <span className="text-slate-800 font-medium">{entry.count}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
