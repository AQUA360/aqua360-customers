// plugins/services/contract/bonification-type-api.js
export default defineNuxtPlugin(nuxtApp => {
  const entity = '/contract/bonification-type/';
  const provideName = 'BonificationTypeApiService';


  const { $apiManager } = useNuxtApp()
  const config = useRuntimeConfig();
  const apiHost = config.public.apiHost;

  const getAll = async (searchQuery = '', filters = [], page = 1, sort = null, desc = false, noSupplyPoint = false, exclude = null) => {
    let apiUrl = apiHost + entity + '?search=' + encodeURIComponent(searchQuery) + `&page=${page}`;

    if (noSupplyPoint) {
      apiUrl += `&no_supply_points=true`;
    }

    if (exclude) {
      apiUrl += `&exclude=${exclude}`;
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
      const method = data.id ? 'PUT' : 'POST';
      if( method == 'PUT' ){
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
    doDelete
  };

  nuxtApp.provide(provideName, apiService);
});
