<script setup>
import { ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import H1Region from '~/components/atoms/H1Region.vue';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import OptionsDropdown from '~/components/molecules/OptionsDropdown.vue';
import DropdownOption from '~/components/atoms/DropdownOption.vue';
import { formatDate } from '~/utils/date';
import Time from '~/components/atoms/Time.vue';

const { t } = useI18n();

const props = defineProps({
  id: Number, // ID de l'element
  data: Object
});

</script>

<template>
  <div role="row" class="grid grid-cols-2">
    <FieldDetail :label='$t("common.code")' :value=data.token></FieldDetail>
    <FieldDetail :label='$t("common.name")' :value=data.name></FieldDetail>
  </div>
  <div role="row" class="grid grid-cols-2">
    <FieldDetail :label='$t("common.cadastral")' :value=data.cadastral></FieldDetail>
  </div>
  <div role="row" class="grid grid-cols-2">
    <FieldDetail :label='$t("address_block.city")' :value=data.address_city?.name></FieldDetail>
    <FieldDetail :label='$t("address_block.postal_code")' :value=data.address_postal_code?.code></FieldDetail>
  </div>

  <hr class="my-2" />
</template>
