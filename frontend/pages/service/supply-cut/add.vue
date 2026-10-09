<script setup>
import { toRaw, ref, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';

import H1 from '~/components/atoms/H1.vue';
import SupplyCutEdit from '~/components/organisms/SupplyCutEdit.vue';

const { t } = useI18n();

</script>

<template>
  <div id="wrapper" class="text-base p-4 max-w-full">
    <div class="flex justify-between items-center mb-6">
      <H1>{{ $t('service_block.new_supply_cut') }}</H1>
    </div>
    <SupplyCutEdit />
  </div>
</template>
