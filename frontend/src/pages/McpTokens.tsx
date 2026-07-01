// =============================================================================
// FGA CRM - Page Conso API MCP (tokens + cout € par outil)
// Reserve admin (donnee de cout). Consomme /mcp-usage/summary + /by-tool.
// =============================================================================

import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ChevronDown, ChevronRight } from 'lucide-react';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
} from 'recharts';
import { getMcpUsageSummary, getMcpUsageByTool } from '../api/client';
import type { McpUsageSummary, McpUsageByTool, ToolUsageSummary } from '../types';

// --- Helpers de formatage ---
function isoDate(d: Date): string {
  return d.toISOString().slice(0, 10);
}

function formatEur(v: number): string {
  const decimals = v > 0 && v < 1 ? 4 : 2;
  return `${v.toLocaleString('fr-FR', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })} €`;
}

function formatInt(v: number): string {
  return v.toLocaleString('fr-FR');
}

export default function McpTokensPage() {
  const now = new Date();
  const [dateFrom, setDateFrom] = useState(
    isoDate(new Date(now.getFullYear(), now.getMonth(), 1)),
  );
  const [dateTo, setDateTo] = useState(isoDate(now));
  const [expanded, setExpanded] = useState<string | null>(null);

  const { data: summary, isLoading, isError } = useQuery<McpUsageSummary>({
    queryKey: ['mcp-usage-summary', dateFrom, dateTo],
    queryFn: () => getMcpUsageSummary(dateFrom, dateTo),
  });

  // Tri par cout decroissant (le plus couteux en haut).
  const byTool = useMemo(
    () => [...(summary?.by_tool ?? [])].sort((a, b) => b.cost_eur - a.cost_eur),
    [summary],
  );
  const chartData = byTool.map((t) => ({
    name: t.tool_name,
    cost: Number(t.cost_eur.toFixed(4)),
  }));

  return (
    <div className="p-8 max-w-6xl mx-auto">
      {/* Header + selecteur de dates */}
      <div className="flex items-center justify-between mb-6 gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-semibold text-slate-800">Conso API MCP</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            Consommation Anthropic par outil MCP et cout estime (€).
          </p>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <input
            type="date"
            value={dateFrom}
            max={dateTo}
            onChange={(e) => setDateFrom(e.target.value)}
            className="px-3 py-1.5 rounded-lg border border-slate-200 text-slate-700 bg-white"
          />
          <span className="text-slate-400">→</span>
          <input
            type="date"
            value={dateTo}
            min={dateFrom}
            onChange={(e) => setDateTo(e.target.value)}
            className="px-3 py-1.5 rounded-lg border border-slate-200 text-slate-700 bg-white"
          />
        </div>
      </div>

      {isError && (
        <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-12 text-center text-sm text-slate-500">
          Impossible de charger la consommation MCP.
        </div>
      )}

      {isLoading && (
        <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-12 text-center text-sm text-slate-400">
          Chargement…
        </div>
      )}

      {summary && !isLoading && (
        <>
          {/* KPI strip */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <KpiCard label="Cout total" value={formatEur(summary.total.cost_eur)} accent />
            <KpiCard label="Appels LLM" value={formatInt(summary.total.calls)} />
            <KpiCard label="Tokens in" value={formatInt(summary.total.tokens_in)} />
            <KpiCard label="Tokens out" value={formatInt(summary.total.tokens_out)} />
          </div>

          {byTool.length === 0 ? (
            <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-12 text-center text-sm text-slate-500">
              Aucune consommation sur la periode.
            </div>
          ) : (
            <>
              {/* Graphe cout par outil */}
              <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-4 mb-6">
                <div className="text-sm font-semibold text-slate-800 mb-3">Cout par outil (€)</div>
                <ResponsiveContainer width="100%" height={Math.max(160, chartData.length * 34)}>
                  <BarChart data={chartData} layout="vertical" margin={{ left: 8, right: 24 }}>
                    <XAxis type="number" tick={{ fontSize: 11 }} stroke="#94a3b8" />
                    <YAxis
                      type="category"
                      dataKey="name"
                      width={190}
                      tick={{ fontSize: 11 }}
                      stroke="#94a3b8"
                    />
                    <Tooltip
                      formatter={(v: number) => [formatEur(v), 'Cout']}
                      cursor={{ fill: '#f1f5f9' }}
                    />
                    <Bar dataKey="cost" fill="#6366f1" radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>

              {/* Liste depliable par outil */}
              <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
                <div className="px-4 py-3 border-b border-slate-100 text-sm font-semibold text-slate-800">
                  Detail par outil
                </div>
                <div className="divide-y divide-slate-100">
                  {byTool.map((t) => (
                    <ToolRow
                      key={t.tool_name}
                      tool={t}
                      expanded={expanded === t.tool_name}
                      onToggle={() =>
                        setExpanded(expanded === t.tool_name ? null : t.tool_name)
                      }
                      dateFrom={dateFrom}
                      dateTo={dateTo}
                    />
                  ))}
                </div>
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}

// ---------- Sous-composants ----------

function KpiCard({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-4">
      <div className="text-xs text-slate-500">{label}</div>
      <div
        className={`text-xl mt-1 tabular-nums font-semibold ${
          accent ? 'text-indigo-700' : 'text-slate-800'
        }`}
      >
        {value}
      </div>
    </div>
  );
}

function ToolRow({
  tool,
  expanded,
  onToggle,
  dateFrom,
  dateTo,
}: {
  tool: ToolUsageSummary;
  expanded: boolean;
  onToggle: () => void;
  dateFrom: string;
  dateTo: string;
}) {
  // Detail charge a la demande (a l'ouverture seulement).
  const { data: detail, isLoading } = useQuery<McpUsageByTool>({
    queryKey: ['mcp-usage-by-tool', tool.tool_name, dateFrom, dateTo],
    queryFn: () => getMcpUsageByTool(tool.tool_name, dateFrom, dateTo),
    enabled: expanded,
  });

  return (
    <div>
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-3 px-4 py-3 hover:bg-slate-50 text-left"
      >
        {expanded ? (
          <ChevronDown className="w-4 h-4 text-slate-400 flex-shrink-0" />
        ) : (
          <ChevronRight className="w-4 h-4 text-slate-400 flex-shrink-0" />
        )}
        <span className="flex-1 text-sm text-slate-800 truncate font-medium">
          {tool.tool_name}
        </span>
        <span className="text-xs text-slate-500 tabular-nums w-24 text-right">
          {formatInt(tool.calls)} appels
        </span>
        <span className="text-xs text-slate-500 tabular-nums w-32 text-right hidden md:inline">
          {formatInt(tool.input_tokens + tool.output_tokens)} tok
        </span>
        <span className="text-sm text-slate-800 tabular-nums w-24 text-right font-medium">
          {formatEur(tool.cost_eur)}
        </span>
      </button>

      {expanded && (
        <div className="px-4 pb-3 pl-11">
          {isLoading ? (
            <div className="text-xs text-slate-400 py-2">Chargement…</div>
          ) : (detail?.rows ?? []).length === 0 ? (
            <div className="text-xs text-slate-400 py-2">Aucun detail.</div>
          ) : (
            <table className="w-full text-xs">
              <thead>
                <tr className="text-slate-400 text-left">
                  <th className="py-1 font-medium">Jour</th>
                  <th className="py-1 font-medium">Modele</th>
                  <th className="py-1 font-medium text-right">Appels</th>
                  <th className="py-1 font-medium text-right">In</th>
                  <th className="py-1 font-medium text-right">Out</th>
                  <th className="py-1 font-medium text-right">Cout</th>
                </tr>
              </thead>
              <tbody className="text-slate-600">
                {(detail?.rows ?? []).map((r, i) => (
                  <tr key={`${r.day}-${r.model}-${i}`} className="border-t border-slate-100">
                    <td className="py-1 tabular-nums">{r.day}</td>
                    <td className="py-1">{r.model}</td>
                    <td className="py-1 text-right tabular-nums">{formatInt(r.calls)}</td>
                    <td className="py-1 text-right tabular-nums">{formatInt(r.input_tokens)}</td>
                    <td className="py-1 text-right tabular-nums">{formatInt(r.output_tokens)}</td>
                    <td className="py-1 text-right tabular-nums">{formatEur(r.cost_eur)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}
