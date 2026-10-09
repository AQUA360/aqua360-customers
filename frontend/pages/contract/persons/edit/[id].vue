<script setup>
import { toRaw, ref, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';

import H1 from '~/components/atoms/H1.vue';
import PersonEdit from '~/components/organisms/PersonEdit.vue';

const { t } = useI18n();

const route = useRoute()
const personId = ref(route.params.id)


onMounted(() => {
});

</script>

<template>
  <div id="wrapper" class="text-base p-4 max-w-full">
    
    <div v-if="personId != null">
      <div class="flex justify-between items-center mb-6">
        <H1>{{ $t('common.modify') }} {{ t('person') }}</H1>
      </div>
      <PersonEdit :id="parseInt(personId)" :connection="null" />
    </div>
  </div>
</template>


