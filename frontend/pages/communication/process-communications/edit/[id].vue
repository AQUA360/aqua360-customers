<script setup>
import { ref, onMounted } from 'vue';

import H1 from '~/components/atoms/H1.vue';
import CommunicationProcessCreation from '~/components/organisms/CommunicationProcessCreation.vue';

const { t }= useI18n();
const route = useRoute();

const { $CommunicationProcessApiService } = useNuxtApp();

const id = ref(0);
const loading = ref(true);
const request = ref(null);

const getData = async () => {
    loading.value = true;
    request.value = null;
    try {
        if (id.value) {
            const data = await $CommunicationProcessApiService.getDetail(id.value);
            request.value = data;
        }
    } catch (error) {
        console.error('Error loading draft:', error);
    }
    loading.value = false;
};

onMounted(() => {
    id.value = parseInt(route.params.id);
    getData();
});


</script>

<template>
  <div id="wrapper" class="text-base p-4 max-w-full">
    <div class="flex justify-between items-center mb-6">
      <H1>{{ $t(`customer_service_block.new_comms_process`) }}</H1>
    </div>
    <div v-if="loading">
      <AtomsAppLoading/>
    </div>
    <div>
      <CommunicationProcessCreation v-if="request" :request="request"/>
    </div>
  </div>
</template>
