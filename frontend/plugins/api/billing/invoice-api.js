// plugins/services/pricing/price-rate-api.js
import { parseAmountInput } from '~/utils/money';

export default defineNuxtPlugin(nuxtApp => {
    const entity = '/billing/invoice/';
    const provideName = 'InvoiceApiService';
  
    const {$apiManager} = useNuxtApp()
    const config = useRuntimeConfig();
    const apiHost = config.public.apiHost;
  
    // Shared query-string builder for the invoice list filters, reused by getAll() (paginated
    // list) and massiveDownload() (backend-side bulk export over the same filtered set).
    const buildInvoiceFilterQuery = (
      searchQuery = '', filters = [], contract = null,
      is_invoice = null, origin = null, billing = null,
      issue_date = null, due_date = null, serie = [],
      total_final = null, payment_type_tokens = [], line_item = null,
      total_final_range = null, person_id = null, invoice_kinds = [],
    ) => {
      let query = 'search=' + encodeURIComponent(searchQuery);

      if (filters.length > 0) {
        query += `&status=${filters.join(',')}`;
      }

      if (contract) {
        query += `&contract=${contract}`;
      }

      if (is_invoice != null) {
        query += `&is_invoice=${is_invoice}`;
      }

      if (origin) {
        query += `&origin=${origin}`;
      }

      if (billing) {
        query += `&billing=${billing}`;
      }

      // El paràmetre és el TOTAL de la factura (etiquetat "Cerca un total
      // específic"), però s'enviava com a `left_to_pay`: es filtrava per
      // l'import pendent, de manera que cercar el total d'una factura ja
      // cobrada (pendent = 0) no trobava mai res. El backend té tots dos
      // filtres; aquí toca `total_final`.
      const total_final_value = parseAmountInput(total_final);
      if (total_final_value !== null) {
        query += `&total_final=${total_final_value}`;
      }

      if (total_final_range && (total_final_range.start_date || total_final_range.end_date)) {
        const range_start = parseAmountInput(total_final_range.start_date);
        const range_end = parseAmountInput(total_final_range.end_date);
        if (range_start !== null) {
          query += `&start_total_final_range=${range_start}`;
        }
        if (range_end !== null) {
          query += `&end_total_final_range=${range_end}`;
        }
      }

      if (issue_date && issue_date.start_date && issue_date.end_date) {
        query += `&start_issue_date=${issue_date.start_date}&end_issue_date=${issue_date.end_date}`;
      }

      if (due_date && due_date.start_date && due_date.end_date) {
        query += `&start_due_date=${due_date.start_date}&end_due_date=${due_date.end_date}`;
      }

      if (serie.length > 0) {
        query += `&serie=${serie.join(',')}`;
      }

      if (payment_type_tokens.length > 0) {
        query += `&payment_type_tokens=${payment_type_tokens.join(',')}`;
      }

      if (person_id) {
        query += `&person=${person_id}`;
      }

      if (invoice_kinds.length > 0) {
        query += `&invoice_kinds=${invoice_kinds.join(',')}`;
      }

      if (line_item && line_item !== '') {
        query += `&line_item=${encodeURIComponent(line_item)}`;
      }

      const exploitation_id = localStorage.getItem('exploitation');
      if (exploitation_id) {
        query += `&exploitation=${exploitation_id}`;
      }

      return query;
    }

    const getAll = async (
      searchQuery = '',filters = [] , page = 1,
      sort = null, desc = false, contract = null,
      is_invoice=null, origin=null, billing = null,
      issue_date = null, due_date = null, serie = [],
      total_final = null, payment_type_tokens = [], line_item = null,
      total_final_range = null, person_id = null, invoice_kinds = [],
      ) => {
      let apiUrl = apiHost + entity + '?' + buildInvoiceFilterQuery(
        searchQuery, filters, contract, is_invoice, origin, billing,
        issue_date, due_date, serie, total_final, payment_type_tokens,
        line_item, total_final_range, person_id, invoice_kinds,
      );

      apiUrl += `&page=${page}`;

      if (sort) {
        apiUrl += `&ordering=${desc ? '-' : ''}${sort}`;
      }

      try {
        const response = await $apiManager.fetch(apiUrl,'GET');
        if (response.results) {
          return response;
        } else {
          throw new Error('Error estructura `results` no trobat');
        }
      } catch (error) {
        throw error;
      }
    }

    // Backend-managed bulk download: sends the same list filters (as query params, like getAll)
    // plus the invoices the user excluded from the current selection; the backend gathers every
    // matching invoice (ignoring pagination), builds the zip/pdf and returns a Celery task_id to
    // poll via the existing `task-progress/<task_id>/` endpoint.
    const massiveDownload = async (
      excludedIds = [], inZip = true,
      searchQuery = '', filters = [], contract = null,
      is_invoice = null, origin = null, billing = null,
      issue_date = null, due_date = null, serie = [],
      total_final = null, payment_type_tokens = [], line_item = null,
      total_final_range = null, person_id = null, invoice_kinds = [],
    ) => {
      const apiUrl = `${apiHost}${entity}massive-download/?` + buildInvoiceFilterQuery(
        searchQuery, filters, contract, is_invoice, origin, billing,
        issue_date, due_date, serie, total_final, payment_type_tokens,
        line_item, total_final_range, person_id, invoice_kinds,
      );

      try {
        const response = await $apiManager.fetch(apiUrl, 'POST', {
          excluded_ids: excludedIds,
          in_zip: inZip,
        }, { 'Content-Type': 'application/json' });
        if (response?.task_id) {
          return response;
        } else {
          throw new Error('Error: `task_id` no trobat');
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
      sort = null, desc = false, contract = null,
      is_invoice = null, origin = null, billing = null,
      issue_date = null, due_date = null, serie = [],
      total_final = null, payment_type_tokens = [], line_item = null,
      total_final_range = null, person_id = null, columns = [],
    ) => {
      const exploitation_id = localStorage.getItem('exploitation');
      const extraParams = {
        contract,
        is_invoice: is_invoice != null ? is_invoice : null,
        origin,
        billing,
        left_to_pay: total_final && total_final !== '' ? total_final.replace(',', '.') : null,
        start_total_final_range: total_final_range?.start_date || null,
        end_total_final_range: total_final_range?.end_date || null,
        serie,
        payment_type_tokens,
        person: person_id,
        line_item: line_item && line_item !== '' ? line_item : null,
        exploitation: exploitation_id || null,
      };
      if (issue_date && issue_date.start_date && issue_date.end_date) {
        extraParams.start_issue_date = issue_date.start_date;
        extraParams.end_issue_date = issue_date.end_date;
      }
      if (due_date && due_date.start_date && due_date.end_date) {
        extraParams.start_due_date = due_date.start_date;
        extraParams.end_due_date = due_date.end_date;
      }
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
    
    const getExpiredInvoices = async () => {
      const apiUrl = `${apiHost}${entity}?expired=true`;

      try {
        const response = await $apiManager.fetch(apiUrl,'GET');

        if (response) {
          return response;
        } else {
          throw new Error('Error no trobat');
        }
      } catch (error) {
        throw error;
      }
    }

    const getInvoiceByCustomerToken = async (searchQuery = '', filters = [] , page = 1, payment_bank_final = null) => {
      let apiUrl = apiHost + entity + '?search=' + encodeURIComponent(searchQuery) + `&page=${page}`;

      if (payment_bank_final) {
        apiUrl += `&payment_bank_final=${payment_bank_final}`;
      }
  
      let filtersValues = [];
      if (filters.length > 0) {
        filters.map(filter => {
          filtersValues.push(filter);
        })
      }
  
      if (filtersValues.length > 0) {
        apiUrl += `&status=${filtersValues.join(',')}`;
      }
      try {
        const response = await $apiManager.fetch(apiUrl,'GET');
        if (response.results) {
          return response;
        } else {
          throw new Error('Error estructura `results` no trobat');
        }
      } catch (error) {
        throw error;
      }
    }
  
    const getDetail = async (id) => {
      const apiUrl = `${apiHost}${entity}${id}/`;
  
      try {
        const response = await $apiManager.fetch(apiUrl,'GET');
        
        if (response) {
          return response;
        } else {
          throw new Error('Error estructura `results` no trobat');
        }
      } catch (error) {
        throw error;
      }
    }

    const getTemporaryPDF = async (id) => {
      const apiUrl = `${apiHost}${entity}temporary-pdf/${id}/`;
  
      try {
        const response = await $apiManager.fetch(apiUrl,'GET');
        
        if (response) {
          return response;
        } else {
          throw new Error('Error estructura `results` no trobat');
        }
      } catch (error) {
        throw error;
      }
    }

    const generateElectronicInvoice = async (id) => {
      const apiUrl = `${apiHost}${entity}${id}/e-invoice/`;
      try {
        const response = await $apiManager.fetch(apiUrl, 'GET');
        return response;
      } catch (error) {
        throw error;
      }
    }

    const getElectronicInvoiceData = async (data) => {
      const apiUrl = `${apiHost}${entity}get-e-invoice/`;
      try {
        const response = await $apiManager.fetch(apiUrl, 'POST', data, { 'Content-Type': 'application/json' });
        return response;
      } catch (error) {
        throw error;
      }
    }

    const downloadInvoice = async (id) => {
      const apiUrl = `${apiHost}/billing/download-invoice/${id}/`;

      try {
        const response = await $apiManager.fetch(apiUrl,'GET');

        if (response) {
          return response;
        } else {
          throw new Error('Error estructura `results` no trobat');
        }
      } catch (error) {
        throw error;
      }
    }

    const downloadPaymentDoc = async (id, date) => {
      const apiUrl = `${apiHost}/billing/download-payment-doc/${id}/?date=${date}`;

      try {
        const response = await $apiManager.fetch(apiUrl,'GET');

        if (response) {
          return response;
        } else {
          throw new Error('Error estructura `results` no trobat');
        }
      } catch (error) {
        throw error;
      }
    }
    
    const getContractInvoice = async (id) => {
      const apiUrl = `${apiHost}${entity}?contract_request=${id}`;

      try {
        const response = await $apiManager.fetch(apiUrl,'GET');

        if (response) {
          return response;
        } else {
          throw new Error('Error estructura `results` no trobat');
        }
      } catch (error) {
        throw error;
      }
    }

    const passToPending = async (data) => {
      const apiUrl = `${apiHost}${entity}${data.id}/pass-to-pending/`;
      try {
        const response = await $apiManager.fetch(apiUrl, 'PUT', data, { 'Content-Type': 'application/json' });
        return response;
      } catch (error) {
        throw error;
      }
    }

    const recalculateSmart = async (id) => {
      const apiUrl = `${apiHost}${entity}${id}/recalculate-smart/`;
      try {
        const response = await $apiManager.fetch(apiUrl, 'POST');
        return response;
      } catch (error) {
        throw error;
      }
    }

    const changePaymentMethod = async (data) => {
      const apiUrl = `${apiHost}${entity}${data.id}/change-payment-method/`;
      try {
        const response = await $apiManager.fetch(apiUrl, 'PUT', data, { 'Content-Type': 'application/json' })
        return response;
      } catch (error) {
        throw error;
      }
    }

    const changeAddress = async (data) => {
      const apiUrl = `${apiHost}${entity}${data.id}/change-address/`;
      try {
        const response = await $apiManager.fetch(apiUrl, 'PUT', data, { 'Content-Type': 'application/json' })
        return response;
      } catch (error) {
        throw error;
      }
    }

    const changeDates = async (data) => {
      const apiUrl = `${apiHost}${entity}${data.id}/change-dates/`;
      try {
        const response = await $apiManager.fetch(apiUrl, 'PUT', data, { 'Content-Type': 'application/json' })
        return response;
      } catch (error) {
        throw error;
      }
    }
    
    const getInvoicesFromContract = async (id, avoid_general = false, is_invoice = null, page = 1) => {
      let apiUrl = `${apiHost}${entity}?contract=${id}&page=${page}`;
      if (avoid_general) {
        apiUrl += `&is_general=false`;
      }
      if (is_invoice !== null) {
        apiUrl += `&is_invoice=${is_invoice}`;
      }

      try {
        const response = await $apiManager.fetch(apiUrl,'GET');

        if (response) {
          return response;
        } else {
          throw new Error('Error estructura `results` no trobat');
        }
      } catch (error) {
        throw error;
      }
    }

    // Loads every page: the grouped invoices tab groups them by billing run,
    // so a partial first page would silently drop the oldest runs.
    const getGeneralInvoicesFromContract = async (id) => {
      const results = [];
      let page = 1;
      let count = 0;

      do {
        const apiUrl = `${apiHost}${entity}?general_contract=${id}&page=${page}`;
        const response = await $apiManager.fetch(apiUrl,'GET');

        if (!response || !Array.isArray(response.results)) {
          throw new Error('Error estructura `results` no trobat');
        }

        results.push(...response.results);
        count = response.count ?? results.length;

        if (!response.next || !response.results.length) break;
        page++;
      } while (results.length < count);

      return { count: results.length, results };
    }

    const downloadGeneralSummaryPdf = async (id) => {
      const apiUrl = `${apiHost}${entity}${id}/general-summary-pdf/`;
      const authToken = localStorage.getItem('auth_token') || '';
      const response = await fetch(apiUrl, {
        method: 'GET',
        headers: { 'Authorization': `Token ${authToken}` }
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || 'Error generant el PDF');
      }

      const disposition = response.headers.get('Content-Disposition') || '';
      const match = disposition.match(/filename=([^;]+)/);
      const filename = match ? match[1].trim() : 'resum_factures_agrupades.pdf';

      const blob = await response.blob();
      const blobUrl = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = blobUrl;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      setTimeout(() => URL.revokeObjectURL(blobUrl), 250);
    }

    const getConnectionRequestInvoice = async (id) => {
      const apiUrl = `${apiHost}${entity}?connection_request=${id}`;

      try {
        const response = await $apiManager.fetch(apiUrl,'GET');

        if (response) {
          return response;
        } else {
          throw new Error('Error estructura `results` no trobat');
        }
      } catch (error) {
        throw error;
      }
    }

    const generateContractInvoice = async (data, contract_id) => {
      const apiUrl = `${apiHost}/billing/invoice/contract-generate/${contract_id}/`;
      try {
        const response = await $apiManager.fetch(apiUrl, 'PUT', data, { 'Content-Type': 'application/json' })
        if (response) {
          return response;
        } else {
          throw new Error('Error no trobat');
        }
      } catch (error) {
        throw error;
      }
    }

    const getConnectionInvoice = async (connection_id) => {
      const apiUrl = `${apiHost}/billing/invoice/connection/${connection_id}/`;
      try {
        const response = await $apiManager.fetch(apiUrl, 'GET', null, { 'Content-Type': 'application/json' })
        if (response) {
          return response;
        } else {
          throw new Error('Error no trobat');
        }
      } catch (error) {
        throw error;
      }
    }

    const generateConnectionInvoice = async (data, connection_id) => {
      const apiUrl = `${apiHost}/billing/invoice/connection-generate/${connection_id}/`;
      try {
        const response = await $apiManager.fetch(apiUrl, 'PUT', data, { 'Content-Type': 'application/json' })
        if (response) {
          return response;
        } else {
          throw new Error('Error no trobat');
        }
      } catch (error) {
        throw error;
      }
    }

    const getInvoiceLineItems = async (invoice_id, company_id=null) => {
      let apiUrl = `${apiHost}/billing/invoice-line-item/?invoice=${invoice_id}`;
      if (company_id) {
        apiUrl += `&company=${company_id}`;
      }
      try {
        const response = await $apiManager.fetch(apiUrl,'GET');

        if (response) {
          return response;
        } else {
          throw new Error('Error estructura `results` no trobat');
        }
      } catch (error) {
        throw error;
      }
    }

    const deleteInvoiceBudget = async (id) => {
      const apiUrl = `${apiHost}/billing/invoice-budget/${id}/`;
      try {
        const response = await $apiManager.fetch(apiUrl, 'DELETE');
        return response || true;
      } catch (error) {
        throw error;
      }
    }

    const getBatchInvoices = async (id, query = '', page = 1, filter = null, sort = null, desc = false, hasPossibleLeakComm = false) => {
      let apiUrl =  `${apiHost}/billing/billing/${id}/invoices`;
      apiUrl += `?search=${encodeURIComponent(query)}&page=${page}`;
      if (filter) {
        apiUrl += `&${filter}`;
      }
      if (sort) {
        apiUrl += `&ordering=${desc ? '-' : ''}${sort}`;
      }
      if (hasPossibleLeakComm) {
        apiUrl += `&has_possible_leak_comm=true`;
      }
      try {
        const response = await $apiManager.fetch(apiUrl,'GET');
        
        if (response) {
          return response;
        } else {
          throw new Error('Error estructura `results` no trobat');
        }
      } catch (error) {
        throw error;
      }
    }

    const getBilledInvoices = async (id, detailed = false, type = null) => {
      let apiUrl = `${apiHost}/billing/billing/${id}/billed-invoices/?detailed=${detailed}`;
      if (type) {
        apiUrl += `&type=${encodeURIComponent(type)}`;
      }
      try {
        const response = await $apiManager.fetch(apiUrl,'GET');
        if (response) {
          return response;
        } else {
          throw new Error('Error no trobat');
        }
      } catch (error) {
        throw error;
      }
    }

    const getBatchInvoicesSummary = async (id) => {
      const apiUrl =  `${apiHost}/billing/billing/${id}/invoices/summary`;
  
      try {
        const response = await $apiManager.fetch(apiUrl,'GET');
        
        if (response) {
          return response;
        } else {
          throw new Error('Error estructura `results` no trobat');
        }
      } catch (error) {
        throw error;
      }
    }

    const generateInvoiceBudget = async (data) => {
      const apiUrl = `${apiHost}/billing/generate-invoice-budget/`;
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
    }

    const manageNewBudgetLine = async (data) => {
      const apiUrl = `${apiHost}/billing/manage-new-budget-line/`;
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
    }

    const returnInvoice = async (data) => {
      const apiUrl = `${apiHost}${entity}${data.id}/return/`;
      try {
        const response = await $apiManager.fetch(apiUrl, 'PUT', data, { 'Content-Type': 'application/json' })
        if (response) {
          return response;
        } else {
          throw new Error('Error no trobat');
        }
      } catch (error) {
        throw error;
      }
    }

    const getPermissions = async () => {
      const apiUrl = `${apiHost}${entity}permissions/`;
      try {
        const response = await $apiManager.fetch(apiUrl,'GET')
        if (response) {
          return response;
        } else {
          throw new Error('Error no trobat');
        }
      } catch (error) {
        throw error;
      }
    }
  
    const getLogs = async (id) => {
      const apiUrl = `${apiHost}${entity}${id}/logs/`;
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

    const getDocuments = async (data) => {
      const apiUrl = `${apiHost}${entity}invoice-documents/`;
      try {
        const response = await $apiManager.fetch(apiUrl, 'POST', data, { 'Content-Type': 'application/json' })
        return response;
      } catch (error) {
        throw error;
      }
    }
  
    const manageMassivelyPaid = async (data) => {
      const apiUrl = `${apiHost}${entity}manage-massively-paid/`;
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
    }

    const excludeInvoice = async (data) => {
      const apiUrl = `${apiHost}${entity}exclude/`;
      try {
        const response = await $apiManager.fetch(apiUrl, 'POST', data, { 'Content-Type': 'application/json' })
        return response;
      } catch (error) {
        throw error;
      }
    }

    const markReviewedRange = async (data) => {
      const apiUrl = `${apiHost}${entity}mark-reviewed-range/`;
      try {
        const response = await $apiManager.fetch(apiUrl, 'POST', data, { 'Content-Type': 'application/json' })
        return response;
      } catch (error) {
        throw error;
      }
    }

    const previewReviewedRange = async (data) => {
      const apiUrl = `${apiHost}${entity}reviewed-range-preview/`;
      try {
        const response = await $apiManager.fetch(apiUrl, 'POST', data, { 'Content-Type': 'application/json' })
        return response;
      } catch (error) {
        throw error;
      }
    }

    const sendEmail = async (id, data) => {
      const apiUrl = `${apiHost}${entity}${id}/send-email/`;
      try {
        const response = await $apiManager.fetch(apiUrl, 'POST', data, { 'Content-Type': 'application/json' })
        return response;
      } catch (error) {
        throw error;
      }
    }
  
    const apiService = {
      getAll,
      massiveDownload,
      exportData,
      save,
      getDetail,
      generateContractInvoice,
      generateConnectionInvoice,
      getContractInvoice,
      getInvoicesFromContract,
      getConnectionRequestInvoice,
      getInvoiceLineItems,
      getConnectionInvoice,
      getExpiredInvoices,
      getTemporaryPDF,
      getBatchInvoices,
      getBatchInvoicesSummary,
      deleteInvoiceBudget,
      downloadInvoice,
      downloadPaymentDoc,
      generateInvoiceBudget,
      manageNewBudgetLine,
      returnInvoice,
      passToPending,
      changePaymentMethod,
      getInvoiceByCustomerToken,
      changeAddress,
      changeDates,
      getGeneralInvoicesFromContract,
      downloadGeneralSummaryPdf,
      excludeInvoice,
      markReviewedRange,
      previewReviewedRange,
      generateElectronicInvoice,
      getElectronicInvoiceData,
      getPermissions,
      getLogs,
      getDocuments,
      recalculateSmart,
      manageMassivelyPaid,
      sendEmail,
      getBilledInvoices
    }
  
    nuxtApp.provide(provideName, apiService);
  });
  