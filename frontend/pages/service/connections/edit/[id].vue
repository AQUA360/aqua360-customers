<script setup>
import { ref, onMounted } from 'vue';

import H1 from '~/components/atoms/H1.vue';

const { t }= useI18n();
const route = useRoute()

const { $ConnectionApiService } = useNuxtApp();

const id = ref(0);
const loading = ref(true);
const connection = ref(null);

const getData = async (showLoading = true) => {
  if (showLoading) {
    loading.value = true;
    connection.value=null;
  }
  try {
    if (id.value) {
      const data = await $ConnectionApiService.getDetail(id.value);
      connection.value = data;
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
  <div id="wrapper" class="text-base p-4 max-w-full">
    <div class="flex justify-between items-center mb-6">
      <H1>{{ $t(`common.modify`) }} {{ t('connection') }}</H1>
    </div>
    <div v-if="loading">
      <div class="border border-gray-300 rounded-b p-4 bg-white">
        <div class="flex justify-center items-center">
          <Icon name="fa6-solid:spinner" class="animate-spin text-2xl text-slate-500" />
          <span class="ml-2">{{ $t('common.loading') }}...</span>
        </div>
      </div>
    </div>
    <div v-else>
      <OrganismsConnectionEdit v-if="connection" :connection="connection"/>
    </div>
  </div>
</template>
