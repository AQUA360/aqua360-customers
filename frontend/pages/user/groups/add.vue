<script setup>
import { toRaw, ref, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';

import H1 from '~/components/atoms/H1.vue';
import GroupEdit from '~/components/organisms/GroupEdit.vue';
const { t } = useI18n();

</script>

<template>
  <div id="wrapper" class="text-base p-4 max-w-full">
    <div class="flex justify-between items-center mb-6">
      <H1>{{ $t('user_group.new_group') }}</H1>
    </div>
    <GroupEdit :id="null" />
  </div>
</template>