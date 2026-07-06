// =============================================================================
// FGA CRM - UI : poignee de redimensionnement (bord droit d'un panneau lateral)
// =============================================================================
// Barre fine sur le bord droit d'un <aside relative>. Le parent doit gerer la
// largeur (cf. useResizableWidth). Purement presentationnel + onMouseDown.
// =============================================================================

import clsx from 'clsx';

interface ResizeHandleProps {
  onMouseDown: (e: React.MouseEvent) => void;
  isResizing?: boolean;
  label?: string;
}

export default function ResizeHandle({
  onMouseDown, isResizing = false, label = 'Redimensionner le panneau',
}: ResizeHandleProps) {
  return (
    <div
      onMouseDown={onMouseDown}
      role="separator"
      aria-orientation="vertical"
      aria-label={label}
      className={clsx(
        'group absolute top-0 right-0 z-20 h-full w-1.5 cursor-col-resize flex justify-center',
        'hover:bg-primary-100/40 transition-colors',
        isResizing && 'bg-primary-100/60',
      )}
    >
      <span
        className={clsx(
          'w-px h-full transition-colors',
          isResizing ? 'bg-primary-400' : 'bg-transparent group-hover:bg-primary-300',
        )}
      />
    </div>
  );
}
