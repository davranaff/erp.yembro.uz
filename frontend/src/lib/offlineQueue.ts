'use client';

/**
 * Offline-очередь мутаций через IndexedDB.
 *
 * Use case: оператор в курятнике без 4G/Wi-Fi заполняет daily-log на телефоне.
 * Если онлайн — POST уходит сразу через `apiFetch`. Если оффлайн — мутация
 * складывается в локальную IDB-очередь и пытается отправиться когда сеть вернётся
 * (`window.online` event + ручной `flush()`).
 *
 * Без зависимостей, нативный IndexedDB API. Один store `mutations` с записями:
 *   { id, path, method, body, createdAt, attempts, lastError }
 *
 * Использование:
 *   const ok = await enqueueOrSend({ path: '/api/feedlot/mortality/', body: {...} });
 *   // Если онлайн — отправит сразу, вернёт ответ.
 *   // Если оффлайн — положит в очередь, вернёт {queued: true}.
 */
import { ApiError, apiFetch, type ApiInit } from './api';


const DB_NAME = 'yembro-offline';
const DB_VERSION = 1;
const STORE = 'mutations';

export interface QueuedMutation {
  id?: number;
  path: string;
  method: 'POST' | 'PATCH' | 'PUT' | 'DELETE';
  body: unknown;
  createdAt: number;
  attempts: number;
  lastError?: string;
}

let _dbPromise: Promise<IDBDatabase> | null = null;

function openDb(): Promise<IDBDatabase> {
  if (typeof indexedDB === 'undefined') {
    return Promise.reject(new Error('IndexedDB is not available in this environment'));
  }
  if (_dbPromise) return _dbPromise;
  _dbPromise = new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE, { keyPath: 'id', autoIncrement: true });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
  return _dbPromise;
}

async function withStore<T>(
  mode: IDBTransactionMode,
  fn: (store: IDBObjectStore) => IDBRequest<T> | Promise<T>,
): Promise<T> {
  const db = await openDb();
  return new Promise<T>((resolve, reject) => {
    const tx = db.transaction(STORE, mode);
    const store = tx.objectStore(STORE);
    const result = fn(store);
    tx.oncomplete = () => {
      if (result instanceof IDBRequest) resolve(result.result as T);
      else Promise.resolve(result).then(resolve, reject);
    };
    tx.onerror = () => reject(tx.error);
    tx.onabort = () => reject(tx.error);
  });
}

export async function enqueue(m: Omit<QueuedMutation, 'id' | 'createdAt' | 'attempts'>): Promise<number> {
  const record: QueuedMutation = {
    ...m,
    createdAt: Date.now(),
    attempts: 0,
  };
  return withStore('readwrite', (store) => store.add(record) as IDBRequest<number>);
}

export async function listQueued(): Promise<QueuedMutation[]> {
  return withStore('readonly', (store) => store.getAll() as IDBRequest<QueuedMutation[]>);
}

export async function deleteQueued(id: number): Promise<void> {
  await withStore('readwrite', (store) => store.delete(id) as IDBRequest<undefined>);
}

export async function updateQueued(m: QueuedMutation): Promise<void> {
  await withStore('readwrite', (store) => store.put(m) as IDBRequest<IDBValidKey>);
}

/**
 * Главный API: попытаться отправить сейчас. Если оффлайн или сетевая ошибка —
 * положить в очередь. Возвращает либо успешный ответ, либо `{queued: true}`.
 */
export async function enqueueOrSend<T = unknown>(opts: {
  path: string;
  body?: unknown;
  method?: 'POST' | 'PATCH' | 'PUT' | 'DELETE';
}): Promise<T | { queued: true; id: number }> {
  const method = opts.method ?? 'POST';

  if (typeof navigator !== 'undefined' && !navigator.onLine) {
    const id = await enqueue({ path: opts.path, method, body: opts.body });
    return { queued: true, id };
  }

  try {
    const result = await apiFetch<T>(opts.path, {
      method,
      body: opts.body as ApiInit['body'],
    });
    return result;
  } catch (e) {
    const err = e as ApiError;
    // 4xx-ошибки — это бизнес-валидация, не сеть. Пробрасываем дальше, очередь не нужна.
    if (err.status >= 400 && err.status < 500) throw err;
    // Сетевая / 5xx — можно поставить в очередь
    const id = await enqueue({ path: opts.path, method, body: opts.body });
    return { queued: true, id };
  }
}

/**
 * Прогон очереди: пытается отправить все накопленные мутации.
 * Удачные — удаляет, неудачные — увеличивает `attempts`.
 *
 * Возвращает `{sent, failed, remaining}`.
 */
export async function flush(): Promise<{ sent: number; failed: number; remaining: number }> {
  if (typeof navigator !== 'undefined' && !navigator.onLine) {
    const all = await listQueued();
    return { sent: 0, failed: 0, remaining: all.length };
  }

  const queued = await listQueued();
  let sent = 0;
  let failed = 0;

  for (const m of queued) {
    if (!m.id) continue;
    try {
      await apiFetch(m.path, {
        method: m.method,
        body: m.body as ApiInit['body'],
      });
      await deleteQueued(m.id);
      sent++;
    } catch (e) {
      const err = e as ApiError;
      // Бизнес-ошибка → удаляем чтобы не зависала навсегда (юзер не сможет ничего исправить)
      if (err.status >= 400 && err.status < 500) {
        await deleteQueued(m.id);
        failed++;
        continue;
      }
      // Сетевая → увеличиваем attempts, оставляем на следующий цикл
      m.attempts = (m.attempts ?? 0) + 1;
      m.lastError = err.message?.slice(0, 200) ?? 'unknown';
      await updateQueued(m);
      failed++;
    }
  }

  const remaining = (await listQueued()).length;
  return { sent, failed, remaining };
}

/** Подключиться к window.online — автоматически прогонять очередь когда сеть появилась. */
export function attachAutoFlush(onResult?: (r: Awaited<ReturnType<typeof flush>>) => void): () => void {
  if (typeof window === 'undefined') return () => {};
  const handler = async () => {
    const r = await flush();
    onResult?.(r);
  };
  window.addEventListener('online', handler);
  return () => window.removeEventListener('online', handler);
}
