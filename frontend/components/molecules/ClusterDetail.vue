<script setup>
// components/organisms/ClusterDetail.vue
import { ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import H1Region from '~/components/atoms/H1Region.vue';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import OptionsDropdown from '~/components/molecules/OptionsDropdown.vue';
import DropdownOption from '~/components/atoms/DropdownOption.vue';
import { formatDate } from '~/utils/date';
import Time from '~/components/atoms/Time.vue';

const { $AddressHelper } = useNuxtApp();

const { t } = useI18n();

const props = defineProps({
  id: Number, // ID de l'element
  data: Object,
  nozzles: Object,
  canChange: {
    type: Boolean,
    default: true
  },
  isSubRegion: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits(['show-detail', 'clickChangeStatus']);

const showDetail = function (component, id, position_id) {
  emit('show-detail', { component: component, id: id, position_id: position_id })
}


const address = computed(() => {
  if (props.data) {
    let text = $AddressHelper.getAddressString(props.data);
    return text;
  }
  else {
    return '';
  }
});

</script>

<template>
  <div role="row" class="grid grid-cols-2">
    <FieldDetail :label='$t("common.code")' :value=data.token></FieldDetail>
    <FieldDetail :label='$t("service_block.short_install_date")' :value=formatDate(data.installation_at)><Time
        :time="data.installation_at"></Time></FieldDetail>
  </div>
  <div role="row" class="grid grid-cols-2 items-center">
    <FieldDetail :label='$t("address_block.address")' :value="address || data.address_complete"></FieldDetail>
    <FieldDetail :label='$t("common.status")' :value="data.status?.name || data.token" class="items-center">
      <span>
        <AtomsColorBadge :color="data.status?.color" :value="data.status?.name"></AtomsColorBadge>
        <button v-if="canChange" class="px-2 py-1 text-gray-500" @click="emit('clickChangeStatus')">
          <Icon name="fa6-solid:pencil" />
        </button>
      </span>
    </FieldDetail>
  </div>

  <div role="row" class="grid grid-cols-2">
    <FieldDetail :label='$t("service_block.bulletin")' :value=data.report_file>
      <a v-if="data.report_file" :href="data.report_file" target="_blank" class="text-left">
        <Icon name="fa6-solid:file-pdf" class="display-inline mr-2 text-lg" /> {{ t('common.download') }}
      </a>
      <span>-</span>
    </FieldDetail>
    <FieldDetail :label='$t("common.water")' :value="data.is_potable ? $t('service_block.potable') : $t('service_block.no_potable')"></FieldDetail>
  </div>

  <div role="row" class="grid grid-cols-2">
    <FieldDetail :label='$t("service_block.usage_destination")' :value="data.usage_destination?.toUpperCase()"></FieldDetail>
    <FieldDetail :label='$t("service_block.nozzles")' :value=String(data.nb_nozzles)></FieldDetail>
  </div>

  <div role="row" class="grid grid-cols-2">
    <FieldDetail :label='$t("connection")'>
      <span v-if="isSubRegion && data.connection">{{ data.connection?.token }}</span>
      <div v-else-if="data.connection" class="flex gap-2">
        <button @click="showDetail('ConnectionRegion', data.connection.id, null)"
          class="text-start text-sky-500 underline">{{ data.connection.token }}</button>
        <AtomsRedirectButton :id="data.connection.id" :path="'/service/connections/'" />
      </div>
      <span v-else>-</span>
    </FieldDetail>
    <FieldDetail v-if="data.property" :label='$t("route")'>
      <span v-if="isSubRegion && data.property.route_position">{{ data.property.route_position?.token }}</span>
      <button v-else-if="data.property.route_position"
        @click="showDetail('RouteRegion', data.property.route_position.route.id, data.property.route_position.id)"
        class="text-start text-sky-500 underline">{{ data.property?.route_position?.token }}</button>
      <span v-else>-</span>
    </FieldDetail>
  </div>

  <hr class="my-2" />

</template>
