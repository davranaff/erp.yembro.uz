'use client';

import { useEffect, useState } from 'react';

import Modal from '@/components/ui/Modal';
import { useSubaccounts } from '@/hooks/useAccounts';
import { useCreatePayout } from '@/hooks/usePayroll';

export default function PayoutModal({
  employeeId, employeeName, onClose,
}: { employeeId: string; employeeName: string; onClose: () => void }) {
  const { data: subaccounts = [] } = useSubaccounts();
  const create = useCreatePayout();

  const [type, setType] = useState<'advance' | 'salary' | 'bonus' | 'correction'>('salary');
  const [amount, setAmount] = useState('');
  const today = new Date().toISOString().slice(0, 10);
  const monthStart = today.slice(0, 8) + '01';
  const [periodFrom, setPeriodFrom] = useState(monthStart);
  const [periodTo, setPeriodTo] = useState(today);
  const [cashId, setCashId] = useState('');
  const [channel, setChannel] = useState('cash');
  const [notes, setNotes] = useState('');

  // Фильтруем кассы (50.* / 51.*)
  const cashOptions = subaccounts.filter((s) =>
    s.code.startsWith('50.') || s.code.startsWith('51.')
  );

  useEffect(() => {
    if (!cashId && cashOptions.length) setCashId(cashOptions[0].id);
  }, [cashOptions, cashId]);

  const handleSubmit = () => {
    const amt = amount.replace(/\s/g, '');
    if (!amt || Number(amt) <= 0) {
      alert('Введите сумму больше нуля.');
      return;
    }
    if (!cashId) {
      alert('Выберите кассу.');
      return;
    }
    create.mutate({
      employee: employeeId,
      type,
      amount_uzs: amt,
      period_from: periodFrom,
      period_to: periodTo,
      cash_subaccount: cashId,
      channel,
      notes,
    }, {
      onSuccess: () => onClose(),
      onError: (e) => alert(e.message),
    });
  };

  return (
    <Modal
      title={`Выплата · ${employeeName}`}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost btn-sm" onClick={onClose}>Отмена</button>
          <button className="btn btn-primary btn-sm" onClick={handleSubmit} disabled={create.isPending}>
            {create.isPending ? 'Сохраняем…' : 'Выплатить'}
          </button>
        </>
      }
    >
      <div style={{ display: 'grid', gap: 10 }}>
        <label>Тип</label>
        <select className="input" value={type} onChange={(e) => setType(e.target.value as never)}>
          <option value="advance">Аванс</option>
          <option value="salary">ЗП</option>
          <option value="bonus">Премия</option>
          <option value="correction">Корректировка</option>
        </select>

        <label>Сумма (UZS)</label>
        <input className="input" inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} />

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
          <div>
            <label>Период с</label>
            <input className="input" type="date" value={periodFrom} onChange={(e) => setPeriodFrom(e.target.value)} />
          </div>
          <div>
            <label>Период по</label>
            <input className="input" type="date" value={periodTo} onChange={(e) => setPeriodTo(e.target.value)} />
          </div>
        </div>

        <label>Касса (откуда)</label>
        <select className="input" value={cashId} onChange={(e) => setCashId(e.target.value)}>
          {cashOptions.length === 0 && <option value="">— нет касс —</option>}
          {cashOptions.map((s) => (
            <option key={s.id} value={s.id}>{s.name}</option>
          ))}
        </select>

        <label>Канал</label>
        <select className="input" value={channel} onChange={(e) => setChannel(e.target.value)}>
          <option value="cash">Наличные</option>
          <option value="transfer">Перечисление</option>
          <option value="click">Click</option>
          <option value="other">Прочее</option>
        </select>

        <label>Заметка</label>
        <input className="input" value={notes} onChange={(e) => setNotes(e.target.value)} />
      </div>
    </Modal>
  );
}
