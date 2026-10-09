// plugins/api/api-manager.js
import { defineNuxtPlugin } from '#app'
import { is } from 'date-fns/locale';
import { useToast } from 'vue-toastification'
import { useSidebarStore } from '~/stores/useNavSideBar';
export default defineNuxtPlugin(nuxtApp => {
  const config = useRuntimeConfig();
  const toast = useToast()

  // Track last 401 toast time to prevent multiple toasts
  let last401ToastTime = 0;

  // Shared 401 handling: clear the expired session and redirect to login.
  // Mirrors NavSidebar.logout() so the auth middleware stops treating the
  // session as valid and no page is left in a loading state.
  const handleUnauthorized = async (message) => {
    const currentTime = Date.now();
    if (message && currentTime - last401ToastTime > 2000) {
      toast.error(message);
      last401ToastTime = currentTime;
    }
    localStorage.removeItem('auth_token');
    localStorage.removeItem('user_username');
    localStorage.removeItem('exploitation');
    try {
      const sidebarStore = useSidebarStore();
      sidebarStore.closeSearch();
      sidebarStore.closeNotifications();
      sidebarStore.closePinnedContract();
    } catch (e) {
      console.error(e);
    }
    nuxtApp.$router.push('/auth/login').catch(() => {});
  };

  const apiService = {
    handleUnauthorized,
    // Name shown in the downloads queue for the next server-side export. Set by
    // useServerExport around its `serverExportFn` call so the ~40 `exportData`
    // wrappers don't have to forward it; exportTable sends it as `export_name`.
    pendingExportName: null,
    async fetch(url, method, body = null, headers = null, suppressToast = false) {
      const authToken = localStorage.getItem('auth_token') || '';
      const isGOTRoute = url.includes('/got/');

      let options = !isGOTRoute
        ? {
          method: method,
          headers: {
            'Authorization': `Token ${authToken}`,
            ...headers
          }
        }
        : {
          method: method,
          headers: {
            ...headers
          }
        };

      /* let exploitation_id = localStorage.getItem('exploitation');
      if (!url.match(/\/\d+\/$/)) {
        if (url.includes('?')) {
          url += `&exploitation=${exploitation_id? exploitation_id: '-1'}`;
        } else {
          url += `?exploitation=${exploitation_id? exploitation_id: '-1'}`; 
        }
      } */

      if (body != null) {
        options.body = body;
      }
      try {
        // Try making the request using $fetch
        return await $fetch(url, options);
      } catch (error) {
        // Extract a user-friendly error message
        let message =
          error?.response?._data?.message ||
          error?.response?._data?.error ||
          error?.response?._data?.detail ||
          error?.response?.data?.message ||
          error?.message ||
          'An unexpected error occurred.';

        // If it's an object (field errors), attempt to extract messages
        if (error?.response?._data && typeof error.response._data === 'object' && !error?.response?._data?.message && !error?.response?._data?.error && !error?.response?._data?.detail) {
          const fieldErrors = error.response._data;
          message = Object.keys(fieldErrors)
            .map(key => {
              const errors = fieldErrors[key];
              return Array.isArray(errors) ? errors.join(', ') : errors;
            })
            .join(' | ');
        }

        logError(`${method} ${url}`, error, { body });

        if (error?.response?.status === 401 && !isGOTRoute) {
          await handleUnauthorized(message);
        } else {
          // Display the error message in a toast notification for non-401 errors
          if (!suppressToast) {
            toast.error(message);
          }
        }

        // Re-throw the error if further handling is needed in the calling function
        throw error;
      }
    },
    async checkTask(task_id) {
      const authToken = localStorage.getItem('auth_token') || '';

      let options = {
        method: 'GET',
        headers: {
          'Authorization': `Token ${authToken}`
        }
      }

      try {
        // Try making the request using $fetch
        return await $fetch(config.public.apiHost + '/task-progress/' + task_id, options);
      } catch (error) {
        // Extract a user-friendly error message
        const message =
          error?.response?.data?.message ||
          error?.message ||
          'An unexpected error occurred.';

        logError(`GET /task-progress/${task_id}`, error);

        if (error?.response?.status === 401) {
          await handleUnauthorized(message);
        } else {
          toast.error(message);
        }

        // Re-throw the error if further handling is needed in the calling function
        throw error;
      }
    },
    async submitMassiveCancelContract(data) {
      const authToken = localStorage.getItem('auth_token') || '';

      let options = {
        method: 'POST',
        headers: {
          'Authorization': `Token ${authToken}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
      }

      try {
        return await $fetch(config.public.apiHost + '/claim-request/massive-cancel-contract/', options);
      } catch (error) {
        const message =
          error?.response?.data?.message ||
          error?.message ||
          'An unexpected error occurred.';

        logError('POST /claim-request/massive-cancel-contract/', error, { data });

        if (error?.response?.status === 401) {
          await handleUnauthorized(message);
        } else {
          toast.error(message);
        }

        throw error;
      }
    },
    // Generic server-side table export. Builds the common search/status/ordering
    // query params and POSTs to `{entity}export/`. `extraParams` carries any
    // entity-specific filters (contract, person, exploitation, ...): scalars are
    // set as-is, arrays are joined with commas, null/undefined/'' are skipped.
    // Backend contract: POST {apiHost}{entity}export/?<query> returns
    // `{ task_id, export_job_id }` (job in the user's downloads queue, see
    // stores/useExportJobs), `{ task_id }` (older endpoints, polled via
    // GET /task-progress/{task_id}) or `{ document_id, document_name }` (ready
    // document) — see useServerExport.
    async exportTable(entity, { searchQuery = '', filters = [], sort = null, desc = false, columns = [], extraParams = {} } = {}) {
      const params = new URLSearchParams();
      params.set('search', searchQuery || '');
      if (filters?.length > 0) params.set('status', filters.join(','));
      if (sort) params.set('ordering', `${desc ? '-' : ''}${sort}`);
      if (columns?.length > 0) params.set('columns', columns.join(','));
      if (this.pendingExportName) params.set('export_name', this.pendingExportName);

      Object.entries(extraParams).forEach(([key, value]) => {
        if (value === null || value === undefined || value === '') return;
        if (Array.isArray(value)) {
          if (value.length > 0) params.set(key, value.join(','));
        } else {
          params.set(key, value);
        }
      });

      const apiUrl = `${config.public.apiHost}${entity}export/?${params.toString()}`;
      return this.fetch(apiUrl, 'POST', { async: true }, { 'Content-Type': 'application/json' });
    },
    async getUserPermissions() {
      const authToken = localStorage.getItem('auth_token') || '';
      try {
        return await $fetch(config.public.apiHost + '/auth/permissions/my-permissions/', {
          headers: {
            'Authorization': `Token ${authToken}`
          }
        });
      } catch (error) {
        const message =
          error?.response?.data?.message ||
          error?.message ||
          'An unexpected error occurred.';

        logError('GET /auth/permissions/my-permissions/', error);

        if (error?.response?.status === 401) {
          await handleUnauthorized(message);
        } else {
          toast.error(message);
        }

        throw error;
      }
    }
  };

  // Proveeix l'objecte `apiManagerService` a tota l'aplicació
  nuxtApp.provide('apiManager', apiService);
});
