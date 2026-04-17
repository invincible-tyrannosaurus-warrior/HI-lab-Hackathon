import type { GraphFilters } from "../hooks/useKnowledgeGraph";

interface GraphToolbarProps {
  modules: string[];
  weeks: string[];
  roles: string[];
  sourceTypes: string[];
  filters: GraphFilters;
  searchQuery: string;
  onSearchChange: (value: string) => void;
  onFiltersChange: (filters: GraphFilters) => void;
  onRefresh: () => void;
  onFitGraph: () => void;
  onSearchSubmit: () => void;
}

function FilterSelect(props: {
  label: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
  disabled?: boolean;
}) {
  const { label, value, options, onChange, disabled } = props;
  return (
    <label className="toolbar-control">
      <span>{label}</span>
      <select value={value} disabled={disabled} onChange={(event) => onChange(event.target.value)}>
        <option value="all">All</option>
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  );
}

export function GraphToolbar(props: GraphToolbarProps) {
  const {
    modules,
    weeks,
    roles,
    sourceTypes,
    filters,
    searchQuery,
    onSearchChange,
    onFiltersChange,
    onRefresh,
    onFitGraph,
    onSearchSubmit,
  } = props;

  return (
    <header className="topbar">
      <div className="topbar-title">
        <p className="eyebrow">Durham AI Education System Upgrade</p>
        <h1>Knowledge Bank Graph</h1>
      </div>

      <div className="topbar-tools">
        <label className="search-control">
          <span className="sr-only">Search knowledge units</span>
          <input
            value={searchQuery}
            placeholder="Search title, knowledge_id, or topic tag"
            onChange={(event) => onSearchChange(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                onSearchSubmit();
              }
            }}
          />
        </label>

        <div className="toolbar-group">
          <FilterSelect
            label="Module"
            value={filters.moduleTag}
            options={modules}
            disabled={modules.length <= 1}
            onChange={(value) => onFiltersChange({ ...filters, moduleTag: value })}
          />
          <FilterSelect
            label="Status"
            value={filters.approvalStatus}
            options={["approved", "draft"]}
            onChange={(value) => onFiltersChange({ ...filters, approvalStatus: value })}
          />
          <FilterSelect
            label="Role"
            value={filters.pedagogicalRole}
            options={roles}
            onChange={(value) => onFiltersChange({ ...filters, pedagogicalRole: value })}
          />
          <FilterSelect
            label="Week"
            value={filters.weekTag}
            options={weeks}
            onChange={(value) => onFiltersChange({ ...filters, weekTag: value })}
          />
          <FilterSelect
            label="Source"
            value={filters.sourceType}
            options={sourceTypes}
            onChange={(value) => onFiltersChange({ ...filters, sourceType: value })}
          />
        </div>

        <div className="toolbar-actions">
          <button className="ghost-button" onClick={onFitGraph} type="button">
            Fit Graph
          </button>
          <button className="primary-button" onClick={onRefresh} type="button">
            Refresh
          </button>
        </div>
      </div>
    </header>
  );
}
