<script setup>
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';

import { formatDateTime } from '~/utils/date';
import TimeRelative from '~/components/atoms/TimeRelative.vue';
import {
  contractDataAddressChanged,
  contractDataModificationHasVisibleContent,
  contractDataPaymentChanged,
  contractDataPaymentTypeChanged,
  contractDataPersonContactEmailChanged,
  contractDataPhonesChangedForRecord,
  contractDataTotalPersonsChanged,
  getPhonesChangeDisplay,
} from '~/utils/contractDataChangeDisplay';

const { t } = useI18n()
const props = defineProps({
  id: Number,
  object: Object
});

const paymentTypeChanged = computed(() =>
  contractDataPaymentTypeChanged(props.object?.new_payment_type, props.object?.previous_payment_type)
)
const paymentChanged = computed(() =>
  contractDataPaymentChanged(props.object?.new_payment, props.object?.previous_payment)
)
const emailChanged = computed(() =>
  contractDataPersonContactEmailChanged(props.object?.new_person_contact_email, props.object?.previous_person_contact_email)
)
const billingAddressChanged = computed(() =>
  contractDataAddressChanged(props.object?.new_address_billing, props.object?.previous_address_billing)
)
const contactAddressChanged = computed(() =>
  contractDataAddressChanged(props.object?.new_address_contact, props.object?.previous_address_contact)
)
const phoneChanged = computed(() => contractDataPhonesChangedForRecord(props.object))
const phonesDisplay = computed(() => getPhonesChangeDisplay(props.object))
const totalPersonsChanged = computed(() =>
  contractDataTotalPersonsChanged(props.object?.new_total_persons, props.object?.previous_total_persons)
)

/** Ordre fix per al títol i els detalls (mateix criteri per a tots els camps). */
const changeFields = computed(() => [
  {
    id: 'paymentType',
    active: paymentTypeChanged.value,
    label: t('common.payment_method'),
  },
  {
    id: 'payment',
    active: paymentChanged.value,
    label: t('billing_block.payment'),
  },
  {
    id: 'billingAddress',
    active: billingAddressChanged.value,
    label: t('contract_block.billing_address'),
  },
  {
    id: 'contactAddress',
    active: contactAddressChanged.value,
    label: t('contract_block.contact_address'),
  },
  {
    id: 'email',
    active: emailChanged.value,
    label: t('common.email_long'),
  },
  {
    id: 'persons',
    active: totalPersonsChanged.value,
    label: t('common.persons'),
  },
  {
    id: 'phone',
    active: phoneChanged.value,
    label: t('common.tlf'),
  },
])

const activeFields = computed(() => changeFields.value.filter((f) => f.active))
const title = computed(() => activeFields.value.map((f) => f.label).join(' & '))
const hasChanges = computed(() => contractDataModificationHasVisibleContent(props.object))

</script>
<template>
  <article v-if="hasChanges"
    class="relative p-2 text-base bg-white group hover:bg-blue-50 px-4 mt-0 pt-0 pb-5 border-l hover:border-sky-500">
    <span class="absolute left-[-5px] top-0 text-[10px]">
      <Icon name="fa6-solid:circle" class="text-sky-500"/>
      </span>
    <footer class="flex justify-between items-center pt-1">
      <div class="flex items-center mb-1">
        <p v-if="object.user" class="text-sm text-gray-700 mr-3">{{ object.user?.username }}</p>
        <p v-else class="text-sm text-gray-700 mr-3">{{ t('common.admin') }}</p>
        <p class="inline-flex items-center text-sm text-gray-900 font-semibold">
          <TimeRelative :datetime=object.created_at></TimeRelative>
        </p>
      </div>
      <div>
        <span class="text-slate-400 text-sm">{{ formatDateTime(object.approved_at) }}</span>
      </div>
    </footer>

    <p class="text-slate-500">{{ title }}</p>
    <template v-for="field in activeFields" :key="field.id">
      <p v-if="field.id === 'paymentType'" class="text-sm flex gap-3">
        <span class="text-slate-500">{{ object.previous_payment_type?.name || t('common.no_data') }}</span>
        <span>&rarr;</span>
        <span class="text-slate-900">{{ object.new_payment_type?.name || t('common.no_data') }}</span>
      </p>
      <p v-else-if="field.id === 'payment'" class="text-sm flex gap-3">
        <AtomsIBAN v-if="object.previous_payment?.iban" :value="object.previous_payment.iban" />
        <span v-else class="text-slate-500">{{ t('common.no_data') }}</span>
        <span>&rarr;</span>
        <AtomsIBAN v-if="object.new_payment?.iban" :value="object.new_payment.iban" />
        <span v-else class="text-slate-900">{{ t('common.no_data') }}</span>
      </p>
      <p v-else-if="field.id === 'billingAddress'" class="text-sm flex gap-3">
        <span class="text-slate-500">{{ object.previous_address_billing ? object.previous_address_billing.address_complete : t('common.no_data') }}</span>
        <span>&rarr;</span>
        <span class="text-slate-900">{{ object.new_address_billing?.address_complete }}</span>
      </p>
      <p v-else-if="field.id === 'contactAddress'" class="text-sm flex gap-3">
        <span class="text-slate-500">{{ object.previous_address_contact ? object.previous_address_contact.address_complete : t('common.no_data') }}</span>
        <span>&rarr;</span>
        <span class="text-slate-900">{{ object.new_address_contact?.address_complete }}</span>
      </p>
      <p v-else-if="field.id === 'email'" class="text-sm flex gap-3">
        <span class="text-slate-500">{{ object.previous_person_contact_email ? object.previous_person_contact_email.email : t('common.no_data') }}</span>
        <span>&rarr;</span>
        <span class="text-slate-900">{{ object.new_person_contact_email?.email }}</span>
      </p>
      <p v-else-if="field.id === 'persons'" class="text-sm flex gap-3">
        <span class="text-slate-500">{{ object.previous_total_persons ?? t('common.no_data') }}</span>
        <span>&rarr;</span>
        <span class="text-slate-900">{{ object.new_total_persons }}</span>
      </p>
      <p v-else-if="field.id === 'phone'" class="text-sm flex gap-3">
        <span class="text-slate-500">{{ phonesDisplay.previous || t('common.no_data') }}</span>
        <span>&rarr;</span>
        <span class="text-slate-900">{{ phonesDisplay.new || t('common.no_data') }}</span>
      </p>
    </template>
  </article>
</template>