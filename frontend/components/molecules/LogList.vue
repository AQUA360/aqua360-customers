<script setup>
import { ref, watch, onMounted, nextTick } from 'vue';

// Define an object for your plugin
const props = defineProps({
  service: Object,
  id: Number,
  entity: String,
  parent_entity: String
});

const pending = ref(true);
const error = ref(null);
const data = ref(null);

const items = ref([]);

const emit = defineEmits(['update:count']);

const getData = async () => {
  pending.value = true;
  error.value = null;
  try {
    const result = await props.service.getAll(props.entity, props.id);
    items.value = result.results;
    emit('update:count', items.value.length);
  } catch (err) {
    console.log(err);
  } finally {
    pending.value = false;
  }
};

getData();
</script>

<template>
  <div v-if="items.length > 0" class="border-l ml-4 mt-4">
    <MoleculesLog 
      v-for="item in items" 
      :id="item.id" 
      :object="item">
    </MoleculesLog>
  </div>
  <div v-else class="mt-2">
    <div class="">
      <span class="footering text-sm text-slate-500">{{ $t('common.no_data_found') }}</span>
    </div>
  </div>
</template>
