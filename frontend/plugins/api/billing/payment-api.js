// plugins/services/pricing/price-rate-api.js
export default defineNuxtPlugin(nuxtApp => {
  const entity = '/billing/payment/';
  const provideName = 'PaymentApiService';

  const { $apiManager } = useNuxtApp()
  const config = useRuntimeConfig();
  const apiHost = config.public.apiHost;

  const getAll = async (
    searchQuery = '', filters = [], page = 1,
    sort = null, desc = false, invoice_id = null,
    is_debit = null, is_pending = null, is_split = null,
    origin = [], start_date = null, end_date = null,
    is_excluded = null, pay_type = [], is_einvoice = false,
    commitment_deposit_id = null, remittance_id = null, total = null, return_reasons = [], pay_origin = []) => {
    let apiUrl = apiHost + entity + '?search=' + encodeURIComponent(searchQuery) + `&page=${page}`;

    let filtersValues = [];
    if (filters.length > 0) {
      filters.map(filter => {
        filtersValues.push(filter);
      })
    }

    if (filtersValues.length > 0) {
      apiUrl += `&status=${filtersValues.join(',')}`;
    }

    if (sort) {
      apiUrl += `&ordering=${desc ? '-' : ''}${sort}`;
    }

    if (invoice_id) {
      apiUrl += `&invoice=${invoice_id}`;
    }

    if (is_debit) {
      apiUrl += `&is_debit=${is_debit}`;
    }

    if (is_einvoice) {
      apiUrl += `&is_einvoice=${is_einvoice}`;
    }

    if (is_pending) {
      apiUrl += `&is_pending=${is_pending}`;
    }

    if (start_date) {
      apiUrl += `&start_date=${start_date}`;
    }

    if (end_date) {
      apiUrl += `&end_date=${end_date}`;
    }
    if (pay_type.length > 0) {
      apiUrl += `&type=${pay_type.join(',')}`;
    }

    if (origin.length > 0) {
      apiUrl += `&origin=${origin.join(',')}`;
    }

    if (is_excluded != null) {
      apiUrl += `&is_excluded=${is_excluded}`;
    }

    if (commitment_deposit_id != null) {
      apiUrl += `&commitment_deposit=${commitment_deposit_id}`;
    }

    if (remittance_id != null) {
      apiUrl += `&remittance=${remittance_id}`;
    }

    if (total != null) {
      apiUrl += `&amount=${total}`;
    }

    if (return_reasons.length > 0) {
      apiUrl += `&return_reason=${return_reasons.join(',')}`;
    }
    
    if (pay_origin.length > 0) {
      apiUrl += `&payment_origin=${pay_origin.join(',')}`;
    }


    let exploitation_id = localStorage.getItem('exploitation');
    if (exploitation_id) {
      apiUrl += `&exploitation=${exploitation_id}`;
    }

    try {
      const response = await $apiManager.fetch(apiUrl, 'GET');
      if (response.results) {
        return response;
      } else {
        throw new Error('Error estructura `results` no trobat');
      }
    } catch (error) {
      throw error;
    }
  }

  // Server-side export (async). Mirrors getAll's filters/search/sort but POSTs
  // to `{entity}export/` so the backend builds the full, filter-aware XLSX as a
  // background task, returning `{ task_id }`. Same args as getAll (no page).
  const exportData = async (
    searchQuery = '', filters = [],
    sort = null, desc = false, invoice_id = null,
    is_debit = null, is_pending = null, is_split = null,
    origin = [], start_date = null, end_date = null,
    is_excluded = null, pay_type = [], is_einvoice = false,
    commitment_deposit_id = null, remittance_id = null, total = null,
    return_reasons = [], pay_origin = [], columns = []) => {
    const exploitation_id = localStorage.getItem('exploitation');
    const extraParams = {
      invoice: invoice_id,
      is_debit: is_debit || null,
      is_pending: is_pending || null,
      start_date,
      end_date,
      type: pay_type,
      origin,
      is_excluded,
      commitment_deposit: commitment_deposit_id,
      remittance: remittance_id,
      amount: total,
      return_reason: return_reasons,
      payment_origin: pay_origin,
      is_einvoice: is_einvoice || null,
      exploitation: exploitation_id || null,
    };
    return $apiManager.exportTable(entity, { searchQuery, filters, sort, desc, columns, extraParams });
  }

  const save = async (data) => {
    let apiUrl = `${apiHost}${entity}`;
    try {
      const method = data.id ? 'PUT' : 'POST';
      if (method == 'PUT') {
        apiUrl += data.id + '/';
      }
      const response = await $apiManager.fetch(apiUrl, method, data, { 'Content-Type': 'application/json' })
      if (response) {
        return response;
      } else {
        throw new Error('Error no trobat');
      }
    } catch (error) {
      throw error;
    }
  }


  const getDetail = async (id) => {
    const apiUrl = `${apiHost}${entity}${id}/`;

    try {
      const response = await $apiManager.fetch(apiUrl, 'GET');

      if (response) {
        return response;
      } else {
        throw new Error('Error estructura `results` no trobat');
      }
    } catch (error) {
      throw error;
    }
  }

  const getPaymentMovements = async (id) => {
    const apiUrl = `${apiHost}/billing/payment-movement/?payment=${id}`;

    try {
      const response = await $apiManager.fetch(apiUrl, 'GET');

      if (response) {
        return response;
      } else {
        throw new Error('Error estructura `results` no trobat');
      }
    } catch (error) {
      throw error;
    }
  }

  const getSEPADocData = async (payments) => {
    const apiUrl = apiHost + '/billing/sepa-document-generate/'
    try {
      const response = await $apiManager.fetch(apiUrl, 'PUT', payments, { 'Content-Type': 'application/json' });

      if (response) {
        return response;
      } else {
        return null;
      }
    } catch (error) {
      throw error;
    }
  }

  const getSEPAInvoices = async (filters, page = 1) => {
    const apiUrl = `${apiHost}/billing/sepa-document-generate/invoices/?page=${page}`;
    try {
      const response = await $apiManager.fetch(apiUrl, 'PUT', filters, { 'Content-Type': 'application/json' });

      if (response) {
        return response;
      } else {
        return null;
      }
    } catch (error) {
      throw error;
    }
  }

  const bulkExcludeSEPAInvoices = async (filters, is_excluded) => {
    const apiUrl = `${apiHost}/billing/sepa-document-generate/invoices/`;
    try {
      const payload = { ...filters, is_excluded };
      const response = await $apiManager.fetch(apiUrl, 'POST', payload, { 'Content-Type': 'application/json' });
      return response;
    } catch (error) {
      throw error;
    }
  }

  const getSEPAAnomalies = async (filters) => {
    const apiUrl = `${apiHost}/billing/sepa-document-generate/anomalies/`;
    try {
      const response = await $apiManager.fetch(apiUrl, 'PUT', filters, { 'Content-Type': 'application/json' });

      if (response) {
        return response;
      } else {
        return null;
      }
    } catch (error) {
      throw error;
    }
  }

  const getSEPAFiles = async (filters) => {
    const apiUrl = `${apiHost}/billing/sepa-document-generate/files/`;
    try {
      const response = await $apiManager.fetch(apiUrl, 'PUT', filters, { 'Content-Type': 'application/json' });

      if (response) {
        return response;
      } else {
        return null;
      }
    } catch (error) {
      throw error;
    }
  }

  const manageRejectionPayments = async (data) => {
    const apiUrl = apiHost + '/billing/payment/manage-rejection-payments/'
    try {

      let options;
      const formData = new FormData();
      formData.append('file', data.file);
      formData.append('return_payments', JSON.stringify(data.return_payments));
      formData.append('claim_payments', JSON.stringify(data.claim_payments));
      formData.append('payments_to_return', JSON.stringify(data.payments_to_return));
      formData.append('og_msg_id', data.og_msg_id);
      if (data.return_date) {
        formData.append('return_date', data.return_date);
      }
      options = formData;
      const response = await $apiManager.fetch(apiUrl, 'POST', options)
      if (response) {
        return response;
      } else {
        throw new Error('Error estructura `results` no trobat');
      }
    } catch (error) {
      throw error;
    }
  }

  const getEInvoiceDocData = async (payments) => {
    const apiUrl = apiHost + '/billing/einvoice-document-generate/'
    try {
      const response = await $apiManager.fetch(apiUrl, 'PUT', payments, { 'Content-Type': 'application/json' });

      if (response) {
        return response;
      } else {
        throw new Error('Error estructura `results` no trobat');
      }
    } catch (error) {
      throw error;
    }
  }

  const getEInvoices = async (filters) => {
    const apiUrl = apiHost + '/billing/einvoice-document-generate/'
    try {
      const response = await $apiManager.fetch(apiUrl, 'POST', filters, { 'Content-Type': 'application/json' });

      if (response) {
        return response;
      } else {
        throw new Error('Error estructura `results` no trobat');
      }
    } catch (error) {
      throw error;
    }
  }

  const getDocumentSEPA = async (id) => {
    const apiUrl = `${apiHost}/billing/document-sepa/${id}/`;

    try {
      const response = await $apiManager.fetch(apiUrl, 'GET');

      if (response) {
        return response;
      } else {
        throw new Error('Error estructura `results` no trobat');
      }
    } catch (error) {
      throw error;
    }
  }

  const getFilterStatus = async () => {
    const apiUrl = apiHost + '/billing/payment-status/';

    try {
      const response = await $apiManager.fetch(apiUrl, 'GET');
      if (response.results) {
        return response.results;
      } else {
        throw new Error('Error estructura `results` no trobat');
      }
    } catch (error) {
      throw error;
    }
  };



  const returnSEPA = async (data) => {
    const apiUrl = `${apiHost}/billing/sepa-return/`;
    try {
      let options;
      const formData = new FormData();
      formData.append('file', data.file);
      options = formData;
      const response = await $apiManager.fetch(apiUrl, 'PUT', options);
      return response;
    } catch (error) {
      throw error;
    }
  }

  const returnBank = async (data) => {
    const apiUrl = `${apiHost}/billing/bank-return/`;
    try {
      let options;
      const formData = new FormData();
      formData.append('file', data.file);
      formData.append('is_saving', data.is_saving);
      if (data.payment_origin) {
        formData.append('payment_origin', data.payment_origin);
      }
      options = formData;
      const response = await $apiManager.fetch(apiUrl, 'PUT', options);
      return response;
    } catch (error) {
      throw error;
    }
  }

  const saveBankBalance = async (data) => {
    const apiUrl = `${apiHost}/billing/bank-return/`;
    try {
      const response = await $apiManager.fetch(apiUrl, 'POST', data, { 'Content-Type': 'application/json' })
      return response;
    } catch (error) {
      throw error;
    }
  }

  const manualPayment = async (data) => {
    let apiUrl = `${apiHost}${entity}manual-payment/`;
    try {
      const response = await $apiManager.fetch(apiUrl, 'POST', data, { 'Content-Type': 'application/json' })
      if (response) {
        return response;
      } else {
        throw new Error('Error no trobat');
      }
    } catch (error) {
      throw error;
    }
  };

  const manageDeliquency = async (data) => {
    let apiUrl = `${apiHost}/billing/get-deliquency/`;
    try {
      const response = await $apiManager.fetch(apiUrl, 'POST', data, { 'Content-Type': 'application/json' })
      if (response) {
        return response;
      } else {
        throw new Error('Error no trobat');
      }
    } catch (error) {
      throw error;
    }
  };

  const generatePaymentDoc = async (id, date) => {
    const apiUrl = `${apiHost}/billing/generate-payment-doc/${id}/?date=${date}`;

    try {
      const response = await $apiManager.fetch(apiUrl, 'GET');

      if (response) {
        return response;
      } else {
        throw new Error('Error estructura `results` no trobat');
      }
    } catch (error) {
      throw error;
    }
  }

  const generatePaymentProofDoc = async (data) => {
    const apiUrl = `${apiHost}/billing/generate-payment-proof/`;
    try {
      const response = await $apiManager.fetch(apiUrl, 'POST', data, { 'Content-Type': 'application/json' });
      return response;
    } catch (error) {
      throw error;
    }
  }

  const getSiiInvoices = async (data) => {
    const apiUrl = `${apiHost}${entity}sii-invoices/`;
    try {
      const response = await $apiManager.fetch(apiUrl, 'POST', data, { 'Content-Type': 'application/json' });
      return response;
    } catch (error) {
      throw error;
    }
  }

  const getSiiFile = async (data) => {
    const apiUrl = `${apiHost}/billing/sii-document-generate/`;

    try {
      const response = await $apiManager.fetch(apiUrl, 'POST', data);

      if (response) {
        return response;
      } else {
        throw new Error('Error estructura `results` no trobat');
      }
    } catch (error) {
      throw error;
    }
  }

  const getPermissions = async () => {
    const apiUrl = `${apiHost}${entity}permissions/`;
    try {
      const response = await $apiManager.fetch(apiUrl, 'GET')
      if (response) {
        return response;
      } else {
        throw new Error('Error no trobat');
      }
    } catch (error) {
      throw error;
    }
  }

  const apiService = {
    getAll,
    exportData,
    save,
    getDetail,

    getPaymentMovements,
    getSEPADocData,
    getSEPAInvoices,
    bulkExcludeSEPAInvoices,
    getSEPAAnomalies,
    getSEPAFiles,
    getEInvoiceDocData,
    getDocumentSEPA,

    getFilterStatus,
    returnSEPA,
    returnBank,
    manualPayment,
    generatePaymentDoc,
    generatePaymentProofDoc,
    saveBankBalance,

    manageDeliquency,
    manageRejectionPayments,
    getSiiInvoices,
    getSiiFile,
    getEInvoices,

    getPermissions,
    regeneratePDF: async (id, date = null) => {
      let apiUrl = `${apiHost}${entity}${id}/regenerate-pdf/`;
      if (date) {
        apiUrl += `?date=${date}`;
      }
      try {
        const response = await $apiManager.fetch(apiUrl, 'POST');
        return response;
      } catch (error) {
        throw error;
      }
    }
  }

  nuxtApp.provide(provideName, apiService);
});
