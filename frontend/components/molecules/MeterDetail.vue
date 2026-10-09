<script setup>
import { ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import { formatDate } from '~/utils/date';
import Time from '~/components/atoms/Time.vue';
import { remoteTypeOptions } from '~/utils/service';

const { $AddressHelper, $MeterApiService } = useNuxtApp();

const { t, te } = useI18n();

const props = defineProps({
  id: Number, // ID de l'element
  isSubRegion: false,
  isSubRegionOpen: Boolean,
  reduced: false,
  data: Object
});

const pending = ref(false);
const localData = ref(props.data? props.data : null);

const address = computed(() => {
  if (localData.value) {
    let text = $AddressHelper.getAddressString(localData.value);
    return text;
  }
  else {
    return '';
  }
});

const getData = async () => {
  pending.value = true;
  try {
    const data = await $MeterApiService.getDetail(props.id);
    localData.value = data;
  } catch (error) {
    console.error(error);
  } finally {
    pending.value = false;
  }
}

onMounted(() => {
  if (props.id && !props.data) {
    getData();
  }
});

watch(() => props.id, () => {
  if (props.id && !props.data) {
    getData();
  }
});


</script>

<template>
  <div v-if="localData && !pending">
    <div role="row" class="grid grid-cols-2">
      <FieldDetail :label='$t("common.code")' :value=localData.code></FieldDetail>
      <FieldDetail :label='$t("service_block.short_install_date")' :value=formatDate(localData.installation_at)><Time
          :time="localData.installation_at"></Time></FieldDetail>
    </div>
    <div role="row" class="grid grid-cols-2">
      <FieldDetail :label='$t("common.status")' :value=localData.status?.name><span class="text-green-600 font-bold">{{
        localData.status?.name }}</span></FieldDetail>
      <FieldDetail :label='$t("service_block.short_uninstall_date")' :value=formatDate(localData.uninstallation_at)><Time
          :time="localData.uninstallation_at"></Time></FieldDetail>
    </div>
    <div role="row" class="grid grid-cols-1" v-if="localData.address_street">
      <FieldDetail :label='$t("address_block.address")' :value="address">
      </FieldDetail>
    </div>
    <hr v-if="!reduced" class="my-2" />

    <div v-if="!reduced" role="row" class="grid grid-cols-2">
      <FieldDetail :label='$t("service_block.manufacturer")' :value=localData.manufacturer></FieldDetail>
      <FieldDetail :label='$t("service_block.model")' :value=localData.model></FieldDetail>
    </div>

    <div v-if="!reduced" role="row" class="grid grid-cols-2">
      <FieldDetail :label='$t("service_block.caliber")' :value=localData.caliber?.name></FieldDetail>
      <FieldDetail :label='$t("service_block.manufacturing_year")' :value="localData.manufacturing_year ? String(localData.manufacturing_year) : null"></FieldDetail>
    </div>
    
    <div v-if="!reduced" role="row" class="grid grid-cols-2">
      <FieldDetail :label='$t("service_block.telecontrol")' :value=localData.has_remote_reading>
        <Icon v-if="localData.has_remote_reading" name="fa6-solid:circle-check" class="text-green-500" />
        <span v-else>-</span>
      </FieldDetail>
      <FieldDetail v-if="localData.has_remote_reading" :label='$t("service_block.remote_type")' 
      :value="localData.remote_reading_type? te(remoteTypeOptions.find(rt => rt.code == localData.remote_reading_type)?.label) ? t(remoteTypeOptions.find(rt => rt.code == localData.remote_reading_type)?.label) : remoteTypeOptions.find(rt => rt.code == localData.remote_reading_type)?.label : t('common.no_type')"/>
    </div>


    <div v-if="!reduced" class="opacity-50">
      <hr class="my-2" />

      <div role="row" class="grid grid-cols-2">
        <FieldDetail :label='$t("service_block.is_compound")' :value='localData.is_compound ? "Sí" : "No"'></FieldDetail>
        <FieldDetail :label='$t("service_block.is_general")' :value='localData.supply_points?.length > 1 ? "Sí" : "No"'></FieldDetail>
      </div>
      <div role="row" class="grid grid-cols-2">
        <FieldDetail :label='`${$t("common.code")} (2)`' :value="localData.code2"></FieldDetail>
        <FieldDetail :label='$t("service_block.is_property")' :value='localData.is_property ? "Sí" : "No"'></FieldDetail>
      </div>
    </div>

  </div>
  <div v-else>
    <div class="flex justify-center items-center h-full">
      <Icon name="fa6-solid:spinner" class="animate-spin text-slate-500" />
      <span class="ml-2">{{ $t('common.loading') }}...</span>
    </div>
  </div>
</template>