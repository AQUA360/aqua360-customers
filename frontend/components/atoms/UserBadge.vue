<script setup>
const { t } = useI18n();
const props = defineProps({
    user: Object,
});

// Helper function to get user initials
const getUserInitials = (firstName, lastName) => {
    const first = firstName?.charAt(0) || '';
    const last = lastName?.charAt(0) || '';
    return (first + last).toUpperCase();
};

// Helper function to get group display text
const getGroupDisplay = (user) => {
    if (user.is_superuser) return t('common.admin');
    if (!user.group_name) return t('user_group.no_group');
    return user.group_name;
};
</script>

<template>
    <div class="flex items-center gap-3 p-3 rounded-lg">
        <div class="flex-shrink-0">
            <div class="w-10 h-10 rounded-full bg-sky-500 flex items-center justify-center text-white font-medium text-sm shadow-sm">
                <span v-if="user.first_name || user.last_name">
                    {{ getUserInitials(user.first_name, user.last_name) }}
                </span>
                <Icon v-else name="fa6-solid:user" class="text-sm" />
            </div>
        </div>

        <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 mb-1">
                <span class="font-semibold text-slate-900 truncate">{{ user.username }}</span>
                <span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium text-slate-700"
                 :class="{ 
                    'bg-slate-200': user.group_name != null, 
                    'bg-yellow-300': user.group_name == null 
                    }">
                    {{ getGroupDisplay(user) }}
                </span>
            </div>

            <div class="space-y-0.5">
                <div class="text-sm text-slate-600 truncate">
                    {{ user.first_name }} {{ user.last_name }}
                </div>
                <div class="text-xs text-slate-500 truncate flex items-center gap-1">
                    <Icon name="fa6-solid:envelope" class="text-slate-400" />
                    <span>{{ user.email || t('common.no_email') }}</span>
                </div>
            </div>
        </div>

        <div class="flex-shrink-0">
            <div class="w-2 h-2 rounded-full shadow-sm" 
            :class="{ 
                'bg-green-500': user.group_name != null, 
                'bg-yellow-400': user.group_name == null,
                }"></div>
        </div>
    </div>
</template>