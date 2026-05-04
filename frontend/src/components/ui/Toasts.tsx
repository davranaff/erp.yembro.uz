import Icon from './Icon';

export interface Toast {
  id: number;
  text: string;
}

export default function Toasts({ items }: { items: Toast[] }) {
  return (
    <div className="toasts">
      {items.map(t => (
        <div key={t.id} className="toast">
          <Icon name="check" size={14} className="ok" />
          {t.text}
        </div>
      ))}
    </div>
  );
}
