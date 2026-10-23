<script setup>
import { ref, computed, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import { checkPermission } from '~/middleware/permission';
import H1Region from '~/components/atoms/H1Region.vue';

const emit = defineEmits(['close', 'changed']);

const { t } = useI18n();
const toast = useToast();
const {
  $AccountingConfigApiService,
  $AccountingPricingApiService,
  $PriceRateApiService,
} = useNuxtApp();

const objectPermissions = ref(null);
const pending = ref(false);
const saving = ref(false);
const error = ref(null);
const loadingPricings = ref(false);
const pricingOptions = ref([]);

const accountingConfig = ref({
  piggybank_as_negative: false,
  include_piggy_status_payments: false,
  incoming_declare_as: 'debt',
  incoming_sign: 'positive',
  incoming_counter_declare_as: 'have',
  incoming_counter_pricing: null,
  return_declare_as: 'have',
  return_sign: 'positive',
  return_counter_declare_as: 'debt',
  return_counter_pricing: null,
});

const declareOptions = computed(() => [
  { token: 'debt', name: t('pricing_block.accounting_declare_debt') },
  { token: 'have', name: t('pricing_block.accounting_declare_have') },
]);

const counterDeclareOptions = computed(() => [
  { token: 'debt', name: t('pricing_block.accounting_declare_debt') },
  { token: 'have', name: t('pricing_block.accounting_declare_have') },
  { token: 'none', name: t('pricing_block.accounting_declare_none') },
]);

const signOptions = computed(() => [
  { token: 'positive', name: t('pricing_block.accounting_sign_positive') },
  { token: 'negative', name: t('pricing_block.accounting_sign_negative') },
]);

const pricingOptionLabel = (item) => {
  if (!item) return '';
  const token = item.token || '';
  const name = item.name || item.declared_as || '';
  const concept = item.accounting_concept?.token || item.accounting_concept?.name || '';
  return [concept, token, name].filter(Boolean).join(' · ') || String(item.id);
};

const toPricingOption = (item) => ({
  ...item,
  code: item.id,
  label: pricingOptionLabel(item),
});

const hydratePricingSelection = (saved) => {
  if (!saved?.id) return null;
  const found = pricingOptions.value.find((item) => String(item.id) === String(saved.id));
  if (found) return found;
  const option = toPricingOption(saved);
  pricingOptions.value = [...pricingOptions.value, option];
  return option;
};

const loadPricingOptions = async () => {
  loadingPricings.value = true;
  try {
    const response = await $AccountingPricingApiService.getAll(
      '', 1, null, false, false, null, null, null, null, 200,
    );
    const list = Array.isArray(response?.results) ? response.results : [];
    pricingOptions.value = list.map(toPricingOption);
  } catch (err) {
    console.error(err);
    pricingOptions.value = [];
  } finally {
    loadingPricings.value = false;
  }
};

const loadConfig = async () => {
  pending.value = true;
  error.value = null;
  try {
    const response = await $AccountingConfigApiService.getCurrent();
    accountingConfig.value = {
      piggybank_as_negative: !!response.piggybank_as_negative,
      include_piggy_status_payments: !!response.include_piggy_status_payments,
      incoming_declare_as: response.incoming_declare_as || 'debt',
      incoming_sign: response.incoming_sign || 'positive',
      incoming_counter_declare_as: response.incoming_counter_declare_as || 'have',
      incoming_counter_pricing: hydratePricingSelection(response.incoming_counter_pricing),
      return_declare_as: response.return_declare_as || 'have',
      return_sign: response.return_sign || 'positive',
      return_counter_declare_as: response.return_counter_declare_as || 'debt',
      return_counter_pricing: hydratePricingSelection(response.return_counter_pricing),
    };
  } catch (err) {
    error.value = err;
    console.error(err);
  } finally {
    pending.value = false;
  }
};

const saveConfig = async () => {
  if (!objectPermissions.value?.can_change || saving.value) return;
  if (!confirm(t('confirmation_text_block.confirm_save'))) return;

  saving.value = true;
  try {
    const payload = {
      piggybank_as_negative: !!accountingConfig.value.piggybank_as_negative,
      include_piggy_status_payments: !!accountingConfig.value.include_piggy_status_payments,
      incoming_declare_as: accountingConfig.value.incoming_declare_as,
      incoming_sign: accountingConfig.value.incoming_sign,
      incoming_counter_declare_as: accountingConfig.value.incoming_counter_declare_as,
      incoming_counter_pricing_id: accountingConfig.value.incoming_counter_pricing?.id ?? null,
      return_declare_as: accountingConfig.value.return_declare_as,
      return_sign: accountingConfig.value.return_sign,
      return_counter_declare_as: accountingConfig.value.return_counter_declare_as,
      return_counter_pricing_id: accountingConfig.value.return_counter_pricing?.id ?? null,
    };
    const response = await $AccountingConfigApiService.saveCurrent(payload);
    accountingConfig.value.incoming_counter_pricing = hydratePricingSelection(
      response.incoming_counter_pricing,
    );
    accountingConfig.value.return_counter_pricing = hydratePricingSelection(
      response.return_counter_pricing,
    );
    toast.success(t('common.saved_successfully') || t('common.correct_save'));
    emit('changed');
  } catch (err) {
    console.error(err);
    toast.error(t('common.error'));
  } finally {
    saving.value = false;
  }
};

onMounted(async () => {
  objectPermissions.value = await checkPermission($PriceRateApiService);
  if (!objectPermissions.value.can_view) {
    toast.error(t('common.no_permissions'));
    emit('close');
    return;
  }
  await loadPricingOptions();
  await loadConfig();
});
</script>

<template>
  <div v-if="objectPermissions?.can_view" class="region__content flex h-full flex-col pr-4">
    <div>
      <H1Region class="!mb-0">
        {{ t('common.check') }}: {{ t('pricing_block.accounting_settings') }}
      </H1Region>
      <p class="mt-2 text-[12px] leading-snug text-slate-500">
        {{ t('pricing_block.accounting_settings_description') }}
      </p>
    </div>

    <div v-if="pending" class="py-6 text-sm text-sky-700">
      {{ t('common.loading') }}...
    </div>
    <div v-else-if="error" class="py-4 text-sm">
      <p>{{ t('common.error') }}: {{ error.message }}</p>
      <button type="button" class="text-sky-500 underline hover:no-underline" @click="loadConfig">
        {{ t('common.load_again') }}
      </button>
    </div>

    <template v-else>
      <div class="mt-4 flex-1 space-y-4 pr-1 pb-4"
        :class="{ 'opacity-60': !objectPermissions?.can_change }">
        <label class="inline-flex cursor-pointer items-start gap-2 text-[13px] text-sky-950">
          <input v-model="accountingConfig.piggybank_as_negative" type="checkbox" class="checkbox mt-0.5"
            :disabled="saving || !objectPermissions?.can_change" />
          <span>
            <span class="font-medium">{{ t('pricing_block.piggybank_as_negative') }}</span>
            <span class="mt-1 block text-[11px] leading-snug text-slate-500">
              {{ t('pricing_block.piggybank_as_negative_hint') }}
            </span>
          </span>
        </label>

        <label class="inline-flex cursor-pointer items-start gap-2 text-[13px] text-sky-950">
          <input v-model="accountingConfig.include_piggy_status_payments" type="checkbox" class="checkbox mt-0.5"
            :disabled="saving || !objectPermissions?.can_change" />
          <span>
            <span class="font-medium">{{ t('pricing_block.include_piggy_status_payments') }}</span>
            <span class="mt-1 block text-[11px] leading-snug text-slate-500">
              {{ t('pricing_block.include_piggy_status_payments_hint') }}
            </span>
          </span>
        </label>

        <div class="rounded-md border border-sky-100 bg-sky-50/40 px-3 py-3 space-y-3">
          <p class="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">
            {{ t('pricing_block.piggybank_incoming') }}
          </p>
          <div class="grid gap-3 sm:grid-cols-2">
            <div>
              <label class="mb-1 block text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-400">
                {{ t('pricing_block.movement_declare_as') }}
              </label>
              <v-select v-model="accountingConfig.incoming_declare_as" :options="declareOptions"
                :reduce="(option) => option.token" label="name" class="block w-full" append-to-body
                :disabled="saving || !objectPermissions?.can_change" />
            </div>
            <div>
              <label class="mb-1 block text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-400">
                {{ t('pricing_block.movement_sign') }}
              </label>
              <v-select v-model="accountingConfig.incoming_sign" :options="signOptions"
                :reduce="(option) => option.token" label="name" class="block w-full" append-to-body
                :disabled="saving || !objectPermissions?.can_change" />
            </div>
            <div>
              <label class="mb-1 block text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-400">
                {{ t('pricing_block.counter_declare_as') }}
              </label>
              <v-select v-model="accountingConfig.incoming_counter_declare_as" :options="counterDeclareOptions"
                :reduce="(option) => option.token" label="name" class="block w-full" append-to-body
                :disabled="saving || !objectPermissions?.can_change" />
            </div>
            <div>
              <label class="mb-1 block text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-400">
                {{ t('pricing_block.counter_accounting_pricing') }}
              </label>
              <v-select v-model="accountingConfig.incoming_counter_pricing" :options="pricingOptions"
                :loading="loadingPricings" class="block w-full" :clearable="true" append-to-body
                :disabled="saving || !objectPermissions?.can_change || accountingConfig.incoming_counter_declare_as === 'none'" />
            </div>
          </div>
        </div>

        <div class="rounded-md border border-sky-100 bg-sky-50/40 px-3 py-3 space-y-3">
          <p class="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">
            {{ t('pricing_block.piggybank_return') }}
          </p>
          <div class="grid gap-3 sm:grid-cols-2">
            <div>
              <label class="mb-1 block text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-400">
                {{ t('pricing_block.movement_declare_as') }}
              </label>
              <v-select v-model="accountingConfig.return_declare_as" :options="declareOptions"
                :reduce="(option) => option.token" label="name" class="block w-full" append-to-body
                :disabled="saving || !objectPermissions?.can_change" />
            </div>
            <div>
              <label class="mb-1 block text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-400">
                {{ t('pricing_block.movement_sign') }}
              </label>
              <v-select v-model="accountingConfig.return_sign" :options="signOptions"
                :reduce="(option) => option.token" label="name" class="block w-full" append-to-body
                :disabled="saving || !objectPermissions?.can_change" />
            </div>
            <div>
              <label class="mb-1 block text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-400">
                {{ t('pricing_block.counter_declare_as') }}
              </label>
              <v-select v-model="accountingConfig.return_counter_declare_as" :options="counterDeclareOptions"
                :reduce="(option) => option.token" label="name" class="block w-full" append-to-body
                :disabled="saving || !objectPermissions?.can_change" />
            </div>
            <div>
              <label class="mb-1 block text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-400">
                {{ t('pricing_block.counter_accounting_pricing') }}
              </label>
              <v-select v-model="accountingConfig.return_counter_pricing" :options="pricingOptions"
                :loading="loadingPricings" class="block w-full" :clearable="true" append-to-body
                :disabled="saving || !objectPermissions?.can_change || accountingConfig.return_counter_declare_as === 'none'" />
            </div>
          </div>
        </div>
      </div>

      <div class="sticky bottom-0 mt-auto border-t border-sky-100 bg-white py-3">
        <button type="button" class="button-primary flex items-center gap-x-2"
          :disabled="saving || pending || !objectPermissions?.can_change" @click="saveConfig">
          <Icon name="fa6-solid:floppy-disk" class="size-3 shrink-0" />
          {{ saving ? t('common.saving') : t('common.save') }}
        </button>
      </div>
    </template>
  </div>
</template>

<style>
/* append-to-body menus must sit above the fixed side region (z-10) */
body > ul.vs__dropdown-menu {
  z-index: 10050;
}
</style>
