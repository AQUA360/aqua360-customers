<script setup>
import { ref } from 'vue';
import { useI18n } from 'vue-i18n';
import _ from 'lodash';

import H1 from '~/components/atoms/H1.vue';
import ClauseDetail from '~/components/molecules/ClauseDetail.vue';

const { t } = useI18n();
const { $ClauseTemplateApiService } = useNuxtApp();
const emit = defineEmits(['selected-item']);

const props = defineProps({
  selectedType: Object,
});

const items = ref([])
const loading = ref(true);

const getItems = async () => {
  const response = await $ClauseTemplateApiService.getAll('', { is_active: true });
  items.value = response.results;
}

const getData = async () => {
  loading.value = true;
  await getItems();
  loading.value = false;
};
 
onMounted(() => {
  getData()
});

const clickItem = (item) => {
  emit('selected-item', item);
}

</script>

<template>
  <div id="wrapper" class="text-base">
    <div class="flex justify-between items-center mb-2">
      <H1>{{ $t('contract_block.clause_selection') }}</H1>
    </div>
    <div class="item__list mt-3">
      <button class="item__list__item flex gap-2 border mb-2 w-full py-1 px-3" v-for="item in items" :key="item.id" @click="clickItem(item)">
        <ClauseDetail :item="item" />
      </button>
    </div>
    <p v-if="!loading && items.length === 0" class="text-slate-500">
      {{ $t('contract_block.no_clauses_configured') }}
    </p>
  </div>
</template>