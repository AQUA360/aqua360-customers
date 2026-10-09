<script setup>
import { ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';

const { t } = useI18n();

const props = defineProps({
  document_changes: Array
});

const document_changes = ref([]);

const setValues = () => {
  document_changes.value = props.document_changes;
}

watch(() => props.document_changes, (newValue) => {
  setValues();
});

onMounted(() => {
  setValues();
});

</script>

<template>
  <div>
    <div v-if="document_changes && document_changes.length != 0"
      class="m-4 rounded-md border border-slate-600 divide-y bg-white">
      <div class="group grid border-slate-600 grid-cols-[80px,1fr,1fr,1fr,1fr,1fr,1fr] divide-x text-sm leading-4 ">
        <span class="p-2 pl-3 text-slate-700 flex items-center"> {{ t('common.accepted') }} </span>
        <span class="p-2 pl-3 text-slate-700 flex items-center"> {{ t('person') }} </span>
        <span class="p-2 pl-3 text-slate-700 flex items-center"> {{ t('common.person_id') }} </span>
        <span class="p-2 pl-3 text-slate-700 flex items-center"> {{ t('address_block.address') }} </span>
        <span class="p-2 pl-3 text-slate-700 flex items-center"> {{ t('address_block.postal_code') }} </span>
        <span class="p-2 pl-3 text-slate-700 flex items-center"> {{ t('address_block.city') }} </span>
        <span class="p-2 pl-3 text-slate-700 flex items-center"> {{ t('contract') }} </span>
      </div>
      <div v-for="item in document_changes"
        class="group grid border-slate-600 grid-cols-[80px,1fr,1fr,1fr,1fr,1fr,1fr] divide-x text-sm leading-4 transition-all duration-100">
        <div class="relative p-2 w-full flex justify-center items-center">
          <Icon name="fa6-solid:check" v-show="item.accepted" class="text-xl text-green-600" />
          <Icon v-show="!item.accepted" name="fa6-solid:xmark" class="text-xl text-red-600" />
        </div>
        <div class="relative group footering text-slate-500 p-2 w-full">
          {{ item.person_name }}
        </div>
        <div class="relative group footering text-slate-500 p-2 w-full">
          {{ item.person_NIF }}
        </div>
        <div class="relative group footering text-slate-500 p-2 w-full">
          {{ item.address }}
        </div>
        <div class="relative group footering text-slate-500 p-2 w-full">
          {{ item.postal_code }}
        </div>
        <div class="relative group footering text-slate-500 p-2 w-full">
          {{ item.city_code }}
        </div>
        <div class="relative group footering text-slate-500 p-2 w-full">
          {{ item.contract_code }}
        </div>
      </div>
    </div>
    <div v-else class="footering text-slate-500 p-2">
      {{ t('common.no_changes') }}
    </div>
  </div><!-- end if pending -->

</template>
