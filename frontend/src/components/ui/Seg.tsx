'use client';

interface SegOption {
  value: string;
  label: string;
}

interface SegProps {
  options: SegOption[];
  value: string;
  onChange: (v: string) => void;
}

export default function Seg({ options, value, onChange }: SegProps) {
  return (
    <div className="seg">
      {options.map(o => (
        <button
          key={o.value}
          className={value === o.value ? 'active' : ''}
          onClick={() => onChange(o.value)}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
