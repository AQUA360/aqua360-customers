// plugins/services/order/order-type-api.js
export default defineNuxtPlugin(nuxtApp => {
    const entity = '/documentmanager/';
    const provideName = 'DocumentManagerApiService';
  
  
    const { $apiManager } = useNuxtApp()
    const config = useRuntimeConfig();
    const apiHost = config.public.apiHost;

    
    const getDetail = async (id) => {
        const apiUrl = `${apiHost}${entity}document/${id}/`;
    
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

    const viewDocument = async (id) => {
      const apiUrl = `${apiHost}${entity}view-document/${id}/`;
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

    const deleteItems = async (data) => {
      const apiUrl = `${apiHost}${entity}delete-document/`;

      try {
        const response = await $apiManager.fetch(apiUrl, 'POST', data);
        return true;
  
      } catch (error) {
        throw error;
      }
    }

    const downloadDocuments = async (data) => {
      const apiUrl = `${apiHost}${entity}download-documents/`;
      try {
        const response = await $apiManager.fetch(apiUrl, 'POST', data);
        if (response) {
          return response;
        } else {
          throw new Error('Error estructura `results` no trobat');
        }
      } catch (error) {
        throw error;
      }
    }

    const downloadSinglePdfDocument = async (data) => {
      const apiUrl = `${apiHost}${entity}download-single-pdf-document/`;
      try {
        const response = await $apiManager.fetch(apiUrl, 'POST', data);
        if (response) {
          return response;
        } else {
          throw new Error('Error estructura `results` no trobat');
        }
      } catch (error) {
        throw error;
      }
    }
  
    const apiService = {
      getDetail,
      viewDocument,
      deleteItems,
      downloadDocuments,
      downloadSinglePdfDocument,
    };
  
    nuxtApp.provide(provideName, apiService);
  });
  