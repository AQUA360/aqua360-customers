
export default defineNuxtPlugin(nuxtApp => {
  const config = useRuntimeConfig();
  const apiHost = config.public.apiHost;

  const {$apiManager} = useNuxtApp()
  const apiService = {
    newItem(entity, property, value, parent_entity = null, parent_id = null, related_id = null) {
      const apiUrl = `${apiHost}/${entity}/`;
      console.log("new")
      let item = {};
      item[property] = value;
      item['name'] = value;
      if( parent_entity && parent_id ) {
        item[parent_entity] = parent_id;
      }
      if( related_id ) {
        item['related_id'] = related_id;
      }
      console.log(item)
      return $apiManager.fetch(apiUrl, 'POST', item);
    },
    
    updateValue(entity, property, id, value) {
      if(value === ''){
        value = null;
      }
      const authToken = localStorage.getItem('auth_token') || '';
      const apiUrl = `${apiHost}/${entity}/${id}/`;
      let item = {};
      item[property] = value;
      return $apiManager.fetch(apiUrl, 'PUT', item);
    }
  };

  // Proveeix l'objecte `apiService` a tota l'aplicació
  nuxtApp.provide('apiService', apiService);
});
