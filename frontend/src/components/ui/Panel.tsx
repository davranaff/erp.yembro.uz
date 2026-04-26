interface PanelProps {
  title?: string;
  tools?: React.ReactNode;
  flush?: boolean;
  children: React.ReactNode;
  style?: React.CSSProperties;
}

export default function Panel({ title, tools, flush, children, style }: PanelProps) {
  return (
    <div className="panel" style={style}>
      {(title || tools) && (
        <div className="panel-hdr">
          {title && <h3>{title}</h3>}
          {tools && <div className="tools">{tools}</div>}
        </div>
      )}
      <div className={`panel-body${flush ? ' flush' : ''}`}>{children}</div>
    </div>
  );
}
