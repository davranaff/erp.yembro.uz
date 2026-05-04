/**
 * Public API клиент для розничного сканера ветпрепаратов.
 *
 * Не использует общий `apiFetch` — он навешивает session-токены и
 * X-Organization-Code, которых на public-странице нет. Здесь свой fetch
 * с поддержкой Bearer-токена продавца (в localStorage).
 */
import type { ScanResult } from '@/types/auth';


const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

const SELLER_TOKEN_KEY = 'vet_seller_token';
const SELLER_LABEL_KEY = 'vet_seller_label';


export class PublicApiError extends Error {
  status: number;
  data: unknown;
  constructor(status: number, message: string, data?: unknown) {
    super(message);
    this.status = status;
    this.data = data;
  }
}


export function getSellerToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(SELLER_TOKEN_KEY);
}


export function setSellerToken(token: string, label: string = '') {
  if (typeof window === 'undefined') return;
  localStorage.setItem(SELLER_TOKEN_KEY, token);
  if (label) localStorage.setItem(SELLER_LABEL_KEY, label);
}


export function getSellerLabel(): string {
  if (typeof window === 'undefined') return '';
  return localStorage.getItem(SELLER_LABEL_KEY) ?? '';
}


export function clearSellerToken() {
  if (typeof window === 'undefined') return;
  localStorage.removeItem(SELLER_TOKEN_KEY);
  localStorage.removeItem(SELLER_LABEL_KEY);
}


/**
 * Анонимно: данные лота/аксессуара по barcode (read-only).
 * Backend ищет в обоих местах и отдаёт discriminated union с `source_kind`.
 */
export async function fetchPublicLot(
  barcode: string,
): Promise<ScanResult | null> {
  const res = await fetch(
    `${API_URL}/api/vet/public/scan/${encodeURIComponent(barcode)}/`,
    { method: 'GET' },
  );
  if (res.status === 404) return null;
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new PublicApiError(res.status, `HTTP ${res.status}`, data);
  }
  return await res.json();
}


export interface SellerSaleResponse {
  sale_order_id: string;
  sale_order_doc: string;
  total_uzs: string;
  remaining_qty: string;
  lot_status: string;
  customer_id: string;
  customer_name: string;
}

/** Bearer: создание продажи через токен продавца. */
export async function submitSellerSale(
  token: string,
  body: {
    barcode: string;
    quantity: string;
    unit_price_uzs?: string;
    /** Опциональный id Counterparty. Если не задан — backend закрепит на «Розничный покупатель». */
    customer_id?: string;
  },
): Promise<SellerSaleResponse> {
  const res = await fetch(`${API_URL}/api/vet/public/sell/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    const detail =
      typeof data === 'object' && data && 'detail' in data
        ? String((data as { detail: unknown }).detail)
        : `HTTP ${res.status}`;
    throw new PublicApiError(res.status, detail, data);
  }
  return await res.json();
}


export interface SellerCustomer {
  id: string;
  code: string;
  name: string;
  kind: 'buyer' | 'other';
}

/** Bearer: список покупателей орги (для select на форме продажи). */
export async function fetchSellerCustomers(
  token: string,
): Promise<SellerCustomer[]> {
  const res = await fetch(`${API_URL}/api/vet/public/customers/`, {
    method: 'GET',
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    if (res.status === 401 || res.status === 403) return [];
    throw new PublicApiError(res.status, `HTTP ${res.status}`);
  }
  return await res.json();
}
