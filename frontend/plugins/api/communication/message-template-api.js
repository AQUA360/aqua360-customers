// plugins/services/order/order-type-api.js
export default defineNuxtPlugin(nuxtApp => {
  const entity = '/communication/message-template/';
  const provideName = 'MessageTemplateApiService';

  const { $apiManager } = useNuxtApp()
  const config = useRuntimeConfig();
  const apiHost = config.public.apiHost;

  const getAll = async (searchQuery = '', filters = [], page = 1, sort = null, desc = false, origin = null) => {
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
    
    if (origin) {
      apiUrl += `&origin=${origin}`;
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

  const getMessageTypeTemplateDetail = async (id) => {
    const apiUrl = `${apiHost}/communication/message-type-template/${id}/`;
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

  const getMessageTypeTemplates = async (id) => {
    const apiUrl = `${apiHost}/communication/message-type-template/?message_template=${id}`;
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

  const getMessageTypeTemplate = async (id) => {
    const apiUrl = `${apiHost}${entity}message-type-templates/${id}`;
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

  const saveTypeTemplate = async (data) => {
    let apiUrl = `${apiHost}/communication/message-type-template/`;
    try {
      const isFormData = data instanceof FormData;
      const id = isFormData ? data.get('id') : data.id;
      const method = id ? 'PUT' : 'POST';
      if (method == 'PUT') {
        apiUrl += id + '/';
      }
      const headers = isFormData ? {} : { 'Content-Type': 'application/json' };
      const response = await $apiManager.fetch(apiUrl, method, data, headers)
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

  const deleteTypeTemplate = async (id) => {
    const apiUrl = `${apiHost}/communication/message-type-template/${id}/`;

    try {
      const response = await $apiManager.fetch(apiUrl, 'DELETE');
      return true;

    } catch (error) {
      throw error;
    }
  };


  // Server-side XLSX export (async). Mirrors getAll's filters/search/sort but
  // POSTs to `{entity}export/`, returning `{ task_id }`. Same args as getAll (no page).
  const exportData = async (searchQuery = '', filters = [], sort = null, desc = false, origin = null) => {
    return $apiManager.exportTable(entity, { searchQuery, filters, sort, desc, extraParams: { origin } });
  };

  const apiService = {
    getAll,
    getDetail,
    getMessageTypeTemplates,
    getMessageTypeTemplate,
    getMessageTypeTemplateDetail,
    save,
    saveTypeTemplate,
    deleteItem,
    deleteTypeTemplate,
    exportData,
  };

  nuxtApp.provide(provideName, apiService);
});
