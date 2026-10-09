// plugins/services/coredata/person-api.js
export default defineNuxtPlugin(nuxtApp => {
  const entity = '/coredata/person/';
  const provideName = 'PersonApiService';

  const config = useRuntimeConfig();
  const {$apiManager} = useNuxtApp()

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

  const getDetailByToken = async (token) => {
    const apiUrl = apiHost + entity + 'token/' + token + '/';

    try {

      const response = await $apiManager.fetch(apiUrl, 'GET');
      return response;
    } catch (error) {
      throw error;
    }
  };

  const getCommunicationDetail = async (data) => {
    const apiUrl = apiHost + entity + 'communication-detail/';
    try {
      const response = await $apiManager.fetch(apiUrl, 'POST', data);
      return response;
    } catch (error) {
      throw error;
    }
  };

  const getAll = async (searchQuery = '', filters = [], page = 1, sort = null, desc = false , juridicFilter = []) => {
    let apiUrl = apiHost + entity + '?search=' + encodeURIComponent(searchQuery) + `&page=${page}`;

    // Afegir els filtres a la URL
    let filtersValues = [];
    if (filters.length > 0) {
      filters.map(filter => {
        filtersValues.push(filter);
      });
    }

    if (juridicFilter.length > 0) {
      apiUrl += `&is_juridic=${juridicFilter[0]}`;
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
  };

  const exportData = async (searchQuery = '', filters = [], sort = null, desc = false, juridicFilter = [], columns = []) => {
    return $apiManager.exportTable(entity, {
      searchQuery, filters, sort, desc, columns,
      extraParams: {
        is_juridic: juridicFilter.length > 0 ? juridicFilter[0] : null,
      }
    });
  };

  const save = async (person, suppressToast = false) => {
    const apiUrl = apiHost + entity;

    const is_created = person.id ? false : true;
    const method = is_created ? 'POST' : 'PATCH';
    const id = person.id ? person.id : '';
    const url = is_created ? apiUrl : `${apiUrl}${id}/`;

    try {

      const response = await $apiManager.fetch(url, method, JSON.stringify(person), null, suppressToast);
      return response;
    } catch (error) {
      throw error;
    }
  };
  const postCNAE = async (person) => {
    const apiUrl = apiHost + '/coredata/person-cnae/';

    try {
      const response = await $apiManager.fetch(apiUrl, 'POST', JSON.stringify(person));
      return response;
    } catch (error) {
      throw error;
    }
  };
  
  const deletePerson = async (id) => {
    const apiUrl = apiHost + entity + id + '/';

    try {
      const response = await $apiManager.fetch(apiUrl,'DELETE')
      
      return response;
    } catch (error) {
      throw error;
    }
  };

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

  const addBalance = async (id, data) => {
    const apiUrl = `${apiHost}${entity}${id}/add-balance/`;
    try {
      const response = await $apiManager.fetch(apiUrl, 'PUT', data, { 'Content-Type': 'application/json' })
      return response;
    } catch (error) {
      throw error;
    }
  }

  const getPersonInvoices = async (id) => {
    const apiUrl = `${apiHost}${entity}${id}/invoices/`;
    try {
      const response = await $apiManager.fetch(apiUrl, 'GET');
      return response;
    } catch (error) {
      throw error;
    }
  }

  const getLogs = async (id) => {
    const apiUrl = `${apiHost}${entity}${id}/logs/`;
    try {
      const response = await $apiManager.fetch(apiUrl, 'GET');
      return response;
    } catch (error) {
      throw error;
    }
  }

  const getFullDetail = async (id) => {
    try {
      const person = await getDetail(id);
      if (!person) return null;

      const [addrRes, bankRes, contactRes, cnaeRes] = await Promise.all([
        $apiManager.fetch(`${apiHost}/coredata/person-address/?person=${id}`, 'GET'),
        $apiManager.fetch(`${apiHost}/coredata/person-bank/?person=${id}`, 'GET'),
        $apiManager.fetch(`${apiHost}/coredata/person-contact/?person=${id}`, 'GET'),
        $apiManager.fetch(`${apiHost}/coredata/person-cnae/?person=${id}`, 'GET')
      ]);

      person.addresses = addrRes.results || [];
      person.banks = bankRes.results || [];
      person.contacts = contactRes.results || [];
      person.cnaes = cnaeRes.results || [];

      return person;
    } catch (error) {
      throw error;
    }
  }

  const getFullDetailByToken = async (token) => {
    try {
      const person = await getDetailByToken(token);
      if (!person) return null;

      const id = person.id;
      const [addrRes, bankRes, contactRes, cnaeRes] = await Promise.all([
        $apiManager.fetch(`${apiHost}/coredata/person-address/?person=${id}`, 'GET'),
        $apiManager.fetch(`${apiHost}/coredata/person-bank/?person=${id}`, 'GET'),
        $apiManager.fetch(`${apiHost}/coredata/person-contact/?person=${id}`, 'GET'),
        $apiManager.fetch(`${apiHost}/coredata/person-cnae/?person=${id}`, 'GET')
      ]);

      person.addresses = addrRes.results || [];
      person.banks = bankRes.results || [];
      person.contacts = contactRes.results || [];
      person.cnaes = cnaeRes.results || [];

      return person;
    } catch (error) {
      throw error;
    }
  }

  const apiService = {
    getAll,
    exportData,
    getDetail,
    getFullDetail,
    getDetailByToken,
    getFullDetailByToken,
    save,
    postCNAE,
    deletePerson,
    getCommunicationDetail,
    addBalance,
    getPersonInvoices,
    getLogs,
    getPermissions
  };

  nuxtApp.provide(provideName, apiService);
});
