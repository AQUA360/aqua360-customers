<script setup>
import { toRaw, ref, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';

import H1 from '~/components/atoms/H1.vue';
import AddCompany from '~/components/molecules/AddCompany.vue';

const { t } = useI18n();

</script>

<template>
  <div id="wrapper" class="text-base p-4 max-w-full">
    <div class="flex justify-between items-center mb-6">
    </div>
    <AddCompany :isSubRegionOpen="false" @close="navigateTo('/')" />
  </div>
</template>
