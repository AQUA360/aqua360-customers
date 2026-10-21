"""Cards que només pinta el frontend amb els seus propis endpoints."""
from .base import DashboardCard, register


class FrontendCard(DashboardCard):
    has_data = False


@register
class DailyActivityCard(FrontendCard):
    key = 'daily_activity'
    default_size = 'lg'


@register
class RecentSearchesCard(FrontendCard):
    key = 'recent_searches'
    default_size = 'lg'


@register
class CalendarCard(FrontendCard):
    key = 'calendar'
    default_size = 'lg'
    sizes = ['md', 'lg']


@register
class QuickAccessCard(FrontendCard):
    key = 'quick_access'
    default_size = 'lg'
