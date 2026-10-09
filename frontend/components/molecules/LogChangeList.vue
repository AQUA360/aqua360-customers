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
  // console.log('getData called', props.id, props.service, props.entity);
  pending.value = true;
  error.value = null;
  try {
    const result = await props.service.getAll(props.entity, props.parent_entity, props.id);
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
  <div class="border-l ml-4 mt-4">
    <MoleculesLogChange 
      v-for="item in items" 
      :id="item.id" 
      :object="item">
    </MoleculesLogChange>
  </div>
</template>
