import Icon from './Icon';

type KpiTone = 'blue' | 'orange' | 'red' | 'green';

interface KpiCardProps {
  tone?: KpiTone;
  label: string;
  sub?: string;
  value?: string;
  valueSuffix?: string;
  meta?: string;
  empty?: boolean;
  iconName?: string;
}

export default function KpiCard({ tone = 'blue', label, sub, value, valueSuffix, meta, empty, iconName }: KpiCardProps) {
  return (
    <div className={`kpi ${tone}`}>
      {iconName && (
        <div className="ic-btn">
          <Icon name={iconName} size={16} />
        </div>
      )}
      <div className="label">{label}</div>
      {sub && <div className="sub">{sub}</div>}
      {empty ? (
        <div className="muted">Нет данных</div>
      ) : (
        <>
          {value !== undefined && (
            <div className="value">
              {value}
              {valueSuffix && (
                <span style={{ fontSize: 13, color: 'var(--fg-3)', marginLeft: 6, fontWeight: 500 }}>
                  {valueSuffix}
                </span>
              )}
            </div>
          )}
          {meta && <div className="meta">{meta}</div>}
        </>
      )}
    </div>
  );
}
