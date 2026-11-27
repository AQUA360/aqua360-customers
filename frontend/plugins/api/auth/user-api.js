export default defineNuxtPlugin(nuxtApp => {
    const entity = '/auth/user/';
    const provideName = 'UserApiService';

    const {$apiManager} = useNuxtApp()
    const config = useRuntimeConfig();
    const apiHost = config.public.apiHost;
  
    const getAll = async (searchQuery = '', page = 1, groups = [], no_groups = [], hide_admin = false) => {
      let apiUrl = apiHost + entity + `?page=${page}`;
      if (searchQuery) {
        apiUrl += `&search=${searchQuery}`;
      }
      if (groups.length > 0) {
        apiUrl += `&group=${groups.join(',')}`;
      }
      if (no_groups.length > 0) {
        apiUrl += `&no_group=${no_groups.join(',')}`;
      }
      if (hide_admin) {
        apiUrl += `&hide_admin=true`;
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
  
    // Server-side export (async). Mirrors getAll's search/filters but POSTs to
    // `{entity}export/` so the backend builds the full, filter-aware XLSX as a
    // background task, returning `{ task_id }`. Same args as getAll (no page).
    const exportData = async (searchQuery = '', groups = [], no_groups = [], hide_admin = false) => {
      return $apiManager.exportTable(entity, {
        searchQuery,
        extraParams: {
          group: groups,
          no_group: no_groups,
          hide_admin: hide_admin ? 'true' : null,
        }
      });
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

      const deleteItem = async (id) => {
        const apiUrl = `${apiHost}${entity}${id}/`;

        try {
          const response = await $apiManager.fetch(apiUrl, 'DELETE');
          return response;
        } catch (error) {
          throw error;
        }
    };
  
    // Canvi de la contrasenya de l'usuari que ha fet login (qualsevol rol); el backend
    // tanca les altres sessions i conserva l'actual
    const changeOwnPassword = async (currentPassword, newPassword) => {
      const apiUrl = `${apiHost}/auth/change-password/`;
      return $apiManager.fetch(apiUrl, 'POST', {
        current_password: currentPassword,
        new_password: newPassword,
      }, { 'Content-Type': 'application/json' });
    };

    // Fitxa de l'usuari que ha fet login: consultar i canviar nom, cognoms i correu
    const getOwnProfile = async () => {
      return $apiManager.fetch(`${apiHost}/auth/profile/`, 'GET');
    };

    const updateOwnProfile = async (data) => {
      return $apiManager.fetch(`${apiHost}/auth/profile/`, 'PATCH', {
        first_name: data.first_name,
        last_name: data.last_name,
        email: data.email,
      }, { 'Content-Type': 'application/json' });
    };

    const apiService = {
      getAll,
      exportData,
      getDetail,
      save,
      deleteItem,
      changeOwnPassword,
      getOwnProfile,
      updateOwnProfile
    };
  
    nuxtApp.provide(provideName, apiService);
  });
  