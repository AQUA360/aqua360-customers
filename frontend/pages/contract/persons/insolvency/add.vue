<script setup>
import H1 from '~/components/atoms/H1.vue';
import InsolvencyProcessCreation from '~/components/organisms/InsolvencyProcessCreation.vue';

const route = useRoute();
const personId = computed(() => (route.query.person_id ? parseInt(route.query.person_id) : null));
const startDate = computed(() => (/^\d{4}-\d{2}-\d{2}$/.test(route.query.start_date || '') ? route.query.start_date : null));
</script>

<template>
  <div id="wrapper" class="text-base p-4 max-w-full">
    <div class="flex justify-between items-center mb-6">
      <H1>{{ $t('insolvency.new') }}</H1>
    </div>
    <InsolvencyProcessCreation :person-id="personId" :start-date="startDate" />
  </div>
</template>
