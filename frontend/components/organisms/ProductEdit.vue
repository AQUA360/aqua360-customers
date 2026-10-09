<script setup>
import { toRaw, ref, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import _ from 'lodash';
import H1 from '~/components/atoms/H1.vue';
import { OriginDataTypeChoices } from '~/utils/origin-type'
import ProductsPriority from '~/components/molecules/ProductsPriority.vue';
import TranslatableNameField from '~/components/molecules/TranslatableNameField.vue';

const props = defineProps({
  id: Number,
});

const { t } = useI18n();
const { $PriceRateApiService, $ProductApiService, $ExploitationApiService } = useNuxtApp();
const toast = useToast();

const attemptedSave = ref(false);
const loading = ref(true);
const saving = ref(false);

const item = ref(null);
const token = ref(null);
const name = ref(null);
const translations = ref([]);
const origin = ref(null);

const loading_companies = ref(true);

const company = ref(null)

const price_rates = ref([])
const products = ref([])
const companies = ref([])
const exploitations = ref([])

const originOptions = ref([])

const selectedPriceRate = ref(null)
const selectedProduct = ref(null)
const selected_company_id = ref(null)
const selected_company = ref(null)
const selected_exploitation = ref(null)

const showRegion = ref(false);
const isSubRegionOpen = ref(false);
const editingCompany = ref(false);
const showingOrderPriority = ref(false);

const billingActive = ref(true);
const billingInactive = ref(true);

const companyPermissions = ref(null);
const order_priority = ref(null);

const getCompanyPermissions = async () => {
  try {
    companyPermissions.value = await $ExploitationApiService.getCompanyPermissions();
  } catch (error) {
    console.log(error);
  }
}

const getData = async () => {
  loading.value = true;

  if (props.id) {
    item.value = await $ProductApiService.getDetail(props.id);
    name.value = item.value.name;
    translations.value = Object.entries(item.value.name_translations || {}).map(([language, name]) => ({ language, name }));
    token.value = item.value.token;
    order_priority.value = item.value.order_priority;
    origin.value = {
      label: item.value.origin.name,
      value: item.value.origin.token
    }
    if (item.value.product_related) {
      selectedProduct.value = {
        label: item.value.product_related_name,
        value: item.value.product_related_id
      };
    }
    if (item.value.exploitation) {
      selected_exploitation.value = {
        label: item.value.exploitation.name,
        code: item.value.exploitation.id
      };
    }
    if (item.value.company) {
      selected_company.value = {
        label: item.value.company.name,
        code: item.value.company.token
      };
      selected_company_id.value = item.value.company.id;
    }

    billingActive.value = item.value.billing_active;
    billingInactive.value = item.value.billing_inactive;
  } else {
    item.value = {};
  }

  originOptions.value = [];
  originOptions.value = Object.keys(OriginDataTypeChoices).map(key => ({
    value: key,
    label: t(OriginDataTypeChoices[key])
  }))
  getProducts();
  getExploitations();
  getCompanies();
  loading.value = false;
}

const getProducts = async () => {
  const response = await $ProductApiService.getAll();
  products.value = [
    {
      value: '',
      label: '-- Sense producte relacionat'
    }
  ]

  response.results.forEach(item => {
    products.value.push({
      value: item.id,
      label: item.name
    })
  })
}

const getCompanies = async () => {
  const result = await $ExploitationApiService.getCompanies();

  companies.value = [];

  result.results.forEach(company => {
    companies.value.push({
      label: company.name,
      code: company.id
    })
  });

  loading_companies.value = false;
};

const getExploitations = async () => {
  const result = await $ExploitationApiService.getData();

  exploitations.value = [];

  result.results.forEach(exploitation => {
    exploitations.value.push({
      label: exploitation.name,
      code: exploitation.id
    })
  });
};

const deleteItem = async () => {
  if (confirm(t('confirmation_text_block.confirm_delete'))) {
    saving.value = true;
    await $ProductApiService.deleteItem(props.id);
    return navigateTo('/pricing/products/')
  }
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
      order_priority: order_priority.value,
      origin_token: origin.value?.value || null,
      product_related_id: selectedProduct.value?.value || null,
      exploitation_id: selected_exploitation.value?.code || null,
      company_id: selected_company_id.value || null,
      billing_active: billingActive.value,
      billing_inactive: billingInactive.value,
    };

    item.value = $ProductApiService.save(selectedOptions);
    if (item.value) {
      return navigateTo('/pricing/products/')
    }
  }
  else {
    saving.value = false;
  }
}

const isValid = () => {
  if (name.value == '' || name.value == null) return false;
  if (token.value == '' || token.value == null) return false;
  if (selected_company.value == null) return false;
  return true;
}

const updateSelect = (event, entity) => {
  switch (entity) {
    /* case 'price_rate':
      console.log(event)
      selectedPriceRate.value = event;
      break; */
    case 'product':
      selectedProduct.value = event;
      break;
    case 'origin':
      origin.value = event;
      break;
    case 'company':
      selected_company.value = event;
      selected_company_id.value = event?.code || null;
      break;
    case 'exploitation':
      selected_exploitation.value = event;
      break;
  }
}

const openRegion = (region) => {
  closeAllRegions();
  if (region == 'company') {
    editingCompany.value = true;
  } else if (region == 'order_priority') {
    showingOrderPriority.value = true;
  }
  showRegion.value = true;
};

const toggleRegion = (force) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
  if (showRegion.value == false) {
    isSubRegionOpen.value = false;
    showingOrderPriority.value = false;
    editingCompany.value = false;
  }
}
const createCompany = () => {
  selected_company_id.value = null;
  selected_company.value = null;
  openRegion('company');

}
const editCompany = () => {
  openRegion('company');
}

const newCompany = async (new_company) => {
  company.value = new_company;
  await getCompanies();
  selected_company.value = {
    label: new_company.name,
    code: new_company.id
  }
  selected_company_id.value = new_company.id;

  closeAllRegions();
};

const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
}

const closeAllRegions = () => {
  editingCompany.value = false;

  // tanquem region
  showRegion.value = false;
};

onMounted(async () => {
  await getCompanyPermissions();
  getData()
});

</script>

<template>
  <div class="wrapper text-base p-4 max-w-full">
    <div v-if="loading">
      <div class="border border-gray-300 rounded p-4 bg-white">
        <div class="flex justify-center items-center">
          <Icon name="fa6-solid:spinner" class="animate-spin text-2xl text-slate-500" />
          <span class="ml-2">{{ $t('common.loading') }}...</span>
        </div>
      </div>
    </div>
    <div v-else class="border border-gray-300 rounded p-4 bg-white">
      <div class="row grid grid-cols-2 gap-3">
        <div class="mb-4">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.identificator') }}</label>
          <input type="text" v-model="token" class="input"
            :class="{ 'invalid': attemptedSave && (token == '' || attemptedSave && token == null) }" />
        </div>

        <div class="mb-4">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.name') }}</label>
          <input type="text" v-model="name" class="input"
            :class="{ 'invalid': attemptedSave && name == '' || attemptedSave && name == null }" />
        </div>

      </div>

      <TranslatableNameField v-model="translations" />

      <div class="row grid grid-cols-2 gap-3 ">

        <div class="mb-4">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('exploitation') }}</label>
          <v-select class="block w-full mr-1" :model-value="selected_exploitation"
            @update:modelValue="updateSelect($event, 'exploitation')" :options="exploitations" :clearable="true">
            <template #clear="{ clearSelection }">
              <span @click.stop="clearSelection" class="vs__clear" title="Clear">
                <Icon name="fa6-solid:xmark" />
              </span>
            </template>
          </v-select>
        </div>

        <div class="mb-4">
          <div class="field">
            <div class="flex">
              <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('company') }}</label>
            </div>
          </div>
          <div class="flex">
            <v-select class="block w-full mr-1 required" :disable="loading_companies" :model-value="selected_company"
              @update:modelValue="updateSelect($event, 'company')" :options="companies"
              :class="{ 'invalid': attemptedSave && selected_company == null }"></v-select>
            <button v-if="companyPermissions?.can_change"
              class="w-9 h-9 border-gray-300 mr-1 border rounded text-slate-600 enabled:hover:bg-slate-200 disabled:bg-slate-200 disabled:text-slate-400 transition-all duration-200"
              @click="editCompany" :disabled="selected_company == null">
              <Icon name="fa6-solid:pencil" class="text-md" />
            </button>
            <button v-if="companyPermissions?.can_change"
              class="w-9 h-9 border-gray-300 border rounded enabled:hover:bg-slate-200 transition-all duration-200"
              @click="createCompany">
              <Icon name="fa6-solid:plus" class="text-md text-slate-600" />
            </button>
          </div>
        </div>

      </div>

      <div class="row grid grid-cols-2 gap-3 ">

        <div class="mb-4">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.origin') }}</label>
          <v-select class="block w-full mr-1" :model-value="origin"
            @update:modelValue="updateSelect($event, 'origin')" :options="originOptions" :clearable="true">
            <template #clear="{ clearSelection }">
              <span @click.stop="clearSelection" class="vs__clear" title="Clear">
                <Icon name="fa6-solid:xmark" />
              </span>
            </template>
          </v-select>
        </div>

        <div class="mb-4">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('pricing_block.related_product') }}</label>
          <v-select class="block w-full mr-1" :model-value="selectedProduct"
            @update:modelValue="updateSelect($event, 'product')" :options="products" :clearable="true">
            <template #clear="{ clearSelection }">
              <span @click.stop="clearSelection" class="vs__clear" title="Clear">
                <Icon name="fa6-solid:xmark" />
              </span>
            </template>
          </v-select>
        </div>

        <div class="mb-4">
          <div class="flex items-center gap-2 mb-2">
            <abbr :title="t('informative_block.info_pricing_order_priority')" class="flex items-center">
              <Icon name="fa6-solid:circle-info" class="text-slate-500" />
            </abbr>
            <label class="block text-sm font-medium text-slate-500">{{ t('pricing_block.order_priority') }}</label>
          </div>
          <div class="flex items-center gap-2">
            <button @click="openRegion('order_priority')"
              class="flex items-center justify-center w-9 h-9 border-gray-300 border rounded-xl text-slate-600 hover:bg-slate-200 transition-all duration-200 self-end">
              <Icon name="fa6-solid:eye" class="text-md" />
            </button>
            <input type="number" v-model="order_priority" class="input max-w-24" />
          </div>
        </div>

        <div class="grid grid-cols-2 gap-3 items-center mb-3">
          <label class="text-slate-500 text-base flex items-center gap-1">
            {{ t('pricing_block.billing_registration') }}
            <input v-model="billingActive" type="checkbox" class="mr-2" :checked="billingActive" />
          </label>
          <label class="text-slate-500 text-base flex items-center gap-1">
            {{ t('pricing_block.billing_termination') }}
            <input v-model="billingInactive" type="checkbox" class="mr-2" :checked="billingInactive" />
          </label>
        </div>
      </div>




      <hr class="mb-2 col-span-2" />
      <div class="col-span-2 flex flex-row-reverse mt-4">
        <button v-if="id != null" @click="deleteItem" :disabled="saving" class="button-default mx-5">
          &nbsp; {{ $t('common.delete') }}
        </button>
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
      <div class="pl-10 h-full">
        <!-- subregions -->
        <MoleculesAddCompany :id="null" v-if="editingCompany" :isSubRegionOpen="isSubRegionOpen"
          @close="closeAllRegions" :company_id="selected_company_id" @new-company="newCompany"
          @show-subregion="handleSubRegionEvent" />
        <ProductsPriority v-if="showingOrderPriority" :exploitation="selected_exploitation" />
      </div>
    </div>
  </div>
</template>

<style scoped>
:deep(.vs__clear) {
  cursor: pointer;
  z-index: 10;
  display: flex;
  align-items: center;
}
</style>
