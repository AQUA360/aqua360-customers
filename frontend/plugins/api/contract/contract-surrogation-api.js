// plugins/services/contract/contract-surrogation-api.js
export default defineNuxtPlugin(nuxtApp => {
  const entity = '/contract/contract-surrogation/';
  const provideName = 'ContractSurrogationApiService';


  const { $apiManager } = useNuxtApp()
  const config = useRuntimeConfig();
  const apiHost = config.public.apiHost;

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

  const saveDocument = async (data) => {
    const apiUrl = `${apiHost}/contract/contract-surrogation-document/`;

    const is_created = data.id ? false : true;
    const method = is_created ? 'POST' : 'PUT';
    const id = data.id ? data.id : '';
    const url = is_created ? apiUrl : `${apiUrl}${id}/`;

    const formData = new FormData();

    // Append all fields from data to formData
    for (const key in data) {
      if (data[key] != "" && data[key] != null) {
        formData.append(key, data[key]);
      }
    }

    try {
      const response = await $apiManager.fetch(url, method, formData);
      if (response) {
        return response;
      } else {
        throw new Error('Error no hi ha resposta');
      }
    } catch (error) {
      throw error;
    }
  };

  const deleteDocument = async (id) => {
    const apiUrl = `${apiHost}/contract/contract-surrogation-document/${id}/`;

    try {
      const response = await $apiManager.fetch(apiUrl, 'DELETE');
      return response;
    }
    catch (error) {
      throw error;
    }
  };

  
  
  const doDelete = async (data ) => {
    const apiUrl = `${apiHost}${entity}${data.id}/`;
    try {
      await $apiManager.fetch(apiUrl, 'DELETE');
    } catch (error) {
      throw error;
    }
  } 

  const apiService = {
    save,
    saveDocument,
    deleteDocument,
    doDelete
  };

  nuxtApp.provide(provideName, apiService);
});
