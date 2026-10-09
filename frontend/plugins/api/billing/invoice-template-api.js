// plugins/services/pricing/price-rate-api.js
export default defineNuxtPlugin(nuxtApp => {
    const entity = '/billing/invoice-template/';
    const provideName = 'InvoiceTemplateApiService';
  
    const {$apiManager} = useNuxtApp()
    const config = useRuntimeConfig();
    const apiHost = config.public.apiHost;
  
    const getAll = async (searchQuery = '',filters = [] , page = 1, sort = null, desc = false) => {
      let apiUrl = apiHost + entity + '?search=' + encodeURIComponent(searchQuery) + `&page=${page}`;
  
      let filtersValues = [];
      if (filters.length > 0) {
        filters.map(filter => {
          filtersValues.push(filter);
        })
      }
  
      if (filtersValues.length > 0) {
        apiUrl += `&status=${filtersValues.join(',')}`;
      }
  
      if( sort ) {
        apiUrl += `&ordering=${desc ? '-' : ''}${sort}`;
      }

  
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
    
    const exportData = async (searchQuery = '', filters = [], sort = null, desc = false, columns = []) => {
      return $apiManager.exportTable(entity, { searchQuery, filters, sort, desc, columns });
    }

    const save = async (data) => {
      let apiUrl = `${apiHost}${entity}`;
      try {
        const method = data.id ? 'PUT' : 'POST';
        if (method == 'PUT') {
          apiUrl += data.id + '/';
        }
        let response = null;
        if(data.file_template_html){
          const formData = new FormData();
          formData.append('id', data.id); 
          formData.append('file_template_html', data.file_template_html);
          let options = formData;
          response = await $apiManager.fetch(apiUrl, method, options)
        }else{
          response = await $apiManager.fetch(apiUrl, method, data, { 'Content-Type': 'application/json' })
        }

        if (response) {
          return response;
        } else {
          throw new Error('Error no trobat');
        }
      } catch (error) {
        throw error;
      }
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
    }
    
    const getTemplatePDF = async (data) => {
      const apiUrl = `${apiHost}/billing/download-template/`;
  
      try {
        const response = await $apiManager.fetch(apiUrl, 'POST', data, { 'Content-Type': 'application/json' })
        
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
      getAll,
      exportData,
      save,
      getDetail,
      getTemplatePDF,
    }
  
    nuxtApp.provide(provideName, apiService);
  });
  