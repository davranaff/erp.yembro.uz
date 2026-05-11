'use client';

import { useParams, useSearchParams } from 'next/navigation';
import { useEffect } from 'react';

import { useEmployeeAccrued, useEmployeeAdjustments, useEmployeeBalance, useEmployeePayouts } from '@/hooks/usePayroll';
import { usePerson } from '@/hooks/usePeople';

const PAYOUT_LABEL: Record<string, string> = {
  advance: 'Аванс',
  salary: 'ЗП',
  bonus: 'Премия',
  correction: 'Корректировка',
};

const ADJ_LABEL: Record<string, string> = {
  bonus: 'Премия',
  deduction: 'Удержание',
  correction_plus: 'Доначисление',
  correction_minus: 'Сторно',
};

function fmt(v: string | number | null | undefined): string {
  if (v === null || v === undefined || v === '') return '—';
  const n = typeof v === 'number' ? v : Number(v);
  if (!Number.isFinite(n)) return '—';
  return new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 }).format(n);
}

function ymd(d: Date): string {
  return d.toISOString().slice(0, 10);
}

export default function PayslipPage() {
  const params = useParams<{ id: string }>();
  const search = useSearchParams();
  const id = params?.id;

  const today = new Date();
  const monthStart = ymd(new Date(today.getFullYear(), today.getMonth(), 1));
  const monthEnd = ymd(new Date(today.getFullYear(), today.getMonth() + 1, 0));
  const fromDate = search?.get('from') ?? monthStart;
  const toDate = search?.get('to') ?? monthEnd;

  const { data: person } = usePerson(id);
  const { data: balance } = useEmployeeBalance(id, toDate);
  const { data: accrued } = useEmployeeAccrued(id, fromDate, toDate);
  const { data: payouts } = useEmployeePayouts(id);
  const { data: adjustments } = useEmployeeAdjustments(id);

  useEffect(() => {
    if (person && balance && accrued) {
      const t = setTimeout(() => window.print(), 600);
      return () => clearTimeout(t);
    }
  }, [person, balance, accrued]);

  if (!person) return <div style={{ padding: 24 }}>Загружаем…</div>;

  const periodPayouts = (payouts ?? []).filter(
    (p) => p.period_to >= fromDate && p.period_from <= toDate,
  );
  const periodAdj = (adjustments ?? []).filter(
    (a) => a.effective_date >= fromDate && a.effective_date <= toDate,
  );

  return (
    <>
      <style jsx global>{`
        @media print {
          .sidebar, .page-hdr, .no-print, header, nav { display: none !important; }
          body { background: white !important; }
          main { margin: 0 !important; padding: 0 !important; max-width: 100% !important; }
        }
        .payslip table { width: 100%; border-collapse: collapse; font-size: 12px; }
        .payslip th, .payslip td { padding: 6px 8px; border-bottom: 1px solid #ddd; text-align: left; }
        .payslip th { background: #f7f7f7; font-weight: 600; }
        .payslip .num { text-align: right; font-family: monospace; }
      `}</style>

      <div className="payslip" style={{ background: 'white', padding: '40px 60px', maxWidth: 820, margin: '0 auto', fontFamily: 'system-ui, sans-serif' }}>
        <div style={{ marginBottom: 32 }}>
          <div style={{ fontSize: 11, color: '#888' }}>Расчётный лист</div>
          <h1 style={{ fontSize: 22, margin: '4px 0' }}>{person.user_full_name || '—'}</h1>
          <div style={{ fontSize: 13, color: '#555' }}>
            {person.position_title || '—'} · {person.user_email}
          </div>
          <div style={{ fontSize: 12, color: '#888', marginTop: 4 }}>
            Период: {fromDate} — {toDate}
          </div>
        </div>

        <h3 style={{ fontSize: 14, marginBottom: 8 }}>Начисления</h3>
        <table style={{ marginBottom: 20 }}>
          <thead>
            <tr>
              <th>Дата</th>
              <th>Описание</th>
              <th className="num">Ставка</th>
              <th className="num">Курс</th>
              <th className="num">Сумма (UZS)</th>
            </tr>
          </thead>
          <tbody>
            {(accrued?.breakdown ?? []).map((ln, i) => {
              const isFx = ln.rate_currency && ln.rate_currency !== 'UZS';
              return (
                <tr key={i}>
                  <td>{ln.date}</td>
                  <td>{ln.note}</td>
                  <td className="num">
                    {fmt(ln.rate_amount)} {ln.rate_currency}
                  </td>
                  <td className="num">
                    {isFx ? fmt(ln.exchange_rate) : '—'}
                  </td>
                  <td className="num">{fmt(ln.accrued)}</td>
                </tr>
              );
            })}
            <tr style={{ fontWeight: 600 }}>
              <td colSpan={4}>Итого начислено</td>
              <td className="num">{fmt(accrued?.accrued_uzs)}</td>
            </tr>
          </tbody>
        </table>

        {periodAdj.length > 0 && (
          <>
            <h3 style={{ fontSize: 14, marginBottom: 8 }}>Корректировки</h3>
            <table style={{ marginBottom: 20 }}>
              <thead>
                <tr><th>Дата</th><th>Тип</th><th>Причина</th><th className="num">Сумма</th></tr>
              </thead>
              <tbody>
                {periodAdj.map((a) => {
                  const positive = a.kind === 'bonus' || a.kind === 'correction_plus';
                  const sign = positive ? '+' : '−';
                  return (
                    <tr key={a.id}>
                      <td>{a.effective_date}</td>
                      <td>{ADJ_LABEL[a.kind] ?? a.kind}</td>
                      <td>{a.reason || '—'}</td>
                      <td className="num">{sign}{fmt(a.amount_uzs)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </>
        )}

        <h3 style={{ fontSize: 14, marginBottom: 8 }}>Выплаты</h3>
        <table style={{ marginBottom: 20 }}>
          <thead>
            <tr><th>Документ</th><th>Тип</th><th>Период</th><th className="num">Сумма</th></tr>
          </thead>
          <tbody>
            {periodPayouts.length === 0 && (
              <tr><td colSpan={4} style={{ color: '#888' }}>Выплат за период не было.</td></tr>
            )}
            {periodPayouts.map((p) => (
              <tr key={p.id}>
                <td>{p.payment_doc_number || '—'}</td>
                <td>{PAYOUT_LABEL[p.type] ?? p.type}</td>
                <td>{p.period_from} — {p.period_to}</td>
                <td className="num">{fmt(p.amount_uzs)}</td>
              </tr>
            ))}
          </tbody>
        </table>

        <div style={{ marginTop: 32, padding: 16, background: '#f7f7f7', borderRadius: 4 }}>
          <div style={{ fontSize: 11, color: '#666', marginBottom: 4 }}>Баланс на {toDate}</div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
            <span>Начислено всего:</span><strong>{fmt(balance?.accrued_total)} сум</strong>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
            <span>Выплачено:</span><strong>{fmt(balance?.paid_total)} сум</strong>
          </div>
          {balance && Number(balance.adjustments_plus) > 0 && (
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4, color: '#16a34a' }}>
              <span>Доначислено:</span><strong>+{fmt(balance.adjustments_plus)} сум</strong>
            </div>
          )}
          {balance && Number(balance.adjustments_minus) > 0 && (
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4, color: '#dc2626' }}>
              <span>Удержано:</span><strong>−{fmt(balance.adjustments_minus)} сум</strong>
            </div>
          )}
          <div style={{ display: 'flex', justifyContent: 'space-between', borderTop: '1px solid #ddd', paddingTop: 8, marginTop: 8, fontSize: 14 }}>
            <span>К выплате:</span>
            <strong>{fmt(balance?.balance_uzs)} сум</strong>
          </div>
        </div>

        <div style={{ marginTop: 60, fontSize: 11, color: '#888', textAlign: 'center' }}>
          Документ сгенерирован автоматически
        </div>
      </div>
    </>
  );
}
