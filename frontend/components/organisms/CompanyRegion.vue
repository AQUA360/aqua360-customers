<script setup>
import { ref, computed, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useToast } from 'vue-toastification';
import { useI18n } from 'vue-i18n';
import H1Region from '~/components/atoms/H1Region.vue';
import CompanyDetail from '../molecules/CompanyDetail.vue';
import OptionsDropdown from '~/components/molecules/OptionsDropdown.vue';
import DropdownOption from '~/components/atoms/DropdownOption.vue';
import FieldDetail from '../atoms/FieldDetail.vue';
import BankDetail from '../molecules/BankDetail.vue';

const { t } = useI18n();
const toast = useToast();
const emit = defineEmits(['close']);

const props = defineProps({
  id: Number, // ID de l'element
});

const router = useRouter();
const { $ExploitationApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const data = ref(null);
const activeTab = ref('bank_data');
const objectPermissions = ref(null);

const getPermissions = async () => {
  try {
    objectPermissions.value = await $ExploitationApiService.getCompanyPermissions();
  } catch (error) {
    console.log(error);
  }
}

const getData = async () => {
  pending.value = true;
  error.value = null;
  try {
    const result = await $ExploitationApiService.getCompany(props.id);
    data.value = result;

  } catch (err) {
    error.value = err;
  } finally {
    pending.value = false;
  }
}

const setActiveTab = (tab) => {
  activeTab.value = tab;
}

// El compte per defecte surt primer: és el que recull tot el que l'encaminament
// de remeses no assigna a cap altre compte, i és el que es vol veure d'un cop d'ull.
const companyBanks = computed(() => {
  const banks = [...(data.value?.company_banks || [])];
  return banks.sort((a, b) => Number(b.is_default || false) - Number(a.is_default || false));
});

const hasDefaultBank = computed(() => companyBanks.value.some(bank => bank.is_default));


watch(() => props.id, () => {
  getData();
});

const edit = function () {
  navigateTo('/service/companies/edit/' + props.id);
}

onMounted(async () => {
  await getPermissions();
  if (!objectPermissions.value.can_view) {
    toast.error(t('common.no_permissions'));
    emit('close');
  }
  getData();
});

</script>

<template>
  <div class="region__content">
    <div v-if="pending || !objectPermissions?.can_view">
      <p>{{ $t('common.loading') }}...</p>
    </div>
    <div v-else-if="error">
      <p>Error: {{ error.message }}</p>
      <p><button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again')
      }}</button></p>
    </div>
    <div v-else>
      <div class="flex justify-between relative">
        <H1Region class="mb-3">{{ $t('company') }}</H1Region>
        <OptionsDropdown v-if="objectPermissions?.can_change" id="ConnectionRequestRegionOptions">
          <DropdownOption :name="`${t('common.modify')} ${t('company')}`" @click="edit"></DropdownOption>
        </OptionsDropdown>
      </div>

      <div v-if="data" id="item_data" :data-rel=id>
        <CompanyDetail :id="props.id" :data="data" />

        <AtomsTabs>

          <li class="me-2">
            <a href="#tab_bank_data" @click.prevent="setActiveTab('bank_data')"
              :class="{ 'text-sky-600 border-sky-600': activeTab === 'bank_data', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'bank_data' }">
              <Icon name="fa6-solid:note-sticky" class="display-inline mr-2" />
              {{ $t("common.bank_data") }}
            </a>
          </li>

        </AtomsTabs>
        <div id="contract_tabpanels">
          <section v-show="activeTab === 'bank_data'" role="tabpanel" id="tab_bank_data"
            class="bg-white antialiased py-3">
            <div v-if="companyBanks.length > 1 && !hasDefaultBank"
              class="mb-2 rounded border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
              {{ $t('billing_block.info_no_default_bank') }}
            </div>
            <div v-for="bank in companyBanks" :key="bank.id"
              class="space-y-1 rounded-lg p-2 my-2"
              :class="bank.is_default ? 'border-2 border-sky-400 bg-sky-50 shadow-sm' : 'border border-slate-200 bg-white'">
              <div v-if="bank.is_default" class="flex items-center gap-2 text-sky-700 mb-1">
                <Icon name="fa6-solid:circle-check" class="text-sm" />
                <span class="text-xs font-semibold uppercase tracking-wide">
                  {{ $t('billing_block.default_company_bank') }}
                </span>
              </div>
              <div role="row" class="">
                <FieldDetail :label='$t("common.bank")' :value="bank.bank?.name ? bank.bank?.name : bank.bank?.token">
                </FieldDetail>
                <FieldDetail :label='$t("common.iban")'>
                  <AtomsIBAN :value="bank.iban"></AtomsIBAN>
                </FieldDetail>
                <FieldDetail :label='$t("common.swift")' :value="bank.swift"></FieldDetail>
              </div>
              <div role="row" class="grid grid-cols-2">
                <FieldDetail :label='`${$t("common.identification")} ${$t("common.sepa")}`'
                  :value="bank.sepa_cred_identifier ? bank.sepa_cred_identifier : '-'"></FieldDetail>
                <FieldDetail :label='$t("common.is_sepa")' :value="bank.is_sepa ? $t('common.yes') : $t('common.no')"></FieldDetail>
              </div>
              <!-- <div class="border bg-sky-50 border-gray-200 w-full p-4 block text-left mb-2">
                <BankDetail :item="bank" :company="data"/>
              </div> -->

            </div>
            <div v-if="companyBanks.length == 0" class="mb-2">
              <span class="text-gray-700 mt-1 font-medium italic text-sm bg-yellow-100 rounded-md px-2 py-1">
                {{ $t('common.no_data_found') }}</span>
            </div>
          </section>
        </div>
      </div><!-- end if data -->
    </div><!-- end if pending -->
  </div>
</template>
