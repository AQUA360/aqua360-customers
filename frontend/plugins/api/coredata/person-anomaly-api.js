// plugins/api/coredata/person-anomaly-api.js
// Anomalies de la persona (DNI/CIF incorrecte, IBAN incorrecte, difunt, insolvent...)
export default defineNuxtPlugin(nuxtApp => {
  const entity = '/coredata/person-anomaly/';
  const typeEntity = '/coredata/person-anomaly-type/';
  const provideName = 'PersonAnomalyApiService';

  const config = useRuntimeConfig();
  const { $apiManager } = useNuxtApp();

  const apiHost = config.public.apiHost;

  const getAll = async (personId) => {
    return await $apiManager.fetch(`${apiHost}${entity}?person_id=${personId}`, 'GET');
  };

  const getTypes = async () => {
    return await $apiManager.fetch(`${apiHost}${typeEntity}`, 'GET');
  };

  const save = async (data) => {
    const url = data.id ? `${apiHost}${entity}${data.id}/` : `${apiHost}${entity}`;
    const method = data.id ? 'PATCH' : 'POST';
    return await $apiManager.fetch(url, method, data);
  };

  const resolve = async (id, endDate = null) => {
    const body = endDate ? { end_date: endDate } : {};
    return await $apiManager.fetch(`${apiHost}${entity}${id}/resolve/`, 'POST', body);
  };

  const remove = async (id) => {
    return await $apiManager.fetch(`${apiHost}${entity}${id}/`, 'DELETE');
  };

  nuxtApp.provide(provideName, { getAll, getTypes, save, resolve, remove });
});
