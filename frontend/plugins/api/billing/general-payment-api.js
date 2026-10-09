// plugins/services//contract/contract-payment-api.js
export default defineNuxtPlugin(nuxtApp => {
  const entity = '/billing/general-payment/';
  const provideName = 'GeneralPaymentApiService';


  const { $apiManager } = useNuxtApp()
  const config = useRuntimeConfig();
  const apiHost = config.public.apiHost;

  const getAll = async (searchQuery = '', filters = [], page = 1, sort = null, desc = false) => {
    let apiUrl = apiHost + entity + '?search=' + encodeURIComponent(searchQuery) + `&page=${page}`;

    if (sort) {
      apiUrl += `&ordering=${desc ? '-' : ''}${sort}`;
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


  const save = async (data) => {
    let apiUrl = `${apiHost}${entity}`;
    try {
      const payload = { ...data };
      if (payload.company_iban && typeof payload.company_iban === 'object') {
        payload.company_iban = payload.company_iban.id;
      }
      if (payload.IBAN && typeof payload.IBAN === 'object') {
        payload.IBAN = payload.IBAN.id;
      }

      const method = payload.id ? 'PUT' : 'POST';
      if( payload.id ) {
        apiUrl += `${payload.id}/`;
      }
      
      const response = await $apiManager.fetch(apiUrl, method, payload, { 'Content-Type': 'application/json' })
      if (response) {
        return response;
      } else {
        throw new Error('Error no trobat');
      }
    } catch (error) {
      throw error;
    }

  }

  const saveSepaDocumentation = async (data) => {
    let apiUrl = `${apiHost}/billing/general-payment-sepa-document/`;
    const method = data.id ? 'PUT' : 'POST';

    if (method === 'PUT') {
      apiUrl += `${data.id}/`;
    }

    try {
      let options;
      const formData = new FormData();
      formData.append('checked', data.checked);
      formData.append('file', data.file);
      formData.append('general_payment', data.general_payment_id)
      formData.append('service', data.service)

      options = formData;
      const response = await $apiManager.fetch(apiUrl, method, options);

      if (response) {
        return response;
      } else {
        throw new Error('Error: response not found');
      }
    } catch (error) {
      throw error;
    }
  };

  const generateSepaDocument = async (id, body) => {
    const apiUrl = `${apiHost}/billing/sepa/download/${id}/`;

    try {
      const response = await $apiManager.fetch(apiUrl, 'POST', body, {'Content-Type': 'application/json'})
      if (response) {
        return response;
      } else {
        throw new Error('Error estructura `results` no trobat');
      }
    } catch (error) {
      throw error;
    }
  }
  
  // Envia per correu el document SEPA generat (GeneralPaymentSepaDocument)
  const sendSepaEmail = async (sepaDocumentId, data) => {
    const apiUrl = `${apiHost}/billing/sepa-document/${sepaDocumentId}/send-email/`;
    try {
      return await $apiManager.fetch(apiUrl, 'POST', data, { 'Content-Type': 'application/json' });
    } catch (error) {
      throw error;
    }
  }

  const doDelete = async (data ) => {
    const apiUrl = `${apiHost}${entity}${data.id}/`;
    try {
      await $apiManager.fetch(apiUrl, 'DELETE');
    } catch (error) {
      throw error;
    }
  } 


  const apiService = {
    getAll,
    getDetail,
    save,
    saveSepaDocumentation,
    generateSepaDocument,
    sendSepaEmail,
    doDelete
  };

  nuxtApp.provide(provideName, apiService);
});
