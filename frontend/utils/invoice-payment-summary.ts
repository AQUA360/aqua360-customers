import { formatDate } from '~/utils/date';

type Translate = (key: string, values?: Record<string, unknown>) => string;

export interface InvoicePaymentSummary {
  payment_status: { name: string; color: string; token: string } | null;
  returned_at: string | null;
  returned_count: number;
}

// "Returned on dd/mm/yyyy" (or "Returned N times, last on ...") for the payment status column.
export const returnedLabel = (t: Translate, summary?: InvoicePaymentSummary | null): string => {
  if (!summary?.returned_count) return '';
  const date = summary.returned_at ? formatDate(summary.returned_at) : '-';
  return summary.returned_count > 1
    ? t('billing_block.returned_times_on', { count: summary.returned_count, date })
    : t('billing_block.returned_on', { date });
};

// Plain text of the column, for the XLSX exports.
export const paymentSummaryText = (t: Translate, summary?: InvoicePaymentSummary | null): string =>
  [summary?.payment_status?.name, returnedLabel(t, summary)].filter(Boolean).join(' · ');
