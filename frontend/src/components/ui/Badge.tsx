type BadgeTone = 'success' | 'danger' | 'warn' | 'info' | 'neutral' | 'id';

interface BadgeProps {
  tone?: BadgeTone;
  dot?: boolean;
  children: React.ReactNode;
  style?: React.CSSProperties;
}

export default function Badge({ tone = 'neutral', dot = false, children, style }: BadgeProps) {
  return (
    <span className={`badge ${tone}`} style={style}>
      {dot && <span className="dot" />}
      {children}
    </span>
  );
}
