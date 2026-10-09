<script setup>
import { toRaw, ref, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { checkPermission } from '~/middleware/permission';
import { useToast } from 'vue-toastification';
import H1 from '~/components/atoms/H1.vue';
import ClusterEdit from '~/components/organisms/ClusterEdit.vue';

const { t } = useI18n();
const toast = useToast();
const objectPermissions = ref(null);
const { $ClusterApiService } = useNuxtApp();
const route = useRoute()
const clusterEditId = ref(route.params.id)

const loading = ref(true);
const error = ref(null);

onMounted(async () => {
  objectPermissions.value = await checkPermission($ClusterApiService);
  if (!objectPermissions.value.can_change) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
});

</script>

<template>
  <div v-if="objectPermissions?.can_change" id="wrapper" class="text-base p-4 max-w-full">
    
    <div v-if="clusterEditId != null">
      <div class="flex justify-between items-center mb-6">
        <H1>{{ $t('common.modify') }} {{ t('cluster') }}</H1>
      </div>
      <ClusterEdit :id="clusterEditId" :connection="null" />
    </div>
  </div>
</template>


