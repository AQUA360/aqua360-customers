<script setup>
import { formatDate } from '~/utils/date';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
const { t } = useI18n();

const props = defineProps({
  item: Object,
  
});

const { $PaymentApiService } = useNuxtApp();

const emit = defineEmits(['show-region']);

const document_data = ref(null);

const getData = async () => {
  try {
    const result = await $PaymentApiService.getDocumentSEPA(props.item.id);
    document_data.value = result
  }catch (err) {
    console.error(err);
  }
}

const showXML = async () => {
  emit('show-region', 'SEPADocumentRegion', document_data.value.document)
}


onMounted(() => {
  getData()
})

</script>

<template>
  <div class="py-1 rounded">
    
    <div class="flex justify-between px-2" >
      <div class="">
        <FieldDetail :label="$t('common.remittance_date')" :value="document_data?.date? document_data.date : '-'"></FieldDetail>
      </div>
      <div v-if="document_data?.document">
        <button class="button-default-xs w-[200px]" @click="showXML()">
          <Icon name="fa6-solid:file-code" class="mr-2" />
          {{ $t('common.check') }} XML
        </button>
      </div>
      <div v-else>
        <span class="text-gray-700 mt-1 font-medium italic text-sm px-2 py-1">
          {{ $t('common.no_data_found') }}
        </span>
      </div>
    </div>

  </div>
</template>