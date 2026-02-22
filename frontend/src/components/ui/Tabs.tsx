// =============================================================================
// FGA CRM - Composant Tabs reutilisable
// =============================================================================

interface Tab {
  key: string;
  label: string;
  count?: number;
}

interface TabsProps {
  tabs: Tab[];
  activeTab: string;
  onChange: (key: string) => void;
}

export default function Tabs({ tabs, activeTab, onChange }: TabsProps) {
  return (
    <div className="border-b border-slate-200">
      <nav className="flex gap-6 px-1" role="tablist">
        {tabs.map((tab) => {
          const isActive = tab.key === activeTab;
          return (
            <button
              key={tab.key}
              role="tab"
              aria-selected={isActive}
              onClick={() => onChange(tab.key)}
              className={`
                pb-3 text-sm font-medium border-b-2 transition-colors
                ${isActive
                  ? 'border-primary-600 text-primary-600'
                  : 'border-transparent text-slate-400 hover:text-slate-600 hover:border-slate-300'
                }
              `}
            >
              {tab.label}
              {tab.count !== undefined && (
                <span className={`ml-1.5 text-xs rounded-full px-1.5 py-0.5 ${isActive ? 'bg-primary-50 text-primary-600' : 'bg-slate-100 text-slate-400'}`}>
                  {tab.count}
                </span>
              )}
            </button>
          );
        })}
      </nav>
    </div>
  );
}
