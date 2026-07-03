// =============================================================================
// FGA CRM - Feed d'activite de la fiche Deal (composer multi-canal + timeline)
// Extrait VERBATIM de DealDetail.tsx (refactor C5) — rendu inchange.
// =============================================================================

import { useMemo } from 'react';
import {
  Paperclip, Smile, Sparkles, Send, FileText,
  Activity as ActivityIcon,
} from 'lucide-react';
import clsx from 'clsx';

import type { Activity } from '../../types';
import { Button } from '../ui';
import type { ComposerChannel } from '../activities/ComposerModal';
import { EmptyTab } from './DealAtoms';
import { ACTIVITY_ICONS, ACTIVITY_BG, formatDay, formatTime } from './dealUtils';

export default function ActivityFeed({
  activities,
  onChannelClick,
}: {
  activities: Activity[];
  onChannelClick: (c: ComposerChannel) => void;
}) {
  const grouped = useMemo(() => {
    const map = new Map<string, Activity[]>();
    for (const a of activities) {
      const day = formatDay(a.created_at);
      if (!map.has(day)) map.set(day, []);
      map.get(day)!.push(a);
    }
    return Array.from(map.entries());
  }, [activities]);

  const channels: { label: string; channel: ComposerChannel }[] = [
    { label: 'Note', channel: 'note' },
    { label: 'Email', channel: 'email' },
    { label: 'Appel', channel: 'call' },
    { label: 'RDV', channel: 'meeting' },
  ];

  return (
    <div>
      <div className="m-4 border border-slate-200 rounded-lg bg-slate-50/50">
        <div className="flex border-b border-slate-200 px-1.5">
          {channels.map(({ label, channel }) => (
            <button
              key={channel}
              type="button"
              onClick={() => onChannelClick(channel)}
              className="px-2.5 py-2 text-xs font-medium text-slate-500 border-b border-transparent hover:text-slate-700 -mb-px"
            >
              {label}
            </button>
          ))}
        </div>
        <div className="px-3 py-2.5">
          <button
            type="button"
            onClick={() => onChannelClick('note')}
            className="w-full text-left text-sm text-slate-400 italic hover:text-slate-600 min-h-[40px]"
          >
            Cliquer ici pour ajouter une note rapide...
          </button>
        </div>
        <div className="flex items-center justify-between px-2 pb-2 pt-1 border-t border-slate-100">
          <div className="flex gap-0.5">
            <button className="p-1.5 rounded text-slate-400 hover:bg-slate-100" aria-label="Pieces jointes"><Paperclip className="w-3.5 h-3.5" /></button>
            <button className="p-1.5 rounded text-slate-400 hover:bg-slate-100" aria-label="Emoji"><Smile className="w-3.5 h-3.5" /></button>
            <button className="inline-flex items-center gap-1 px-2 py-1 rounded text-slate-500 hover:bg-slate-100 text-xs"><Sparkles className="w-3 h-3" />IA</button>
          </div>
          <div className="flex gap-1.5">
            <Button variant="primary" size="sm" icon={Send} onClick={() => onChannelClick('note')}>Publier</Button>
          </div>
        </div>
      </div>

      {activities.length === 0 ? (
        <EmptyTab icon={ActivityIcon} text="Aucune activite enregistree" />
      ) : (
        <div className="relative pb-4">
          <div className="absolute left-[31px] top-9 bottom-3 w-px bg-slate-100" />
          {grouped.map(([day, items]) => (
            <div key={day}>
              <div className="flex items-center gap-2 px-4 pt-3 pb-1.5">
                <span className="text-[11px] font-medium text-slate-400 uppercase tracking-wider">{day}</span>
                <span className="flex-1 h-px bg-slate-100" />
              </div>
              {items.map((a) => {
                const Icon = ACTIVITY_ICONS[a.type] ?? FileText;
                return (
                  <div key={a.id} className="grid grid-cols-[28px_1fr_auto] gap-3 px-4 py-2.5 hover:bg-slate-50/60 transition-colors">
                    <div className={clsx('w-7 h-7 rounded-lg border flex items-center justify-center flex-shrink-0 relative z-10', ACTIVITY_BG[a.type] ?? 'bg-slate-100 text-slate-500', 'border-slate-200/60')}>
                      <Icon className="w-3.5 h-3.5" />
                    </div>
                    <div className="min-w-0 space-y-1">
                      <div className="text-sm font-medium text-slate-800">{a.subject || a.type}</div>
                      {a.content && (
                        <div className="text-xs text-slate-600 bg-slate-50 border border-slate-100 rounded-md px-2.5 py-2 leading-relaxed line-clamp-3">{a.content}</div>
                      )}
                    </div>
                    <div className="text-[11px] text-slate-400 tabular-nums whitespace-nowrap">{formatTime(a.created_at)}</div>
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
