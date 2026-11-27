"""Format permès a les clàusules del contracte.

Una clàusula pot portar negreta, cursiva, subratllat, salts de línia i enllaços.
Tot el que no és a la llista blanca es mostra com a text escapat, i els scripts
i els estils desapareixen sencers. Aquest mòdul no depèn de Django.
"""

from html import escape
from html.parser import HTMLParser
from urllib.parse import urlparse

ALLOWED_TAGS = {"b", "strong", "i", "em", "u", "a", "br"}
VOID_TAGS = {"br"}
DROP_CONTENT_TAGS = {"script", "style"}
ALLOWED_LINK_SCHEMES = {"http", "https", "mailto"}


def _safe_href(value):
    value = "".join((value or "").split())
    if not value:
        return None
    parsed = urlparse(value)
    if parsed.scheme.lower() in ALLOWED_LINK_SCHEMES:
        return value
    return None


class _ClauseSanitizer(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []
        self.open_tags = []
        self.dropping = 0

    def handle_starttag(self, tag, attrs):
        if tag in DROP_CONTENT_TAGS:
            self.dropping += 1
            return
        if self.dropping or tag not in ALLOWED_TAGS:
            return
        if tag == "br":
            self.out.append("<br>")
            return
        if tag == "a":
            href = _safe_href(dict(attrs).get("href"))
            if href is None:
                self.open_tags.append(None)
                return
            self.out.append(f'<a href="{escape(href, quote=True)}" rel="noopener noreferrer">')
        else:
            self.out.append(f"<{tag}>")
        self.open_tags.append(tag)

    def handle_startendtag(self, tag, attrs):
        if tag in VOID_TAGS:
            self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag in DROP_CONTENT_TAGS:
            self.dropping = max(0, self.dropping - 1)
            return
        if self.dropping or tag not in ALLOWED_TAGS or tag in VOID_TAGS:
            return
        if tag not in self.open_tags and not (tag == "a" and None in self.open_tags):
            return
        while self.open_tags:
            opened = self.open_tags.pop()
            if opened is not None:
                self.out.append(f"</{opened}>")
            if opened == tag or (tag == "a" and opened is None):
                break

    def handle_data(self, data):
        if not self.dropping:
            self.out.append(escape(data, quote=False))

    def close(self):
        super().close()
        while self.open_tags:
            opened = self.open_tags.pop()
            if opened is not None:
                self.out.append(f"</{opened}>")


def sanitize_clause_html(text):
    """Retorna HTML segur amb només les etiquetes permeses."""
    if not text:
        return ""
    parser = _ClauseSanitizer()
    parser.feed(str(text))
    parser.close()
    return "".join(parser.out)
