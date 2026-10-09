// plugins/services/coredata/config-project-api.js
export default defineNuxtPlugin(nuxtApp => {
  const entity = '/billing/joined-payment/';
  const provideName = 'JoinedPaymentApiService';

  const { $apiManager } = useNuxtApp()
  const config = useRuntimeConfig();
  const apiHost = config.public.apiHost;

  const getDetail = async (id) => {
    const apiUrl = apiHost + entity + id + '/';

    try {

      const response = await $apiManager.fetch(apiUrl, 'GET');
      return response;
    } catch (error) {
      throw error;
    }
  };
  
  const getAll = async (searchQuery = '', filters = [], page = 1, sort = null, desc = false, payment_date = null, due_date = null, total = null, payment_type = null) => {
    let apiUrl = apiHost + entity + '?search=' + encodeURIComponent(searchQuery) + `&page=${page}`;

    // Afegir els filtres a la URL
    let filtersValues = [];
    if (filters.length > 0) {
      filters.map(filter => {
        filtersValues.push(filter);
      });
    }

    if (filtersValues.length > 0) {
      apiUrl += `&status=${filtersValues.join(',')}`;
    }

    if (sort) {
      apiUrl += `&ordering=${desc ? '-' : ''}${sort}`;
    }

    if (payment_date && payment_date.start_date && payment_date.end_date) {
      apiUrl += `&start_payment_date=${payment_date.start_date}&end_payment_date=${payment_date.end_date}`;
    }

    if (due_date && due_date.start_date && due_date.end_date) {
      apiUrl += `&start_due_date=${due_date.start_date}&end_due_date=${due_date.end_date}`;
    }

    if (total != null) {
      apiUrl += `&total_final=${total}`;
    }

    if (payment_type) {
      apiUrl += `&payment_type=${payment_type}`;
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
  };

  const exportData = async (searchQuery = '', filters = [], sort = null, desc = false, payment_date = null, due_date = null, total = null, payment_type = null) => {
    const extraParams = {
      start_payment_date: payment_date && payment_date.start_date && payment_date.end_date ? payment_date.start_date : null,
      end_payment_date: payment_date && payment_date.start_date && payment_date.end_date ? payment_date.end_date : null,
      start_due_date: due_date && due_date.start_date && due_date.end_date ? due_date.start_date : null,
      end_due_date: due_date && due_date.start_date && due_date.end_date ? due_date.end_date : null,
      total_final: total,
      payment_type,
    };
    return $apiManager.exportTable(entity, { searchQuery, filters, sort, desc, extraParams });
  };

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

  const getPendingClientData = async (data) => {
    const apiUrl = `${apiHost}${entity}pending-client-data/`;
    try {
      const response = await $apiManager.fetch(apiUrl, 'POST', data, { 'Content-Type': 'application/json' })
      return response;
    } catch (error) {
      throw error;
    }
  }

  const generatePaymentProofDoc = async (data) => {
    const apiUrl = `${apiHost}${entity}payment-proof/`;
    try {
      const response = await $apiManager.fetch(apiUrl, 'POST', data, { 'Content-Type': 'application/json' })
      return response;
    } catch (error) {
      throw error;
    }
  }

  const generatePDF = async (id, payload = null) => {
    const apiUrl = `${apiHost}${entity}${id}/generate-pdf/`;
    const method = payload && !id ? 'POST' : 'GET';
    try {
      let response = null;
      if (method == 'POST' && payload) {
        response = await $apiManager.fetch(apiUrl, method, payload, { 'Content-Type': 'application/json' });
      } else {
        response = await $apiManager.fetch(apiUrl, method);
      }
      return response;
    } catch (error) {
      throw error;
    }
  }
  const apiService = {
    getAll,
    exportData,
    getDetail,
    save,
    getPendingClientData,
    generatePaymentProofDoc,
    generatePDF,
  };

  nuxtApp.provide(provideName, apiService);
});
