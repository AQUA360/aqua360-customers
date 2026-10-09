<script setup>
import H1 from '~/components/atoms/H1.vue';
import CommitmentDepositEdit from '~/components/organisms/CommitmentDepositEdit.vue';

const { t }= useI18n();

onMounted(() => {
});


</script>

<template>
  <div id="wrapper" class="text-base p-4 max-w-full">
    <div class="flex justify-between items-center mb-6">
      <H1>{{ $t(`claim_block.new_commitment_deposit`) }}</H1>
    </div>
    <div>
      <CommitmentDepositEdit />
    </div>
  </div>
</template>
