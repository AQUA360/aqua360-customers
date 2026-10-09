export default defineNuxtPlugin(nuxtApp => {
  const entity = '/billing/contract-estimation/';
  const provideName = 'ContractEstimationApiService';

  const { $apiManager } = useNuxtApp()
  const config = useRuntimeConfig();
  const apiHost = config.public.apiHost;

  const getContractsForEstimation = async (batch_template_id = null, last_invoice_date_start = null, last_invoice_date_end = null) => {
    let apiUrl = `${apiHost}${entity}`;
    const params = new URLSearchParams();
    
    if (batch_template_id) {
      if (Array.isArray(batch_template_id)) {
        batch_template_id.forEach(id => params.append('batch_template_id', id));
      } else if (typeof batch_template_id === 'string' && batch_template_id.includes(',')) {
        batch_template_id.split(',').forEach(id => params.append('batch_template_id', id.trim()));
      } else {
        params.append('batch_template_id', batch_template_id);
      }
    }
    
    if (last_invoice_date_start) params.append('last_invoice_date_start', last_invoice_date_start);
    if (last_invoice_date_end) params.append('last_invoice_date_end', last_invoice_date_end);
    
    const queryString = params.toString();
    if (queryString) {
      apiUrl += `?${queryString}`;
    }

    try {
      const response = await $apiManager.fetch(apiUrl, 'GET');
      return response;
    } catch (error) {
      throw error;
    }
  };

  const createMassiveEstimation = async (data) => {
    let apiUrl = `${apiHost}${entity}`;
    try {
      const response = await $apiManager.fetch(apiUrl, 'POST', data, { 'Content-Type': 'application/json' });
      return response;
    } catch (error) {
      throw error;
    }
  };

  const apiService = {
    getContractsForEstimation,
    createMassiveEstimation,
  };

  nuxtApp.provide(provideName, apiService);
});
