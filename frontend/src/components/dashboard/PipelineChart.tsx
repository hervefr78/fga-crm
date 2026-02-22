// =============================================================================
// FGA CRM - Pipeline Bar Chart (Dashboard V2)
// =============================================================================

import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import type { DealsByStage } from '../../types';
import { DEAL_STAGES } from '../../types';

// Labels FR pour les stages
const STAGE_LABELS: Record<string, string> = Object.fromEntries(
  DEAL_STAGES.map((s) => [s.value, s.label]),
);

// Couleurs par stage
const STAGE_COLORS: Record<string, string> = {
  new: '#64748b',        // slate
  contacted: '#3b82f6',  // blue
  meeting: '#8b5cf6',    // violet
  proposal: '#f59e0b',   // amber
  negotiation: '#f97316', // orange
  won: '#10b981',        // emerald
  lost: '#ef4444',       // red
};

// Ordre fixe des stages
const STAGE_ORDER = ['new', 'contacted', 'meeting', 'proposal', 'negotiation', 'won', 'lost'];

interface PipelineChartProps {
  data: DealsByStage[];
}

// Tooltip custom
function CustomTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: { label: string; count: number; total_amount: number } }> }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="bg-white border border-slate-200 shadow-lg rounded-lg px-3 py-2 text-sm">
      <p className="font-medium text-slate-700">{d.label}</p>
      <p className="text-slate-500">{d.count} deal{d.count > 1 ? 's' : ''}</p>
      <p className="text-slate-500 font-medium">
        {d.total_amount.toLocaleString('fr-FR', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 })}
      </p>
    </div>
  );
}

export default function PipelineChart({ data }: PipelineChartProps) {
  // Creer un map pour lookup rapide
  const dataMap = new Map(data.map((d) => [d.stage, d]));

  // Garantir l'ordre fixe des stages avec labels FR
  const chartData = STAGE_ORDER.map((stage) => {
    const d = dataMap.get(stage);
    return {
      stage,
      label: STAGE_LABELS[stage] || stage,
      count: d?.count || 0,
      total_amount: d?.total_amount || 0,
    };
  });

  const hasData = chartData.some((d) => d.count > 0);

  if (!hasData) {
    return (
      <div className="flex items-center justify-center h-full text-slate-400 text-sm">
        Aucun deal dans le pipeline
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={chartData} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
        <XAxis
          dataKey="label"
          tick={{ fontSize: 11, fill: '#94a3b8' }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          tick={{ fontSize: 11, fill: '#94a3b8' }}
          axisLine={false}
          tickLine={false}
          tickFormatter={(v: number) => v >= 1000 ? `${(v / 1000).toFixed(0)}k` : `${v}`}
        />
        <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(0,0,0,0.04)' }} />
        <Bar dataKey="total_amount" radius={[4, 4, 0, 0]} maxBarSize={40}>
          {chartData.map((entry) => (
            <Cell key={entry.stage} fill={STAGE_COLORS[entry.stage] || '#94a3b8'} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
