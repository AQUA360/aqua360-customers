// plugins/services/order/order-type-api.js
export default defineNuxtPlugin(nuxtApp => {
  const entity = '/billing/commitment-deposit/';
  const provideName = 'CommitmentDepositApiService';


  const { $apiManager } = useNuxtApp()
  const config = useRuntimeConfig();
  const apiHost = config.public.apiHost;

  const getAll = async (searchQuery = '', filters = [], page = 1, sort = null, desc = false, contract_id = null) => {
    let apiUrl = apiHost + entity + '?search=' + encodeURIComponent(searchQuery) + `&page=${page}`;

    if (sort) {
      apiUrl += `&ordering=${desc ? '-' : ''}${sort}`;
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

    if (contract_id) {
      apiUrl += `&contract=${contract_id}`;
    }

    let exploitation_id = localStorage.getItem('exploitation');
    if (exploitation_id) {
      apiUrl += `&exploitation=${exploitation_id}`;
    }

    try {
      const response = await $apiManager.fetch(apiUrl, 'GET')

      if (response.results) {
        return response;
      } else {
        throw new Error('Error estructura `results` no trobat');
      }
    } catch (error) {
      throw error;
    }
  }

  const exportData = async (searchQuery = '', filters = [], sort = null, desc = false, contract_id = null, columns = []) => {
    const exploitation_id = localStorage.getItem('exploitation');
    return $apiManager.exportTable(entity, { searchQuery, filters, sort, desc, columns, extraParams: { contract: contract_id, exploitation: exploitation_id || null } });
  }

  const getDetail = async (id) => {
    const apiUrl = `${apiHost}${entity}${id}/`;

    try {
      const response = await $apiManager.fetch(apiUrl, 'GET')
      if (response) {
        return response;
      } else {
        throw new Error('Error estructura `results` no trobat');
      }
    } catch (error) {
      throw error;
    }
  }

  // Compromís(os) de dipòsit que inclouen una factura concreta (relació M2M CommitmentDeposit.invoices).
  const getByInvoice = async (invoice_id) => {
    const apiUrl = `${apiHost}${entity}?invoice=${invoice_id}`;

    try {
      const response = await $apiManager.fetch(apiUrl, 'GET')
      if (response.results) {
        return response;
      } else {
        throw new Error('Error estructura `results` no trobat');
      }
    } catch (error) {
      throw error;
    }
  }

  const getData = async (data) => {
    let apiUrl = `${apiHost}/billing/get-commitment-data/`;

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

  const liquidateAll = async (id) => {
    const apiUrl = `${apiHost}${entity}${id}/liquidate-all/`;
    try {
      const response = await $apiManager.fetch(apiUrl, 'PUT');
      return response;
    } catch (error) {
      throw error;
    }
  }

  const deleteItem = async (id) => {
    const apiUrl = `${apiHost}${entity}${id}/`;

    try {
      const response = await $apiManager.fetch(apiUrl, 'DELETE');
      return true;

    } catch (error) {
      throw error;
    }
  };

  const saveBalance = async (id) => {
    const apiUrl = `${apiHost}${entity}${id}/save-balance/`;

    try {
      const response = await $apiManager.fetch(apiUrl, 'PUT');
      return true;

    } catch (error) {
      throw error;
    }
  };

  const getCommitmentFile = async (id) => {
    const apiUrl = `${apiHost}/billing/commitment-deposit-document-generate/${id}/`;
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
    getDetail,
    getData,
    save,
    deleteItem,
    getCommitmentFile,
    getPermissions,
    saveBalance,
    liquidateAll,
    getByInvoice
  };

  nuxtApp.provide(provideName, apiService);
});
