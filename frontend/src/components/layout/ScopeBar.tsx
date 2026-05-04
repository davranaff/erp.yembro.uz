import Icon from '@/components/ui/Icon';

interface Resource { n: string; l: string; }

interface ScopeBarProps {
  company: { code: string; name: string };
  module?: { name: string; icon?: string };
  block?: { code: string; name: string };
  resources?: Resource[];
}

export default function ScopeBar({ company, module, block, resources }: ScopeBarProps) {
  return (
    <div className="scopebar">
      <div className="scope-cell level-company">
        <div className="lbl">Компания</div>
        <div className="val">
          <div style={{ width: 18, height: 18, borderRadius: 3, background: 'var(--brand-orange)', color: 'white', display: 'grid', placeItems: 'center', fontSize: 9, fontWeight: 700, flexShrink: 0 }}>
            {company.code}
          </div>
          <span>{company.name}</span>
          <Icon name="chevron-down" size={12} style={{ color: 'var(--fg-muted)' }} />
        </div>
      </div>

      {module && (
        <div className="scope-cell level-module">
          <div className="lbl">Модуль</div>
          <div className="val">
            <Icon name={module.icon ?? 'factory'} size={14} style={{ color: 'var(--brand-orange)' }} />
            <span>{module.name}</span>
            <Icon name="chevron-down" size={12} style={{ color: 'var(--fg-muted)' }} />
          </div>
        </div>
      )}

      {block && (
        <div className="scope-cell level-block">
          <div className="lbl">Блок</div>
          <div className="val">
            <span className="badge id" style={{ fontSize: 10 }}>{block.code}</span>
            <span>{block.name}</span>
            <Icon name="chevron-down" size={12} style={{ color: 'var(--fg-muted)' }} />
          </div>
        </div>
      )}

      {resources && (
        <div className="scope-resources">
          {resources.map((r, i) => (
            <div key={i} className="r"><b>{r.n}</b>{r.l}</div>
          ))}
        </div>
      )}
    </div>
  );
}
