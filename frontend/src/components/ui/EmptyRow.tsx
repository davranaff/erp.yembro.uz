import Icon from './Icon';

interface EmptyRowProps {
  cols: number;
  label?: string;
}

export default function EmptyRow({ cols, label = 'Нет данных' }: EmptyRowProps) {
  return (
    <tr>
      <td colSpan={cols}>
        <div className="empty">
          <Icon name="inbox" size={40} className="emp-ic" />
          {label}
        </div>
      </td>
    </tr>
  );
}
