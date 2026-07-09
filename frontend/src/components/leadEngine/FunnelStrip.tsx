// =============================================================================
// FGA CRM - Lead Engine : funnel compact par play (30 j)
// =============================================================================
// Mesure §2.3 de la vision : ou ca fuit, quel play convertit. V1 : compteurs
// detected -> actionne -> drafte -> envoye (drafts/envois : P1 uniquement).
// =============================================================================

import type { LeadFunnelResult, PlayFunnel } from '../../types/leadEngine';

interface FunnelStripProps {
  funnel: LeadFunnelResult;
}

function PlayLine({ label, funnel, withOutreach }: {
  label: string;
  funnel: PlayFunnel;
  withOutreach: boolean;
}) {
  const steps: Array<[string, number]> = [
    ['détectés', funnel.detected],
    ['traités', funnel.actioned],
  ];
  if (withOutreach) {
    steps.push(['draftés', funnel.drafted], ['envoyés', funnel.sent]);
  }
  return (
    <div className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5">
      <span className="text-xs font-medium text-slate-600 w-40 shrink-0">{label}</span>
      {steps.map(([name, value], i) => (
        <span key={name} className="text-xs text-slate-500">
          {i > 0 && <span className="text-slate-300 mr-3">→</span>}
          <span className="font-medium text-slate-700 tabular-nums">{value}</span> {name}
        </span>
      ))}
    </div>
  );
}

export default function FunnelStrip({ funnel }: FunnelStripProps) {
  return (
    <div className="bg-white border border-slate-200 rounded-xl shadow-sm px-4 py-3 space-y-1.5">
      <p className="text-xs text-slate-400 font-medium">
        Funnel par play — {funnel.period_days} derniers jours
      </p>
      <PlayLine label="P1 · MMF Gap (outreach)" funnel={funnel.p1_mmf_gap} withOutreach />
      <PlayLine label="P2 · Levées (audit)" funnel={funnel.p2_funding} withOutreach={false} />
      <PlayLine label="P3 · Inbound (SPICED)" funnel={funnel.p3_inbound} withOutreach={false} />
    </div>
  );
}
