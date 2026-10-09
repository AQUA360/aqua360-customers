// plugins/services/contract/contract-request-type-api.js
export default defineNuxtPlugin(nuxtApp => {
  const entity = '/contract/contract-request-type/';
  const provideName = 'ContractRequestTypeApiService';


  const { $apiManager } = useNuxtApp()
  const config = useRuntimeConfig();
  const apiHost = config.public.apiHost;

  const getAll = async (searchQuery = '', filters = [], page = 1, sort = null, desc = false, noSupplyPoint = false, exclude = null, token = null, exploitation = null) => {
    let apiUrl = apiHost + entity + '?search=' + encodeURIComponent(searchQuery) + `&page=${page}`;

    if (noSupplyPoint) {
      apiUrl += `&no_supply_points=true`;
    }

    if (exclude) {
      apiUrl += `&exclude=${exclude}`;
    }

    if (token) {
      apiUrl += `&token=${encodeURIComponent(token)}`;
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

    let exploitation_id = localStorage.getItem('exploitation');
    if (exploitation) {
      exploitation_id = exploitation;
    }
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

  // Resol dinàmicament un ContractRequestType pel seu `token` (p. ex. 'canvi_nom'),
  // en lloc de dependre d'un id fix que pot variar entre entorns.
  const getByToken = async (token) => {
    let page = 1;
    let hasNext = true;
    while (hasNext && page < 50) {
      const data = await getAll('', [], page, null, false, false, null, token);
      const match = data.results?.find(r => r.token === token);
      if (match) {
        return match;
      }
      hasNext = !!data.next;
      page += 1;
    }
    return null;
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
    getByToken,
    getDetail,
    save,
    doDelete
  };

  nuxtApp.provide(provideName, apiService);
});
