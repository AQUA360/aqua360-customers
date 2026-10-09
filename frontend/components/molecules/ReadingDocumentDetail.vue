<script setup>
// components/organisms/ClusterDetail.vue
import { useI18n } from 'vue-i18n';
import FieldDetail from '~/components/atoms/FieldDetail.vue';


const { $ReadingDocumentApiService } = useNuxtApp();

const { t } = useI18n();

const props = defineProps({
  id: Number, // ID de l'element
  data: Object,
  isSubRegion: {
    type: Boolean,
    default: false
  },
  isSubRegionOpen: {
    type: Boolean,
    default: false
  },
});

const loading = ref(false);
const localData = ref(props.data ? props.data : null);

const emit = defineEmits(['show-detail']);

const showDetail = function (component, id) {
  emit('show-detail', component, id)
}

const getData = async () => {
  try {
    const response = await $ReadingDocumentApiService.getDetail(props.id);
    localData.value = response;
  } catch (error) {
    console.error('Error obtaining the data:', error);
    error.value = error;
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  if (props.id && (!props.data || props.data.length == 0)) {
    loading.value = true
    await getData()
  }
})
</script>

<template>
  <div id="wrapper" class="text-base">
    <div v-if="loading">
      <div class="p-4">
        <div class="flex justify-center items-center">
          <Icon name="fa6-solid:spinner" class="animate-spin text-2xl text-slate-500" />
          <span class="ml-2">{{ $t('common.loading') }}...</span>
        </div>
      </div>
    </div>
    <div v-else-if="localData">
      <div role="row" class="grid grid-cols-2 gap-3">
        <FieldDetail class="truncate" :label='$t("common.doc")' :value="localData.file?.split('/').pop()" />
        <FieldDetail :label='$t("common.uploaded")' :value="formatDate(localData.created_at)" class="items-center"/>
        <FieldDetail :label='$t("billing_block.added_readings")' :value="(localData.num_readings).toString()" />
        <FieldDetail :label="$t('billing_block.reading_batch')">
          <div v-if="!isSubRegion && localData.batch" class="flex gap-2">
            <button @click="showDetail('ReadingBatchRegion', localData.batch?.id)"
              class="text-start text-sky-500 underline flex items-center gap-2">
              {{ localData.batch?.token }} {{ localData.batch?.name }}
            </button>
            <AtomsRedirectButton :id="localData.batch.id" :path="'/reading/reading-batches/'" />
          </div>
          <span v-else>
            {{ localData.batch? localData.batch.token + ' ' + localData.batch.name : '-' }}
          </span>
        </FieldDetail>
      </div>
    </div>

  </div>
</template>
