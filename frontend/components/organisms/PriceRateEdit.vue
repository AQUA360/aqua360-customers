<script setup>
import { toRaw, ref, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { useRoute } from 'vue-router';
import _ from 'lodash';
import AppLoading from '~/components/atoms/AppLoading.vue';
import TranslatableNameField from '~/components/molecules/TranslatableNameField.vue';

const route = useRoute()

const props = defineProps({
  id: Number,
});

const { t } = useI18n();
const { $PriceRateApiService, $ProductApiService } = useNuxtApp();

const attemptedSave = ref(false);
const loading = ref(true);
const saving = ref(false);

const item = ref(null);
const token = ref(null);
const name = ref(null);
const translations = ref([]);
const is_bail = ref(false);
const is_return_fee = ref(false);

const inpr = ref(false);

const products = ref([])
const selectedProduct = ref(null)

const showRegion = ref(false);
const isSubRegionOpen = ref(false);

const emits = defineEmits(['show-subregion']);


const getData = async () => {
  loading.value = true;

  if (props.id) {
    item.value = await $PriceRateApiService.getDetail(props.id);
    name.value = item.value.name;
    translations.value = Object.entries(item.value.name_translations || {}).map(([language, name]) => ({ language, name }));
    token.value = item.value.token;
    is_bail.value = item.value.is_bail;
    is_return_fee.value = item.value.is_return_fee;
    console.log("selectedProduct", item.value);
    selectedProduct.value = { 'value': item.value.product.id, 'label': item.value.product.name };
  } else {
    item.value = {};
  }

  getProducts();
  loading.value = false;
}

const getProducts = async () => {
  const response = await $ProductApiService.getAll();
  products.value = []

  response.results.forEach(item => {
    products.value.push({
      value: item.id,
      label: item.name
    })
  })
}


const save = async () => {
  attemptedSave.value = true;
  if (isValid()) {
    saving.value = true;

    const selectedOptions = {
      id: props?.id || null,
      token: token.value,
      name: name.value,
      name_translations: Object.fromEntries(translations.value.filter((row) => row.name).map((row) => [row.language, row.name])),
      is_bail: is_bail.value,
      is_return_fee: is_return_fee.value,
      product: selectedProduct?.value?.value || null,
    };

    item.value = $PriceRateApiService.save(selectedOptions);
    if (inpr.value) {
      return navigateTo('/pricing/products/?id=' + selectedProduct?.value?.value)
    } else {
      return navigateTo('/pricing/price-rates/')
    }
  }
  else {
    saving.value = false;
  }
}


const isValid = () => {
  if (name.value == '' || name.value == null) return false;
  if (token.value == '' || token.value == null) return false;
  return true;
}

const updateSelect = (event, entity) => {
  switch (entity) {
    case 'product':
      selectedProduct.value = event;
      break;
  }
}

const toggleRegion = (force) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
  if (showRegion.value == false) {
    isSubRegionOpen.value = false;
  }
}

onMounted(() => {
  getData()
  if (route.query.inprod) {
    inpr.value = true;
  }
});

</script>

<template>
  <div class="wrapper text-base p-4 max-w-full">
    <div v-if="loading">
      <AppLoading :text="$t('common.loading')" />
    </div>
    <div v-else class="border border-gray-300 rounded p-4 bg-white">
      <div class="row grid grid-cols-2 gap-3">
        <div class="mb-4">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.identificator') }}</label>
          <input type="text" v-model="token" class="input"
            :class="{ 'invalid': attemptedSave && (token == '' || attemptedSave && token == null) }" />
        </div>

        <div class="flex items-center text-slate-500 gap-x-2">
          <abbr :title="t('informative_block.info_apply_bail')" class="flex items-center">
            <Icon name="fa6-solid:circle-info" class="text-slate-500" />
          </abbr>
          <input v-model="is_bail" type="checkbox" id="is_bail" name="is_bail" class="checkbox" />
          <label for="is_bail"> {{ t('bail') }}</label>
        </div>

        <div class="flex items-center text-slate-500 gap-x-2 col-start-2">
          <abbr :title="t('informative_block.info_apply_return_fee')" class="flex items-center">
            <Icon name="fa6-solid:circle-info" class="text-slate-500" />
          </abbr>
          <input v-model="is_return_fee" type="checkbox" id="is_return_fee" name="is_return_fee"
            class="checkbox" />
          <label for="is_return_fee"> {{ t('return_fee') }}</label>
        </div>

      </div>

      <div class="row grid grid-cols-2 gap-3 ">

        <div class="mb-4">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.name') }}</label>
          <input type="text" v-model="name" class="input"
            :class="{ 'invalid': attemptedSave && name == '' || attemptedSave && name == null }" />
        </div>

        <TranslatableNameField v-model="translations" class="col-span-2" />

        <div class="mb-4">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('product') }}</label>
          <v-select class="block w-full mr-1 required" :model-value="selectedProduct"
            @update:modelValue="updateSelect($event, 'product')" :options="products" />
        </div>
      </div>

      <hr class="mb-2 col-span-2" />
      <div class="col-span-2 flex flex-row-reverse mt-4">
        <!-- <button v-if="id != null" @click="deleteItem" :disabled="saving" class="button-default mx-5">
          &nbsp; {{ $t('common.delete') }}
        </button> -->
        <button @click="save" :disabled="saving" class="button-primary">
          <Icon name="fa6-solid:floppy-disk" />&nbsp; {{
            $t('common.save') }}
        </button>
      </div><!-- end contingut botons -->



    </div>

    <div role="region" id="right_page"
      class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white z-10"
      :class="{ 'translate-x-0': showRegion, 'translate-x-[2000px]': !showRegion, 'w-[95%]': isSubRegionOpen, 'w-1/2': !isSubRegionOpen }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="toggleRegion(false)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">
        <!-- subregions -->
      </div>
    </div>

  </div>
</template>
