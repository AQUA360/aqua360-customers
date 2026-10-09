export default defineNuxtPlugin(nuxtApp => {
  const baseURL = 'https://ovc.catastro.meh.es/OVCServWeb/OVCWcfCallejero/COVCCallejero.svc/json/ObtenerCallejero?';
  const provideName = 'CatastroApiService';

  const config = useRuntimeConfig();
  // const apiHost = config.public.apiHost; // You can set up environment variables here if needed.

  const getData = async (province, municipality, street_type, street_name, searchQuery = '', filters = [], page = 1, sort = null, desc = false) => {
    // Construct the URL with parameters
    let apiUrl = `${baseURL}Provincia=${province}&Municipio=${municipality}&TipoVia=${street_type}&NomVia=${street_name}`;

    // Add filters to the URL if any
    if (filters.length > 0) {
      apiUrl += `&status=${filters.join(',')}`;
    }

    if (sort) {
      apiUrl += `&ordering=${desc ? '-' : ''}${sort}`;
    }

    // Set up Fetch configuration
    const fetchConfig = {
      method: 'GET',
     
    };

    try {
      const response = await fetch(apiUrl, fetchConfig);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      // Check if response has the required structure
      if (data) {
        return data;
      } else {
        throw new Error('Error: `results` structure not found in response.');
      }
    } catch (error) {
      console.error(error);
      throw error;
    }
  };

  // Provide the `getData` function through the Nuxt app
  const apiService = {
    getData
  };

  nuxtApp.provide(provideName, apiService);
});
