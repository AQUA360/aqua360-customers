<script setup>
// path: pages/contract/contract-requests/edit/[id].vue
import { ref, onMounted } from 'vue';

import H1 from '~/components/atoms/H1.vue';
import ContractRequestEdit from '~/components/organisms/ContractRequestEdit.vue';

const { t }= useI18n();
const route = useRoute()

const { $ContractRequestApiService } = useNuxtApp();

const id = ref(0);
const loading = ref(true);
const request = ref(null);

const getData = async (showLoading = true) => {
  if (showLoading) {
    loading.value = true;
    request.value=null;
  }
  try {
    if (id.value) {
      const data = await $ContractRequestApiService.getDetail(id.value);
      request.value = data;
    }
  } catch (error) {
    console.error('Error loading draft:', error);
  }
  if (showLoading) loading.value = false;
};

onMounted(() => {
  id.value = parseInt(route.params.id);
  getData();
});


</script>

<template>
  <div class="text-base p-4 max-w-full">
    <div v-if="loading">
      <div class="border border-gray-300 rounded-b p-4 bg-white">
        <div class="flex justify-center items-center">
          <Icon name="fa6-solid:spinner" class="animate-spin text-2xl text-slate-500" />
          <span class="ml-2">{{ $t('common.loading') }}...</span>
        </div>
      </div>
    </div>
    <div v-else>
      <ContractRequestEdit v-if="request" :request="request" @refresh="getData"/>
    </div>
  </div>
</template>
