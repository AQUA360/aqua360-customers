// plugins/services/pricing/price-rate-api.js
export default defineNuxtPlugin(nuxtApp => {
  const entity = '/billing/reading-document/';
  const provideName = 'ReadingDocumentApiService';

  const { $apiManager } = useNuxtApp()
  const config = useRuntimeConfig();
  const apiHost = config.public.apiHost;

  const getAll = async (searchQuery = '', filters = [], page = 1, sort = null, desc = false) => {
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

  const save = async (data) => {
    let apiUrl = `${apiHost}${entity}`;
    try {
      const method = 'POST';
      const formData = new FormData();
      for (const key in data) {
        if (data[key] != "" && data[key] != null) {
          formData.append(key, data[key]);
        }
      }

      const response = await $apiManager.fetch(apiUrl, method, formData)
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

  const getTemplate = async () => {
    const apiUrl = `${apiHost}${entity}template/`;
    try {
      const response = await $apiManager.fetch(apiUrl, 'GET');
      return response;
    } catch (error) {
      throw error;
    }
  }

  const getReadingDetail = async (id) => {
    const apiUrl = `${apiHost}/billing/reading-detail/${id}/`;

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

  const getReadingsByBatch = async (batch_id, page) => {

    let apiUrl = `${apiHost}${entity}by-batch/`
    if (batch_id) {
      apiUrl += `?batch=${batch_id}`;
    }
    apiUrl += `&page=${page}`;
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
  const getReadingsByBatchMinimal = async (batch_id, page, filter = null) => {

    let apiUrl = `${apiHost}${entity}by-batch-minimal/`
    if (batch_id) {
      apiUrl += `?batch=${batch_id}`;
    }
    if (filter) {
      apiUrl += `&${filter}`;
    }
    apiUrl += `&page=${page}`;
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

  const update = async (id, data) => {
    const apiUrl = `${apiHost}${entity}${id}/`;
    try {
      const formData = new FormData();
      for (const key in data) {
        if (data[key] != '' && data[key] != null) {
          formData.append(key, data[key]);
        }
      }
      const response = await $apiManager.fetch(apiUrl, 'PATCH', formData);
      if (response) {
        return response;
      }
      throw new Error('Error no trobat');
    } catch (error) {
      throw error;
    }
  };

  const validate = async (id, params = {}) => {
    // Compatibilitat: validate(id, 100) → max_rows
    const query =
      typeof params === 'number'
        ? { max_rows: params }
        : { ...params };

    const searchParams = new URLSearchParams();
    Object.entries(query).forEach(([key, value]) => {
      if (value === undefined || value === null || value === '') return;
      searchParams.set(key, String(value));
    });

    const qs = searchParams.toString();
    const apiUrl = `${apiHost}${entity}${id}/validate/${qs ? `?${qs}` : ''}`;
    try {
      const response = await $apiManager.fetch(apiUrl, 'GET');
      if (response) {
        return response;
      }
      throw new Error('Error no trobat');
    } catch (error) {
      throw error;
    }
  };

  const process = async (id) => {
    const apiUrl = `${apiHost}${entity}${id}/process/`;
    try {
      // suppressToast: el 409 (ja en curs) el gestiona el caller amb el task_id existent
      const response = await $apiManager.fetch(apiUrl, 'POST', {}, null, true);
      if (response) {
        return response;
      }
      throw new Error('Error no trobat');
    } catch (error) {
      const status = error?.response?.status ?? error?.statusCode ?? error?.status;
      const data = error?.response?._data ?? error?.data;
      if (status === 409 && data?.task_id) {
        return {
          task_id: data.task_id,
          already_processing: true,
          detail: data.detail,
        };
      }
      throw error;
    }
  };

  const reprocess = async (id) => {
    const apiUrl = `${apiHost}${entity}${id}/reprocess/`;
    try {
      const response = await $apiManager.fetch(apiUrl, 'POST', {});
      if (response) {
        return response;
      }
      throw new Error('Error no trobat');
    } catch (error) {
      throw error;
    }
  };

  const apiService = {
    getAll,
    save,
    update,
    getDetail,
    getReadingDetail,
    getReadingsByBatch,
    getReadingsByBatchMinimal,
    getTemplate,
    getPermissions,
    validate,
    process,
    reprocess,
  }

  nuxtApp.provide(provideName, apiService);
});
