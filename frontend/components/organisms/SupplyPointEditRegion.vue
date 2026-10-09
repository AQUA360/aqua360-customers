<script setup>
import { ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';

const { t } = useI18n();

const props = defineProps({
  id: Number, // ID de l'element
  edit: String,
});

const emit = defineEmits(['accept', 'show-subregion',]);
</script>

<template>
  <div class="region__content">
    <MoleculesSupplyPointEditType :id="props.id" @clickChangeStatus="handleUpdated"></MoleculesSupplyPointEditType>
    <MoleculesSupplyPointEditMeter :id="props.id" @clickChangeStatus="handleUpdated"></MoleculesSupplyPointEditMeter>
    <MoleculesSupplyPointEditRoute :id="props.id" @clickChangeStatus="handleUpdated"></MoleculesSupplyPointEditRoute>
    <MoleculesSupplyPointEditConnection :id="props.id" @clickChangeStatus="handleUpdated"></MoleculesSupplyPointEditConnection>

  </div><!-- end region__content -->
</template>
