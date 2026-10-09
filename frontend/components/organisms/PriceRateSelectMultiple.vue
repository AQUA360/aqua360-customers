<script setup>
// components/organisms/ClauseTemplateSelectMultiple.vue
import { ref, computed, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import Draggable from 'vuedraggable';

const { t } = useI18n();
const { $PriceRateApiService } = useNuxtApp();

const props = defineProps({
  modelValue: {
    type: Array,
    default: () => []
  },
  filter: {
    type: Array,
    default: null
  }, 
  exploitation_id: {
    type: Number,
    default: null
  },
  title: {
    type: String,
    default: null
  }
});

const emit = defineEmits(['update:modelValue']);
const columnClass = ref('grid-cols-[35px,120px,1fr]');

const pending = ref(true);
const error = ref(null);
const items = ref([]);
const checked = ref([]);
const selected = ref([]);
const rates = ref([]);
const filter = ref(props.filter);

const selectedItems = computed({
  get() {
    return props.modelValue;
  },
  set(value) {
    emit('update:modelValue', value);
  }
});

const onChange = () => {
  selectedItems.value = [];
  if (checked.value && selected.value) {
    const values = [];
    for (let i = 0; i < checked.value.length; i++) {
      if (checked.value[i] === true) {
        values.push( selected.value[i]);
      }
    }
    selectedItems.value = values;
  }
};

const groupBy = (list, keyGetter) => {
  const map = new Map();
  list.forEach((item) => {
    const key = keyGetter(item);
    const collection = map.get(key);
    if (!collection) {
      map.set(key, [item]);
    } else {
      collection.push(item);
    }
  });
  return map;
}

const setData = () => {
  items.value = groupBy(rates.value, pr => pr.product?.id || t('pricing_block.no_product'));
}

const getData = async () => {
  pending.value = true;
  try {
    const dataResponse = await $PriceRateApiService.getAll('', [], 1, null, false, null, filter.value, true, props.exploitation_id);
    checked.value = [];
    selected.value = [];
    rates.value = dataResponse.results;
    items.value = groupBy(dataResponse.results, pr => pr.product?.id || t('pricing_block.no_product'));
    checked.value

    for (const [key, value] of items.value) {
      let sel = null;
      for (const rate of props.modelValue) {
        sel = value.find(item => item.id == rate);
        if (sel) break;
      }
      if (sel) {
        checked.value.push(true);
      }
      else {
        checked.value.push(false);
        sel = value[0];
      }
      selected.value.push(sel.id);
    }
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
  <div v-if="pending" class="flex gap-x-2 h-full items-center">
    <Icon name="fa-solid:spinner" class="animate-spin text-slate-500" />
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
    <h1 class="text-xl font-semibold mb-3">{{ title || $t('contract_block.contract_price_rates') }}</h1>
    <!-- Total -->
    <div>
      <div id="config__totals" class="text-sm text-right text-slate-500">
        {{ $t('common.total') }}: {{ items.size }}
      </div>
      <div id="config__items" class="text-base">
        <!-- Header Row -->
        <div :class="['heading', 'grid', columnClass, 'gap-3', 'text-base', 'border-b', 'items-center']">
          <span class="text-slate-400 p-1">#</span>
          <span class="text-slate-400 p-1">{{ $t('product') }}</span>
          <span class="text-slate-400 p-1">{{ $t('price_rate') }}</span>
        </div>
        <!-- Draggable Items -->
        <div v-for="([key, rates], index) in Array.from(items)" :key="key">
          <div :class="['grid', columnClass, 'gap-3', 'text-base', 'border-b', 'items-center', 'bg-white']">
            <!-- Checkbox Column -->
            <span class="text-slate-900 p-1 border-r">
              <input
                @change="onChange()"
                type="checkbox" 
                :value="checked[index]" 
                v-model="checked[index]" 
                class="h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
              />
            </span>
            <!-- Identificador Column -->
            <span class="text-slate-900 p-1 border-r cursor-pointer relative">
              {{ rates[0].product?.name || t('pricing_block.no_product') }}
            </span>
            <!-- Títol Column -->
            <span class="text-slate-900 p-1 border-r font-semibold">
              <select v-model="selected[index]" class="input" @change="onChange()">
                <!-- <option value="">-- {{ $t('Seleccionar Tipus de Bonificació') }}</option> -->
                <option v-for="type in rates" :key="type.id" :value="type.id">
                  {{ type.name }}
                </option>
              </select>
            </span>
          </div>

        </div>
      </div><!-- end config__items -->
    </div><!-- end if items.length -->
  </div>
</template>

<style scoped>
.heading {
  /* Estils personalitzats per a la fila d'encapçalament */
  background-color: #f9fafb;
}
</style>
