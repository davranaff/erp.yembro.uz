'use client';

import { makeCrud } from '@/lib/crudFactory';
import type { ExpenseArticle } from '@/types/auth';

/**
 * Тело POST/PATCH для статьи расходов/доходов.
 */
export interface ExpenseArticleInput {
  code: string;
  name: string;
  kind: 'expense' | 'income' | 'salary' | 'transfer';
  default_subaccount?: string | null;
  default_module?: string | null;
  parent?: string | null;
  is_active?: boolean;
  notes?: string;
}

export const expenseArticlesCrud = makeCrud<
  ExpenseArticle,
  ExpenseArticleInput,
  Partial<ExpenseArticleInput>
>({
  key: ['accounting', 'expense-articles'],
  path: '/api/accounting/expense-articles/',
  ordering: 'code',
});
