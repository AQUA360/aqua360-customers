// plugins/services/coredata/address-api.js
export default defineNuxtPlugin(nuxtApp => {
    const entity = '/coredata/address/';
    const provideName = 'AddressApiService';

    const {$apiManager} = useNuxtApp()
    const config = useRuntimeConfig();
    const apiHost = config.public.apiHost;
    
    const getAll = async (searchQuery = '', filters = [], page = 1, sort = null, desc = false) => {
      let apiUrl = apiHost + entity + '?search=' + encodeURIComponent(searchQuery) + `&page=${page}`;
      
      // Afegir els filtres a la URL
      let filtersValues = [];
      if (filters.length > 0 ) {
        filters.map( filter => {
          filtersValues.push(filter);
        })
      }

      if( filtersValues.length > 0 ) {
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

    const getDetail = async (id) => {
      const apiUrl = `${apiHost}${entity}${id}/`;
  
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

    const createAddress = async (address) => {
      let apiUrl = apiHost + entity;

      try {

        const response = await $apiManager.fetch(apiUrl,'POST',JSON.stringify(address));

        if (response) {
          return response;
        } else {
          throw new Error('Error estructura `results` no trobat');
        }
      } catch (error) {
        throw error;
      }
    }
    
    const updateAddress = async (address) => {
      let apiUrl = apiHost + entity + address.id + '/';

      try {

        const response = await $apiManager.fetch(apiUrl, 'PUT', JSON.stringify(address), { 'Content-Type': 'application/json' } );
        if (response) {
          return response;
        } else {
          throw new Error('Error estructura `results` no trobat');
        }
      } catch (error) {
        throw error;
      }
    }

    const savePartialAddress = async (address) => {
      let apiUrl = apiHost + '/coredata/partial-address/';

      try {

        const response = await $apiManager.fetch(apiUrl, 'POST', JSON.stringify(address), { 'Content-Type': 'application/json' } );

        if (response) {
          return response;
        } else {
          throw new Error('Error estructura `results` no trobat');
        }
      } catch (error) {
        throw error;
      }
    }

    const getCities = async ( searchQuery = '' , page = 1, sort = null, desc = false, hasStreets = null) => {
      let apiUrl = apiHost + '/coredata/city?search=' + encodeURIComponent(searchQuery) + `&page=${page}`;
      
      if( sort ) {
        apiUrl += `&ordering=${desc ? '-' : ''}${sort}`;
      }

      if( hasStreets !== null ) {
        apiUrl += `&has_streets=${hasStreets}`;
      }

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
    };

    const getCitiesByProvince = async ( province_id ) => {
      let apiUrl = apiHost + '/coredata/province/' + province_id + '/cities';
      
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
    };
    
    const getProvinces = async (country_id) => {
      let apiUrl = apiHost + '/coredata/province/';
      
      if (country_id) {
        apiUrl += `?country=${country_id}`;
      }
      // + '?search=' + encodeURIComponent(searchQuery) + `&page=${page}`

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
    };

    const getCountries = async () => {
      let apiUrl = apiHost + '/coredata/country/'; 

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
    };

    const getBanks = async (page = 1) => {
      let apiUrl = apiHost + '/coredata/bank/?page=' + page; 
      /* let allBanks = [];
      let nextPage = apiUrl; */
    
      try {
        const response = await $apiManager.fetch(apiUrl, 'GET');
        if (response) {
          return response;
        } else {
          throw new Error('Error estructura `results` no trobat');
        }
        /* while (nextPage) {
          const response = await $apiManager.fetch(nextPage, 'GET');
          if (response.results) {
            allBanks = [...allBanks, ...response.results];
            nextPage = response.next; // Assuming the API provides a "next" URL for pagination
          } else {
            throw new Error('Error: `results` field not found in response');
          }
        }
        return allBanks; */
      } catch (error) {
        throw error;
      }
    };
    

    const getSwiftFromIban = async (ibanPrefix) => {
      let apiUrl = apiHost + '/coredata/bank/get-swift/?iban_prefix=' + encodeURIComponent(ibanPrefix);
      try {
        const response = await $apiManager.fetch(apiUrl, 'GET');
        return response;
      } catch (error) {
        console.error('Error fetching SWIFT from IBAN prefix:', error);
        return null;
      }
    };

    const apiService = {
      getAll,
      getCities,
      getCitiesByProvince,
      getProvinces,
      getCountries,
      savePartialAddress,
      createAddress,
      updateAddress,
      getBanks,
      getDetail,
      getSwiftFromIban,
    };
  
    nuxtApp.provide(provideName, apiService);
  });
  