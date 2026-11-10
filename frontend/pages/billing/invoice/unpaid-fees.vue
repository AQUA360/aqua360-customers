<script setup>
import H1 from '~/components/atoms/H1.vue';
import UnpaidFeesManage from '~/components/organisms/UnpaidFeesManage.vue';
</script>

<template>
  <div id="wrapper" class="text-base p-4 max-w-full">
    <div class="flex justify-between items-center mb-6">
      <H1>{{ $t('billing_block.unpaid_fee_title') }}</H1>
    </div>
    <UnpaidFeesManage />
  </div>
</template>
