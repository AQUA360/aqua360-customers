<script setup>
import { set } from 'date-fns';
import { ref, watch, onMounted, nextTick } from 'vue';

const props = defineProps({
  nozzle: {
    type: Object,
    default: {},
  }
});

const { $ConfiglistApiService } = useNuxtApp();
const { t } = useI18n();
const emit = defineEmits(['save']);

const type = ref(null);
const supply_type = ref(null);
const source = ref(null);
const placement = ref(null);

const types = ref([]);
const supply_types = ref([]);
const sources = ref([]);
const placements = ref([]);

const getSelectData = async (entity, targetArray, targetValue) => {
  let data = await $ConfiglistApiService.getAll('service/' + entity);
  data.results?.forEach(item => {
    targetArray.value.push({
      code: item.id,
      label: item.name || item.token
    })
  });
}

const save = () => {
  emit('save', {
    position: props.nozzle.position,
    type: type.value.code,
    supply_type: supply_type.value.code,
    source: source.value.code,
    placement: placement.value.code,
  });
}

const updateSelected = (e) => {
  if (e.entity == 'type') {
    type.value = e.id;
  }
  else if (e.entity == 'source') {
    source.value = e.id;
  }
  else if (e.entity == 'placement') {
    placement.value = e.id;
  }
  else if (e.entity == 'supply_type') {
    supply_type.value = e.id;
  }
}

const setValues = () => {
  console.log(props.nozzle)
  if (props.nozzle?.supplyPoint) {
    type.value = types.value?.find(t => t.code == props.nozzle?.supplyPoint?.type);
    supply_type.value = supply_types.value?.find(t => t.code == props.nozzle?.supplyPoint?.supply_type);
    source.value = sources.value?.find(s => s.code == props.nozzle?.supplyPoint?.source);
    placement.value = placements.value?.find(p => p.code == props.nozzle?.supplyPoint?.placement);
  }
  // if (props.nozzle.supply_points && props.nozzle.supply_points.length > 0) {
  //   const sp = props.nozzle.supply_points[0];
  //   type.value = types.value?.find(t => t.code == sp.type);
  //   supply_type.value = supply_types.value?.find(t => t.code == sp.supply_type);
  //   source.value = sources.value?.find(s => s.code == sp.source);
  //   placement.value = placements.value?.find(p => p.code == sp.placement);
  // }
}

// Call resizeTextarea once the component is mounted
onMounted( async() => {
  await getSelectData('supply-point-type', types, type);
  await getSelectData('supply-point-supply-type', supply_types, supply_type);
  await getSelectData('supply-point-source', sources, source);
  await getSelectData('supply-point-placement', placements, placement);
  setValues()
});

watch(() => props.nozzle, (newVal) => {
  setValues()
}, { immediate: true });

</script>

<template>
  <h2 class="text-xl font-semibold mb-4">{{ $t('service_block.supply_data') }}</h2>
  <div class="grid grid-cols-2  gap-2">
    <div class="mb-2">
      <div class="flex">
        <label for="type" class="block text-sm text-slate-500 my-1 ml-1">
          {{ $t('common.type') }}</label>
      </div>
      <v-select class="block w-full mr-2 required" :disabled="types.length == 0" :model-value="type"
        @update:modelValue="updateSelected({ entity: 'type', id: $event })" :options="types" />
    </div>
    <div class="mb-2">
      <div class="flex">
        <label for="source" class="block text-sm text-slate-500 my-1 ml-1">
          {{ $t('service_block.supply_source') }}</label>
      </div>
      <v-select class="block w-full mr-2 required" :disabled="sources.length == 0" :model-value="source"
        @update:modelValue="updateSelected({ entity: 'source', id: $event })" :options="sources" />
    </div>
    <div class="mb-2">
      <div class="flex">
        <label for="supply_type" class="block text-sm text-slate-500 my-1 ml-1">
          {{ $t('service_block.supply_type') }}</label>
      </div>
      <v-select class="block w-full mr-2 required" :disabled="types.length == 0" :model-value="supply_type"
        @update:modelValue="updateSelected({ entity: 'supply_type', id: $event })" :options="supply_types" />
    </div>
    <div class="mb-2">
      <div class="flex">
        <label for="type" class="block text-sm text-slate-500 my-1 ml-1">
          {{ $t('address_block.placement') }}</label>
      </div>
      <v-select class="block w-full mr-2 required" :disabled="types.length == 0" :model-value="placement"
        @update:modelValue="updateSelected({ entity: 'placement', id: $event })" :options="placements" />
    </div>
  </div>
  <div class="col-span-3 flex flex-row-reverse mt-4">
    <button @click="save" class="button-primary"><Icon name="fa6-solid:floppy-disk" />&nbsp; {{
      $t('common.save') }}</button>
  </div>
</template>
