const isAuthenticated = () => {
  return localStorage.getItem('auth_token') !== null;
};

const isGOTAuthenticated = () => {
  return localStorage.getItem('got_token') !== null;
};

export default defineNuxtRouteMiddleware(async (to, from) => {
  if(!process.client) return;

  // Handle GOT routes (operator platform)
  if (to.path.startsWith('/got')) { // Changed from '/got/' to '/got'
    // Redirect /got or /got/ to /got/orders
    if (to.path === '/got' || to.path === '/got/') {
      if (!isGOTAuthenticated()) {
        return navigateTo('/got/login');
      }
      return navigateTo('/got/orders');
    }

    const no_auth_paths = ['/got/login'];
    if (no_auth_paths.includes(to.path)) return;
    
    if (!isGOTAuthenticated()) {
      return navigateTo('/got/login');
    }

    // Validate token with API
    const { $gotApi } = useNuxtApp();
    const isValid = await $gotApi.validateToken();
    
    if (!isValid) {
      // Remove invalid token
      $gotApi.removeToken();
      return navigateTo('/got/login');
    }
    
    return; // Stop here for GOT routes
  }

  // Handle main application routes
  const no_auth_paths = ['/auth/login', '/auth/register', '/auth/logout'];
  if( no_auth_paths.includes(to.path) ) return;
  
  if (!isAuthenticated()) {
    // Desa la ruta que s'intentava obrir perquè el login hi torni un cop dins, en lloc de deixar
    // l'usuari a la pàgina principal. NOMÉS quan la petició ve del canvi d'instal·lació, que és qui
    // marca l'adreça amb `from_site` (CurrentExploitationSelect.goToSite): cada instal·lació té la
    // seva base de dades i els seus usuaris, així que en arribar-hi cal iniciar sessió i, sense
    // això, es perdria la pàgina que s'estava mirant.
    //
    // El marcador és la porta: aquest middleware corre abans de tenir sessió, així que no pot
    // consultar la taula ExploitationSite per saber si la instal·lació té germanes. Com que l'únic
    // que posa `from_site` és la graella d'instal·lacions germanes, i aquesta només es dibuixa si
    // la taula té files, a la resta de desplegaments aquesta branca no es pot activar mai i el
    // comportament és exactament el d'abans: login i pàgina principal.
    if (to.query.from_site) {
      // Es desa `path` i no `fullPath` a propòsit: el marcador (i qualsevol altre paràmetre) no ha
      // de quedar a la barra d'adreces després del login. `goToSite` no n'envia cap altre.
      const redirect = to.path;
      if (redirect && redirect !== '/') {
        return navigateTo({ path: '/auth/login', query: { redirect } });
      }
    }
    return navigateTo('/auth/login');
  }
});