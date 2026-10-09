// plugins/services/order/order-type-api.js
export default defineNuxtPlugin(nuxtApp => {
  const entity = '/claimrequest/claim-request/';
  const provideName = 'ClaimRequestApiService';


  const { $apiManager } = useNuxtApp()
  const config = useRuntimeConfig();
  const apiHost = config.public.apiHost;

  const getAll = async (searchQuery = '', filters = [], page = 1, sort = null, desc = false, 
    step_ids = [], contract_id = null, person_id = null, is_communication = false) => {
    let apiUrl = apiHost + entity + '?search=' + encodeURIComponent(searchQuery) + `&page=${page}`;

    if (sort) {
      apiUrl += `&ordering=${desc ? '-' : ''}${sort}`;
    }

    if (filters?.length > 0) {
      apiUrl += `&status=${filters.join(',')}`;
    }

    if (step_ids?.length > 0) {
      apiUrl += `&step=${step_ids.join(',')}`;
    }

    if (contract_id) {
      apiUrl += `&contract=${contract_id}`;
    }

    if (is_communication) {
      apiUrl += `&is_communication=true`;
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


  const getAllSteps = async (searchQuery = '', filters = [], page = 1, sort = null, desc = false) => {
    let apiUrl = apiHost + '/claimrequest/claim-request-step-template/' + '?search=' + encodeURIComponent(searchQuery) + `&page=${page}`;

    if (sort) {
      apiUrl += `&ordering=${desc ? '-' : ''}${sort}`;
    }

    if (filters?.length > 0) {
      apiUrl += `&status=${filters.join(',')}`;
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




  // Server-side export (async). Mirrors getAll's filters/search/sort but POSTs
  // to `{entity}export/` so the backend builds the full, filter-aware XLSX as a
  // background task, returning `{ task_id }`. Same args as getAll (no page).
  const exportData = async (searchQuery = '', filters = [], sort = null, desc = false,
    step_ids = [], contract_id = null, person_id = null, is_communication = false, columns = []) => {
    return $apiManager.exportTable(entity, {
      searchQuery, filters, sort, desc, columns,
      extraParams: { step: step_ids, contract: contract_id, is_communication: is_communication ? 'true' : null }
    });
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
  
  const deleteItem = async (id) => {
    const apiUrl = `${apiHost}${entity}${id}/`;

    try {
      const response = await $apiManager.fetch(apiUrl, 'DELETE');
      return true;

    } catch (error) {
      throw error;
    }
  };

  const getClaimRequestTemplates = async () => {
    const apiUrl = `${apiHost}/claimrequest/claim-request-template/`;
    try {
      const response = await $apiManager.fetch(apiUrl, 'GET')
      return response;
    } catch (error) {
      throw error;
    }
  }

  const getClaimRequestStepTemplateDetail = async ( id ) => {
    const apiUrl = `${apiHost}/claimrequest/claim-request-step-template/${id}/`;
    try {
      const response = await $apiManager.fetch(apiUrl, 'GET')
      if (response) {
        return response;
      } else {
        throw new Error('Error estructura `results` no trobat');
      }
    }
    catch (error) {
      throw error
    }
  }

  const getClaimRequestStepTemplates = async ( claim_request_template_id = null ) => {
    let apiUrl = `${apiHost}/claimrequest/claim-request-step-template/`;
    if (claim_request_template_id) {
      apiUrl += `?template=${claim_request_template_id}`;
    }
    
    try {
      const response = await $apiManager.fetch(apiUrl, 'GET')
      return response;
    }
    catch (error) {
      throw error
    }
  }

  const getClaimStepsData = async (request_id) => {
    let apiUrl = apiHost + `/claimrequest/claim-request/${request_id}/steps/`;

    try {
      const response = await $apiManager.fetch(apiUrl, 'GET')
      return response;
      
    } catch (error) {
      throw error;
    }
  }

  const getClaimStepDetail = async (id) => {
    const apiUrl = `${apiHost}/claimrequest/claim-request-step/${id}/`;

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

  const saveClaimStep = async (data) => {
    let apiUrl = `${apiHost}/claimrequest/claim-request-step/`;
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

  const saveClaimStepTemplate = async (data) => {
    let apiUrl = `${apiHost}/claimrequest/claim-request-step-template/`;
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

  const getClaimExcelFile = async (id) => {
    const apiUrl = `${apiHost}/claimrequest/claim-request-excel-generate/${id}/`;

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

  const downloadClaimDocument = async (data) => {
    const apiUrl = `${apiHost}/claimrequest/download-claim-document/${data.id}/`;

    try {
      const response = await $apiManager.fetch(apiUrl, 'PUT', data, { 'Content-Type': 'application/json' })
      if (response) {
        return response;
      } else {
        throw new Error('Error estructura `results` no trobat');
      }
    } catch (error) {
      throw error;
    }
  }

  const updateClaimRequestNextStep = async (id) => {
    const apiUrl = apiHost + `/claimrequest/claim-request-next-step/${id}/`;
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

  const getClaimData = async (data, task_id = null) => {
    let apiUrl = apiHost + `/claimrequest/claim-request-data/`;
    if (task_id) {
      apiUrl += `?task_id=${task_id}`;
    }
    try {
      let response;
      if (task_id) {
        response = await $apiManager.fetch(apiUrl, 'GET')
      } else {
        response = await $apiManager.fetch(apiUrl, 'POST', data, { 'Content-Type': 'application/json' })
      }
      if (response) {
        return response;
      } else {
        throw new Error('Error no trobat');
      }
    } catch (error) {
      throw error;
    }
  }

  const getContractsClaimRequest = async (payload) => {
    const apiUrl = `${apiHost}${entity}get-contracts-claim-request/`;
    try {
      let data = payload;
      if (data.file) {
        const formData = new FormData();
        formData.append('file', data.file);
        formData.append('claim_request_id', data.claim_request_id);
        data = formData;
      }
      const response = await $apiManager.fetch(apiUrl, 'POST', data)
        if (response) {
          return response;
        } else {
          throw new Error('Error no trobat');
        }
      } catch (error) {
        throw error;
      }
  }

  const saveDocumentationFile = async (data) => {
    let apiUrl = `${apiHost}/claimrequest/claim-request-step/step-documentation/`;
    try {
      const formData = new FormData();
      formData.append('document', data.document);
      formData.append('claim_request_step_id', data.claim_request_step_id);
      const response = await $apiManager.fetch(apiUrl, 'POST', formData)
        if (response) {
          return response;
        } else {
          throw new Error('Error no trobat');
        }
      } catch (error) {
        throw error;
      }
    }

  const getContracts = async (id, is_juridic = null, step_id = null) => {
    let apiUrl = `${apiHost}/claimrequest/claim-request/${id}/contracts/`;
    if (is_juridic !== null) {
      apiUrl += `?is_juridic=${is_juridic}`;
    }
    if (step_id) {
      apiUrl += `${apiUrl.includes('?') ? '&' : '?'}step=${step_id}`;
    }
    try {
      const response = await $apiManager.fetch(apiUrl, 'GET')
      // mirem que tingui el camp results
      if (response.results) {
        return response;
      } else {
        throw new Error('Error estructura `results` no trobat');
      }
    } catch (error) {
      throw error;
    }
  } 

  /**
   * Marca contractes com a vulnerables
   * @param {Object} data - Dades de la petició
   * @param {number} data.request_id - ID de la reclamació
   * @param {Array<number>} data.contract_ids - Array d'IDs dels contractes a marcar com a vulnerables
   * @returns {Promise<Object>} - Resposta de l'API amb els contractes marcats
   * @throws {Error} - Error si la petició falla
   */
  const markContractsAsVulnerable = async (data) => {
    const apiUrl = `${apiHost}/claimrequest/claim-request-manage/mark-contracts-vulnerable/`;
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

  /**
   * Actualitza un step d'una reclamació
   * @param {Object} data - Dades de la petició
   * @param {number} data.id - ID del claim-request-step
   * @param {string} data.action_date_at - Data de l'acció realitzada
   * @returns {Promise<Object>} - Resposta de l'API amb el step actualitzat
   * @throws {Error} - Error si la petició falla
   */
  const updateClaimRequestStep = async (data) => {
    const apiUrl = `${apiHost}/claimrequest/claim-request-step/${data.id}/`;
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

  const getClaimRequestOrders = async (claim_request_id, order_type_token) => {
    const apiUrl = `${apiHost}/order/order/?claim_request=${claim_request_id}&type_token=${order_type_token}`;
    try {
      const response = await $apiManager.fetch(apiUrl, 'GET')
      return response;
    }
    catch (error) {
      throw error
    }
  }

  /**
   * Exclou un contracte i els seus pagaments d'una reclamació
   * @param {Object} data - Dades de la petició
   * @param {number} data.request_id - ID de la reclamació
   * @param {number} data.contract_id - ID del contracte a excloure
   * @returns {Promise<Object>} - Resposta de l'API
   * @throws {Error} - Error si la petició falla
   */
  const excludeContract = async (data) => {
    const apiUrl = `${apiHost}/claimrequest/claim-request-manage/exclude-contract/`;
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

  /**
   * Envia una petició per cancel·lar contractes de manera massiva
   * @param {Object} data - Dades de la petició
   * @param {number} data.request_id - ID de la reclamació
   * @param {Array<number>} data.contracts - Array d'IDs dels contractes a cancel·lar
   * @param {string} data.cancellation_date - Data de cancel·lació en format ISO
   * @param {string} data.cancellation_reason - Motiu de la cancel·lació
   * @param {string} [data.observations] - Observacions opcionals
   * @returns {Promise<Object>} - Resposta de l'API
   * @throws {Error} - Error si la petició falla
   */
  const submitMassiveTerminationContract = async (data) => {
    const apiUrl = `${apiHost}/claimrequest/claim-request-manage/massive-termination-contract/`;
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

  const generateExpenses = async (data) => {
    const apiUrl = `${apiHost}/claimrequest/claim-request/generate-expenses/`;
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

  const getStepExpenses = async (id, page = null) => {
    let apiUrl = `${apiHost}/claimrequest/claim-request-step/${id}/expenses/`;
    if (page) {
      apiUrl += `?page=${page}`;
    }
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

  const apiService = {
    getAll,
    getAllSteps,
    exportData,
    getDetail,
    save,
    deleteItem,

    getClaimRequestTemplates,
    getClaimRequestStepTemplates,
    getClaimRequestStepTemplateDetail,
    saveClaimStepTemplate,
    getClaimData,

    getClaimStepsData,
    getClaimStepDetail,
    saveClaimStep,
    getStepExpenses,
    
    getClaimExcelFile,
    updateClaimRequestNextStep,
    downloadClaimDocument,

    getContracts,
    getContractsClaimRequest,
    markContractsAsVulnerable,

    updateClaimRequestStep,
    saveDocumentationFile,
    getClaimRequestOrders,
    excludeContract,

    generateExpenses,
    submitMassiveTerminationContract,
    getPermissions
  };

  nuxtApp.provide(provideName, apiService);
});
