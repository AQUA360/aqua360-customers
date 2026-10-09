<script setup>
import { ref, onMounted } from 'vue';

import H1 from '~/components/atoms/H1.vue';
import CommunicationProcessCreation from '~/components/organisms/CommunicationProcessCreation.vue';

const { t }= useI18n();

onMounted(() => {
});


</script>

<template>
  <div id="wrapper" class="text-base p-4 max-w-full">
    <div class="flex justify-between items-center mb-6">
      <H1>{{ $t(`customer_service_block.new_comms_process`) }}</H1>
    </div>
    <div>
      <CommunicationProcessCreation/>
    </div>
  </div>
</template>
