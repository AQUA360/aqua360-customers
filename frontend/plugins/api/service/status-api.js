// plugins/services/service/configlist-api.js
import { useToast } from 'vue-toastification'
export default defineNuxtPlugin(nuxtApp => {
  const entity_base = '/service/';
  const provideName = 'StatusApiService';
  const toast = useToast()
  const { $apiManager } = useNuxtApp()
  const config = useRuntimeConfig();
  const apiHost = config.public.apiHost;

  const getAll = async (entity, module = null) => {
    entity = (module != null ? `/${module}/` : entity_base) + entity + '/';
    let apiUrl = apiHost + entity + '?ordering=position';

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

  const save = async (entity, id, data, module = null) => {
    entity =  (module != null ? `/${module}/` : entity_base) + entity + '/';
    let apiUrl = apiHost + entity + id + '/';
    try {
      const response = await $apiManager.fetch(apiUrl, 'PUT', JSON.stringify(data), { 'Content-Type': 'application/json' });
      if (response && response.check_response && response.check_response.status == 'success') {
        toast.success(response.check_response.message);
      }
      return response;
    } catch (error) {
      throw error;
    }
  }

  const apiService = {
    getAll,
    save
  }

  nuxtApp.provide(provideName, apiService);
});
