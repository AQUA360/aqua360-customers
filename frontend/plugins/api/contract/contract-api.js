// plugins/services/contract/contract-api.js
export default defineNuxtPlugin(nuxtApp => {
  const entity = '/contract/contract/';
  const provideName = 'ContractApiService';


  const { $apiManager } = useNuxtApp()
  const config = useRuntimeConfig();
  const apiHost = config.public.apiHost;

  const getAll = async (searchQuery = '', filters = [], page = 1, sort = null, desc = false,
    variable_type_id = [], bonification_type_id = [],
    client_type_ids = [], use_type_ids = [], category_ids = [],
    product_ids = [], debt_management_types = [], is_checked = false,
    comm_types = [], search_all_address = '', payment_type_ids = [], person_ids = [], search_by_address = '', total_persons_min = null,
    company_ids = [], holder = null, role = null, block_billing = null, has_debt = null, search_email = '', search_iban = '', search_meter = '') => {
    let apiUrl = apiHost + entity + '?search=' + encodeURIComponent(searchQuery) + `&page=${page}`;
  
    if (role) {
      apiUrl += `&role=${role}`;
    }

    if (holder) {
      apiUrl += `&holder=${holder}`;
    }
  
    if (total_persons_min) {
      apiUrl += `&total_persons_min=${total_persons_min}`;
    }

    if (company_ids?.length > 0) {
      apiUrl += `&company=${company_ids.join(',')}`;
    }

    if (block_billing !== null) {
      apiUrl += `&block_billing=${block_billing}`;
    }

    if (has_debt !== null) {
      apiUrl += `&has_debt=${has_debt}`;
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

    if (variable_type_id?.length > 0) {
      apiUrl += `&variable_type=${variable_type_id.join(',')}`;
    }

    if (bonification_type_id?.length > 0) {
      apiUrl += `&bonification_type=${bonification_type_id.join(',')}`;
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

    if (product_ids?.length > 0) {
      apiUrl += `&product=${productids.join(',')}`;
    }

    if (debt_management_types?.length > 0) {
      apiUrl += `&debt_management=${debt_management_types.join(',')}`;
    }

    if (is_checked) {
      apiUrl += `&is_checked=${is_checked}`;
    }

    if (comm_types?.length > 0) {
      apiUrl += `&communication_type=${comm_types.join(',')}`;
    }

    if (search_all_address) {
      apiUrl += `&search_all_address=${encodeURIComponent(search_all_address)}`;
    }

    if (payment_type_ids?.length > 0) {
      apiUrl += `&payment_type=${payment_type_ids.join(',')}`;
    }

    if (person_ids?.length > 0) {
      apiUrl += `&persons=${person_ids.join(',')}`;
    }

    if (search_by_address) {
      apiUrl += `&search_by_address=${encodeURIComponent(search_by_address)}`;
    }

    if (search_email) {
      apiUrl += `&search_email=${encodeURIComponent(search_email)}`;
    }

    if (search_iban) {
      apiUrl += `&search_iban=${encodeURIComponent(search_iban)}`;
    }

    if (search_meter) {
      apiUrl += `&search_meter=${encodeURIComponent(search_meter)}`;
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

  const getPinnedContract = async (id) => {
    const apiUrl = `${apiHost}${entity}${id}/pinned/`;
    try {
      const response = await $apiManager.fetch(apiUrl, 'GET')
      return response;
    } catch (error) {
      throw error;
    }
  }

  const getPinnedContractData = async (id) => {
    const apiUrl = `${apiHost}${entity}${id}/pinned-full/`;
    try {
      const response = await $apiManager.fetch(apiUrl, 'GET')
      return response;
    } catch (error) {
      throw error;
    }
  }

  const getFilterStatus = async () => {
    const apiUrl = apiHost + '/contract/contract-status/';

    try {
      const response = await $apiManager.fetch(apiUrl, 'GET')
      if (response.results) {
        return response.results;
      } else {
        throw new Error('Error estructura `results` no trobat');
      }
    } catch (error) {
      throw error;
    }
  }


  // Contractes on la persona és titular, propietària o llogatera. El detall de la persona
  // ja no inclou aquestes llistes (PersonSerializer, backend 8bdf35fd).
  const getByPerson = async (personId) => {
    const apiUrl = `${apiHost}${entity}?persons=${personId}`;
    try {
      const response = await $apiManager.fetch(apiUrl, 'GET');
      return response?.results || [];
    } catch (error) {
      throw error;
    }
  }


  // Contracte pel seu token exacte (o null si no existeix).
  const getByToken = async (token) => {
    const apiUrl = `${apiHost}${entity}?token=${encodeURIComponent(token)}`;
    try {
      const response = await $apiManager.fetch(apiUrl, 'GET');
      return response?.results?.[0] || null;
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

  /** GET lleuger per al formulari de modificació de dades del contracte. */
  const getDataChangeDetail = async (id) => {
    const apiUrl = `${apiHost}${entity}${id}/data-change/`;
    try {
      const response = await $apiManager.fetch(apiUrl, 'GET');
      if (response) {
        return response;
      }
      throw new Error('Error estructura de resposta no trobada');
    } catch (error) {
      throw error;
    }
  }


  const getAllByHolder = async (holder_id) => {
    const apiUrl = `${apiHost}${entity}${holder_id}/contracts/`;

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

  const getMinimalDetail = async (id) => {
    const apiUrl = `${apiHost}${entity}${id}/minimal/`;

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

  const getDocument = async (id, is_contract = false) => {
    const apiUrl = `${apiHost}/contract/download/${id}/?is_contract=${is_contract}`;

    try {
      const response = await $apiManager.fetch(apiUrl, 'GET', null, { 'Content-Type': 'application/pdf' })
      if (response) {
        return response;
      } else {
        throw new Error('Error estructura `results` no trobat');
      }
    } catch (error) {
      throw error;
    }
  }

  const getCommunicationPdf = async (id, use_type_id, contract_type_id = null) => {
    let apiUrl = `${apiHost}${entity}${id}/communication-pdf/`;
    if (use_type_id) {
      apiUrl += `?use_type=${use_type_id}`;
    }
    if (contract_type_id) {
      apiUrl += `${apiUrl.includes('?') ? '&' : '?'}contract_type=${contract_type_id}`;
    }
    try {
      const response = await $apiManager.fetch(apiUrl, 'GET', null, { 'Content-Type': 'application/pdf' });
      if (response) {
        return response;
      } else {
        throw new Error('Error estructura `results` no trobat');
      }
    } catch (error) {
      throw error;
    }
  }

  const getFromExpiredInvoices = async (use_types = [], client_types = [], zones = [], debt_management_types = [], status = [], origins = [], date_start = null, date_end = null) => {
    let apiUrl = `${apiHost}${entity}?expired=true`;

    if (use_types.length > 0) {
      apiUrl += `&use_type=${use_types.join(',')}`;
    }

    if (client_types.length > 0) {
      apiUrl += `&client_type=${client_types.join(',')}`;
    }

    if (zones.length > 0) {
      apiUrl += `&zone=${zones.join(',')}`;
    }

    if (debt_management_types.length > 0) {
      apiUrl += `&debt_management=${debt_management_types.join(',')}`;
    }

    if (status.length > 0) {
      apiUrl += `&status=${status.join(',')}`;
    }

    if (date_start) {
      apiUrl += `&start_at=${date_start}`;
    }

    if (date_end) {
      apiUrl += `&end_at=${date_end}`;
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

  const getBySupplyPoint = async (id) => {
    const apiUrl = `${apiHost}${entity}?supply_point=${id}`;

    try {
      const response = await $apiManager.fetch(apiUrl, 'GET')
      if (response && response.results) {
        return response.results;
      } else {
        throw new Error('Error estructura `results` no trobat');
      }
    } catch (error) {
      throw error;
    }
  }

  const save = async (data, options = {}) => {
    let apiUrl = `${apiHost}${entity}`;
    try {
      const method = data.id ? 'PUT' : 'POST';
      if (method == 'PUT') {
        apiUrl += data.id + '/';
        if (options.dataChangeEdit) {
          apiUrl += '?edit=data-change';
        }
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

  const saveFile = async (data) => {
    let apiUrl = `${apiHost}${entity}${data.id}/save-file/`;
    try {
      let options;
      if (data.file) {
        const formData = new FormData();
        formData.append('file', data.file);
        formData.append('id', data.id);
        formData.append('is_contract', data.is_contract);
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

  const changeTenant = async (data) => {
    const apiUrl = `${apiHost}/contract/contract-tenant-change/`;
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

  const changeData = async (data) => {
    const apiUrl = `${apiHost}/contract/contract-data-change/`;
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

  const manageMassively = async (data) => {
    let apiUrl = `${apiHost}/contract/contract-manage/`;
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
  const doDelete = async (data) => {
    const apiUrl = `${apiHost}${entity}${data.id}/`;
    try {
      await $apiManager.fetch(apiUrl, 'DELETE');
    } catch (error) {
      throw error;
    }
  }

  const toggleBillable = async (id) => {
    let apiUrl = `${apiHost}${entity}`;
    try {
      apiUrl += id + '/toggle-billable/';
      const response = await $apiManager.fetch(apiUrl, 'PUT', {}, { 'Content-Type': 'application/json' })
      if (response) {
        return response;
      } else {
        throw new Error('Error no trobat');
      }
    } catch (error) {
      throw error;
    }
  }

  const setBopPriceRate = async (id, contractPriceRateId) => {
    let apiUrl = `${apiHost}${entity}${id}/set-bop-price-rate/`;
    try {
      const response = await $apiManager.fetch(apiUrl, 'PUT', { contract_price_rate_id: contractPriceRateId }, { 'Content-Type': 'application/json' })
      if (response) {
        return response;
      } else {
        throw new Error('Error no trobat');
      }
    } catch (error) {
      throw error;
    }
  }

  const processBankChange = async (data) => {
    const apiUrl = `${apiHost}${entity}bank-change/`;
    try {
      let options;
      const formData = new FormData();
      formData.append('file', data.file);
      formData.append('save', data.save);
      options = formData;
      const response = await $apiManager.fetch(apiUrl, 'POST', options)
      if (response) {
        return response;
      } else {
        throw new Error('Error no trobat');
      }
    } catch (error) {
      throw error;
    }
  }

  const getLogs = async (id) => {
    const apiUrl = `${apiHost}${entity}${id}/logs/`;
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

  const exportExcel = async (
    searchQuery = '', filters = [], sort = null, desc = false,
    variable_type_id = [], bonification_type_id = [],
    client_type_ids = [], use_type_ids = [], category_ids = [],
    product_ids = [], debt_management_types = [], is_checked = false,
    comm_types = [], search_all_address = '', payment_type_ids = [],
    person_ids = [], search_by_address = '', total_persons_min = null, company_ids = [],
    block_billing = null, has_debt = null, search_email = '', search_iban = '', search_meter = ''
  ) => {
    let apiUrl = apiHost + entity + 'export/excel/';
    let queryParams = [];

    if (searchQuery) {
      queryParams.push('search=' + encodeURIComponent(searchQuery));
    }

    if (filters?.length > 0) {
      queryParams.push(`status=${filters.join(',')}`);
    }

    if (sort) {
      queryParams.push(`ordering=${desc ? '-' : ''}${sort}`);
    }

    if (variable_type_id?.length > 0) {
      queryParams.push(`variable_type=${variable_type_id.join(',')}`);
    }

    if (bonification_type_id?.length > 0) {
      queryParams.push(`bonification_type=${bonification_type_id.join(',')}`);
    }

    if (category_ids?.length > 0) {
      queryParams.push(`category=${category_ids.join(',')}`);
    }

    if (use_type_ids?.length > 0) {
      queryParams.push(`use_type=${use_type_ids.join(',')}`);
    }

    if (client_type_ids?.length > 0) {
      queryParams.push(`client_type=${client_type_ids.join(',')}`);
    }

    if (product_ids?.length > 0) {
      queryParams.push(`product=${product_ids.join(',')}`);
    }

    if (debt_management_types?.length > 0) {
      queryParams.push(`debt_management=${debt_management_types.join(',')}`);
    }

    if (is_checked) {
      queryParams.push(`is_checked=${is_checked}`);
    }

    if (comm_types?.length > 0) {
      queryParams.push(`communication_type=${comm_types.join(',')}`);
    }

    if (search_all_address) {
      queryParams.push(`search_all_address=${encodeURIComponent(search_all_address)}`);
    }

    if (payment_type_ids?.length > 0) {
      queryParams.push(`payment_type=${payment_type_ids.join(',')}`);
    }

    if (person_ids?.length > 0) {
      queryParams.push(`persons=${person_ids.join(',')}`);
    }

    if (search_by_address) {
      queryParams.push(`search_by_address=${encodeURIComponent(search_by_address)}`);
    }

    if (total_persons_min) {
      queryParams.push(`total_persons_min=${total_persons_min}`);
    }

    if (company_ids?.length > 0) {
      queryParams.push(`company=${company_ids.join(',')}`);
    }

    if (block_billing !== null) {
      queryParams.push(`block_billing=${block_billing}`);
    }

    if (has_debt !== null) {
      queryParams.push(`has_debt=${has_debt}`);
    }

    if (search_email) {
      queryParams.push(`search_email=${encodeURIComponent(search_email)}`);
    }

    if (search_iban) {
      queryParams.push(`search_iban=${encodeURIComponent(search_iban)}`);
    }

    if (search_meter) {
      queryParams.push(`search_meter=${encodeURIComponent(search_meter)}`);
    }

    let exploitation_id = localStorage.getItem('exploitation');
    if (exploitation_id) {
      queryParams.push(`exploitation=${exploitation_id}`);
    }

    if (queryParams.length > 0) {
      apiUrl += '?' + queryParams.join('&');
    }

    const authToken = localStorage.getItem('auth_token') || '';

    try {
      const response = await $fetch(apiUrl, {
        method: 'GET',
        headers: {
          'Authorization': `Token ${authToken}`
        }
      });

      return response;
    } catch (error) {
      if (error?.response?.status === 401) {
        const message = error?.response?._data?.detail || error?.data?.detail || error?.response?._data?.message || error?.data?.message || error?.message;
        await $apiManager.handleUnauthorized(message);
      }
      throw error;
    }
  }

  const addBalance = async (id, data) => {
    const apiUrl = `${apiHost}${entity}${id}/add-balance/`;
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

  const generateSepaDocumentNoDirect = async (contractId, data = {}, options = {}) => {
    let apiUrl = `${apiHost}/billing/contract/${contractId}/sepa/`;
    if (options.is_request) {
      apiUrl += '?is_request=true';
    }
    try {
      const response = await $apiManager.fetch(apiUrl, 'POST', data, { 'Content-Type': 'application/json' });
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
    getDetail,
    getByPerson,
    getByToken,
    getDataChangeDetail,
    getMinimalDetail,
    getPinnedContract,
    getPinnedContractData,
    save,
    manageMassively,
    changeTenant,
    doDelete,
    getDocument,
    getCommunicationPdf,
    getFilterStatus,
    changeData,
    getBySupplyPoint,
    getFromExpiredInvoices,
    toggleBillable,
    setBopPriceRate,
    processBankChange,
    getLogs,
    saveFile,
    getAllByHolder,
    getPermissions,
    exportExcel,
    addBalance,
    generateSepaDocumentNoDirect,
  };

  nuxtApp.provide(provideName, apiService);
});
