<script setup>
// Taules mestres dels diccionaris de comptadors (Configuració > Comptadors).
// `model` es mostra en mestre-detall: primer es tria el fabricant i després se'n gestionen els models.
import { ref, computed, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import H1Region from '~/components/atoms/H1Region.vue';
import MeterDictionaryNameList from '~/components/molecules/MeterDictionaryNameList.vue';

const props = defineProps({
  kind: {
    type: String,
    required: true,
    validator: (value) => ['manufacturer', 'model', 'comm_technology'].includes(value),
  },
  title: { type: String, default: '' },
});

const { t } = useI18n();
const { $MeterManufacturerApiService, $MeterModelApiService, $MeterCommTechnologyApiService } = useNuxtApp();

const selectedManufacturer = ref(null);

const singleListService = computed(() => (
  props.kind === 'comm_technology' ? $MeterCommTechnologyApiService : $MeterManufacturerApiService
));

const manufacturerFilter = computed(() => (
  selectedManufacturer.value ? { manufacturer: selectedManufacturer.value.id } : {}
));

watch(() => props.kind, () => {
  selectedManufacturer.value = null;
});
</script>

<template>
  <div class="pr-4">
    <H1Region class="mb-3">{{ title }}</H1Region>

    <div v-if="kind === 'model'" class="grid grid-cols-2 gap-4">
      <MeterDictionaryNameList :title="t('service_block.manufacturers')" :service="$MeterManufacturerApiService"
        selectable :selectedId="selectedManufacturer?.id ?? null" @select="selectedManufacturer = $event" />
      <MeterDictionaryNameList
        :title="selectedManufacturer ? `${t('service_block.models')}: ${selectedManufacturer.name}` : t('service_block.models')"
        :service="$MeterModelApiService" :listParams="manufacturerFilter" :createPayload="manufacturerFilter"
        :disabled="!selectedManufacturer" :disabledHint="t('service_block.select_manufacturer_first')" />
    </div>

    <MeterDictionaryNameList v-else :key="kind" :service="singleListService" />
  </div>
</template>
