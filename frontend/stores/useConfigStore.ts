import { defineStore } from 'pinia';

export const useConfigStore = defineStore('config', {
    state: () => ({
        ovEnabled: null as boolean | null,
        documentSignEnabled: null as boolean | null,
        sendBatchEnabled: null as boolean | null,
        acaNotificationEnabled: null as boolean | null,
        // Organisme públic del projecte: 'aca', '' (fora de Catalunya) o un altre.
        publicOrgType: null as string | null,
        loading: false,
    }),
    getters: {
        /** Cert si el projecte depèn de l'ACA (`public_org_type === 'aca'`). */
        isAcaOrg(state) {
            return (state.publicOrgType || '') === 'aca';
        },
    },
    actions: {
        async fetchOvEnabled() {
            if (this.ovEnabled !== null) return; // Already fetched

            this.loading = true;

            try {
                const { $ConfigProjectApiService } = useNuxtApp();
                // The API service handles caching in localStorage
                const value = await $ConfigProjectApiService.get('OV_ENABLED');
                this.ovEnabled = value === true || value === 'True' || value === 'true';
            } catch (error) {
                console.error('Error fetching OV_ENABLED config:', error);
                this.ovEnabled = false; // Fallback
            } finally {
                this.loading = false;
            }
        },
        async fetchDocumentSignEnabled() {
            if (this.documentSignEnabled !== null) return; // Already fetched

            this.loading = true;

            try {
                const { $ConfigProjectApiService } = useNuxtApp();
                // The API service handles caching in localStorage
                const value = await $ConfigProjectApiService.get('DOCUMENT_SIGN_ENABLED');
                this.documentSignEnabled = value === true || value === 'True' || value === 'true';
            } catch (error) {
                console.error('Error fetching DOCUMENT_SIGN_ENABLED config:', error);
                this.documentSignEnabled = false; // Fallback
            } finally {
                this.loading = false;
            }
        },
        async fetchSendBatchEnabled() {
            if (this.sendBatchEnabled !== null) return;

            this.loading = true;

            try {
                const { $ConfigProjectApiService } = useNuxtApp();
                // ODOO_ENABLED gates send-batch UI today; rename later if more providers share it.
                const value = await $ConfigProjectApiService.get('ODOO_ENABLED');
                this.sendBatchEnabled = value === true || value === 'True' || value === 'true';
            } catch (error) {
                console.error('Error fetching send-batch enabled config:', error);
                this.sendBatchEnabled = false;
            } finally {
                this.loading = false;
            }
        },
        async fetchAcaNotificationEnabled() {
            if (this.acaNotificationEnabled !== null) return; // Already fetched

            this.loading = true;

            try {
                const { $ConfigProjectApiService } = useNuxtApp();
                // The API service handles caching in localStorage
                const value = await $ConfigProjectApiService.get('aca_notification_enabled');
                this.acaNotificationEnabled = value === true || value === 'True' || value === 'true';
            } catch (error) {
                console.error('Error fetching aca_notification_enabled config:', error);
                this.acaNotificationEnabled = false; // Fallback
            } finally {
                this.loading = false;
            }
        },
        async fetchPublicOrgType() {
            if (this.publicOrgType !== null) return; // Already fetched

            this.loading = true;

            try {
                const { $ConfigProjectApiService } = useNuxtApp();
                // `getAll` refresca la cache de localStorage; `get()` la serviria tal com està
                // i el valor podria quedar desactualitzat entre sessions.
                const response = await $ConfigProjectApiService.getAll('public_org_type');
                const value = Array.isArray(response) && response.length ? response[0]?.value : '';
                this.publicOrgType = String(value ?? '').trim().toLowerCase();
            } catch (error) {
                console.error('Error fetching public_org_type config:', error);
                // Leave pending (null) so the next call can retry instead of hiding ACA until reload.
            } finally {
                this.loading = false;
            }
        }
    }
});
