<script setup>
import { toRaw, ref, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import AppLoading from '~/components/atoms/AppLoading.vue';

import H1 from '~/components/atoms/H1.vue';

const { t } = useI18n();
const { $PropertyApiService } = useNuxtApp();

const route = useRoute()
const id = route.params.id

const property = ref(null);

const loading = ref(true);
const error = ref(null);

const getData = async () => {
  
  loading.value = true;

  try {
    error.value = null;
    const new_property = await $PropertyApiService.getDetail(id);

    if (new_property != null) {
      property.value = new_property;
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
      <AppLoading :text="$t('common.loading')" />
    </div>
    <div v-else-if="error != null">
      <div class="border border-gray-300 rounded p-4 bg-white">
        <div class="flex justify-center items-center">
          <Icon name="fa6-solid:xmark" class="text-2xl text-red-400" />
          <span class="ml-2">{{error?.message}}</span>
        </div>
      </div>
    </div>
    <div v-if="property != null">
      <div class="flex justify-between items-center mb-6">
        <H1>{{ $t('common.modify') }} {{ t('property') }}</H1>
      </div>
      <OrganismsPropertyEdit :property="property" />
    </div>
  </div>
</template>
