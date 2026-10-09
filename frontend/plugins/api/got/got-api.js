import { defineNuxtPlugin } from '#app'

export default defineNuxtPlugin(nuxtApp => {
  const config = useRuntimeConfig();
  const { $apiManager } = useNuxtApp();

  const gotApiService = {
    // Auth endpoints
    async login(username, password) {
      return await $apiManager.fetch(
        config.public.apiHost + '/got/auth/login/',
        'POST',
        JSON.stringify({ username, password }),
        { 'Content-Type': 'application/json' }
      );
    },

    async getProfile() {
      const response = await $apiManager.fetch(
        config.public.apiHost + '/got/auth/profile/',
        'GET',
        null,
        { 'X-App-Token': this.getToken() }
      );
      
      // The API returns operator data directly, wrap it in a consistent format
      if (response && !response.success) {
        return {
          success: true,
          operator: response
        };
      }
      
      return response;
    },

    async logout() {
      return await $apiManager.fetch(
        config.public.apiHost + '/got/auth/logout/',
        'POST',
        null,
        { 'X-App-Token': this.getToken() }
      );
    },

    // Order endpoints
    async getOrders(page = 1, perPage = 20, filters = {}) {
      let url = config.public.apiHost + `/got/orders/?page=${page}&per_page=${perPage}`;
      
      // Add optional filters
      if (filters.lectureUserId) {
        url += `&lecture_user_id=${filters.lectureUserId}`;
      }
      if (filters.unassigned === true) {
        url += `&unassigned=true`;
      }

      const response = await $apiManager.fetch(
        url,
        'GET',
        null,
        { 'X-App-Token': this.getToken() }
      );

      if (response.success) {
        // Transform orders to include computed properties
        response.orders = response.orders.map(order => ({
          ...order,
          status_name: order.status?.name || '',
          status_color: order.status?.color || 'gray',
          priority_name: order.priority?.name || '',
          priority_color: order.priority?.color || 'gray',
          type_name: order.type?.name || '',
          reason_name: order.reason?.name || '',
          is_completed: !!order.completed_at,
        }));
      }

      return response;
    },
    
    async getOrdersList(page = 1, perPage = 20, filters = {}) {
      let url = config.public.apiHost + `/got/orders-list/?page=${page}&per_page=${perPage}`;
      
      // Add optional filters
      if (filters.lectureUserId) {
        url += `&lecture_user_id=${filters.lectureUserId}`;
      }
      if (filters.unassigned === true) {
        url += `&unassigned=true`;
      }
      if (filters.exploitationId) {
        url += `&exploitation=${filters.exploitationId}`;
      }
      if (filters.showPending === true) {
        url += `&show_pending=true`;
      }
      if (filters.showCompleted === true) {
        url += `&show_completed=true`;
      }

      const response = await $apiManager.fetch(
        url,
        'GET',
        null,
        { 'X-App-Token': this.getToken() }
      );

      if (response.success) {
        // Transform orders to include computed properties
        response.orders = response.orders.map(order => ({
          ...order,
          status_name: order.status?.name || '',
          status_color: order.status?.color || 'gray',
          priority_name: order.priority?.name || '',
          priority_color: order.priority?.color || 'gray',
          type_name: order.type?.name || '',
          reason_name: order.reason?.name || '',
          is_completed: !!order.completed_at,
        }));
      }

      return response;
    },

    async getDoc(filters) {
      let url = config.public.apiHost + `/got/orders/report/?page=1`;

      if (filters.lectureUserId) {
        url += `&lecture_user_id=${filters.lectureUserId}`;
      }
      if (filters.unassigned === true) {
        url += `&unassigned=true`;
      }
      if (filters.exploitationId) {
        url += `&exploitation=${filters.exploitationId}`;
      }
      if (filters.showPending === true) {
        url += `&show_pending=true`;
      }
      if (filters.showCompleted === true) {
        url += `&show_completed=true`;
      }

      const response = await $apiManager.fetch(
        url,
        'GET',
        null,
        { 'X-App-Token': this.getToken() }
      );

      return response;
    },

    async getExploitations() {
      let url = config.public.apiHost + `/got/exploitations/`;

      const response = await $apiManager.fetch(
        url,
        'GET',
        null,
        { 'X-App-Token': this.getToken() }
      );

      return response;
    },

    async getOrderDetail(orderId) {
      const response = await $apiManager.fetch(
        config.public.apiHost + `/got/orders/${orderId}/`,
        'GET',
        null,
        { 'X-App-Token': this.getToken() }
      );

      if (response.success && response.order) {
        // Transform order data for easier use
        response.order = {
          ...response.order,
          status_name: response.order.status?.name || '',
          status_color: response.order.status?.color || 'gray',
          priority_name: response.order.priority?.name || '',
          priority_color: response.order.priority?.color || 'gray',
          type_name: response.order.type?.name || '',
          reason_name: response.order.reason?.name || '',
          is_completed: !!response.order.completed_at,
          operators_list: response.order.operators?.map(op =>
            `${op.token} - ${op.name} ${op.surname}`
          ).join(', ') || '',
        };
      }

      return response;
    },

    async finalizeOrder(orderId, data) {
      return await $apiManager.fetch(
        config.public.apiHost + `/got/orders/${orderId}/finalize/`,
        'POST',
        JSON.stringify(data),
        { 
          'Content-Type': 'application/json',
          'X-App-Token': this.getToken()
        }
      );
    },

    async addObservation(orderId, observation) {
      return await $apiManager.fetch(
        config.public.apiHost + `/got/orders/${orderId}/add-observation/`,
        'POST',
        JSON.stringify({ observation }),
        { 
          'Content-Type': 'application/json',
          'X-App-Token': this.getToken()
        }
      );
    },

    // Report endpoints
    async addReport(orderId, reportData) {
      return await $apiManager.fetch(
        config.public.apiHost + `/got/orders/${orderId}/add-report/`,
        'POST',
        JSON.stringify(reportData),
        { 
          'Content-Type': 'application/json',
          'X-App-Token': this.getToken()
        }
      );
    },

    async addReportDocument(orderId, reportId, file) {
      const formData = new FormData();
      formData.append('file', file);

      // When using FormData, don't manually set Content-Type - let browser set it with boundary
      return await $apiManager.fetch(
        config.public.apiHost + `/got/orders/${orderId}/reports/${reportId}/add-document/`,
        'POST',
        formData,
        { 'X-App-Token': this.getToken() }
      );
    },

    async getReports(orderId) {
      return await $apiManager.fetch(
        config.public.apiHost + `/got/orders/${orderId}/reports/`,
        'GET',
        null,
        { 'X-App-Token': this.getToken() }
      );
    },

    // Order Form endpoints
    async getOrderForm(orderId) {
      return await $apiManager.fetch(
        config.public.apiHost + `/got/orders/${orderId}/form/`,
        'GET',
        null,
        { 'X-App-Token': this.getToken() }
      );
    },

    async uploadFormPhoto(orderId, file, fieldToken) {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('field_token', fieldToken);

      return await $apiManager.fetch(
        config.public.apiHost + `/got/orders/${orderId}/upload-form-photo/`,
        'POST',
        formData,
        { 'X-App-Token': this.getToken() }
      );
    },

    async removeFormPhoto(orderId, documentId) {
      return await $apiManager.fetch(
        config.public.apiHost + `/got/orders/${orderId}/remove-form-photo/`,
        'DELETE',
        JSON.stringify({ document_id: documentId }),
        { 
          'Content-Type': 'application/json',
          'X-App-Token': this.getToken()
        }
      );
    },

    async viewDocument(documentId) {
      return await $apiManager.fetch(
        config.public.apiHost + `/got/orders/view-document/${documentId}/`,
        'GET',
        null,
        { 'X-App-Token': this.getToken() }
      );
    },

    // Lecture User Management
    async getLectureUsers() {
      return await $apiManager.fetch(
        config.public.apiHost + '/got/orders/lecture-users/',
        'GET',
        null,
        { 'X-App-Token': this.getToken() }
      );
    },

    async assignLectureUser(orderId, action, lectureUserId = null, lectureUserIds = null) {
      const body = { action };
      
      if (lectureUserId !== null) {
        body.lecture_user_id = lectureUserId;
      }
      if (lectureUserIds !== null) {
        body.lecture_user_ids = lectureUserIds;
      }

      return await $apiManager.fetch(
        config.public.apiHost + `/got/orders/${orderId}/assign-lecture-user/`,
        'POST',
        JSON.stringify(body),
        { 
          'Content-Type': 'application/json',
          'X-App-Token': this.getToken()
        }
      );
    },

    
    // Token management
    getToken() {
      return localStorage.getItem('got_token') || '';
    },

    setToken(token) {
      localStorage.setItem('got_token', token);
    },

    removeToken() {
      localStorage.removeItem('got_token');
    },

    async validateToken() {
      try {
        const response = await $apiManager.fetch(
          config.public.apiHost + '/got/auth/validate-token/',
          'GET',
          null,
          { 'X-App-Token': this.getToken() }
        );
        return response.success === true;
      } catch (error) {
        return false;
      }
    }
  };




  nuxtApp.provide('gotApi', gotApiService);
});
