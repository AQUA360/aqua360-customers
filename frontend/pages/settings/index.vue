<script setup>
import { ref, computed } from 'vue';
import { useRouter } from 'vue-router';

import H1 from '../../components/atoms/H1.vue'
import ConfigList from '../../components/organisms/ConfigList.vue';
import VariableTypeEdit from '../../components/organisms/VariableTypeEdit.vue';
import OrderReasonEdit from '../../components/organisms/OrderReasonEdit.vue';
import BailTypeEdit from '../../components/organisms/BailTypeEdit.vue';
import BankConfigList from '~/components/organisms/BankConfigList.vue';
import AccountValuesRegion from '~/components/molecules/AccountValuesRegion.vue';
const { $ConfigProjectApiService } = useNuxtApp();
import { usePermissions } from '~/middleware/permission';
import { useToast } from 'vue-toastification';

const { t } = useI18n();
const toast = useToast();

const showRegion = ref(false);
const showRegionClass = computed(() => {
  return showRegion.value ? 'translate-x-0' : 'translate-x-[2000px]';
});

const toggleRegion = (force) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
}

const { permissions, loading } = usePermissions();
const configureColor = ref(false);
const configureMandatory = ref(false);
const configureDescription = ref(false);
const configureSerieDigits = ref(false);

// Blocks GMAO edits when NUXT_EXTERNAL_GOT=True is set in .env
const runtimeConfig = useRuntimeConfig();
const blockGmaoEdits = ref(String(runtimeConfig.public.externalGot).toLowerCase() === 'true');
const blockEdits = ref(false);

const configListTitle = ref(null);
const configListEntity = ref(null);

const RegionActive = ref(false);
const showConfigList = (title, entity, hasColor = false, hasMandatoryCheck = false, hasDescription = false, blockEditsParam = false, hasSerieDigits = false) => {
  configListTitle.value = title;
  configListEntity.value = entity;
  configureColor.value = hasColor
  configureMandatory.value = hasMandatoryCheck
  configureDescription.value = hasDescription
  blockEdits.value = blockEditsParam
  configureSerieDigits.value = hasSerieDigits

  console.log('blockEdits', blockEdits.value);
  console.log('blockGmaoEdits', blockGmaoEdits.value);

  RegionActive.value = 'ConfigListEntity';
  toggleRegion(true);
}

const config_projects = ref([]);
const getConfigProject = async () => {
  const response = await $ConfigProjectApiService.getAll();
  config_projects.value = response;
}

// Edició en línia dels valors de configuració interna (ConfigProject)
const editingConfigToken = ref(null);
const editingConfigValue = ref('');
const savingConfigToken = ref(null);

const startEditConfigProject = (item) => {
  editingConfigToken.value = item.token;
  editingConfigValue.value = item.value ?? '';
}

const cancelEditConfigProject = () => {
  editingConfigToken.value = null;
  editingConfigValue.value = '';
}

const saveConfigProject = async (item) => {
  savingConfigToken.value = item.token;
  try {
    const response = await $ConfigProjectApiService.bulkUpdateValues([
      { token: item.token, value: editingConfigValue.value },
    ]);

    if (response?.errors?.length) {
      toast.error(response.errors[0].detail || t('common.error'));
      return;
    }

    item.value = response?.updated?.[0]?.value ?? editingConfigValue.value;
    toast.success(t('common.correct_save'));
    cancelEditConfigProject();
  } catch (error) {
    console.error(error);
    toast.error(t('common.error'));
  } finally {
    savingConfigToken.value = null;
  }
}

const showConfigVariableTypes = () => {
  RegionActive.value = 'VariableType';
  toggleRegion(true);
}

const showConfigOrderReasons = () => {
  RegionActive.value = 'OrderReason';
  toggleRegion(true);
}

const showConfigBailTypes = () => {
  RegionActive.value = 'BailType';
  toggleRegion(true);
}

const showConfigBankList = () => {
  RegionActive.value = 'Bank';
  toggleRegion(true);
}

const showConfigAccountValues = () => {
  RegionActive.value = 'AccountValues';
  toggleRegion(true);
}

getConfigProject();
</script>

<template>
  <div class="pb-6">
    <div v-if="!loading" class="text-slate-900">
      <div class="flex justify-between items-center mb-6">
        <H1 class="!mb-0">{{ $t('common.settings') }}</H1>
        <AtomsLanguageSwitcher />
      </div>
      <h2 class="text-xl my-2 mb-4 font-bold">{{ $t('settings_block.master_tables') }}</h2>

      <h3 v-if="permissions?.permissions?.view_service" class="text-lg mb-2 font-bold pl-3">{{ $t('service') }}</h3>
      <ul v-if="permissions?.permissions?.view_service" class="text-base ml-3 pl-6 list-disc mb-4">

        <li class="mb-1">
          <NuxtLink to="/service/exploitations/" class="text-sky-500 underline hover:no-underline"
            :class="{ 'bg-slate-200': $route.path.indexOf('/service/exploitations/') != -1 }">{{ t('service') }}: {{
              t('service_block.exploitations') }}</NuxtLink>
        </li>
        <li class="mb-1">
          <NuxtLink to="/service/companies/" class="text-sky-500 underline hover:no-underline"
            :class="{ 'bg-slate-200': $route.path.indexOf('/service/companies/') != -1 }">{{ t('service') }}: {{
              t('service_block.companies') }}</NuxtLink>
        </li>

        <li class="mb-1"><button
            @click="showConfigList((t('service_block.companies') + ': ' + t('common.type')), 'service/company-type', false, false, false)"
            class="text-sky-500 underline hover:no-underline">{{ t('service_block.companies') }}: {{ t('common.type')
            }}</button></li>
        <li class="mb-1"><button
            @click="showConfigList((t('common.supply_points') + ': ' + t('common.statuses')), 'service/supply-point-status', true, false, false, true)"
            class="text-sky-500 underline hover:no-underline">{{ t('common.supply_points') }}: {{ t('common.statuses')
            }}</button></li>
        <li class="mb-1"><button
            @click="showConfigList((t('common.supply_points') + ': ' + t('common.type')), 'service/supply-point-type', false, false, false, true)"
            class="text-sky-500 underline hover:no-underline">{{ t('common.supply_points') }}: {{ t('common.type')
            }}</button></li>
        <li class="mb-1"><button
            @click="showConfigList((t('common.supply_points') + ': ' + t('service_block.supply_source')), 'service/supply-point-source', false, false, false)"
            class="text-sky-500 underline hover:no-underlinee">{{ t('common.supply_points') }}: {{
              t('service_block.supply_source') }}</button></li>
        <li class="mb-1"><button
            @click="showConfigList((t('common.supply_points') + ': ' + t('service_block.supply_type')), 'service/supply-point-supply-type', false, false, false)"
            class="text-sky-500 underline hover:no-underline">{{ t('common.supply_points') }}: {{
              t('service_block.supply_type') }}</button></li>
        <li class="mb-1"><button
            @click="showConfigList((t('common.supply_points') + ': ' + t('address_block.location')), 'service/supply-point-placement', false, false, false)"
            class="text-sky-500 underline hover:no-underline">{{ t('common.supply_points') }}: {{
              t('address_block.location') }}</button></li>

        <li class="mb-1"><button
            @click="showConfigList((t('common.meters') + ': ' + t('common.statuses')), 'service/meter-status', true, false, false, true)"
            class="text-sky-500 underline hover:no-underline">{{ t('common.meters') }}: {{ t('common.statuses')
            }}</button></li>
        <li class="mb-1"><button
            @click="showConfigList((t('common.meters') + ': ' + t('service_block.calibers')), 'service/meter-caliber', false, false, false)"
            class="text-sky-500 underline hover:no-underline">{{ t('common.meters') }}: {{ t('service_block.calibers')
            }}</button></li>

        <li class="mb-1"><button
            @click="showConfigList((t('common.clusters') + ' ' + t('service_block.nozzles') + ': ' + t('common.statuses')), 'service/cluster-nozzle-status', true, false, false, true)"
            class="text-sky-500 underline hover:no-underline">{{ t('common.clusters') }} {{ t('service_block.nozzles')
            }}: {{ t('common.statuses') }}</button></li>
        <li class="mb-1"><button
            @click="showConfigList((t('common.clusters') + ' ' + t('service_block.nozzles') + ': ' + t('common.type')), 'service/cluster-nozzle-type', false, false, false)"
            class="text-sky-500 underline hover:no-underline">{{ t('common.clusters') }} {{ t('service_block.nozzles')
            }}: {{ t('common.type') }}</button></li>
        <li class="mb-1"><button
            @click="showConfigList((t('common.clusters') + ': ' + t('common.statuses')), 'service/cluster-status', true, false, false, true)"
            class="text-sky-500 underline hover:no-underline">{{ t('common.clusters') }}: {{ t('common.statuses')
            }}</button></li>

        <li class="mb-1"><button
            @click="showConfigList((t('common.connections') + ': ' + t('common.statuses')), 'service/connection-status', true, false, false, true)"
            class="text-sky-500 underline hover:no-underline">{{ t('common.connections') }}: {{ t('common.statuses')
            }}</button></li>
        <li class="mb-1"><button
            @click="showConfigList((t('common.connections') + ': ' + t('common.type')), 'service/connection-type', false, false, false)"
            class="text-sky-500 underline hover:no-underline">{{ t('common.connections') }}: {{ t('common.type')
            }}</button></li>
        <li class="mb-1"><button
            @click="showConfigList((t('common.connections') + ': ' + t('service_block.installation_type')), 'service/connection-installation-type', false, false, false, true)"
            class="text-sky-500 underline hover:no-underline">{{ t('common.connections') }}: {{
              t('service_block.installation_type') }}</button></li>
        <li class="mb-1"><button
            @click="showConfigList((t('common.connections') + ': ' + t('common.usage_type')), 'service/connection-use-type', false, false, false, true)"
            class="text-sky-500 underline hover:no-underline">{{ t('common.connections') }}: {{ t('common.usage_type')
            }}</button></li>
        <li class="mb-1"><button
            @click="showConfigList((t('common.connections') + ': ' + t('service_block.valve_type')), 'service/connection-valve-type', false, false, false)"
            class="text-sky-500 underline hover:no-underline">{{ t('common.connections') }}: {{
              t('service_block.valve_type') }}</button></li>
        <li class="mb-1"><button
            @click="showConfigList((t('common.connections') + ': ' + t('service_block.diameters')), 'service/connection-diameter', false, false, false)"
            class="text-sky-500 underline hover:no-underline">{{ t('common.connections') }}: {{
              t('service_block.diameters') }}</button></li>
        <li class="mb-1"><button
            @click="showConfigList((t('common.connections') + ': ' + t('service_block.materials')), 'service/connection-material', false, false, false)"
            class="text-sky-500 underline hover:no-underline">{{ t('common.connections') }}: {{
              t('service_block.materials') }}</button></li>
        <li class="mb-1"><button
            @click="showConfigList((t('common.connections') + ': ' + t('common.documentation')), 'service/connection-documentation-type', false, false, false)"
            class="text-sky-500 underline hover:no-underline">{{ t('common.connections') }}: {{
              t('common.documentation') }}</button></li>
        <li class="mb-1"><button
            @click="showConfigList((t('common.clusters') + ': ' + t('common.documentation')), 'service/cluster-documentation-type', false, false, false)"
            class="text-sky-500 underline hover:no-underline">{{ t('common.clusters') }}: {{ t('common.documentation')
            }}</button></li>

        <li class="mb-1"><button
            @click="showConfigList((t('common.connection_requests') + ': ' + t('common.statuses')), 'service/connection-request-status', true, false, false, true)"
            class="text-sky-500 underline hover:no-underline">{{ t('common.connection_requests') }}: {{
              t('common.statuses') }}</button></li>

        <li class="mb-1"><button
            @click="showConfigList((t('common.supply_cuts') + ': ' + t('common.statuses')), 'service/supply-cut-status', true, false, false, true)"
            class="text-sky-500 underline hover:no-underline">{{ t('common.supply_cuts') }}: {{ t('common.statuses')
            }}</button></li>
      </ul>

      <h3 v-if="permissions?.permissions?.view_service" class="text-lg mb-2 font-bold pl-3">{{
        $t('address_block.addresses') }}</h3>
      <ul v-if="permissions?.permissions?.view_service" class="text-base ml-3 pl-6 list-disc mb-4">
        <li class="mb-1">
          <NuxtLink to="/service/streets/" class="text-sky-500 underline hover:no-underline"
            :class="{ 'bg-slate-200': $route.path.indexOf('/service/streets/') != -1 }">{{
              t('address_block.street_management') }}</NuxtLink>
        </li>
        <li class="mb-1"><button
            @click="showConfigList((t('address_block.streets') + ': ' + t('common.type')), 'coredata/street-type', false, false, false, true)"
            class="text-sky-500 underline hover:no-underline">{{ t('address_block.streets') }}: {{ t('common.type')
            }}</button></li>
      </ul>

      <h3 v-if="permissions?.permissions?.view_contract" class="text-lg mb-2 font-bold pl-3">{{ $t('contracting') }}
      </h3>
      <ul v-if="permissions?.permissions?.view_contract" class="text-base ml-3 pl-6 list-disc mb-4">
        <li class="mb-1"><button
            @click="showConfigList((t('person') + ': ' + t('common.identificator')), 'coredata/identification-type', false, false, false, true)"
            class="text-sky-500 underline hover:no-underline">{{ t('person') }}: {{ t('common.identificator')
            }}</button></li>
        <li class="mb-1"><button
            @click="showConfigList((t('contract') + ': ' + t('common.statuses')), 'contract/contract-status', true, false, false, true)"
            class="text-sky-500 underline hover:no-underline">{{ t('contract') }}: {{ t('common.statuses') }}</button>
        </li>
        <li class="mb-1"><button
            @click="showConfigList((t('contract') + ': ' + t('common.usage_type')), 'contract/contract-use-type', false, false, false, true)"
            class="text-sky-500 underline hover:no-underline">{{ t('contract') }}: {{ t('common.usage_type') }}</button>
        </li>
        <li class="mb-1"><button
            @click="showConfigList((t('contract') + ': ' + t('contract_block.client_type')), 'contract/contract-client-type', false, false, false)"
            class="text-sky-500 underline hover:no-underline">{{ t('contract') }}: {{ t('contract_block.client_type')
            }}</button></li>
        <li class="mb-1"><button
            @click="showConfigList((t('contract') + ': ' + t('contract_block.representative_type')), 'contract/contract-representative-type', false, false, false)"
            class="text-sky-500 underline hover:no-underline">{{ t('contract') }}: {{
              t('contract_block.representative_type') }}</button></li>
        <li class="mb-1"><button
            @click="showConfigList((t('contract') + ': ' + t('common.documentation')), 'contract/contract-documentation-type', false, false, false)"
            class="text-sky-500 underline hover:no-underline">{{ t('contract') }}: {{ t('common.documentation')
            }}</button></li>
        <li class="mb-1"><button
            @click="showConfigList((t('contract') + ': ' + t('contract_block.category')), 'contract/contract-category', false, false, false)"
            class="text-sky-500 underline hover:no-underline">{{ t('contract') }}: {{ t('contract_block.category')
            }}</button></li>
        <li class="mb-1"><button
            @click="showConfigList((t('contract') + ': ' + t('contract_block.surrogation')), 'contract/contract-surrogation-type', false, false, false)"
            class="text-sky-500 underline hover:no-underline">{{ t('contract') }}: {{ t('contract_block.surrogation')
            }}</button></li>
        <li class="mb-1"><button
            @click="showConfigList((t('contract') + ': ' + t('contract_block.surrogation') + ' ' + t('common.doc_type').toLowerCase()), 'contract/contract-surrogation-document-type', false, false, false)"
            class="text-sky-500 underline hover:no-underline">{{ t('contract') }}: {{ t('contract_block.surrogation') }}
            {{ t('common.doc_type').toLowerCase() }}</button></li>
        <li class="mb-1"><button
            @click="showConfigList((t('contract') + ': ' + t('contract_block.tenant_change') + ' ' + t('common.doc_type').toLowerCase()), 'contract/contract-tenant-change-document-type', false, false, false)"
            class="text-sky-500 underline hover:no-underline">{{ t('contract') }}: {{ t('contract_block.tenant_change')
            }} {{ t('common.doc_type').toLowerCase() }}</button></li>
        <li class="mb-1"><button
            @click="showConfigList((t('common.aca_documents') + ': ' + t('common.statuses')), 'contract/aca-document-status', true, false, false, true)"
            class="text-sky-500 underline hover:no-underline">{{ t('common.aca_documents') }}: {{ t('common.statuses')
            }}</button></li>

        <li class="mb-1">
          <NuxtLink to="/contract/contract-request-type/" class="text-sky-500 underline hover:no-underline">{{
            t('contract_request') }}: {{ t('common.type') }}</NuxtLink>
        </li>
        <li class="mb-1">
          <NuxtLink to="/contract/clause-templates/" class="text-sky-500 underline hover:no-underline">{{
            t('contract_block.clauses') }}: {{ t('contract_block.clause_templates') }}</NuxtLink>
        </li>
        <li class="mb-1"><button
            @click="showConfigList((t('contract_request') + ': ' + t('common.statuses')), 'contract/contract-request-status', true, false, false, true)"
            class="text-sky-500 underline hover:no-underline">{{ t('contract_request') }}: {{ t('common.statuses')
            }}</button></li>

        <li class="mb-1"><button
            @click="showConfigList((t('contract_termination_request') + ': ' + t('common.type')), 'contract/contract-termination-request-type', false, false, false)"
            class="text-sky-500 underline hover:no-underline">{{ t('contract_termination_request') }}: {{
              t('common.type') }}</button></li>
        <li class="mb-1"><button
            @click="showConfigList((t('contract_termination_request') + ': ' + t('common.statuses')), 'contract/contract-termination-request-status', true, false, false, true)"
            class="text-sky-500 underline hover:no-underline">{{ t('contract_termination_request') }}: {{
              t('common.statuses') }}</button></li>

        <li class="mb-1">
          <NuxtLink to="/contract/bonification-type/" class="text-sky-500 underline hover:no-underline">{{
            t('bonifications') }}: {{ t('contract_block.bonification_type') }}</NuxtLink>
        </li>
        <li class="mb-1"><button @click="showConfigVariableTypes" class="text-sky-500 underline hover:no-underline">{{
          t('variables') }}: {{ t('contract_block.variable_type') }}</button></li>
        <li class="mb-1"><button @click="showConfigBailTypes" class="text-sky-500 underline hover:no-underline">{{
          t('bail') }}: {{ t('billing_block.bail_type') }}</button></li>
        <li class="mb-1"><button @click="showConfigBankList" class="text-sky-500 underline hover:no-underline">{{
          t('common.banks') }}</button></li>
      </ul>

      <h3 v-if="permissions?.permissions?.view_order" class="text-lg mb-2 font-bold pl-3">{{ $t('work_orders') }}</h3>
      <ul v-if="permissions?.permissions?.view_order" class="text-base ml-3 pl-6 list-disc mb-4">
        <li class="mb-1">
          <NuxtLink to="/order/order-types/" class="text-sky-500 underline hover:no-underline"
            :class="{ 'bg-slate-200': $route.path.indexOf('/order/order-types/') != -1 }">{{ t('work_orders') }}: {{
              t('common.type') }}</NuxtLink>
        </li>
        <li class="mb-1"><button @click="showConfigOrderReasons" class="text-sky-500 underline hover:no-underline">{{
          t('work_orders') }}: {{ t('order_block.reasons') }}</button></li>
        <li class="mb-1"><button
            @click="showConfigList((t('work_orders') + ': ' + t('common.statuses')), 'order/order-status', true, false, false, true)"
            class="text-sky-500 underline hover:no-underline">{{ t('work_orders') }}: {{ t('common.statuses')
            }}</button></li>
        <li class="mb-1"><button
            @click="showConfigList((t('work_orders') + ': ' + t('common.priority')), 'order/order-priority', true, false, false, true)"
            class="text-sky-500 underline hover:no-underline">{{ t('work_orders') }}: {{ t('common.priority')
            }}</button></li>
      </ul>

      <h3 v-if="permissions?.permissions?.view_pricing" class="text-lg mb-2 font-bold pl-3">{{ $t('pricing') }}</h3>
      <ul v-if="permissions?.permissions?.view_pricing" class="text-base ml-3 pl-6 list-disc mb-4">
        <li class="mb-1">
          <NuxtLink to="/pricing/billing-ranges/" class="text-sky-500 underline hover:no-underline"
            :class="{ 'bg-slate-200': $route.path.indexOf('/pricing/billing-ranges/') != -1 }">{{ (t('pricing')) }}: {{
              (t('pricing_block.billing_ranges')) }}</NuxtLink>
        </li>
        <li class="mb-1">
          <NuxtLink to="/pricing/line-item-types/" class="text-sky-500 underline hover:no-underline"
            :class="{ 'bg-slate-200': $route.path.indexOf('/pricing/line-item-types/') != -1 }">{{ (t('pricing')) }}: {{
              (t('pricing_block.line_items')) }}</NuxtLink>
        </li>
        <li class="mb-1"><button
            @click="showConfigList((t('common.products') + ': ' + t('common.origins')), 'pricing/product-origin', false, false, false, true)"
            class="text-sky-500 underline hover:no-underline">{{ t('common.products') }}: {{ t('common.origins')
            }}</button></li>
        <!-- <li class="mb-1"><button @click="showConfigList($t('Conceptes: Variables de càlcul'), 'pricing/variable-calculation', false, false, false, true)" class="text-sky-500 underline hover:no-underline">{{ $t('Conceptes: Variables de càlcul') }}</button></li> -->
        <li class="mb-1"><button
            @click="showConfigList((t('taxes') + ': ' + t('common.type')), 'pricing/tax', false, false, false, true)"
            class="text-sky-500 underline hover:no-underline">{{ t('taxes') }}: {{ t('common.type') }}</button></li>
        <li class="mb-1"><button
            @click="showConfigList((t('billing') + ': ' + t('pricing_block.periodicity')), 'pricing/billing-period', false, false, false, true)"
            class="text-sky-500 underline hover:no-underline">{{ t('billing') }}: {{ t('pricing_block.periodicity')
            }}</button></li>
        <!-- <li class="mb-1"><button @click="showConfigList((t('billing') + ': ' + t('pricing_block.account_code')), 'pricing/article-code', false, false, false, true)" class="text-sky-500 underline hover:no-underline">{{ t('billing') }}: {{ t('pricing_block.account_code') }}</button></li>
      <li class="mb-1"><NuxtLink to="/pricing/article-codes/" class="text-sky-500 underline hover:no-underline" :class="{ 'bg-slate-200': $route.path.indexOf('/pricing/article-codes/') != -1 }">{{ (t('pricing')) }}: {{ (t('settings_block.config_article_codes')) }}</NuxtLink></li> -->
      </ul>

      <h3 v-if="permissions?.permissions?.view_billing" class="text-lg mb-2 font-bold pl-3">{{ $t('billing') }}</h3>
      <ul v-if="permissions?.permissions?.view_billing" class="text-base ml-3 pl-6 list-disc mb-4">
        <li class="mb-1">
          <NuxtLink to="/billing/biller/" class="text-sky-500 underline hover:no-underline"
            :class="{ 'bg-slate-200': $route.path.indexOf('/billing/biller/') != -1 }">{{ $t('common.configure') }} {{
              $t('billing_block.biller') }}</NuxtLink>
        </li>

        <!-- <li class="mb-1"><NuxtLink to="/billing/payments/" class="text-sky-500 underline hover:no-underline">{{ $t('Facturació: Pagaments') }}</NuxtLink></li> -->
        <li class="mb-1"><button
            @click="showConfigList((t('billing') + ': ' + t('common.statuses')), 'billing/billing-status', true, false, false, true)"
            class="text-sky-500 underline hover:no-underline">{{ t('billing') }}: {{ t('common.statuses') }}</button>
        </li>
        <!-- <li class="mb-1"><NuxtLink to="/pricing/line-item-types/" class="text-sky-500 underline hover:no-underline" :class="{ 'bg-slate-200': $route.path.indexOf('/pricing/line-item-types/') != -1 }">{{ $t('Lots de facturació: Plantilles') }}</NuxtLink></li> -->

        <!-- <li class="mb-1"><button @click="showConfigList($t('Pagaments: Estats'), 'billing/payment-status', true, false, false, true)" class="text-sky-500 underline hover:no-underline">{{ $t('Pagaments: Estats') }}</button></li> -->
        <li class="mb-1"><button
            @click="showConfigList((t('invoices') + ': ' + t('common.statuses')), 'billing/invoice-status', true, false, true, true)"
            class="text-sky-500 underline hover:no-underline">{{ $t('invoices') }}: {{ t('common.statuses') }}</button>
        </li>
        <li class="mb-1"><button
            @click="showConfigList((t('payment') + ': ' + t('common.statuses')), 'billing/payment-status', true, false, true, true)"
            class="text-sky-500 underline hover:no-underline">{{ $t('payment') }}: {{ t('common.statuses') }}</button>
        </li>
        <li class="mb-1"><button
            @click="showConfigList((t('billing_block.joined_payment') + ': ' + t('common.statuses')), 'billing/joined-payment-status', true, false, false, true)"
            class="text-sky-500 underline hover:no-underline">{{ $t('billing_block.joined_payment') }}: {{
              t('common.statuses') }}</button></li>
        <li class="mb-1"><button
            @click="showConfigList((t('commitment_deposit') + ': ' + t('common.statuses')), 'billing/commitment-deposit-status', true, false, true, true)"
            class="text-sky-500 underline hover:no-underline">{{ $t('commitment_deposit') }}: {{ t('common.statuses')
            }}</button></li>
        <li class="mb-1"><button
            @click="showConfigList((t('claim_block.commitment_payments') + ': ' + t('common.statuses')), 'billing/payment-commitment-status', true, false, true, true)"
            class="text-sky-500 underline hover:no-underline">{{ t('claim_block.commitment_payments') }}: {{
              t('common.statuses') }}</button></li>
        <li class="mb-1"><button
            @click="showConfigList((t('invoices') + ': ' + t('billing_block.series')), 'billing/invoice-serie', false, false, false, true)"
            class="text-sky-500 underline hover:no-underline">{{ t('invoices') }}: {{ t('billing_block.series')
            }}</button></li>
        <li class="mb-1"><button
            @click="showConfigList((t('invoices') + ': ' + t('common.type')), 'billing/invoice-type', false, false, false, true)"
            class="text-sky-500 underline hover:no-underline">{{ t('invoices') }}: {{ t('common.type') }}</button></li>
        <li class="mb-1"><button
            @click="showConfigList((t('invoices') + ': ' + t('billing_block.alerts')), 'billing/invoice-warnings', false, false, false, true)"
            class="text-sky-500 underline hover:no-underline">{{ t('invoices') }}: {{ t('billing_block.alerts')
            }}</button></li>
        <li class="mb-1"><button
            @click="showConfigList((t('invoices') + ': ' + t('common.return_reason')), 'billing/reject-motive', false, false, false, true)"
            class="text-sky-500 underline hover:no-underline">{{ t('invoices') }}: {{ t('common.return_reason')
            }}</button></li>
        <!-- <li class="mb-1"><NuxtLink to="/billing/messages/" class="text-sky-500 underline hover:no-underline">{{ $t('Facturació: Missatges') }}</NuxtLink></li> -->
        <li class="mb-1">
          <NuxtLink to="/billing/invoice-templates/" class="text-sky-500 underline hover:no-underline">{{ t('billing')
            }} {{ t('billing_block.invoice_templates') }}</NuxtLink>
        </li>
        <li class="mb-1"><button
            @click="showConfigList((t('claim_block.claim_payments') + ': ' + t('common.statuses')), 'claimrequest/claim-request-status', true, false, false, true)"
            class="text-sky-500 underline hover:no-underline">{{ t('claim_block.claim_payments') }}: {{
              t('common.statuses') }}</button></li>
        <li class="mb-1">
          <NuxtLink to="/billing/claim-steps/" class="text-sky-500 underline hover:no-underline">{{
            $t('claim_block.claim_payments') }}: {{ $t('billing_block.steps') }}</NuxtLink>
        </li>
        <!-- <li class="mb-1"><button @click="showConfigList((t('common.reports') + ': ' + t('pricing_block.account_codes')), 'statistics/accounting-code', false, false, false, true)" class="text-sky-500 underline hover:no-underline">{{ t('common.reports') }}: {{ t('pricing_block.account_codes') }}</button></li>
      <li class="mb-1"><button @click="showConfigAccountValues()" class="text-sky-500 underline hover:no-underline">{{ t('common.reports') }}: {{ t('pricing_block.account_values') }}</button></li> -->
        <li class="mb-1">
          <NuxtLink to="/billing/vulnerability-request-type/" class="text-sky-500 underline hover:no-underline">{{
            t('vulnerability_request') }}: {{ t('common.type') }}</NuxtLink>
        </li>
        <li class="mb-1"><button
            @click="showConfigList((t('invoices') + ': ' + t('billing_block.categories')), 'billing/invoice-category', false, false, false, false, true)"
            class="text-sky-500 underline hover:no-underline">{{ t('invoices') }}: {{ t('billing_block.categories')
            }}</button></li>
      </ul>

      <h3 v-if="permissions?.permissions?.view_reading" class="text-lg mb-2 font-bold pl-3">{{ $t('readings') }}</h3>
      <ul v-if="permissions?.permissions?.view_reading" class="text-base ml-3 pl-6 list-disc mb-4">
        <li class="mb-1">
          <NuxtLink to="/reading/reading-batch-templates/" class="text-sky-500 underline hover:no-underline"
            :class="{ 'bg-slate-200': $route.path.indexOf('/reading/reading-batch-templates/') != -1 }">{{
              $t('settings_block.config_reading_batch_template') }}</NuxtLink>
        </li>
        <li class="mb-1">
          <NuxtLink to="/statistics/reading-batch-export-config" class="text-sky-500 underline hover:no-underline"
            :class="{ 'bg-slate-200': $route.path.indexOf('/statistics/reading-batch-export-config') != -1 }">{{
              $t('settings_block.reading_batch_export_file') }}</NuxtLink>
        </li>
        <li class="mb-1"><button
            @click="showConfigList((t('common.reading_batches') + ': ' + t('common.statuses')), 'billing/reading-batch-status', true, false, false, true)"
            class="text-sky-500 underline hover:no-underline">{{ t('common.reading_batches') }}: {{ t('common.statuses')
            }}</button></li>
        <li class="mb-1"><button
            @click="showConfigList((t('billing_block.invoice_alerts') + ': ' + t('common.type')), 'billing/reading-alert-type', true, false, false, true)"
            class="text-sky-500 underline hover:no-underline">{{ t('billing_block.invoice_alerts') }}: {{
              t('common.type') }}</button></li>
        <li class="mb-1"><button
            @click="showConfigList((t('billing_block.reader_alerts') + ': ' + t('common.type')), 'billing/reader-alert', false, false, false)"
            class="text-sky-500 underline hover:no-underline">{{ t('billing_block.reader_alerts') }}: {{
              t('common.type') }}</button></li>
        <li class="mb-1"><button
            @click="showConfigList((t('billing_block.remote_alerts') + ': ' + t('common.type')), 'billing/remote-reading-alert', false, false, false, true)"
            class="text-sky-500 underline hover:no-underline">{{ t('billing_block.remote_alerts') }}: {{
              t('common.type') }}</button></li>
      </ul>

      <h3 v-if="permissions?.permissions?.view_service" class="text-lg mb-2 font-bold pl-3">{{ $t('common.frauds') }}
      </h3>
      <ul v-if="permissions?.permissions?.view_service" class="text-base ml-3 pl-6 list-disc mb-4">
        <li class="mb-1"><button
            @click="showConfigList((t('common.fraud_mngs') + ': ' + t('common.statuses')), 'fraud/fraud-status', true, false, false, true)"
            class="text-sky-500 underline hover:no-underline">{{ t('common.fraud_mngs') }}: {{ t('common.statuses')
            }}</button></li>
        <li class="mb-1"><button
            @click="showConfigList((t('common.fraud_mngs') + ': ' + t('common.type')), 'fraud/fraud-type', true, false, false, true)"
            class="text-sky-500 underline hover:no-underline">{{ t('common.fraud_mngs') }}: {{ t('common.type')
            }}</button></li>
      </ul>

      <h3 v-if="permissions?.permissions?.view_customer_service" class="text-lg mb-2 font-bold pl-3">{{
        $t('communication') }}</h3>
      <ul v-if="permissions?.permissions?.view_customer_service" class="text-base ml-3 pl-6 list-disc mb-4">
        <li class="mb-1"><button
            @click="showConfigList((t('communication') + ': ' + t('common.statuses')), 'communication/communication-status', true, false, true, true)"
            class="text-sky-500 underline hover:no-underline">{{ t('communication') }}: {{ t('common.statuses')
            }}</button></li>
        <li class="mb-1"><button
            @click="showConfigList((t('communication') + ': ' + t('common.use_type')), 'communication/communication-use-type', false, false, false, true)"
            class="text-sky-500 underline hover:no-underline">{{ t('communication') }}: {{ t('common.use_type')
            }}</button></li>
        <li class="mb-1"><button
            @click="showConfigList((t('common.comms_process_detail') + ': ' + t('common.statuses')), 'communication/communication-process-status', true, false, true, true)"
            class="text-sky-500 underline hover:no-underline">{{ t('common.comms_process_detail') }}: {{
              t('common.statuses') }}</button></li>
        <li class="mb-1"><button
            @click="showConfigList((t('customer_service_block.comms_templates') + ': ' + t('common.origins')), 'communication/message-origin', false, false, false, true)"
            class="text-sky-500 underline hover:no-underline">{{ t('customer_service_block.comms_templates') }}: {{
              t('common.origins') }}</button></li>
        <li class="mb-1">
          <NuxtLink to="/communication/message-templates/" class="text-sky-500 underline hover:no-underline">{{
            t('communication') }}: {{ t('customer_service_block.comms_templates') }}</NuxtLink>
        </li>
        <!-- <li class="mb-1"><NuxtLink to="/communication/communications/" class="text-sky-500 underline hover:no-underline">{{ $t('Comunicacions') }}</NuxtLink></li> -->
      </ul>

      <h3 v-if="permissions?.permissions?.view_customer_service" class="text-lg mb-2 font-bold pl-3">{{
        $t('common.incidents') }}</h3>
      <ul v-if="permissions?.permissions?.view_customer_service" class="text-base ml-3 pl-6 list-disc mb-4">
        <li class="mb-1"><button
            @click="showConfigList((t('common.incidents') + ': ' + t('common.type')), 'notification/incident-type', true, false, false)"
            class="text-sky-500 underline hover:no-underline">{{ t('common.incidents') }}: {{ t('common.type')
            }}</button></li>
        <li class="mb-1"><button
            @click="showConfigList((t('common.incidents') + ': ' + t('common.statuses')), 'notification/incident-status', true, false, false, true)"
            class="text-sky-500 underline hover:no-underline">{{ t('common.incidents') }}: {{ t('common.statuses')
            }}</button></li>
      </ul>

      <h3 v-if="permissions?.permissions?.view_customer_service" class="text-lg mb-2 font-bold pl-3">{{
        $t('common.docs') }}</h3>
      <ul v-if="permissions?.permissions?.view_customer_service" class="text-base ml-3 pl-6 list-disc mb-4">
        <li class="mb-1"><button
            @click="showConfigList((t('common.doc') + ': ' + t('common.statuses')), 'statistics/daily-document-status', true, false, false, true)"
            class="text-sky-500 underline hover:no-underline">{{ t('common.doc') }}: {{ t('common.statuses') }}</button>
        </li>
        <!-- <li class="mb-1"><button @click="showConfigList((t('common.doc') + ': ' + t('common.template')), 'statistics/daily-document-template', true, false, false)" class="text-sky-500 underline hover:no-underline">{{ t('common.doc') }}: {{ t('common.template') }}</button></li> -->
        <li class="mb-1">
          <NuxtLink to="/statistics/daily-document-templates/" class="text-sky-500 underline hover:no-underline"
            :class="{ 'bg-slate-200': $route.path.indexOf('/statistics/daily-document-templates/') != -1 }">{{
              t('common.doc') }}: {{ $t('statistics_block.daily_document_templates') }}</NuxtLink>
        </li>
      </ul>

      <h3 v-if="permissions?.permissions?.view_user" class="text-lg mb-2 font-bold pl-3">{{ $t('users') }}</h3>
      <ul v-if="permissions?.permissions?.view_user" class="text-base ml-3 pl-6 list-disc mb-4">
        <li class="mb-1">
          <NuxtLink to="/user/groups/" class="text-sky-500 underline hover:no-underline"
            :class="{ 'bg-slate-200': $route.path.indexOf('/user/groups/') != -1 }">{{ $t('settings_block.mng_groups')
            }}</NuxtLink>
        </li>
        <li class="mb-1">
          <NuxtLink to="/user/users/" class="text-sky-500 underline hover:no-underline"
            :class="{ 'bg-slate-200': $route.path.indexOf('/user/users/') != -1 }">{{ $t('settings_block.mng_users') }}
          </NuxtLink>
        </li>
      </ul>

      <h2 v-if="permissions?.permissions?.view_user" class="text-xl my-2 mb-4 font-bold">{{
        $t('settings_block.settings') }}</h2>

      <ul v-if="permissions?.permissions?.view_user" class="text-base ml-3 pl-6 list-disc mb-4">
        <li class="mb-1">
          <NuxtLink to="/settings/config_aca/" class="text-sky-500 underline hover:no-underline"
            :class="{ 'bg-slate-200': $route.path.indexOf('/settings/config_aca/') != -1 }">{{
              t('settings_block.config_aca') }}</NuxtLink>
        </li>
        <!-- <li class="mb-1">
          <NuxtLink to="/settings/accounting/" class="text-sky-500 underline hover:no-underline"
            :class="{ 'bg-slate-200': $route.path.indexOf('/settings/accounting/') != -1 }">{{
              t('pricing_block.accounting') }}</NuxtLink>
        </li> -->
      </ul>

      <details v-if="permissions?.permissions?.view_user" class="text-base  pl-6">
        <summary class="cursor-pointer">{{ $t('settings_block.internal_settings') }}</summary>
        <ul v-if="config_projects.length" class="mt-3 ml-3 leading-6">
          <li v-for="(item, index) in config_projects" :key="index" class="flex gap-3 items-center mb-1">
            <abbr class="font-bold" :title=item.name>{{ item.token }}:</abbr>
            <template v-if="editingConfigToken === item.token">
              <input v-model="editingConfigValue" type="text" class="input !w-auto !py-1 min-w-[12rem]"
                :disabled="savingConfigToken === item.token" @keyup.enter="saveConfigProject(item)"
                @keyup.esc="cancelEditConfigProject()" />
              <button class="button-secondary !py-1" :disabled="savingConfigToken === item.token"
                @click="saveConfigProject(item)">
                <Icon v-if="savingConfigToken === item.token" name="fa6-solid:spinner" class="animate-spin" />
                <span v-else>{{ t('common.save') }}</span>
              </button>
              <button class="button-default-xs !py-1" :disabled="savingConfigToken === item.token"
                @click="cancelEditConfigProject()">{{ t('common.cancel') }}</button>
            </template>
            <template v-else>
              <span>{{ item.value }}</span>
              <button v-if="permissions?.permissions?.change_user" class="text-sky-500 hover:text-sky-700"
                :title="t('common.edit')" @click="startEditConfigProject(item)">
                <Icon name="fa6-solid:pen-to-square" />
              </button>
            </template>
          </li>
        </ul>
      </details>

    </div>
    <div v-else>
      <div class="rounded p-4 bg-white">
        <div class="flex items-center">
          <Icon name="fa6-solid:spinner" class="animate-spin text-2xl text-slate-500" />
          <span class="ml-2">{{ $t('common.loading') }}...</span>
        </div>
      </div>
    </div>

    <div role="region" id="right_page"
      :class="['fixed', 'bg-white', 'w-1/2', 'h-full', 'border-l', 'border-gray-100', 'top-0', 'right-0', 'transition-transform', 'duration-270', 'ease', 'py-2', 'text-base', showRegionClass, 'overflow-y-auto', 'overflow-x-hidden']">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="toggleRegion(false)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="pl-10 h-full">
        <ConfigList v-if="RegionActive == 'ConfigListEntity' && configListEntity" :title="configListTitle"
          :entity="configListEntity" :hasColor="configureColor" :hasMandatoryCheck="configureMandatory"
          :hasDescription="configureDescription" :blockEdits="blockEdits" :hasSerieDigits="configureSerieDigits" />
        <VariableTypeEdit v-if="RegionActive == 'VariableType'" />
        <OrderReasonEdit v-if="RegionActive == 'OrderReason'" />
        <BailTypeEdit v-if="RegionActive == 'BailType'" />
        <BankConfigList v-if="RegionActive == 'Bank'" />
        <AccountValuesRegion v-if="RegionActive == 'AccountValues'" @close="toggleRegion(false)" />
      </div>
    </div>
  </div>
</template>

<style>
div#right_page {
  box-shadow: rgba(15, 15, 15, 0.04) 0px 0px 0px 1px, rgba(15, 15, 15, 0.03) 0px 3px 6px, rgba(15, 15, 15, 0.06) 0px 9px 24px;
}
</style>
