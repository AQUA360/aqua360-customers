import { defineStore } from 'pinia';

export const useConfigStore = defineStore('config', {
    state: () => ({
        ovEnabled: null as boolean | null,
        documentSignEnabled: null as boolean | null,
        acaNotificationEnabled: null as boolean | null,
        attachClaimDocumentsEnabled: null as boolean | null,
        loading: false,
    }),
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
        async fetchAttachClaimDocumentsEnabled() {
            if (this.attachClaimDocumentsEnabled !== null) return; // Already fetched

            this.loading = true;

            try {
                const { $ConfigProjectApiService } = useNuxtApp();
                // The API service handles caching in localStorage
                const value = await $ConfigProjectApiService.get('ATTACH_CLAIM_DOCUMENTS_ENABLED');
                this.attachClaimDocumentsEnabled = value === true || value === 'True' || value === 'true';
            } catch (error) {
                console.error('Error fetching ATTACH_CLAIM_DOCUMENTS_ENABLED config:', error);
                this.attachClaimDocumentsEnabled = false; // Fallback
            } finally {
                this.loading = false;
            }
        }
    }
});
