// =============================================================================
// FGA CRM - Trends : graphique "Interet dans le temps" + detail au clic
// =============================================================================
// Google Trends ne fournit qu'un couple {date, valeur} par point. Au clic sur un
// point, on affiche un detail DERIVE de la serie (variation vs point precedent,
// pic/creux, position vs moyenne) — 100 % calcule cote client, aucune donnee
// inventee. Le point selectionne reste epingle jusqu'au clic suivant.
// =============================================================================

import { useState } from 'react';
import {
  CartesianGrid, Line, LineChart, ReferenceDot, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import clsx from 'clsx';

import type { TrendTimeseriesPoint } from '../../types/trends';
import { buildPointDetail, type TrendPointDetail } from './trendUtils';

function formatFullDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' });
}

export function TrendInterestChart({ timeseries }: { timeseries: TrendTimeseriesPoint[] }) {
  const [selected, setSelected] = useState<number | null>(null);
  const data = timeseries.map((p) => ({ date: p.date, value: p.value }));
  const detail = selected !== null ? buildPointDetail(data, selected) : null;

  return (
    <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
      <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between gap-2">
        <span className="text-sm font-semibold text-slate-800">Interet dans le temps</span>
        {data.length > 0 && (
          <span className="text-xs text-slate-400">Cliquez un point pour le detail</span>
        )}
      </div>
      <div className="p-4">
        {data.length === 0 ? (
          <div className="py-8 text-center text-sm text-slate-400">Pas de serie disponible</div>
        ) : (
          <>
            <ResponsiveContainer width="100%" height={220}>
              <LineChart
                data={data}
                margin={{ top: 8, right: 12, left: -12, bottom: 0 }}
                onClick={(state) => {
                  const idx = (state as { activeTooltipIndex?: number } | null)?.activeTooltipIndex;
                  if (typeof idx === 'number') setSelected(idx);
                }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#94a3b8' }} minTickGap={40} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: '#94a3b8' }} />
                <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e2e8f0' }} />
                <Line
                  type="monotone" dataKey="value" stroke="#4f46e5" strokeWidth={2}
                  dot={false} activeDot={{ r: 5 }}
                />
                {detail && (
                  <ReferenceDot
                    x={detail.date} y={detail.value} r={5}
                    fill="#4f46e5" stroke="#fff" strokeWidth={2} isFront
                  />
                )}
              </LineChart>
            </ResponsiveContainer>

            {detail ? (
              <PointDetailCard detail={detail} />
            ) : (
              <p className="mt-3 text-xs text-slate-400 text-center">
                Selectionnez un point du graphique pour afficher son detail.
              </p>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function PointDetailCard({ detail }: { detail: TrendPointDetail }) {
  const { date, value, delta, isPeak, isTrough, mean } = detail;
  return (
    <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50/60 px-4 py-3">
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-sm font-medium text-slate-800">{formatFullDate(date)}</span>
        <span className="text-sm text-slate-500">
          Indice <span className="font-semibold text-slate-800 tabular-nums">{value}</span>/100
        </span>
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-1.5">
        {delta !== null && (
          <Pill tone={delta > 0 ? 'up' : delta < 0 ? 'down' : 'flat'}>
            {delta > 0 ? '+' : ''}{delta} vs point precedent
          </Pill>
        )}
        {/* Pic/creux mutuellement exclusifs ; sinon (ou serie plate) position vs moyenne. */}
        {isPeak && !isTrough && <Pill tone="up">Pic de la periode</Pill>}
        {isTrough && !isPeak && <Pill tone="down">Point le plus bas</Pill>}
        {isPeak === isTrough && (
          <Pill tone="flat">{value >= mean ? 'Au-dessus' : 'Sous'} la moyenne ({mean})</Pill>
        )}
      </div>
    </div>
  );
}

function Pill({ tone, children }: { tone: 'up' | 'down' | 'flat'; children: React.ReactNode }) {
  return (
    <span
      className={clsx(
        'inline-flex items-center rounded px-2 py-0.5 text-[11px] font-medium tabular-nums',
        tone === 'up' && 'bg-emerald-50 text-emerald-700',
        tone === 'down' && 'bg-red-50 text-red-600',
        tone === 'flat' && 'bg-slate-100 text-slate-600',
      )}
    >
      {children}
    </span>
  );
}
