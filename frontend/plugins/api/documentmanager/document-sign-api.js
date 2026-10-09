// plugins/api/documentmanager/document-sign-api.js
export default defineNuxtPlugin(nuxtApp => {
  const entity = '/documentmanager/';
  const provideName = 'DocumentSignApiService';

  const { $apiManager } = useNuxtApp()
  const config = useRuntimeConfig();
  const apiHost = config.public.apiHost;

  const getAll = async () => {
    const apiUrl = `${apiHost}${entity}document-sign/`;
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

  const getDetail = async (id) => {
    const apiUrl = `${apiHost}${entity}document-sign/${id}/`;
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
    const method = data.id ? 'PUT' : 'POST';
    let apiUrl = `${apiHost}${entity}document-sign/`;
    if (method == 'PUT') { apiUrl += data.id + '/'; }
    try {
      const response = await $apiManager.fetch(apiUrl, method, data, { 'Content-Type': 'application/json' })
      if (response) {
        return response;
      } else {
        throw new Error('Error estructura `results` no trobat');
      }
    } catch (error) {
      throw error;
    }
  }

  const doDelete = async (data) => {
    const apiUrl = `${apiHost}${entity}document-sign/${data.id}/`;
    try {
      await $apiManager.fetch(apiUrl, 'DELETE');
    } catch (error) {
      throw error;
    }
  }

  /** Retorna { document_signs: [...] } de tots els DocumentSign d'un contracte. */
  const getByContract = async (contract_id) => {
    const apiUrl = `${apiHost}${entity}document-signs-by-contract/?contract_id=${contract_id}`;
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

  /**
   * Retorna { document_signs: [...] } dels DocumentSign creats amb `contract_request_id`
   * (flux d'alta abans que existeixi contracte). Assumeix el mateix endpoint que
   * `getByContract`, substituint el paràmetre `contract_id` per `contract_request_id`.
   */
  const getByContractRequest = async (contract_request_id) => {
    const apiUrl = `${apiHost}${entity}document-signs-by-contract/?contract_request_id=${contract_request_id}`;
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

  /** Retorna { document_signs: [...] } de tots els DocumentSign, amb filtre opcional de status. */
  const getAllSummary = async (status = null) => {
    let apiUrl = `${apiHost}${entity}document-signs-all/`;
    if (status !== null && status !== undefined && status !== '') {
      apiUrl += `?status=${status}`;
    }
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

  /** Envia el document a firmar via Aqua360 Sign. */
  const send = async (id, force = false, callback_url = null) => {
    const apiUrl = `${apiHost}${entity}document-sign/${id}/send/`;
    const body = { force };
    if (callback_url) body.callback_url = callback_url;
    try {
      const response = await $apiManager.fetch(apiUrl, 'POST', body, { 'Content-Type': 'application/json' })
      if (response) {
        return response;
      } else {
        throw new Error('Error estructura `results` no trobat');
      }
    } catch (error) {
      throw error;
    }
  }

  const getDownloadUrl = (id) => `${apiHost}${entity}document-sign-download/${id}/`;

  /**
   * Demana a Aqua360 el PDF si l'usuari ja l'ha signat. No és `/send/`
   * (això només envia la petició OTP). No retorna binari.
   */
  const requestSignedDocument = async (id) => {
    const apiUrl = `${apiHost}${entity}document-sign/${id}/retrieve/`;
    const response = await $apiManager.fetch(apiUrl, 'POST', {}, { 'Content-Type': 'application/json' });
    return response;
  };

  const apiService = {
    getAll,
    getDetail,
    save,
    doDelete,
    getByContract,
    getByContractRequest,
    getAllSummary,
    send,
    getDownloadUrl,
    requestSignedDocument,
  };

  nuxtApp.provide(provideName, apiService);
});
