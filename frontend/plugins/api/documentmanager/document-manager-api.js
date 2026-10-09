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

    const uploadDocument = async (data) => {
      const formData = new FormData();
      formData.append('file', data.file);
      formData.append('entity', data.entity);
      formData.append('field', data.field);
      formData.append('entity_id', data.entity_id);
      formData.append('entity_name', data.entity_name);
      formData.append('folder', data.folder);
      formData.append('service', data.service);
      formData.append('document_name', data.document_name);
      const apiUrl = `${apiHost}${entity}upload-document/`;
  
      try {
        const response = await $apiManager.fetch(apiUrl, 'POST', formData)
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
      uploadDocument,
      viewDocument,
      deleteItems,
      downloadDocuments,
      downloadSinglePdfDocument,
    };
  
    nuxtApp.provide(provideName, apiService);
  });
  