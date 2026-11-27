from django import template
from django.template.defaultfilters import linebreaks_filter
from django.utils.safestring import mark_safe

from contract.utils.clause_html import sanitize_clause_html

register = template.Library()


@register.filter
def clause_html(value):
    """Clàusula del contracte: només negreta, cursiva, subratllat, salts de línia i enllaços."""
    return mark_safe(linebreaks_filter(sanitize_clause_html(value), autoescape=False))
