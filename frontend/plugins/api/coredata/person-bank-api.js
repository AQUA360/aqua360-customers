// plugins/services/coredata/person-address-api.js
export default defineNuxtPlugin(nuxtApp => {
  const entity = '/coredata/person-bank/';
  const provideName = 'PersonBankApiService';

  const config = useRuntimeConfig();
  const {$apiManager} = useNuxtApp()

  const apiHost = config.public.apiHost;
 
  const save = async (data) => {
    const apiUrl = apiHost + entity;

    const is_created = data.id ? false : true;
    const method = is_created ? 'POST' : 'PUT';
    const id = data.id ? data.id : '';
    const url = is_created ? apiUrl : `${apiUrl}${id}/`;

    try {

      const response = await $apiManager.fetch(url, method, JSON.stringify(data));
      return response;
    } catch (error) {
      throw error;
    }
  };
   

  /**
   * Resol el compte a assignar des d'un context de contracte/factura sense
   * modificar cap fila existent: si la persona ja té un compte actiu amb aquest
   * IBAN el retorna tal com està (`reused: true`), i si no en crea un de nou.
   * Un PersonBank el poden compartir diversos contractes, per això aquí no
   * s'hi fa mai PUT.
   */
  const resolve = async (data) => {
    const apiUrl = `${apiHost}${entity}resolve/`;
    try {
      const response = await $apiManager.fetch(apiUrl, 'POST', data, { 'Content-Type': 'application/json' });
      return response;
    } catch (error) {
      throw error;
    }
  };

  const getAll = async (personId) => {
    const apiUrl = `${apiHost}${entity}?person=${personId}`;
    try {
      const response = await $apiManager.fetch(apiUrl, 'GET');
      return response;
    } catch (error) {
      throw error;
    }
  }

  const apiService = { 
    save,
    resolve,
    getAll
  };

  nuxtApp.provide(provideName, apiService);
});
