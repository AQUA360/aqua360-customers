<script setup>
import { ref, watch, onMounted, popScopeId } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import ButtonOutline from '~/components/atoms/ButtonOutline.vue';
import H1Region from '~/components/atoms/H1Region.vue';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import OptionsDropdown from '~/components/molecules/OptionsDropdown.vue';
import DropdownOption from '~/components/atoms/DropdownOption.vue';
import { formatDate } from '~/utils/date';
import Time from '~/components/atoms/Time.vue';
import { lastDayOfDecade } from 'date-fns';

const { t } = useI18n();

const props = defineProps({
  id: Number, // ID de l'element
  request: Object,
});
const emit = defineEmits(['clickChangeStatus']);

const router = useRouter();
const { $AddressHelper } = useNuxtApp();
const data = ref(null);

const addBillingAddress = async () => {
  // TODO
};

const generateInvoice = async () => {
  // TODO
};

const generateWorkOrder = async () => {
  // TODO
};

onMounted(() => {
  data.value = props.request;
});

watch(() => props.request, () => {
  data.value = props.request;
});

</script>

<template>
  <div v-if="data" id="item_data" :data-rel=id class="grid grid-cols-2 gap-3">
    <h2 class="text-xl font-semibold mb-4">{{ $t('common.step') }} 4: {{ $t('common.completion') }}</h2>
    <div class="col-span-2">
      <fieldset id="ordre_treball__box" v-if="data.connection && data.connection?.token"
        class="mb-3 border px-3 py-2 bg-sky-50 rounded">
        <legend class="px-3 font-semibold bg-white shadow">
          <h3>{{ $t('supply_point') }}</h3>
        </legend>
        <div class="grid grid-cols-2">
          <div class="mr-2">
            <p class="font-semibold">{{ $t('common.origin') }}:</p>
            <div class="px-3 mb-3">
              {{ data.source?.name }}<br />
            </div>
          </div>
          <div class="ml-2">
            <p class="font-semibold">{{ $t('common.type') }}:</p>
            <div class="px-3 mb-3">
              {{ data.type?.name }}<br />
            </div>
          </div>
          <div class="mr-2">
            <p class="font-semibold">{{ $t('service_block.supply_type') }}:</p>
            <div class="px-3 mb-3">
              {{ data.supply_type?.name }}<br />
            </div>
          </div>
          <div class="ml-2">
            <p class="font-semibold">{{ $t('address_block.location') }}:</p>
            <div class="px-3 mb-3">
              {{ data.placement?.name }}<br />
            </div>
          </div>
          <div class="mr-2">
            <div>
              <p class="font-semibold">{{ $t('contract') }}:</p>
              <div class="px-3 mb-3 text-sm underline text-sky-600 hover:text-sky-400">
                <a :href="data.contract"><Icon name="fa6-solid:file"/> -  {{ data.contract ? data.contract.split('/').pop().replace('_', ' ') : '' }}</a>
              </div>
            </div>
            <div>
              <p class="font-semibold">{{ $t('property') }}:</p>
              <div class="px-3 mb-3">
                {{ $AddressHelper.getAddressString(data.property) }}
              </div>
            </div>
            <div>
              <p class="font-semibold">{{ $t('route') }}:</p>
              <div class="px-3 mb-3">
                {{ data.route?.name }}
              </div>
            </div>
          </div>
          <div class="ml-2">
            <p class="font-semibold">{{ $t('common.docs') }}:</p>
            <div v-for="doc in data.documents" class="px-3 mb-2 ">
              <div class="text-slate-800 semi-bold underline">
                {{ doc.supply_point_request_document_type?.name }}
              </div>
              <div class="text-sm text-slate-700" >
                - {{ t('Comprovat ') }}: <Icon v-show="doc.checked" class="text-green-600" name="fa6-solid:check"/> <Icon v-show="!doc.checked" class="text-red-600" name="fa6-solid:xmark"/>
                <a v-if="doc.file && doc.file != ''" class="ml-2 underline text-sky-600 hover:text-sky-400" :href="doc.file">
                  <Icon name="fa6-solid:file"/> -  {{ doc.file ? doc.file.split('/').pop().replace('_', ' ') : '' }}</a>
              </div>
            </div>
          </div>
        </div>
      </fieldset>
    </div>

    <div>
      <fieldset id="solicitant__box" v-if="data.person" class="mb-3 border px-3 py-2 bg-sky-50 rounded">
        <legend class="px-3 font-semibold bg-white shadow">{{ $t('common.requester') }}</legend>
        <p>{{ data.person?.name || "" }} {{ data.person?.surname || "" }}</p>
        <p>{{ data.person?.token || "" }}</p>
        <ButtonOutline @click="addBillingAddress">{{ $t('common.add') }} {{ $t('contract_block.billing_address') }}</ButtonOutline>
      </fieldset>

      <fieldset id="facturacio__box" v-if="data.person" class="mb-3 border px-3 py-2 bg-sky-50 rounded">
        <legend class="px-3 font-semibold bg-white shadow">
          <h3>{{ $t('billing') }}</h3>
        </legend>
        <ButtonOutline @click="generateInvoice">{{ $t('common.generate') }} {{ $t('invoice') }}</ButtonOutline>
      </fieldset>

      <fieldset id="status__box" class="mb-3 border px-3 py-2 bg-sky-50 rounded">
        <legend class="px-3 font-semibold bg-white shadow">
          <h3>{{ $t('common.status') }}</h3>
        </legend>
        <div class="py-2">
          <AtomsColorBadge :value="data.status?.name || data.status?.token || ''" :color="data.status?.color">
          </AtomsColorBadge>
        </div>
        <div>
          <ButtonOutline @click="emit('clickChangeStatus')">{{ $t('common.change') }} {{ $t('common.status') }}</ButtonOutline>
        </div>
      </fieldset>
    </div>
    <div class="h-full pb-3">
      <fieldset id="ordre_treball__box" v-if="data.connection && data.connection?.token"
        class="mb-3 border px-3 py-2 bg-sky-50 h-full rounded">
        <legend class="px-3 font-semibold bg-white shadow">
          <h3>{{ $t('common.work_order') }}</h3>
        </legend>

        <p class="font-semibold">{{ $t('address_block.location') }}:</p>
        <div class="px-3 mb-3">
          {{ data.address?.address_complete }}<br />
          {{ data.address?.postal_code || "" }} - {{ data.address?.city?.name || "" }}
        </div>

        <p class="font-semibold">{{ $t('connection') }}:</p>
        <div class="px-3 mb-3" v-if="data.connection">
          <span>#{{ data.connection?.token || "" }}</span><br />
        </div>
        <p class="font-semibold">{{ $t('meter') }}:</p>
        <div class="px-3 mb-3" v-if="data.meter">
          <span>#{{ data.meter?.code || "" }}</span><br />
          <!-- <span class="inline-block min-w-40">Manufacturer: {{ data.meter?.manufacturer }}</span>
          <span>{{ data.meter?.use_type?.name }}</span><br /> -->
          <span class="inline-block min-w-40">{{ $t('service_block.model') }}: {{ data.meter?.manufacturer }}  {{
            data.meter?.model }}</span><br />
          <span class="inline-block min-w-40">{{ $t('address_block.address') }}: {{ $AddressHelper.getAddressString(data.meter) }} </span>
          <!-- Vàlvula: <span>{{ data.meter?.valve_type?.name }}</span> -->
        </div>
        <ButtonOutline @click="generateWorkOrder">{{ $t('common.generate') }} {{ $t('common.work_order') }}</ButtonOutline>

      </fieldset>
    </div>
  </div><!-- end if data -->

</template>
