<script setup>
import { toRaw, ref, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';

import H1 from '~/components/atoms/H1.vue';
import PersonEdit from '~/components/organisms/PersonEdit.vue';

const { t } = useI18n();

onMounted(() => {
});

</script>

<template>
  <div id="wrapper" class="text-base p-4 max-w-full">
    
    <div>
      <div class="flex justify-between items-center mb-6">
        <H1>{{ t('contract_block.new_person') }}</H1>
      </div>
      <PersonEdit :connection="null" />
    </div>
  </div>
</template>


