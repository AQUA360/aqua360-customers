import { formatDate } from '~/utils/date';
import { paymentSummaryText } from '~/utils/invoice-payment-summary';

// Columnes de l'exportació XLSX dels llistats de factures (InvoiceMiniDetail i la pestanya de
// factures del contracte, que exporta des de la seva barra de botons).
export const hasPaymentSummary = (rows) => (rows || []).some((row) => row.payment_summary !== undefined);

export function buildInvoiceExportColumns(t, { isInfo = false, showPaymentSummary = false } = {}) {
  const cols = [
    {
      header: t('common.date'),
      value: (row) => row.issue_date ? formatDate(row.issue_date) : '',
      key: 'issue_date'
    },

    {
      header: t('invoice'),
      value: (row) => row.serie_final,
      key: 'serie'
    },

    {
      header: t('billing_block.payment'),
      value: (row) => row.paid_at ? formatDate(row.paid_at) : '',
      key: 'paid_at'
    },
  ];

  if (!isInfo) {

    cols.push({
      header: t('common.status'),
      value: (row) => row.status_name,
      key: 'status'
    });

    if (showPaymentSummary) {
      cols.push({
        header: t('billing_block.payment_status_column'),
        value: (row) => paymentSummaryText(t, row.payment_summary),
        key: 'payment_status'
      });
    }

    cols.push({
      header: t('contract_block.holder'),
      value: (row) => [
        row.customer_final,
        row.customer_token_final
      ].filter(Boolean).join(' ')
    });

  } else {

    cols.push({
      header: t('common.title'),
      value: (row) => row.title_final,
      key: 'number'
    });

  }

  cols.push({
    header: t('billing_block.total_to_pay'),
    value: (row) => Number(row.left_to_pay ?? 0),
    key: 'left_to_pay'
  });

  cols.push({
    header: t('common.total'),
    value: (row) => Number(row.total_final ?? 0),
    key: 'total_final'
  });

  return cols;
}
