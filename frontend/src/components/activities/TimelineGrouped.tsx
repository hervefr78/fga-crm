// =============================================================================
// FGA CRM - TimelineGrouped : timeline d'activites groupee par jour (read-only)
// =============================================================================
//
// Composant partage (DC8) pour afficher une liste d'activites sous forme de
// timeline verticale, avec entetes par jour ("Aujourd'hui", "Hier", "12 mai").
//
// Version "display only" : pas de composer, pas d'edition. Utilisee par le
// dashboard pour montrer les 30 dernieres activites de l'equipe.
// Pour la version avec composer multi-canal, voir l'ActivityFeed inline des
// pages Company/Contact/Deal Detail.
// =============================================================================

import { useMemo } from 'react';
import {
  Mail, Phone, Video, FileText, Linkedin, Check, Zap,
  Activity as ActivityIcon,
} from 'lucide-react';
import clsx from 'clsx';
import type { Activity } from '../../types';

// Icones par type d'activite (DC8 — meme mapping que les pages detail)
const ACTIVITY_ICONS: Record<string, React.ElementType> = {
  email: Mail,
  call: Phone,
  meeting: Video,
  note: FileText,
  linkedin: Linkedin,
  task: Check,
  audit: Zap,
};

// Couleurs sobres alignees sur la palette §2.1 (UI_GUIDELINES)
const ACTIVITY_BG: Record<string, string> = {
  email: 'bg-blue-50 text-blue-600',
  call: 'bg-emerald-50 text-emerald-600',
  meeting: 'bg-indigo-50 text-indigo-600',
  note: 'bg-amber-50 text-amber-600',
  linkedin: 'bg-sky-50 text-sky-600',
  task: 'bg-slate-100 text-slate-600',
  audit: 'bg-violet-50 text-violet-600',
};

interface TimelineGroupedProps {
  activities: Activity[];
  // Hauteur max pour activer le scroll interne (ex: 'max-h-96').
  // Si non fourni, la timeline s'etend en hauteur naturelle.
  maxHeight?: string;
}

export default function TimelineGrouped({ activities, maxHeight }: TimelineGroupedProps) {
  // Groupage par jour (memoize — DC8)
  const grouped = useMemo(() => {
    const map = new Map<string, Activity[]>();
    for (const a of activities) {
      const day = formatDay(a.created_at);
      if (!map.has(day)) map.set(day, []);
      map.get(day)!.push(a);
    }
    return Array.from(map.entries());
  }, [activities]);

  // Empty state (DC5)
  if (activities.length === 0) {
    return (
      <div className="py-10 flex flex-col items-center justify-center text-center text-sm text-slate-400 gap-2">
        <div className="w-9 h-9 rounded-lg bg-slate-50 flex items-center justify-center">
          <ActivityIcon className="w-4 h-4" />
        </div>
        Aucune activite enregistree
      </div>
    );
  }

  return (
    <div className={clsx('relative', maxHeight && `${maxHeight} overflow-y-auto`)}>
      {/* Trait vertical : aligne sur le centre des icones (28px wrapper + 14px = 31px) */}
      <div className="absolute left-[31px] top-9 bottom-3 w-px bg-slate-100" />
      {grouped.map(([day, items]) => (
        <div key={day}>
          <div className="flex items-center gap-2 px-4 pt-3 pb-1.5 sticky top-0 bg-white z-10">
            <span className="text-[11px] font-medium text-slate-400 uppercase tracking-wider">
              {day}
            </span>
            <span className="flex-1 h-px bg-slate-100" />
          </div>
          {items.map((a) => {
            const Icon = ACTIVITY_ICONS[a.type] ?? FileText;
            return (
              <div
                key={a.id}
                className="grid grid-cols-[28px_1fr_auto] gap-3 px-4 py-2.5 hover:bg-slate-50/60 transition-colors"
              >
                <div
                  className={clsx(
                    'w-7 h-7 rounded-lg border flex items-center justify-center flex-shrink-0 relative z-10 border-slate-200/60',
                    ACTIVITY_BG[a.type] ?? 'bg-slate-100 text-slate-500',
                  )}
                >
                  <Icon className="w-3.5 h-3.5" />
                </div>
                <div className="min-w-0 space-y-1">
                  <div className="text-sm font-medium text-slate-800 truncate">
                    {a.subject || a.type}
                  </div>
                  {a.content && (
                    <div className="text-xs text-slate-600 bg-slate-50 border border-slate-100 rounded-md px-2.5 py-2 leading-relaxed line-clamp-3">
                      {a.content}
                    </div>
                  )}
                </div>
                <div className="text-[11px] text-slate-400 tabular-nums whitespace-nowrap">
                  {formatTime(a.created_at)}
                </div>
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}

// -----------------------------------------------------------------------------
// Helpers (alignes sur les pages detail — DC8)
// -----------------------------------------------------------------------------

function formatDay(d?: string | null): string {
  if (!d) return '';
  const date = new Date(d);
  const today = new Date();
  const yesterday = new Date();
  yesterday.setDate(today.getDate() - 1);
  if (date.toDateString() === today.toDateString()) return "Aujourd'hui";
  if (date.toDateString() === yesterday.toDateString()) return 'Hier';
  return date.toLocaleDateString('fr-FR', { day: 'numeric', month: 'long' });
}

function formatTime(d?: string | null): string {
  if (!d) return '';
  return new Date(d).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
}
