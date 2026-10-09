<script setup>
import { useI18n } from 'vue-i18n';

import { formatDate } from '~/utils/date';
import IBAN from '../atoms/IBAN.vue';
const { $SepaDocumentationApiService } = useNuxtApp();
const { t } = useI18n();

const props = defineProps({
  item: Object, // PersonBank
  person: Object,
  company: Object,
  country: Object,
  sepa: Object,
  show_sepa: {
    type: Boolean,
    default: false
  },
  is_detail: Boolean,
  is_checked: Boolean
});

const isLoading = ref(false);

</script>
<template>
  <div v-if="props.item">
    <div class="flex grid grid-cols-[4fr,2fr] items-center" v-if="!props.is_detail">
      <AtomsFieldDetail v-if="item.name" :label="$t('contract_block.holder')" :value="item.name">
        <span>{{ item.name }}</span>
      </AtomsFieldDetail>
      <AtomsFieldDetail v-else-if="person" :label="$t('contract_block.holder')"
        :value="item.name ? item.name : person?.full_name" />
      <AtomsFieldDetail v-else-if="company" :label="$t('company')" :value="company.name ? company.name : '-'" />
      <AtomsFieldDetail :label="$t('common.updated')" :value="formatDate(item.updated_at)" />
    </div>

    <div class="flex grid grid-cols-[4fr,2fr] items-center" v-if="!props.is_detail">
      <AtomsFieldDetail v-if="person" :label="$t('common.person_id')" :value="item.dni ? item.dni : item.name? '-' :person?.token" />
      <AtomsFieldDetail v-else-if="company" :label="$t('service_block.vat')" :value="company.vat ? company.vat : '-'" />
      <AtomsFieldDetail v-if="!item.is_active" :label="$t('common.deactivated')" 
        :value="item.deactivated_at ? formatDateTime(item.deactivated_at) : '-'">
      </AtomsFieldDetail>
    </div>

    <div>
      <AtomsFieldDetail v-if="item.bank && typeof item.bank === 'object' && item.bank.name" :label="$t('common.bank')" :value="item.bank.name" />
      <AtomsFieldDetail v-if="item.iban" :label="$t('common.iban')">
        <IBAN :value="item.iban" />
      </AtomsFieldDetail>
      <AtomsFieldDetail v-if="item.swift" :label="$t('common.swift')" :value="item.swift">
      </AtomsFieldDetail>
      <AtomsFieldDetail v-if="item.iban && props.is_detail && (props.sepa || $slots['sepa-actions'])" :label="$t('common.sepa')">
        <div class="flex items-center gap-2">
          <abbr :title="sepa ? t('contract_block.sepa_updated') : t('contract_block.sepa_not_updated')">
            <Icon v-show="sepa" name="fa6-solid:circle-check" class="text-green-600" />
            <Icon v-show="!sepa" name="fa6-solid:circle-xmark" class="text-red-600" />
          </abbr>
          <slot name="sepa-actions" />
        </div>
      </AtomsFieldDetail>
      <AtomsFieldDetail v-if="props.show_sepa && !props.is_detail" :label="$t('common.sepa')">
        <div class="flex items-center gap-2">
          <abbr :title="(sepa?.file != null && sepa?.checked) ? t('contract_block.sepa_updated') : t('contract_block.sepa_not_updated')">
            <Icon v-show="(sepa?.file != null && sepa?.checked) && !isLoading" name="fa6-solid:circle-check" class="text-green-600" />
            <Icon v-show="!(sepa?.file != null && sepa?.checked) && !isLoading" name="fa6-solid:circle-xmark" class="text-red-600" />
          </abbr>
          <Icon v-show="isLoading" name="fa6-solid:spinner" class="animate-spin text-2xl text-slate-500" />
          <slot name="sepa-actions" />
        </div>
      </AtomsFieldDetail>
    </div>
  </div>

</template>