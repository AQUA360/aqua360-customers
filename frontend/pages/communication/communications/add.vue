<script setup>
import AddNewCommunication from '~/components/organisms/AddNewCommunication.vue';
import H1 from '~/components/atoms/H1.vue';
import { checkPermission } from '~/middleware/permission';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';

const { $ConfiglistApiService, $CommunicationApiService } = useNuxtApp();

const toast = useToast();
const objectPermissions = ref(null);

onMounted(async () => {
    objectPermissions.value = await checkPermission($CommunicationApiService);
    if (!objectPermissions.value.can_view) {
        toast.error(t('common.no_permissions'));
        return navigateTo('/');
    }
});

</script>

<template>
    <div v-if="objectPermissions?.can_view" id="wrapper" class="text-base p-4 max-w-full">
        <div class="flex justify-between items-center mb-6">
            <H1>{{ $t('customer_service_block.new_comm') }}</H1>
        </div>
        <AddNewCommunication />
    </div>
</template>