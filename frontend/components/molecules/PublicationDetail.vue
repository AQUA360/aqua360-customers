<script setup>
import { ref, watch, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import { formatDate } from '~/utils/date';
import Date from '~/components/atoms/Date.vue';
import AddPublication from './AddPublication.vue';

const { $PublicationApiService } = useNuxtApp();
const { t } = useI18n();

const props = defineProps({
  id: {
    type: Number,
    required: true
  },
  isSubRegion: {
    type: Boolean,
    default: false
  },
  isSubRegionOpen: {
    type: Boolean,
    default: false
  },
  data: {
    type: Object,
    required: false
  }
});

const emit = defineEmits(['show-detail']);

// Variables locals
const localData = ref(props.data ? { ...props.data } : null);
const lineItems = ref([]);
const isLoading = ref(false);
const error = ref(null);
const isEditing = ref(false);

// Funció per mostrar detalls
const showDetail = (component, id) => {
  emit('show-detail', { component, id });
};

const onSaved = async () => {
  isEditing.value = false;
  await fetchData();
};

// Funció per obtenir les dades des de l'API
const fetchData = async () => {
  isLoading.value = true;
  try {
    const detail = await $PublicationApiService.getDetail(props.id);
    localData.value = detail;

    //getLineItemTypes()
  } catch (err) {
    console.error('Error obtenint les dades:', err);
    error.value = err;
  } finally {
    isLoading.value = false;
  }


};


// Executar la funció quan el component es munta
onMounted(() => {
  if (!props.data && props.id) {
    fetchData();
  }
});

// Observa canvis en l'id per tornar a carregar les dades si cal
watch(() => props.id, (newId, oldId) => {
  if (newId && newId !== oldId) {
    fetchData();
  }
});
</script>

<template>
  <div v-if="isLoading" class="loading">
    <!-- Aquí pots posar un spinner o algun altre indicador de càrrega -->
    {{ $t('common.loading') }}...
  </div>

  <div v-else-if="error" class="error">
    <!-- Gestiona l'error segons sigui necessari -->
    {{ $t('common.error_load') }}
  </div>

  <div v-else-if="localData">
    <AddPublication v-if="isEditing" :id="props.id" :isSubRegion="props.isSubRegion"
      :isSubRegionOpen="props.isSubRegionOpen" @new-publication="onSaved" />

    <template v-else>
      <div class="flex justify-end mb-2">
        <button @click="isEditing = true" class="button-primary !px-2.5 !py-1 text-xs">
          <Icon name="fa6-solid:pen" class="mr-1" /> {{ $t('common.modify') }}
        </button>
      </div>

      <div role="row" class="grid grid-cols-2 flex-item-center gap-3">
        <FieldDetail :label="t('common.identification')" :value="localData.token"></FieldDetail>

      </div>

      <hr class="mb-2" />
      <div role="row" class="grid grid-cols-2 flex-item-center gap-3">
        <FieldDetail :label="$t('common.name')" :value="localData.name"></FieldDetail>
        <FieldDetail :label="$t('pricing_block.boe')" :value="localData.boe_number"></FieldDetail>

      </div>
      <div role="row" class="grid grid-cols-2 flex-item-center gap-3">
        <FieldDetail :label="$t('common.reference')" :value="localData.reference"></FieldDetail>
        <FieldDetail :label="$t('common.date')" :value="formatDate(localData.boe_date)"></FieldDetail>
      </div>

      <div role="row" class="grid grid-cols-2 flex-item-center gap-3">
        <FieldDetail :label="$t('common.description')" :value="localData.content"></FieldDetail>
      </div>
    </template>
  </div>
</template>

<style scoped>
.error {
  color: red;
  /* Altres estils per als errors */
}
</style>
