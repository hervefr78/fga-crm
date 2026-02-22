// =============================================================================
// FGA CRM - Composant Pagination reutilisable
// =============================================================================

interface PaginationProps {
  page: number;
  pages: number;
  total: number;
  onPageChange: (page: number) => void;
}

export default function Pagination({ page, pages, total, onPageChange }: PaginationProps) {
  if (pages <= 1) return null;

  return (
    <div className="px-6 py-3 border-t border-slate-100 flex items-center justify-between">
      <p className="text-xs text-slate-400">
        Page {page} sur {pages} ({total} résultats)
      </p>
      <div className="flex gap-2">
        <button
          onClick={() => onPageChange(Math.max(1, page - 1))}
          disabled={page === 1}
          className="px-3 py-1.5 text-xs text-slate-500 border border-slate-200 rounded-lg hover:bg-slate-50 disabled:opacity-40"
        >
          Précédent
        </button>
        <button
          onClick={() => onPageChange(Math.min(pages, page + 1))}
          disabled={page >= pages}
          className="px-3 py-1.5 text-xs text-slate-500 border border-slate-200 rounded-lg hover:bg-slate-50 disabled:opacity-40"
        >
          Suivant
        </button>
      </div>
    </div>
  );
}
