<script setup>
import { toRaw, ref, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';

import H1 from '~/components/atoms/H1.vue';
import UserEdit from '~/components/organisms/UserEdit.vue';
const { t } = useI18n();

const route = useRoute()
const id = route.params.id
</script>

<template>
  <div id="wrapper" class="text-base p-4 max-w-full">
    <div class="flex justify-between items-center mb-6">
      <H1>{{ $t('common.modify') }} {{ t('user') }} </H1>
    </div>
    <UserEdit :id="id" />
  </div>
</template>