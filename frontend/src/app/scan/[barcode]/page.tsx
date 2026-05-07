'use client';

import { use, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';

import {
  PublicApiError,
  fetchPublicLot,
  fetchSellerCustomers,
  getSellerLabel,
  getSellerToken,
  submitSellerSale,
  type SellerCustomer,
} from '@/lib/sellerApi';
import type { ScanResult, VetStockBatchPublic } from '@/types/auth';


function fmtMoney(uzs: string | number | null | undefined): string {
  if (uzs == null || uzs === '') return '—';
  const n = typeof uzs === 'string' ? parseFloat(uzs) : uzs;
  if (!Number.isFinite(n)) return '—';
  return n.toLocaleString('ru-RU', { maximumFractionDigits: 0 }) + ' сум';
}

function statusColor(s: string | undefined): string {
  switch (s) {
    case 'available':
    case 'active':       return '#10B981';
    case 'expiring_soon': return '#F59E0B';
    case 'expired': return '#EF4444';
    case 'recalled': return '#EF4444';
    case 'depleted': return '#6B7280';
    case 'quarantine': return '#3B82F6';
    default: return '#6B7280';
  }
}

// Объединяем статусы vet-партии (`available|quarantine|expiring_soon|
// expired|depleted|recalled`) и feed-партии мешков (`active|depleted|
// recalled`). Лукап безопасный — fallback на сам код, чтобы /scan не
// крашился если бэкенд добавит новый статус.
const STATUS_LABEL: Record<string, string> = {
  available: 'Доступно для продажи',
  active: 'Доступно для продажи',
  quarantine: 'На карантине',
  expiring_soon: 'Скоро истекает',
  expired: 'Срок истёк',
  depleted: 'Закончился',
  recalled: 'Отозван',
};

function statusLabel(s: string | undefined): string {
  if (!s) return '—';
  return STATUS_LABEL[s] ?? s;
}


export default function ScanBarcodePage({
  params,
}: {
  params: Promise<{ barcode: string }>;
}) {
  const { barcode } = use(params);
  const router = useRouter();
  const [item, setItem] = useState<ScanResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [hasToken, setHasToken] = useState(false);
  const [sellerLabel, setSellerLabel] = useState('');

  const [qty, setQty] = useState('1');
  const [priceOverride, setPriceOverride] = useState('');
  const [customerId, setCustomerId] = useState('');
  const [customers, setCustomers] = useState<SellerCustomer[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState<
    { doc: string; total: string; customer: string } | null
  >(null);

  useEffect(() => {
    const tok = getSellerToken();
    setHasToken(Boolean(tok));
    setSellerLabel(getSellerLabel());
    setLoading(true);
    fetchPublicLot(barcode)
      .then((data) => {
        setItem(data);
        if (data) {
          // Цены по дефолту: accessory → sale_price, vet drug → price_per_unit,
          // feed bag → suggested_price_uzs (себестоимость × 1.30, приходит
          // только для авторизованного продавца). Если суггешн не пришёл
          // — оставляем пусто, продавец вводит сам.
          const defaultPrice =
            data.source_kind === 'accessory' ? data.sale_price_uzs
            : data.source_kind === 'drug_lot' ? data.price_per_unit_uzs
            : data.source_kind === 'feed_bag_lot' ? (data.suggested_price_uzs ?? '')
            : '';
          setPriceOverride(defaultPrice ? String(defaultPrice) : '');
        }
        setLoading(false);
      })
      .catch((e) => {
        setError(e instanceof Error ? e.message : 'Ошибка загрузки');
        setLoading(false);
      });
    if (tok) {
      fetchSellerCustomers(tok)
        .then((list) => setCustomers(list))
        .catch(() => setCustomers([]));
    }
  }, [barcode]);

  const handleSell = async () => {
    const tok = getSellerToken();
    if (!tok) {
      router.push('/scan/login');
      return;
    }
    const qNum = parseFloat(qty);
    if (!qNum || qNum <= 0) {
      alert('Укажите количество > 0');
      return;
    }
    const trimmedPrice = priceOverride.trim();
    if (trimmedPrice !== '') {
      const pNum = parseFloat(trimmedPrice);
      if (!Number.isFinite(pNum) || pNum <= 0) {
        alert('Цена должна быть > 0');
        return;
      }
    }
    setSubmitting(true);
    try {
      const result = await submitSellerSale(tok, {
        barcode,
        quantity: qty,
        ...(trimmedPrice !== '' ? { unit_price_uzs: trimmedPrice } : {}),
        ...(customerId ? { customer_id: customerId } : {}),
      });
      setSuccess({
        doc: result.sale_order_doc,
        total: result.total_uzs,
        customer: result.customer_name,
      });
      const updated = await fetchPublicLot(barcode);
      setItem(updated);
      if (updated) {
        const defaultPrice = updated.source_kind === 'accessory'
          ? updated.sale_price_uzs
          : updated.source_kind === 'drug_lot'
          ? updated.price_per_unit_uzs
          : updated.source_kind === 'feed_bag_lot'
          ? (updated.suggested_price_uzs ?? '')
          : '';
        setPriceOverride(defaultPrice ? String(defaultPrice) : '');
      }
      setCustomerId('');
    } catch (e) {
      const msg = e instanceof PublicApiError ? e.message : 'Ошибка продажи';
      alert(msg);
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div style={{ padding: 40, textAlign: 'center', fontSize: 16 }}>
        Загрузка…
      </div>
    );
  }

  if (error || !item) {
    return (
      <div style={{
        minHeight: '100vh', padding: 20,
        background: '#FEF2F2',
        display: 'flex', flexDirection: 'column', alignItems: 'center',
        justifyContent: 'center',
      }}>
        <div style={{
          maxWidth: 420, width: '100%',
          background: '#fff', borderRadius: 12,
          border: '1px solid #FCA5A5', padding: 24,
        }}>
          <h2 style={{ margin: 0, color: '#EF4444' }}>Товар не найден</h2>
          <p style={{ fontSize: 13, color: '#6B7280', marginTop: 8 }}>
            Штрих-код <code>{barcode}</code> не зарегистрирован в системе.
          </p>
          <a href="/scan" style={{
            display: 'inline-block', marginTop: 16,
            color: '#E8751A', textDecoration: 'underline', fontSize: 14,
          }}>
            ← Назад к сканеру
          </a>
        </div>
      </div>
    );
  }

  const isAccessory = item.source_kind === 'accessory';
  const isFeedBag = item.source_kind === 'feed_bag_lot';

  const title = isAccessory
    ? (item.nomenclature_name ?? '—')
    : (item.drug_name ?? '—');
  const subtitleSku = isAccessory
    ? item.nomenclature_sku
    : isFeedBag
    ? item.doc_number
    : item.drug_sku;
  // unitPrice — то, что пишем в карточке «ЦЕНА ЗА ЕД.» (отпускная).
  // Для feed используем suggested_price_uzs (себестоимость × 1.30) —
  // приходит только для авторизованного продавца через Bearer.
  const unitPrice = isAccessory
    ? item.sale_price_uzs
    : isFeedBag
    ? (item.suggested_price_uzs ?? null)
    : item.price_per_unit_uzs;

  const canSell = (() => {
    if (parseFloat(item.current_quantity) <= 0) return false;
    if (!hasToken) return false;
    if (isAccessory) return item.is_active;
    if (isFeedBag) return item.status === 'active';
    const sellableStatus = item.status === 'available' || item.status === 'expiring_soon';
    return sellableStatus && !item.is_expired;
  })();

  return (
    <div style={{
      minHeight: '100vh', padding: 16,
      background: '#FFF7ED',
    }}>
      <div style={{
        maxWidth: 520, margin: '0 auto',
        background: '#fff', borderRadius: 12,
        border: '1px solid #E5E7EB',
        padding: 20,
      }}>
        <div style={{
          display: 'inline-block',
          padding: '4px 12px',
          borderRadius: 20,
          background: isAccessory
            ? (item.is_active ? '#10B981' : '#6B7280')
            : statusColor(item.status),
          color: '#fff',
          fontSize: 12, fontWeight: 600,
          marginBottom: 12,
        }}>
          {isAccessory
            ? (item.is_active ? 'Аксессуар · в продаже' : 'Аксессуар · отключён')
            : isFeedBag
            ? `Корм · ${statusLabel(item.status)}`
            : statusLabel(item.status)}
        </div>

        <h1 style={{ margin: 0, fontSize: 22, color: '#111827' }}>
          {title}
        </h1>
        <div style={{ fontSize: 13, color: '#6B7280', marginTop: 4 }}>
          <strong className="mono">{subtitleSku ?? '—'}</strong>
          {item.source_kind === 'drug_lot' && item.drug_type_display && <> · {item.drug_type_display}</>}
        </div>

        <div style={{
          marginTop: 20,
          display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12,
        }}>
          <div style={{
            padding: 12, background: '#F9FAFB',
            borderRadius: 8, border: '1px solid #E5E7EB',
          }}>
            <div style={{ fontSize: 11, color: '#6B7280', textTransform: 'uppercase' }}>
              Остаток
            </div>
            <div style={{ fontSize: 24, fontWeight: 700, fontFamily: 'monospace' }}>
              {parseFloat(item.current_quantity).toLocaleString('ru-RU')}
              <span style={{ fontSize: 14, color: '#6B7280', marginLeft: 4 }}>
                {item.unit_code ?? ''}
              </span>
            </div>
          </div>
          <div style={{
            padding: 12, background: '#F9FAFB',
            borderRadius: 8, border: '1px solid #E5E7EB',
          }}>
            <div style={{ fontSize: 11, color: '#6B7280', textTransform: 'uppercase' }}>
              Цена за ед.
            </div>
            <div style={{ fontSize: 18, fontWeight: 700, fontFamily: 'monospace' }}>
              {fmtMoney(unitPrice)}
            </div>
          </div>
        </div>

        {item.source_kind === 'drug_lot' && (
          <div style={{ marginTop: 16, fontSize: 13 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0' }}>
              <span style={{ color: '#6B7280' }}>Lot №</span>
              <span className="mono">{item.lot_number}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0' }}>
              <span style={{ color: '#6B7280' }}>Годен до</span>
              <span style={{
                color: item.is_expired
                  ? '#EF4444'
                  : item.is_expiring_soon
                  ? '#F59E0B'
                  : '#111827',
                fontWeight: item.is_expired || item.is_expiring_soon ? 600 : 400,
              }}>
                {item.expiration_date}
                {item.days_to_expiry !== null && (
                  <span style={{ fontSize: 11, marginLeft: 6 }}>
                    ({item.days_to_expiry < 0
                      ? `истёк ${Math.abs(item.days_to_expiry)} дн назад`
                      : `${item.days_to_expiry} дн`})
                  </span>
                )}
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0' }}>
              <span style={{ color: '#6B7280' }}>Штрих-код</span>
              <span className="mono" style={{ fontSize: 11 }}>{item.barcode}</span>
            </div>
          </div>
        )}

        {isFeedBag && (
          <>
            {/* Финансовый блок: видим только продавцу (cost приходит с Bearer).
                Без token блок просто не отрисовывается — анон видит остаток
                и характеристики, но не маржу. */}
            {item.unit_cost_uzs !== undefined && (
              <div style={{
                marginTop: 14,
                padding: 12,
                background: '#F0FDF4',
                border: '1px solid #86EFAC',
                borderRadius: 8,
              }}>
                <div style={{
                  fontSize: 11, fontWeight: 700, color: '#14532D',
                  textTransform: 'uppercase', letterSpacing: '.04em',
                  marginBottom: 8,
                }}>
                  💰 Себестоимость и маржа
                </div>
                <div style={{
                  display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8,
                  fontSize: 12,
                }}>
                  <div>
                    <div style={{ color: '#6B7280', fontSize: 10 }}>Себест. 1 мешок</div>
                    <div className="mono" style={{ fontWeight: 600, color: '#111827' }}>
                      {fmtMoney(item.unit_cost_uzs)}
                    </div>
                  </div>
                  <div>
                    <div style={{ color: '#6B7280', fontSize: 10 }}>Себест. 1 кг</div>
                    <div className="mono" style={{ fontWeight: 600, color: '#111827' }}>
                      {fmtMoney(
                        parseFloat(item.unit_cost_uzs) /
                        Math.max(parseFloat(item.bag_weight_kg), 0.0001),
                      )}
                    </div>
                  </div>
                  {item.suggested_price_uzs && (
                    <>
                      <div>
                        <div style={{ color: '#6B7280', fontSize: 10 }}>Реком. цена (×1.30)</div>
                        <div className="mono" style={{ fontWeight: 700, color: '#15803D' }}>
                          {fmtMoney(item.suggested_price_uzs)}
                        </div>
                      </div>
                      <div>
                        <div style={{ color: '#6B7280', fontSize: 10 }}>Маржа на мешок</div>
                        <div className="mono" style={{ fontWeight: 700, color: '#15803D' }}>
                          +{fmtMoney(
                            parseFloat(item.suggested_price_uzs) -
                            parseFloat(item.unit_cost_uzs)
                          )}
                        </div>
                      </div>
                    </>
                  )}
                </div>
                {priceOverride && parseFloat(priceOverride) > 0 && parseFloat(priceOverride) < parseFloat(item.unit_cost_uzs) && (
                  <div style={{
                    marginTop: 8, fontSize: 11, color: '#B91C1C',
                    fontWeight: 600,
                  }}>
                    ⚠ Цена ниже себестоимости — будет убыток!
                  </div>
                )}
              </div>
            )}

            <div style={{ marginTop: 16, fontSize: 13 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0' }}>
                <span style={{ color: '#6B7280' }}>Партия</span>
                <span className="mono">{item.lot_number}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0' }}>
                <span style={{ color: '#6B7280' }}>Вес мешка</span>
                <span className="mono">
                  {parseFloat(item.bag_weight_kg).toLocaleString('ru-RU')} кг
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0' }}>
                <span style={{ color: '#6B7280' }}>Остаток</span>
                <span className="mono">
                  {item.bags_remaining}/{item.bags_initial} шт
                  {item.total_remaining_kg && (
                    <span style={{ color: '#6B7280', marginLeft: 6, fontSize: 11 }}>
                      ≈ {parseFloat(item.total_remaining_kg).toLocaleString('ru-RU', {
                        maximumFractionDigits: 0,
                      })} кг
                    </span>
                  )}
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0' }}>
                <span style={{ color: '#6B7280' }}>Расфасовано</span>
                <span className="mono" style={{ fontSize: 12 }}>
                  {new Date(item.packaged_at).toLocaleDateString('ru-RU', {
                    day: 'numeric', month: 'long', year: 'numeric',
                  })}
                </span>
              </div>
              {item.warehouse_code && (
                <div style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0' }}>
                  <span style={{ color: '#6B7280' }}>Склад</span>
                  <span className="mono">{item.warehouse_code}</span>
                </div>
              )}
              {item.is_medicated && (
                <div style={{
                  marginTop: 6, padding: '8px 10px',
                  background: '#FFFBEB',
                  border: '1px solid #F59E0B',
                  borderRadius: 6,
                  fontSize: 12, color: '#92400E',
                }}>
                  ⚠ <b>Медикаментозный корм.</b> Каренция до{' '}
                  <b>{item.withdrawal_period_ends ?? `${item.withdrawal_period_days} дн`}</b>
                  {' '}— до этого срока птицу с него на убой нельзя.
                </div>
              )}
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0' }}>
                <span style={{ color: '#6B7280' }}>Штрих-код</span>
                <span className="mono" style={{ fontSize: 11 }}>{item.barcode}</span>
              </div>
            </div>
          </>
        )}

        {isAccessory && (
          <div style={{ marginTop: 16, fontSize: 13 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0' }}>
              <span style={{ color: '#6B7280' }}>Штрих-код</span>
              <span className="mono" style={{ fontSize: 11 }}>{item.barcode}</span>
            </div>
          </div>
        )}

        {canSell && !success && (
          <div style={{
            marginTop: 24, padding: 16,
            background: '#FFF7ED', borderRadius: 8,
            border: '1px solid #E8751A',
          }}>
            <div style={{ fontSize: 13, color: '#374151', marginBottom: 8 }}>
              Продать <span style={{ fontSize: 11, color: '#6B7280' }}>(в продажу со склада)</span>
            </div>

            {customers.length > 0 && (
              <div style={{ marginBottom: 10 }}>
                <label style={{
                  display: 'block', fontSize: 11, color: '#6B7280',
                  textTransform: 'uppercase', marginBottom: 4,
                }}>
                  Клиент <span style={{ textTransform: 'none' }}>(опционально)</span>
                </label>
                <select
                  value={customerId}
                  onChange={(e) => setCustomerId(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '10px 12px',
                    fontSize: 14,
                    border: '1px solid #D1D5DB', borderRadius: 6,
                    background: '#fff',
                  }}
                >
                  <option value="">— Розничный покупатель (по умолчанию) —</option>
                  {customers.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}{c.code ? ` · ${c.code}` : ''}
                    </option>
                  ))}
                </select>
              </div>
            )}

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
              <div>
                <label style={{
                  display: 'block', fontSize: 11, color: '#6B7280',
                  textTransform: 'uppercase', marginBottom: 4,
                }}>
                  Кол-во
                </label>
                <input
                  type="number"
                  step="0.001"
                  min="0"
                  value={qty}
                  onChange={(e) => setQty(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '12px 14px',
                    fontSize: 18, fontFamily: 'monospace',
                    border: '1px solid #D1D5DB', borderRadius: 6,
                  }}
                />
              </div>
              <div>
                <label style={{
                  display: 'block', fontSize: 11, color: '#6B7280',
                  textTransform: 'uppercase', marginBottom: 4,
                }}>
                  Цена за ед.
                </label>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={priceOverride}
                  onChange={(e) => setPriceOverride(e.target.value)}
                  placeholder={unitPrice ? String(unitPrice) : '0'}
                  style={{
                    width: '100%',
                    padding: '12px 14px',
                    fontSize: 18, fontFamily: 'monospace',
                    border: '1px solid #D1D5DB', borderRadius: 6,
                  }}
                />
              </div>
            </div>
            <button
              onClick={handleSell}
              disabled={submitting}
              style={{
                marginTop: 10,
                width: '100%',
                padding: '12px 20px',
                background: '#E8751A', color: '#fff',
                border: 'none', borderRadius: 6,
                fontSize: 15, fontWeight: 600,
                cursor: submitting ? 'wait' : 'pointer',
                opacity: submitting ? 0.6 : 1,
              }}
            >
              {submitting ? '...' : 'Продать'}
            </button>
            <div style={{
              fontSize: 12, color: '#6B7280', marginTop: 8,
              display: 'flex', justifyContent: 'space-between', alignItems: 'baseline',
            }}>
              <span>
                Сумма: <strong style={{ color: '#111827', fontSize: 14 }}>
                  {fmtMoney(
                    parseFloat(qty || '0') *
                    parseFloat(priceOverride || String(unitPrice || '0') || '0'),
                  )}
                </strong>
              </span>
              {priceOverride && unitPrice && parseFloat(priceOverride) !== parseFloat(String(unitPrice)) && (
                <span style={{ color: '#92400E' }}>
                  ≠ базовой ({fmtMoney(unitPrice)})
                </span>
              )}
            </div>
            {item.source_kind === 'drug_lot' && item.status === 'expiring_soon' && (
              <div style={{
                marginTop: 10, padding: '8px 10px',
                background: '#FFFBEB', borderRadius: 6,
                border: '1px solid #F59E0B',
                fontSize: 12, color: '#92400E',
              }}>
                ⚠ Скоро истекает{item.days_to_expiry !== null && (
                  <> — осталось <b>{item.days_to_expiry} дн</b></>
                )}. Продавайте в первую очередь.
              </div>
            )}
          </div>
        )}

        {!hasToken && (
          <div style={{
            marginTop: 20, padding: 14,
            background: '#EFF6FF', borderRadius: 8,
            border: '1px solid #3B82F6',
            fontSize: 13, color: '#1E40AF',
          }}>
            Чтобы продавать — войдите как продавец.{' '}
            <a href="/scan/login" style={{ color: '#1E40AF', fontWeight: 600 }}>
              Ввести токен →
            </a>
          </div>
        )}

        {!canSell && hasToken && !isAccessory && (
          (isFeedBag && item.status !== 'active') ||
          (!isFeedBag && item.status !== 'available')
        ) && (
          <div style={{
            marginTop: 20, padding: 14,
            background: '#FEF2F2', borderRadius: 8,
            border: '1px solid #EF4444',
            fontSize: 13, color: '#991B1B',
          }}>
            Продажа невозможна: {statusLabel(item.status).toLowerCase()}.
          </div>
        )}

        {!canSell && hasToken && isAccessory && (
          <div style={{
            marginTop: 20, padding: 14,
            background: '#FEF2F2', borderRadius: 8,
            border: '1px solid #EF4444',
            fontSize: 13, color: '#991B1B',
          }}>
            Продажа невозможна: {!item.is_active ? 'товар отключён' : 'нулевой остаток'}.
          </div>
        )}

        {success && (
          <div style={{
            marginTop: 20, padding: 16,
            background: '#ECFDF5', borderRadius: 8,
            border: '2px solid #10B981',
            textAlign: 'center',
          }}>
            <div style={{ fontSize: 32 }}>✓</div>
            <div style={{ fontSize: 16, fontWeight: 700, color: '#065F46' }}>
              Продажа оформлена
            </div>
            <div style={{ fontSize: 13, color: '#374151', marginTop: 4 }}>
              Документ: <strong className="mono">{success.doc}</strong>
              <br />
              Клиент: <strong>{success.customer}</strong>
              <br />
              Сумма: <strong>{fmtMoney(success.total)}</strong>
            </div>
            <button
              onClick={() => setSuccess(null)}
              style={{
                marginTop: 12,
                padding: '8px 16px',
                background: '#10B981', color: '#fff',
                border: 'none', borderRadius: 6,
                fontSize: 13, fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              Продолжить
            </button>
          </div>
        )}

        <div style={{ marginTop: 24, textAlign: 'center', fontSize: 12, color: '#6B7280' }}>
          {sellerLabel && <>{sellerLabel} · </>}
          <a href="/scan" style={{ color: '#E8751A' }}>← Сканировать другой</a>
        </div>
      </div>
    </div>
  );
}
