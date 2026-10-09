import { ref } from 'vue';

/**
 * Resol els tokens de ConfigProject que calen per saber quin dels documents que
 * pengen d'una sol·licitud (pressupost, factura, abonament, anul·lada...) és la
 * factura vigent, i exposa els helpers que la trien.
 *
 * Els abonaments hereten el `type` de la factura original (`return_invoice()` al
 * backend), de manera que filtrar només per tipus factura no els descarta. Tampoc
 * n'hi ha prou amb comparar contra `invoice_status_cancelled_token` (-6, Abonada):
 * anul·lar una factura sense moviments de cobrament li estampa
 * `invoice_status_dropped_token` (-7, Anul·lada).
 */
export function useFinalInvoiceTokens() {
  const invoiceTypeToken = ref(null);
  const cancelStatusToken = ref(null);
  const droppedStatusToken = ref(null);
  const payoffStatusToken = ref(null);
  const paidStatusToken = ref(null);

  const fetchFinalInvoiceTokens = async () => {
    const { $ConfigProjectApiService } = useNuxtApp();
    // Un token no configurat en un client no ha de tombar la resta.
    const fetchInto = async (target, token) => {
      try {
        target.value = await $ConfigProjectApiService.get(token);
      } catch (err) {
        console.error(err);
        target.value = null;
      }
    };
    await Promise.all([
      fetchInto(invoiceTypeToken, 'invoice_type_invoice_token'),
      fetchInto(cancelStatusToken, 'invoice_status_cancelled_token'),
      fetchInto(droppedStatusToken, 'invoice_status_dropped_token'),
      fetchInto(payoffStatusToken, 'invoice_status_payoff_token'),
      fetchInto(paidStatusToken, 'invoice_status_paid_token'),
    ]);
  };

  const normalize = (value) => (value === null || value === undefined ? null : String(value));

  const getTypeToken = (invoice) =>
    normalize(invoice?.type_token ?? invoice?.type?.token ?? invoice?.type_final ?? null);

  const getStatusToken = (invoice) =>
    normalize(invoice?.status_token ?? invoice?.status?.token ?? invoice?.status_final ?? null);

  const isInvoice = (invoice) => getTypeToken(invoice) === normalize(invoiceTypeToken.value);

  /** Anul·lada, abonada o abonament: no pot ser la factura vigent de la sol·licitud. */
  const isVoidedInvoice = (invoice) => {
    const statusToken = getStatusToken(invoice);
    if (statusToken === null) return false;
    return [cancelStatusToken.value, droppedStatusToken.value, payoffStatusToken.value]
      .map(normalize)
      .filter(token => token !== null)
      .includes(statusToken);
  };

  const findFinalInvoice = (invoices) =>
    (invoices || []).find(invoice => isInvoice(invoice) && !isVoidedInvoice(invoice)) || null;

  return {
    invoiceTypeToken,
    cancelStatusToken,
    droppedStatusToken,
    payoffStatusToken,
    paidStatusToken,
    fetchFinalInvoiceTokens,
    getTypeToken,
    getStatusToken,
    isInvoice,
    isVoidedInvoice,
    findFinalInvoice,
  };
}
