<script setup>
import H1Region from '../atoms/H1Region.vue';
import { useI18n } from 'vue-i18n';

const { t } = useI18n();

const props = defineProps({
  group_name: String,
  users: Array,
});
</script>

<template>
    <div>
        <H1Region>{{ group_name }}</H1Region>
        <div class="mt-4" :style="{ 
            overflowY: 'auto', 
            maxWidth: '100%', minHeight: 'calc(100vh - 120px)', maxHeight: 'calc(100vh - 120px)',
        }">
            <div v-for="user in users" :key="user.id">
                <AtomsUserBadge :user="user" />
            </div>
            <div v-if="users.length == 0 || users == null">
                <p class="footering text-sm text-slate-500">
                    {{ t('user_group.no_users') }}
                </p>
            </div>
        </div>
    </div>

</template>