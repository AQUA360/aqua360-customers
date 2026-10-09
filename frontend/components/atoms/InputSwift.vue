<script setup>
import { ref, watch, onMounted } from 'vue';

const props = defineProps({
  value: {
    type: Object,
    default: () => ({}),
  },
  readonly: {
    type: Boolean,
    default: false
  }
});

const { t } = useI18n();
const emit = defineEmits(['change']);

const swift = ref('');

const emitChange = () => {
  emit('change', {
    ...props.value,
    swift: swift.value
  });
};

watch(() => props.value, (newVal) => {
  if (newVal && newVal.swift !== undefined) {
    swift.value = newVal.swift || '';
  }
}, { immediate: true, deep: true });

onMounted(() => {
  if (props.value?.swift) {
    swift.value = props.value.swift;
  }
});
</script>

<template>
  <div>
    <div v-if="readonly && swift"
      class="mt-1 p-2 border border-gray-300 bg-slate-50 rounded-md text-slate-500 sm:text-sm">
      {{ swift }}
    </div>
    <div v-else
      class="mb-2 grid border border-gray-300 bg-white rounded-md shadow-sm focus-within:ring-indigo-500 focus-within:border-indigo-500 sm:text-sm disabled:bg-slate-100 disabled:text-slate-400">
      <input id="swift" maxlength="11" v-model="swift" placeholder="SWIFT"
        @input="emitChange" @change="emitChange"
        class="bg-transparent focus:outline-none sm:text-sm p-2 rounded-md" type="text" />
    </div>
  </div>
</template>
