export default defineNuxtPlugin(nuxtApp => {
    const entity = '/auth/group/';
    const provideName = 'GroupApiService';

    const {$apiManager} = useNuxtApp()
    const config = useRuntimeConfig();
    const apiHost = config.public.apiHost;
  
    const getAll = async (page = 1) => {
      let apiUrl = apiHost + entity + `?page=${page}`;
      
      try {
        const response = await $apiManager.fetch(apiUrl,'GET');
        if (response.results) {
          return response;
        } else {
          throw new Error('Error estructura `results` no trobat');
        }
      } catch (error) {
        throw error;
      }
    }
  
    // Server-side export (async). Mirrors getAll (no page) and POSTs to
    // `{entity}export/` so the backend builds the full XLSX as a background
    // task, returning `{ task_id }`.
    const exportData = async (columns = []) => {
      return $apiManager.exportTable(entity, { columns });
    }

    const getDetail = async (id) => {
      const apiUrl = `${apiHost}${entity}${id}/`;
  
      try {
        const response = await $apiManager.fetch(apiUrl,'GET');
        
        if (response) {
          return response;
        } else {
          throw new Error('Error estructura `results` no trobat');
        }
      } catch (error) {
        throw error;
      }
    };
    
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
      getAll,
      exportData,
      getDetail,
      save
    };
  
    nuxtApp.provide(provideName, apiService);
  });
  