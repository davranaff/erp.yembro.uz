import { redirect } from 'next/navigation';

/**
 * `/finance` — служебный родительский маршрут. Реальные страницы находятся в
 * `/finance/cashbox` и `/finance/rates`. Если кто-то открыл голый `/finance`
 * (например через старую закладку или ⌘K), редиректим на самый часто
 * используемый — кассу.
 */
export default function FinanceIndex() {
  redirect('/finance/cashbox');
}
