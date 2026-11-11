<script setup>
import { ref, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import H1 from '../../components/atoms/H1.vue'
import Tabs from '~/components/atoms/Tabs.vue';
import ConfigList from '../../components/organisms/ConfigList.vue';
import VariableTypeEdit from '../../components/organisms/VariableTypeEdit.vue';
import OrderReasonEdit from '../../components/organisms/OrderReasonEdit.vue';
import BailTypeEdit from '../../components/organisms/BailTypeEdit.vue';
import BankConfigList from '~/components/organisms/BankConfigList.vue';
import IncidentSettings from '~/components/organisms/IncidentSettings.vue';
import AccountValuesRegion from '~/components/molecules/AccountValuesRegion.vue';
import MeterDictionaryList from '~/components/organisms/MeterDictionaryList.vue';
const { $ConfigProjectApiService } = useNuxtApp();
import { usePermissions } from '~/middleware/permission';
import { useToast } from 'vue-toastification';

const { t } = useI18n();
const toast = useToast();

const showRegion = ref(false);
const showRegionClass = computed(() => {
  return showRegion.value ? 'translate-x-0' : 'translate-x-full';
});

const toggleRegion = (force) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
}

const { permissions, loading } = usePermissions();

const configureColor = ref(false);
const configureMandatory = ref(false);
const configureDescription = ref(false);
const configureSerieDigits = ref(false);
const configureChangeOfName = ref(false);

// Blocks GMAO edits when NUXT_EXTERNAL_GOT=True is set in .env
const runtimeConfig = useRuntimeConfig();
const blockGmaoEdits = ref(String(runtimeConfig.public.externalGot).toLowerCase() === 'true');
const blockEdits = ref(false);

const configListTitle = ref(null);
const configListEntity = ref(null);

const RegionActive = ref(false);
const showConfigList = (title, entity, hasColor = false, hasMandatoryCheck = false, hasDescription = false, blockEditsParam = false, hasSerieDigits = false, hasChangeOfNameCheck = false) => {
  configListTitle.value = title;
  configListEntity.value = entity;
  configureColor.value = hasColor
  configureMandatory.value = hasMandatoryCheck
  configureDescription.value = hasDescription
  blockEdits.value = blockEditsParam
  configureSerieDigits.value = hasSerieDigits
  configureChangeOfName.value = hasChangeOfNameCheck

  console.log('blockEdits', blockEdits.value);
  console.log('blockGmaoEdits', blockGmaoEdits.value);

  RegionActive.value = 'ConfigListEntity';
  toggleRegion(true);
}

const config_projects = ref([]);
const smartMeteringEnabled = computed(() => {
  const item = (config_projects.value || []).find(
    (entry) => entry?.token === 'smart_metering_authentication_token',
  );
  return Boolean(String(item?.value ?? '').trim());
});
// Secció Configuració ACA: només per als projectes que depenen de l'ACA.
const isAcaOrg = computed(() => {
  const item = (config_projects.value || []).find(
    (entry) => entry?.token === 'public_org_type',
  );
  return String(item?.value ?? '').trim().toLowerCase() === 'aca';
});
const getConfigProject = async () => {
  const response = await $ConfigProjectApiService.getAll();
  config_projects.value = Array.isArray(response) ? response : [];
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

const showConfigAccountValues = () => {
  RegionActive.value = 'AccountValues';
  toggleRegion(true);
}

const meterDictionaryKind = ref(null);
const meterDictionaryTitle = ref('');
const showMeterDictionary = (title, kind) => {
  meterDictionaryTitle.value = title;
  meterDictionaryKind.value = kind;
  RegionActive.value = 'MeterDictionary';
  toggleRegion(true);
}

// Opcions de la pàgina. Cada opció és un enllaç a una pàgina pròpia (`to`), una taula
// simple editada amb ConfigList (`entity`), un diccionari de comptadors (`dictionaryKind`)
// o un panell lateral concret (`region`).
// Les opcions de configuració van a la pestanya General i les taules simples
// (estats, tipus, motius...) a Taules mestres.
const list = (label, entity, hasColor = false, hasMandatoryCheck = false, hasDescription = false, blockEdits = false, hasSerieDigits = false, hasChangeOfNameCheck = false) => ({
  label, entity, options: [hasColor, hasMandatoryCheck, hasDescription, blockEdits, hasSerieDigits, hasChangeOfNameCheck],
});
const link = (label, to, visible = true) => ({ label, to, visible });
const region = (label, regionKey) => ({ label, region: regionKey });
const meterDictionary = (label, kind) => ({ label, dictionaryKind: kind });
const lbl = (...keys) => keys.map((key) => t(key)).join(': ');

const settingsSections = computed(() => {
  const perms = permissions.value?.permissions || {};
  return [
    {
      key: 'service', title: t('service'), visible: perms.view_service,
      general: [
        link(lbl('service', 'service_block.exploitations'), '/service/exploitations/'),
        link(lbl('service', 'service_block.companies'), '/service/companies/'),
      ],
      master: [
        list(lbl('service_block.companies', 'common.type'), 'service/company-type'),
        list(lbl('common.supply_points', 'common.statuses'), 'service/supply-point-status', true, false, false, true),
        list(lbl('common.supply_points', 'common.type'), 'service/supply-point-type', false, false, false, true),
        list(lbl('common.supply_points', 'service_block.supply_source'), 'service/supply-point-source'),
        list(lbl('common.supply_points', 'service_block.supply_type'), 'service/supply-point-supply-type'),
        list(lbl('common.supply_points', 'address_block.location'), 'service/supply-point-placement'),
        list(lbl('common.meters', 'common.statuses'), 'service/meter-status', true, false, false, true),
        list(lbl('common.meters', 'service_block.calibers'), 'service/meter-caliber'),
        meterDictionary(lbl('common.meters', 'service_block.manufacturers'), 'manufacturer'),
        meterDictionary(lbl('common.meters', 'service_block.models'), 'model'),
        meterDictionary(lbl('common.meters', 'service_block.comm_technologies'), 'comm_technology'),
        list(t('common.clusters') + ' ' + lbl('service_block.nozzles', 'common.statuses'), 'service/cluster-nozzle-status', true, false, false, true),
        list(t('common.clusters') + ' ' + lbl('service_block.nozzles', 'common.type'), 'service/cluster-nozzle-type'),
        list(lbl('common.clusters', 'common.statuses'), 'service/cluster-status', true, false, false, true),
        list(lbl('common.connections', 'common.statuses'), 'service/connection-status', true, false, false, true),
        list(lbl('common.connections', 'common.type'), 'service/connection-type'),
        list(lbl('common.connections', 'service_block.installation_type'), 'service/connection-installation-type', false, false, false, true),
        list(lbl('common.connections', 'common.usage_type'), 'service/connection-use-type', false, false, false, true),
        list(lbl('common.connections', 'service_block.valve_type'), 'service/connection-valve-type'),
        list(lbl('common.connections', 'service_block.diameters'), 'service/connection-diameter'),
        list(lbl('common.connections', 'service_block.materials'), 'service/connection-material'),
        list(lbl('common.connections', 'common.documentation'), 'service/connection-documentation-type'),
        list(lbl('common.clusters', 'common.documentation'), 'service/cluster-documentation-type'),
        list(lbl('common.connection_requests', 'common.statuses'), 'service/connection-request-status', true, false, false, true),
        list(lbl('common.connection_requests', 'service_block.connection_request_form.building_type'), 'service/connection-request-building-type'),
        list(lbl('common.connection_requests', 'service_block.connection_request_form.representative_type'), 'service/connection-request-representative-type'),
        list(lbl('common.supply_cuts', 'common.statuses'), 'service/supply-cut-status', true, false, false, true),
      ],
    },
    {
      key: 'addresses', title: t('address_block.addresses'), visible: perms.view_service,
      general: [
        link(t('address_block.street_management'), '/service/streets/'),
      ],
      master: [
        list(lbl('address_block.streets', 'common.type'), 'coredata/street-type', false, false, false, true),
      ],
    },
    {
      key: 'contracting', title: t('contracting'), visible: perms.view_contract,
      general: [
        link(lbl('contract_request', 'common.type'), '/contract/contract-request-type/'),
        link(lbl('contract_block.clauses', 'contract_block.clause_templates'), '/contract/clause-templates/'),
        link(lbl('bonifications', 'contract_block.bonification_type'), '/contract/bonification-type/'),
      ],
      master: [
        list(lbl('person', 'common.identificator'), 'coredata/identification-type', false, false, false, true),
        list(lbl('contract', 'common.statuses'), 'contract/contract-status', true, false, false, true),
        list(lbl('contract', 'common.usage_type'), 'contract/contract-use-type', false, false, false, true),
        list(lbl('contract', 'contract_block.client_type'), 'contract/contract-client-type'),
        list(lbl('contract', 'contract_block.representative_type'), 'contract/contract-representative-type'),
        list(lbl('contract', 'common.documentation'), 'contract/contract-documentation-type'),
        list(lbl('contract', 'contract_block.category'), 'contract/contract-category'),
        list(lbl('contract', 'contract_block.surrogation'), 'contract/contract-surrogation-type'),
        list(lbl('contract', 'contract_block.surrogation') + ' ' + t('common.doc_type').toLowerCase(), 'contract/contract-surrogation-document-type'),
        list(lbl('contract', 'contract_block.tenant_change') + ' ' + t('common.doc_type').toLowerCase(), 'contract/contract-tenant-change-document-type'),
        list(lbl('common.aca_documents', 'common.statuses'), 'contract/aca-document-status', true, false, false, true),
        list(lbl('contract_request', 'common.statuses'), 'contract/contract-request-status', true, false, false, true),
        list(lbl('contract_termination_request', 'common.type'), 'contract/contract-termination-request-type', false, false, false, false, false, true),
        list(lbl('contract_termination_request', 'common.statuses'), 'contract/contract-termination-request-status', true, false, false, true),
        region(lbl('variables', 'contract_block.variable_type'), 'VariableType'),
        region(lbl('bail', 'billing_block.bail_type'), 'BailType'),
        region(t('common.banks'), 'Bank'),
      ],
    },
    {
      key: 'work_orders', title: t('work_orders'), visible: perms.view_order,
      general: [
        link(lbl('work_orders', 'common.type'), '/order/order-types/'),
      ],
      master: [
        region(lbl('work_orders', 'order_block.reasons'), 'OrderReason'),
        list(lbl('work_orders', 'common.statuses'), 'order/order-status', true, false, false, true),
        list(lbl('work_orders', 'common.priority'), 'order/order-priority', true, false, false, true),
      ],
    },
    {
      key: 'pricing', title: t('pricing'), visible: perms.view_pricing,
      general: [
        link(lbl('pricing', 'pricing_block.billing_ranges'), '/pricing/billing-ranges/'),
        link(lbl('pricing', 'pricing_block.line_items'), '/pricing/line-item-types/'),
      ],
      master: [
        list(lbl('common.products', 'common.origins'), 'pricing/product-origin', false, false, false, true),
        list(lbl('taxes', 'common.type'), 'pricing/tax', false, false, false, true),
        list(lbl('billing', 'pricing_block.periodicity'), 'pricing/billing-period', false, false, false, true),
      ],
    },
    {
      key: 'billing', title: t('billing'), visible: perms.view_billing,
      general: [
        link(t('common.configure') + ' ' + t('billing_block.biller'), '/billing/biller/'),
        link(t('billing') + ' ' + t('billing_block.invoice_templates'), '/billing/invoice-templates/'),
        link(lbl('claim_block.claim_payments', 'billing_block.steps'), '/billing/claim-steps/'),
        link(lbl('vulnerability_request', 'common.type'), '/billing/vulnerability-request-type/'),
      ],
      master: [
        list(lbl('billing', 'common.statuses'), 'billing/billing-status', true, false, false, true),
        list(lbl('invoices', 'common.statuses'), 'billing/invoice-status', true, false, true, true),
        list(lbl('payment', 'common.statuses'), 'billing/payment-status', true, false, true, true),
        list(lbl('billing_block.joined_payment', 'common.statuses'), 'billing/joined-payment-status', true, false, false, true),
        list(lbl('commitment_deposit', 'common.statuses'), 'billing/commitment-deposit-status', true, false, true, true),
        list(lbl('claim_block.commitment_payments', 'common.statuses'), 'billing/payment-commitment-status', true, false, true, true),
        list(lbl('invoices', 'billing_block.series'), 'billing/invoice-serie', false, false, false, true),
        list(lbl('invoices', 'common.type'), 'billing/invoice-type', false, false, false, true),
        list(lbl('invoices', 'billing_block.alerts'), 'billing/invoice-warnings', false, false, false, true),
        list(lbl('invoices', 'common.return_reason'), 'billing/reject-motive', false, false, false, true),
        list(lbl('claim_block.claim_payments', 'common.statuses'), 'claimrequest/claim-request-status', true, false, false, true),
        list(lbl('invoices', 'billing_block.categories'), 'billing/invoice-category', false, false, false, false, true),
      ],
    },
    {
      key: 'readings', title: t('readings'), visible: perms.view_reading,
      general: [
        link(t('settings_block.config_reading_batch_template'), '/reading/reading-batch-templates/'),
        link(t('settings_block.reading_batch_export_file'), '/statistics/reading-batch-export-config'),
      ],
      master: [
        list(lbl('common.reading_batches', 'common.statuses'), 'billing/reading-batch-status', true, false, false, true),
        list(lbl('billing_block.invoice_alerts', 'common.type'), 'billing/reading-alert-type', true, false, false, true),
        list(lbl('billing_block.reader_alerts', 'common.type'), 'billing/reader-alert'),
        list(lbl('billing_block.remote_alerts', 'common.type'), 'billing/remote-reading-alert', false, false, false, true),
      ],
    },
    {
      key: 'frauds', title: t('common.frauds'), visible: perms.view_service,
      general: [],
      master: [
        list(lbl('common.fraud_mngs', 'common.statuses'), 'fraud/fraud-status', true, false, false, true),
        list(lbl('common.fraud_mngs', 'common.type'), 'fraud/fraud-type', true, false, false, true),
      ],
    },
    {
      key: 'communication', title: t('communication'), visible: perms.view_customer_service,
      general: [
        link(lbl('communication', 'customer_service_block.comms_templates'), '/communication/message-templates/'),
      ],
      master: [
        list(lbl('communication', 'common.statuses'), 'communication/communication-status', true, false, true, true),
        list(lbl('communication', 'common.use_type'), 'communication/communication-use-type', false, false, false, true),
        list(lbl('common.comms_process_detail', 'common.statuses'), 'communication/communication-process-status', true, false, true, true),
        list(lbl('customer_service_block.comms_templates', 'common.origins'), 'communication/message-origin', false, false, false, true),
      ],
    },
    {
      key: 'incidents', title: t('common.incidents'), visible: perms.view_customer_service,
      general: [
        region(t('incident_settings.title'), 'IncidentSettings'),
      ],
      master: [
        list(lbl('common.incidents', 'common.type'), 'notification/incident-type', true),
        list(lbl('common.incidents', 'common.statuses'), 'notification/incident-status', true, false, false, true),
        list(lbl('common.incidents', 'incident_settings.channels'), 'notification/incident-channel'),
      ],
    },
    {
      key: 'docs', title: t('common.docs'), visible: perms.view_customer_service,
      general: [
        link(lbl('common.doc', 'statistics_block.daily_document_templates'), '/statistics/daily-document-templates/'),
      ],
      master: [
        list(lbl('common.doc', 'common.statuses'), 'statistics/daily-document-status', true, false, false, true),
      ],
    },
    {
      key: 'users', title: t('users'), visible: perms.view_user,
      general: [
        link(t('settings_block.mng_groups'), '/user/groups/'),
        link(t('settings_block.mng_users'), '/user/users/'),
      ],
      master: [],
    },
    {
      key: 'settings', title: t('settings_block.settings'), visible: perms.view_user,
      general: [
        link(t('settings_block.config_aca'), '/settings/config_aca/', isAcaOrg.value),
        link(t('pricing_block.accounting'), '/settings/accounting/'),
        link(t('settings_block.smart_metering_config'), '/settings/smart_metering/', smartMeteringEnabled.value),
        link(t('settings_block.send_batch_config'), '/settings/send-batch/'),
      ],
      master: [],
    },
  ].filter((section) => section.visible);
});

// Cerca sense distingir majúscules ni accents. Si coincideix el títol del bloc, es mostren totes les opcions.
const searchText = ref('');
const normalize = (value) => String(value ?? '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
const matchesSearch = (...values) => {
  const query = normalize(searchText.value).trim();
  return !query || values.some((value) => normalize(value).includes(query));
};
const sectionsFor = (group) => settingsSections.value
  .map((section) => {
    const items = section[group].filter((item) => item.visible !== false);
    return {
      ...section,
      items: matchesSearch(section.title) ? items : items.filter((item) => matchesSearch(item.label)),
    };
  })
  .filter((section) => section.items.length);
const generalSections = computed(() => sectionsFor('general'));
const masterSections = computed(() => sectionsFor('master'));
const filteredConfigProjects = computed(() => config_projects.value.filter(
  (item) => matchesSearch(item.token, item.name, item.value),
));

const openItem = (item) => {
  if (item.entity) {
    showConfigList(item.label, item.entity, ...item.options);
  } else if (item.dictionaryKind) {
    showMeterDictionary(item.label, item.dictionaryKind);
  } else {
    RegionActive.value = item.region;
    toggleRegion(true);
  }
}

// Pestanyes de la pàgina. Configuració interna (ConfigProject) només per a l'usuari tècnic.
const route = useRoute();
const router = useRouter();
const settingsTabs = computed(() => [
  { key: 'general', label: t('settings_block.general'), icon: 'fa6-solid:gear', visible: settingsSections.value.some((section) => section.general.length) },
  { key: 'master_tables', label: t('settings_block.master_tables'), icon: 'fa6-solid:table-list', visible: settingsSections.value.some((section) => section.master.length) },
  { key: 'internal', label: t('settings_block.internal_settings'), icon: 'fa6-solid:screwdriver-wrench', visible: Boolean(permissions.value?.can_edit_config_project) },
].filter((tab) => tab.visible));
// La pestanya activa surt sempre de la URL (?tab=), també en navegar enrere o endavant.
const activeTab = computed(() => {
  const keys = settingsTabs.value.map((tab) => tab.key);
  return keys.includes(route.query.tab) ? route.query.tab : keys[0];
});
const setActiveTab = (key) => {
  router.replace({ query: { ...route.query, tab: key } });
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
      <Tabs class="mb-4" list-role="tablist">
        <li v-for="tab in settingsTabs" :key="tab.key" class="me-2" role="presentation">
          <a :id="`tab_${tab.key}`" :href="`?tab=${tab.key}`" role="tab" :aria-selected="activeTab === tab.key"
            :aria-controls="`panel_${tab.key}`" @click.prevent="setActiveTab(tab.key)" :class="{
            'text-sky-600 border-sky-600': activeTab === tab.key,
            'hover:text-gray-600 hover:border-gray-300': activeTab !== tab.key,
          }">
            <Icon :name="tab.icon" class="display-inline mr-2" />
            {{ tab.label }}
          </a>
        </li>
      </Tabs>

      <div class="relative mb-6 max-w-md">
        <Icon name="fa6-solid:magnifying-glass" class="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
        <input v-model="searchText" type="search" class="input !pl-9" :placeholder="t('common.search')" />
      </div>

      <section v-for="tab in ['general', 'master_tables']" v-show="activeTab === tab" :id="`panel_${tab}`" :key="tab"
        role="tabpanel" :aria-labelledby="`tab_${tab}`">
        <div v-for="section in (tab === 'general' ? generalSections : masterSections)" :key="section.key">
          <h3 class="text-lg mb-2 font-bold pl-3">{{ section.title }}</h3>
          <ul class="text-base ml-3 pl-6 list-disc mb-4">
            <li v-for="item in section.items" :key="item.to || item.entity || item.region || item.dictionaryKind" class="mb-1">
              <NuxtLink v-if="item.to" :to="item.to" class="text-sky-500 underline hover:no-underline">{{ item.label }}
              </NuxtLink>
              <button v-else @click="openItem(item)" class="text-sky-500 underline hover:no-underline">{{ item.label
                }}</button>
            </li>
          </ul>
        </div>
        <p v-if="!(tab === 'general' ? generalSections : masterSections).length" class="pl-3 text-slate-500">
          {{ t('common.no_results') }}</p>
      </section>

      <section v-if="permissions?.can_edit_config_project" v-show="activeTab === 'internal'" id="panel_internal"
        role="tabpanel" aria-labelledby="tab_internal">
        <ul v-if="filteredConfigProjects.length" class="ml-3 leading-6">
          <li v-for="item in filteredConfigProjects" :key="item.token" class="flex gap-3 items-center mb-1">
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
              <button v-if="permissions?.can_edit_config_project" class="text-sky-500 hover:text-sky-700"
                :title="t('common.edit')" @click="startEditConfigProject(item)">
                <Icon name="fa6-solid:pen-to-square" />
              </button>
            </template>
          </li>
        </ul>
        <p v-else-if="config_projects.length" class="pl-3 text-slate-500">{{ t('common.no_results') }}</p>
      </section>

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
          :hasDescription="configureDescription" :blockEdits="blockEdits" :hasSerieDigits="configureSerieDigits"
          :hasChangeOfNameCheck="configureChangeOfName" />
        <VariableTypeEdit v-if="RegionActive == 'VariableType'" />
        <OrderReasonEdit v-if="RegionActive == 'OrderReason'" />
        <BailTypeEdit v-if="RegionActive == 'BailType'" />
        <BankConfigList v-if="RegionActive == 'Bank'" />
        <IncidentSettings v-if="RegionActive == 'IncidentSettings'" />
        <AccountValuesRegion v-if="RegionActive == 'AccountValues'" @close="toggleRegion(false)" />
        <MeterDictionaryList v-if="RegionActive == 'MeterDictionary' && meterDictionaryKind" :key="meterDictionaryKind"
          :kind="meterDictionaryKind" :title="meterDictionaryTitle" />
      </div>
    </div>
  </div>
</template>

<style>
div#right_page {
  box-shadow: rgba(15, 15, 15, 0.04) 0px 0px 0px 1px, rgba(15, 15, 15, 0.03) 0px 3px 6px, rgba(15, 15, 15, 0.06) 0px 9px 24px;
}
</style>
