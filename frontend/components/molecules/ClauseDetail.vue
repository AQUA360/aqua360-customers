<script setup>
// components/organisms/ClusterDetail.vue

const props = defineProps({
  item: Object
});

const emit = defineEmits(['show-detail', 'clickChangeStatus']);

</script>

<template>
<div class="flex items-center gap-2">
  <Icon name="fa6-solid:paragraph" class="text-slate-500 text-lg" />
  <span class="">{{ item.title }}</span>
</div>
</template>
