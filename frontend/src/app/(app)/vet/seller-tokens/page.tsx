'use client';

import SellerTokensPanel from '@/components/SellerTokensPanel';

/**
 * Единая страница токенов продавцов. SellerDeviceToken org-scoped и
 * работает для vet+feed одновременно — поэтому одна страница на всё.
 *
 * URL остался под /vet по историческим причинам (бэкенд токенов живёт
 * в apps/vet). Меню-пункт ведёт сюда независимо от того, какой модуль
 * у пользователя в основе.
 */
export default function SellerTokensPage() {
  return <SellerTokensPanel />;
}
