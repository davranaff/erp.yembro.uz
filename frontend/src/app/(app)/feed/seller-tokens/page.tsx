'use client';

import SellerTokensPanel from '@/components/SellerTokensPanel';

/**
 * Токены продавцов корма. Один и тот же org-scoped Bearer-токен работает
 * для vet+feed (см. SellerDeviceToken — нет per-module ограничений), но
 * UI-страница дублируется в каждом модуле, чтобы head'у feed не нужно
 * было идти в /vet/seller-tokens.
 */
export default function FeedSellerTokensPage() {
  return (
    <SellerTokensPanel
      permissionModule="feed"
      title="Токены продавцов корма"
      subtitle={
        <>
          Bearer-токены для розничной продажи мешков комбикорма через{' '}
          <code style={{ fontSize: 12 }}>/scan/&lt;barcode&gt;</code>. Один токен
          работает для vet- и feed-товаров.
        </>
      }
    />
  );
}
