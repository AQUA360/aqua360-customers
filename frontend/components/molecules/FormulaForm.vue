<script setup>
import { ref, onMounted, computed } from 'vue';
import { useI18n } from 'vue-i18n';
import H1Region from '../atoms/H1Region.vue';

const props = defineProps({
  id: Number,
  formula: String,
});
const emit = defineEmits(['save']);

const { t } = useI18n();
const { $ProductApiService } = useNuxtApp();

const products = ref([]);
const formula = ref(props.formula ? props.formula : ''); // Initialize with props.formula
const searchQuery = ref('');

const filteredProducts = computed(() => {
  if (!searchQuery.value) return products.value;

  const query = searchQuery.value.toLowerCase();
  return products.value.filter(p =>
    p.label.toLowerCase().includes(query) ||
    p.token.toLowerCase().includes(query)
  );
});

const getData = async () => {
  try {
    const response = await $ProductApiService.getAll();
    response.results.forEach(item => {
      products.value.push({
        value: item.id,
        token: item.token,
        label: `${item.name} (${item.exploitation.name})`
      });
    });
  } catch (error) {
    console.error(error);
  }
};

const insertPlaceholder = (value) => {
  const textarea = document.getElementById('formulaTextarea');

  const start = textarea.selectionStart;
  const end = textarea.selectionEnd;

  formula.value = formula.value.substring(0, start) + value + formula.value.substring(end);

  textarea.value = formula.value;

  textarea.selectionStart = textarea.selectionEnd = start + value.length;
  textarea.focus();
};

const save = () => {
  emit('save', formula.value);
}

onMounted(() => {
  getData();
});
</script>

<template>
  <H1Region>{{ $t('common.add') }} {{ t('pricing_block.for') }}</H1Region>
  <form name="add_condition" class="mt-3" @submit.prevent="addCondition" autocomplete="off">
    <div class="mb-4">
      <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.value') }} / {{ t('pricing_block.for')
      }}</label>
      <textarea id="formulaTextarea" v-model="formula" class="input" autocomplete="off"></textarea>
    </div>
    <button type="submit" class="button-primary flex gap-3 items-center" @click="save">
      <icon name="fa6-solid:floppy-disk"></icon><span>{{ t('common.save') }}</span>
    </button>
  </form>

  <hr class="my-6" />

  <div class="mb-3">
    <div>
      <h4 class="text-sm font-medium text-gray-700 mb-2">
        {{ t('pricing_block.variables_formula') }}
      </h4>

      <div class="mt-3 space-y-4">
        <!-- Search -->
        <div class="relative">
          <input v-model="searchQuery" type="text" :placeholder="t('dashboard.search')"
            class="w-full px-3 py-2 pl-10 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-transparent" />
          <Icon name="fa6-solid:magnifying-glass"
            class="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 text-sm" />
        </div>

        <!-- Products -->
        <details v-if="products.length > 0">
          <summary class="flex items-center gap-x-2 py-1 hover:bg-gray-100 cursor-pointer">
            <Icon name="fa6-solid:angle-down" class="text-slate-500" />
            <p class="font-medium">{{ t('common.products') }}</p> 
            <span v-if="searchQuery" class="text-gray-500 font-normal">
              ({{ filteredProducts.length }} {{ t('common.from') }} {{ products.length }})
            </span>
          </summary>
          <div class="flex flex-wrap gap-2 mt-1">
            <span v-for="v in filteredProducts" :key="v.token" :title="`${v.label}`"
              @click="insertPlaceholder(`%product.${v.token}`)"
              class="inline-flex items-center gap-2 px-3 py-2 bg-sky-50 text-sky-700 text-sm rounded-md border border-sky-200 hover:bg-sky-100 transition-colors cursor-pointer">
              <span class="text-sky-500">{{ v.label }}</span>
              <span class="font-medium">%product.{{ v.token }}</span>
            </span>
          </div>
          <div v-if="searchQuery && filteredProducts.length === 0" class="text-gray-500 text-sm py-2">
            {{ t('common.no_search_results') }}: "{{ searchQuery }}"
          </div>
        </details>

        <!-- Contract -->
        <div>
          <h4 class="text-sm font-medium text-gray-700 mb-2">{{ t('common.other') }}</h4>
          <div class="flex flex-wrap gap-2">
            <span @click="insertPlaceholder('%contract.persons')"
              class="inline-flex items-center gap-1 px-2 py-1 bg-green-50 text-green-700 text-xs font-mono rounded-md border border-green-200 hover:bg-green-100 transition-colors cursor-pointer">
              {{ t('contract_block.total_persons') }}
              <span class="text-green-500">%</span>
              contract.persons
            </span>
            <span @click="insertPlaceholder('%invoice.total_final')"
              class="inline-flex items-center gap-1 px-2 py-1 bg-green-50 text-green-700 text-xs font-mono rounded-md border border-green-200 hover:bg-green-100 transition-colors cursor-pointer">
              {{ t('billing_block.total_invoice') }}
              <span class="text-green-500">%</span>
              invoice.total_final
            </span>
            <span @click="insertPlaceholder('%consumption')"
              class="inline-flex items-center gap-1 px-2 py-1 bg-green-50 text-green-700 text-xs font-mono rounded-md border border-green-200 hover:bg-green-100 transition-colors cursor-pointer">
              {{ t('billing_block.consumption') }}
              <span class="text-green-500">%</span>
              consumption
            </span>
            <span @click="insertPlaceholder('%consumption_days')"
              class="inline-flex items-center gap-1 px-2 py-1 bg-green-50 text-green-700 text-xs font-mono rounded-md border border-green-200 hover:bg-green-100 transition-colors cursor-pointer">
              {{ t('billing_block.consumption_days') }}
              <span class="text-green-500">%</span>
              consumption_days
            </span>
            <span @click="insertPlaceholder('%consumption_responsible')"
              class="inline-flex items-center gap-1 px-2 py-1 bg-green-50 text-green-700 text-xs font-mono rounded-md border border-green-200 hover:bg-green-100 transition-colors cursor-pointer">
              {{ t('billing_block.consumption_responsible') }}
              <span class="text-green-500">%</span>
              consumption_responsible
            </span>
          </div>
        </div>
        <!-- <div>
          <h4 class="text-sm font-medium text-gray-700 mb-2">{{ t('contract') }}</h4>
          <div class="flex flex-wrap gap-2">
            <span @click="insertPlaceholder('%contract.persons')"
              class="inline-flex items-center gap-1 px-2 py-1 bg-green-50 text-green-700 text-xs font-mono rounded-md border border-green-200 hover:bg-green-100 transition-colors cursor-pointer">
              {{ t('contract_block.total_persons') }}
              <span class="text-green-500">%</span>
              contract.persons
            </span>
          </div>
        </div>

        <div>
          <h4 class="text-sm font-medium text-gray-700 mb-2">{{ t('invoice') }}</h4>
          <div class="flex flex-wrap gap-2">
            <span @click="insertPlaceholder('%invoice.total_final')"
              class="inline-flex items-center gap-1 px-2 py-1 bg-purple-50 text-purple-700 text-xs font-mono rounded-md border border-purple-200 hover:bg-purple-100 transition-colors cursor-pointer">
              {{ t('billing_block.total_invoice') }}
              <span class="text-purple-500">%</span>
              invoice.total_final
            </span>
          </div>
        </div> -->
      </div>
    </div>
  </div>
</template>

<style scoped>
.input {
  min-height: 100px;
  border: 1px solid #ccc;
  padding: 8px;
  border-radius: 4px;
  overflow-y: auto;
}
</style>
