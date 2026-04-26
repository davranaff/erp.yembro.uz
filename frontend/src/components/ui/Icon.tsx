interface IconProps {
  name: string;
  size?: number;
  className?: string;
  style?: React.CSSProperties;
}

export default function Icon({ name, size = 16, className, style }: IconProps) {
  const s: React.CSSProperties = { width: size, height: size, display: 'inline-block', flexShrink: 0, ...style };
  const p = { fill: 'none', stroke: 'currentColor', strokeWidth: 1.75, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const };

  switch (name) {
    case 'grid':
      return <svg viewBox="0 0 24 24" style={s} className={className} {...p}><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>;
    case 'egg':
      return <svg viewBox="0 0 24 24" style={s} className={className} {...p}><path d="M12 3c4 0 7 3 7 7 0 5-5 11-7 11s-7-6-7-11c0-4 3-7 7-7z"/></svg>;
    case 'incubator':
      return <svg viewBox="0 0 24 24" style={s} className={className} {...p}><circle cx="12" cy="12" r="9"/><path d="M12 3v18M3 12h18"/></svg>;
    case 'factory':
      return <svg viewBox="0 0 24 24" style={s} className={className} {...p}><rect x="3" y="8" width="18" height="12"/><path d="M7 8V5h10v3M7 14h2M13 14h2M7 18h2M13 18h2"/></svg>;
    case 'building':
      return <svg viewBox="0 0 24 24" style={s} className={className} {...p}><path d="M4 20h16M6 20V9l6-4 6 4v11M10 20v-5h4v5"/></svg>;
    case 'bag':
      return <svg viewBox="0 0 24 24" style={s} className={className} {...p}><path d="M4 7h16l-1 13H5L4 7zM8 7V4h8v3"/></svg>;
    case 'pharma':
      return <svg viewBox="0 0 24 24" style={s} className={className} {...p}><rect x="4" y="6" width="16" height="14" rx="2"/><path d="M12 10v6M9 13h6"/></svg>;
    case 'chart':
      return <svg viewBox="0 0 24 24" style={s} className={className} {...p}><path d="M5 20h14M7 20V10h4v10M13 20V4h4v16"/></svg>;
    case 'users':
      return <svg viewBox="0 0 24 24" style={s} className={className} {...p}><circle cx="9" cy="9" r="3.5"/><path d="M3 20c0-3 3-5 6-5s6 2 6 5"/><circle cx="17" cy="10" r="2.5"/><path d="M15 20c0-2 2-4 4-4"/></svg>;
    case 'book':
      return <svg viewBox="0 0 24 24" style={s} className={className} {...p}><path d="M5 4h12a2 2 0 012 2v14H7a2 2 0 01-2-2V4zM5 18a2 2 0 012-2h12"/></svg>;
    case 'box':
      return <svg viewBox="0 0 24 24" style={s} className={className} {...p}><path d="M4 8l8-5 8 5v8l-8 5-8-5V8zM4 8l8 5 8-5M12 13v9"/></svg>;
    case 'settings':
      return <svg viewBox="0 0 24 24" style={s} className={className} {...p}><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.6 1.6 0 00.3 1.8l.1.1a2 2 0 11-2.8 2.8l-.1-.1a1.6 1.6 0 00-1.8-.3 1.6 1.6 0 00-1 1.5V21a2 2 0 01-4 0v-.1a1.6 1.6 0 00-1-1.5 1.6 1.6 0 00-1.8.3l-.1.1a2 2 0 11-2.8-2.8l.1-.1a1.6 1.6 0 00.3-1.8 1.6 1.6 0 00-1.5-1H3a2 2 0 010-4h.1a1.6 1.6 0 001.5-1 1.6 1.6 0 00-.3-1.8l-.1-.1a2 2 0 112.8-2.8l.1.1a1.6 1.6 0 001.8.3H9a1.6 1.6 0 001-1.5V3a2 2 0 014 0v.1a1.6 1.6 0 001 1.5 1.6 1.6 0 001.8-.3l.1-.1a2 2 0 112.8 2.8l-.1.1a1.6 1.6 0 00-.3 1.8V9a1.6 1.6 0 001.5 1H21a2 2 0 010 4h-.1a1.6 1.6 0 00-1.5 1z"/></svg>;
    case 'star':
      return <svg viewBox="0 0 24 24" style={s} className={className} fill="#F5B700" stroke="#D19A00" strokeWidth="1.5" strokeLinejoin="round"><polygon points="12,3 15,9 21,10 16.5,14.5 18,21 12,17.5 6,21 7.5,14.5 3,10 9,9"/></svg>;
    case 'plus':
      return <svg viewBox="0 0 24 24" style={s} className={className} {...p}><path d="M12 5v14M5 12h14"/></svg>;
    case 'search':
      return <svg viewBox="0 0 24 24" style={s} className={className} {...p}><circle cx="11" cy="11" r="7"/><path d="M21 21l-5-5"/></svg>;
    case 'filter':
      return <svg viewBox="0 0 24 24" style={s} className={className} {...p}><path d="M4 5h16l-6 8v6l-4-2v-4z"/></svg>;
    case 'download':
      return <svg viewBox="0 0 24 24" style={s} className={className} {...p}><path d="M12 4v12M6 12l6 6 6-6M4 20h16"/></svg>;
    case 'chevron-down':
      return <svg viewBox="0 0 24 24" style={s} className={className} {...p}><path d="M6 9l6 6 6-6"/></svg>;
    case 'chevron-right':
      return <svg viewBox="0 0 24 24" style={s} className={className} {...p}><path d="M9 6l6 6-6 6"/></svg>;
    case 'help':
      return <svg viewBox="0 0 24 24" style={s} className={className} {...p}><circle cx="12" cy="12" r="9"/><path d="M9.5 9a2.5 2.5 0 015 0c0 2-2.5 2-2.5 4M12 17h.01"/></svg>;
    case 'close':
      return <svg viewBox="0 0 24 24" style={s} className={className} {...p}><path d="M6 6l12 12M6 18L18 6"/></svg>;
    case 'inbox':
      return <svg viewBox="0 0 24 24" style={s} className={className} {...p}><path d="M3 13l3-8h12l3 8M3 13v6a2 2 0 002 2h14a2 2 0 002-2v-6M3 13h5a2 2 0 014 0 2 2 0 014 0h5"/></svg>;
    case 'check':
      return <svg viewBox="0 0 24 24" style={s} className={className} {...p}><path d="M5 12l5 5L20 7"/></svg>;
    case 'arrow-right':
      return <svg viewBox="0 0 24 24" style={s} className={className} {...p}><path d="M5 12h14M13 5l7 7-7 7"/></svg>;
    case 'menu':
      return <svg viewBox="0 0 24 24" style={s} className={className} {...p}><path d="M4 6h16M4 12h16M4 18h16"/></svg>;
    default:
      return null;
  }
}
