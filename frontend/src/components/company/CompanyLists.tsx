// =============================================================================
// FGA CRM - Company : listes de deals et contacts (extraites de CompanyDetail.tsx)
// =============================================================================

import { Link } from 'react-router-dom';
import { Target, Users, Star, Mail, ChevronRight } from 'lucide-react';
import clsx from 'clsx';

import type { Contact, Deal } from '../../types';
import { Badge } from '../ui';
import { EmptyTab } from './CompanyAtoms';
import { STAGE_COLORS, STAGE_LABELS, formatDate } from './companyUtils';

export function DealsList({ deals }: { deals: Deal[] }) {
  if (deals.length === 0) return <EmptyTab icon={Target} text="Aucune opportunite" />;
  return (
    <div>
      {deals.map((d) => (
        <Link
          key={d.id}
          to={`/pipeline/${d.id}`}
          className="grid grid-cols-[1fr_auto_auto_auto] gap-3 items-center px-4 py-3 border-b border-slate-100 last:border-0 hover:bg-slate-50/60 transition-colors"
        >
          <div>
            <div className="text-sm font-medium text-slate-800">{d.title}</div>
            <div className="text-xs text-slate-400 mt-0.5">
              Cloture {d.expected_close_date ? formatDate(d.expected_close_date) : '—'}
            </div>
          </div>
          <span className={clsx('inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium', STAGE_COLORS[d.stage])}>
            {STAGE_LABELS[d.stage]}
          </span>
          <div className="text-right">
            <div className="text-sm font-semibold text-slate-900 tabular-nums">{(d.amount ?? 0).toLocaleString('fr-FR')} {d.currency}</div>
            <div className="text-xs text-slate-400 mt-0.5">{d.probability ?? 0}%</div>
          </div>
          <ChevronRight className="w-4 h-4 text-slate-300" />
        </Link>
      ))}
    </div>
  );
}

export function ContactsList({ contacts }: { contacts: Contact[] }) {
  if (contacts.length === 0) return <EmptyTab icon={Users} text="Aucun contact attache" />;
  return (
    <div>
      {contacts.map((c) => (
        <Link
          key={c.id}
          to={`/contacts/${c.id}`}
          className="grid grid-cols-[32px_1fr_auto] gap-3 items-center px-4 py-3 border-b border-slate-100 last:border-0 hover:bg-slate-50/60 transition-colors"
        >
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-50 to-indigo-50 flex items-center justify-center text-xs font-semibold text-primary-700">
            {(c.first_name?.[0] ?? '') + (c.last_name?.[0] ?? '')}
          </div>
          <div>
            <div className="text-sm font-medium text-slate-800 flex items-center gap-1.5">
              {c.first_name} {c.last_name}
              {c.is_decision_maker && (
                <Badge variant="success" className="!px-1.5 !py-0 !text-[10px]">
                  <Star className="w-2.5 h-2.5 mr-0.5 inline" />
                  Decisionnaire
                </Badge>
              )}
            </div>
            <div className="text-xs text-slate-400 mt-0.5">{c.title || '—'} · {c.email || '—'}</div>
          </div>
          {c.email && (
            <a
              href={`mailto:${c.email}`}
              onClick={(e) => e.stopPropagation()}
              className="p-1.5 rounded text-slate-400 hover:bg-slate-100"
              aria-label="Envoyer un email"
            >
              <Mail className="w-3.5 h-3.5" />
            </a>
          )}
        </Link>
      ))}
    </div>
  );
}
