<script setup>
// components/organisms/BailTypeSelectMultiple.vue
import { ref, computed, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import Draggable from 'vuedraggable';

const { t } = useI18n();
const { $BailTypeApiService } = useNuxtApp();

const props = defineProps({
  modelValue: {
    type: Array,
    default: () => []
  }
});

const emit = defineEmits(['update:modelValue']);
const columnClass = ref('grid-cols-[35px,120px,200px,100px]');

const pending = ref(true);
const error = ref(null);
const items = ref([]);

const selectedItems = computed({
  get() {
    return props.modelValue;
  },
  set(value) {
    emit('update:modelValue', value);
  }
});

const getData = async () => {
  pending.value = true;
  try {
    const dataResponse = await $BailTypeApiService.getAll();
    items.value = dataResponse.results;
    pending.value = false;
    error.value = null;
  } catch (err) {
    error.value = err;
    pending.value = false;
  }
}

onMounted(() => {
  getData();
});
</script>

<template>
  <div v-if="pending">
    <p>{{ $t('common.loading') }}...</p>
  </div>
  <div v-else-if="error">
    <p>{{ $t('common.error') }}: {{ error.message }}</p>
    <p>
      <button @click="getData" class="underline text-sky-500 hover:no-underline">
        {{ $t('common.load_again') }}
      </button>
    </p>
  </div>
  <div v-else>
    <h1 class="text-xl font-semibold mb-3">{{ $t('billing_block.bail_type') }}</h1>
    <!-- Total -->
    <div v-if="items.length">
      <div id="config__totals" class="text-sm text-right text-slate-500">
        {{ $t('Total') }}: {{ items.length }}
      </div>
      <div id="config__items" class="text-base">
        <!-- Header Row -->
        <div :class="['heading', 'grid', columnClass, 'gap-3', 'text-base', 'border-b', 'items-center']">
          <span class="text-slate-400 p-1">#</span>
          <span class="text-slate-400 p-1">{{ $t('common.identificator') }}</span>
          <span class="text-slate-400 p-1">{{ $t('common.name') }}</span>
          <span class="text-slate-400 p-1">{{ $t('common.amount') }} ({{ $t('default') }})</span>
        </div>
        <!-- Draggable Items -->
        <Draggable v-model="items" itemKey="id" handle=".handle-move" class="dragArea">
          <template #item="{ element: item }">
            <div :class="['grid', columnClass, 'gap-3', 'text-base', 'border-b', 'items-center', 'bg-white']">
              <!-- Checkbox Column -->
              <span class="text-slate-900 p-1 border-r">
                <input 
                  type="checkbox" 
                  :value="item.id" 
                  v-model="selectedItems" 
                  class="h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                />
              </span>
              <!-- Identificador Column -->
              <span class="text-slate-900 p-1 border-r cursor-pointer relative">
                {{ item.token }}
              </span>
              <!-- Nom Column -->
              <span class="text-slate-900 p-1 border-r font-semibold">
                {{ item.name }}
              </span>
              <!-- Import Predeterminat Column -->
              <span class="text-slate-900 p-1">
                {{ item.default_import }} &euro;
              </span>
            </div>
          </template>
        </Draggable>
      </div><!-- end config__items -->
    </div><!-- end if items.length -->
  </div>
</template>

<style scoped>
.heading {
  /* Estils personalitzats per a la fila d'encapçalament */
  background-color: #f9fafb;
}
.dragArea {
  /* Estils personalitzats per a l'àrea draggable */
}
</style>

