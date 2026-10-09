<script setup>
import { toRaw, ref, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import AppLoading from '~/components/atoms/AppLoading.vue';

import H1 from '~/components/atoms/H1.vue';
import AddCompany from '~/components/molecules/AddCompany.vue';
import Id from '~/pages/contract/aca-documents/edit/[id].vue';

const { t } = useI18n();
const { $ExploitationApiService } = useNuxtApp();

const route = useRoute()
const id = route.params.id

const company = ref(null);

const loading = ref(true);
const error = ref(null);

const getData = async () => {
  
  loading.value = true;

  try {
    error.value = null;
    const new_company = await $ExploitationApiService.getCompany(id);

    if (new_company != null) {
      company.value = new_company;
    }
    else {
      error.value = new Error(t('common.no_data_found'));
    }

  }
  catch (err) {
    error.value = err;
  }

  loading.value = false;
}

onMounted(() => {
  getData()
});

</script>

<template>
  <div id="wrapper" class="text-base p-4 max-w-full">
    <div v-if="loading">
      <div class="border border-gray-300 rounded p-4 bg-white">
        <div class="flex justify-center items-center">
          <Icon name="fa6-solid:spinner" class="animate-spin text-2xl text-slate-500" />
          <span class="ml-2">{{ $t('common.loading') }}...</span>
        </div>
      </div>
    </div>
    <div v-else-if="error != null">
      <div class="border border-gray-300 rounded p-4 bg-white">
        <div class="flex justify-center items-center">
          <Icon name="fa6-solid:xmark" class="text-2xl text-red-400" />
          <span class="ml-2">{{error?.message}}</span>
        </div>
      </div>
    </div>
    <div v-if="company != null">
      <AddCompany :company_id="parseInt(id)" @close="navigateTo('/')" />
    </div>
  </div>
</template>
