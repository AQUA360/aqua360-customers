// plugins/services/contract/contract-request-api.js
export default defineNuxtPlugin(nuxtApp => {
  const entity = '/contract/contract-request/';
  const provideName = 'ContractRequestApiService';


  const { $apiManager } = useNuxtApp()
  const config = useRuntimeConfig();
  const apiHost = config.public.apiHost;

  const getAll = async (
    searchQuery = '', filters = [], page = 1, sort = null, desc = false,
    category_ids = [], use_type_ids = [], client_type_ids = [], has_invoice = null,
    search_by_address = ''
  ) => {
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

    if (category_ids?.length > 0) {
      apiUrl += `&category=${category_ids.join(',')}`;
    }
    if (use_type_ids?.length > 0) {
      apiUrl += `&use_type=${use_type_ids.join(',')}`;
    }
    if (client_type_ids?.length > 0) {
      apiUrl += `&client_type=${client_type_ids.join(',')}`;
    }

    if (has_invoice != null) {
      apiUrl += `&no_invoice=${has_invoice}`;
    }

    if (search_by_address) {
      apiUrl += `&search_by_address=${encodeURIComponent(search_by_address)}`;
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

  const exportData = async (
    searchQuery = '', filters = [], sort = null, desc = false,
    category_ids = [], use_type_ids = [], client_type_ids = [], has_invoice = null,
    search_by_address = '', columns = []
  ) => {
    return $apiManager.exportTable(entity, {
      searchQuery, filters, sort, desc, columns,
      extraParams: {
        category: category_ids,
        use_type: use_type_ids,
        client_type: client_type_ids,
        no_invoice: has_invoice,
        search_by_address,
      }
    });
  }


  const save = async (data) => {
    let apiUrl = `${apiHost}${entity}`;
    try {
      const method = data.id ? 'PUT' : 'POST';
      if( method == 'PUT' ){
        apiUrl += data.id + '/';
      }
      let response;
      if(data.file){
        let options;
        const formData = new FormData();
        formData.append('contract_file', data.file);
        formData.append('id', data.id);
        formData;
        options = formData;
        response = await $apiManager.fetch(apiUrl, method, options);
      }else{
        response = await $apiManager.fetch(apiUrl, method, data, { 'Content-Type': 'application/json' })
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
  
  
  const doDelete = async (data ) => {
    const apiUrl = `${apiHost}${entity}${data.id}/`;
    try {
      await $apiManager.fetch(apiUrl, 'DELETE');
    } catch (error) {
      throw error;
    }
  } 

  const finalize = async (data) => {
    const apiUrl = `${apiHost}${entity}finalize/${data.id}/`;
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

  // Finalitza una sol·licitud de tipus "Canvi de nom": el backend ha d'actualitzar
  // en el mateix Contract (mateix número/token) el titular i la resta de dades
  // recollides a la sol·licitud, en lloc de crear un Contract nou (comportament
  // equivalent al d'una ContractSurrogation).
  const finalizeInPlace = async (data) => {
    const apiUrl = `${apiHost}${entity}finalize-in-place/${data.id}/`;
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

  const doContract = async (data) => {
    const apiUrl = `${apiHost}${entity}contract-create/${data.id}/`;
    try {
      const response = await $apiManager.fetch(apiUrl, 'PUT', data)
      return response;
    } catch (error) {
      throw error;
    }
  }

  const getFilterStatus = async () => {
    const apiUrl = apiHost + '/contract/contract-request-status/';

    try {
      const response = await $apiManager.fetch(apiUrl,'GET')
      if (response.results) {
        return response.results;
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

  
  const saveFile = async (data) => {
    let apiUrl = `${apiHost}${entity}${data.id}/save-file/`;
    try {
      let options;
      if (data.file) {
        const formData = new FormData();
        formData.append('file', data.file);
        formData.append('id', data.id);
        formData.append('contract_type', data.contract_type);
        if (data.text) formData.append('text', data.text);
        options = formData;
      } else {
        apiUrl = `${apiHost}${entity}${data.id}/save-documentation/`;
        options = {
          contract_type: data.contract_type,
          text: data.text || '',
        };
        const response = await $apiManager.fetch(apiUrl, 'POST', options, { 'Content-Type': 'application/json' });
        if (response) return response;
        throw new Error('Error no trobat');
      }

      const response = await $apiManager.fetch(apiUrl, 'PUT', options)
      if (response) {
        return response;
      } else {
        throw new Error('Error no trobat');
      }
    } catch (error) {
      throw error;
    }
  }


  const updateCaliber = async (data) => {
    const apiUrl = `${apiHost}${entity}${data.id}/set-requested-meter-caliber/`;
    try {
      const response = await $apiManager.fetch(apiUrl, 'PUT', data)
      return response;
    } catch (error) {
      throw error;
    }
  }

  const patch = async (data) => {
    const apiUrl = `${apiHost}${entity}${data.id}/`;
    try {
      const response = await $apiManager.fetch(apiUrl, 'PATCH', data, { 'Content-Type': 'application/json' })
      if (response) {
        return response;
      } else {
        throw new Error('Error no trobat');
      }
    } catch (error) {
      throw error;
    }
  }

  const validateData = async (id) => {
    const apiUrl = `${apiHost}${entity}${id}/validate-data/`;
    try {
      const response = await $apiManager.fetch(apiUrl, 'GET')
      return response;
    } catch (error) {
      throw error;
    }
  }

  const regenerateToken = async (id) => {
    const apiUrl = `${apiHost}${entity}${id}/regenerate-token/`;
    try {
      const response = await $apiManager.fetch(apiUrl, 'POST', {}, { 'Content-Type': 'application/json' })
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
    patch,
    doDelete,
    doContract,
    finalize,
    finalizeInPlace,
    getFilterStatus,
    getPermissions,
    saveFile,
    updateCaliber,
    validateData,
    regenerateToken
  };

  nuxtApp.provide(provideName, apiService);
});
