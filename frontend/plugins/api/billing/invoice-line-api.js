// plugins/services/pricing/price-rate-api.js
export default defineNuxtPlugin(nuxtApp => {
    const entity = '/billing/invoice-line-item/';
    const provideName = 'InvoiceApiService';
  
    const {$apiManager} = useNuxtApp()
    const config = useRuntimeConfig();
    const apiHost = config.public.apiHost;
  
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
    
    const apiService = {
      save
    }
  
    nuxtApp.provide(provideName, apiService);
  });
  