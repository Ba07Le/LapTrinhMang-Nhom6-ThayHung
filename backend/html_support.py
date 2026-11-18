"""Safe-ish offline HTML presentation and readable plain-text alternative for email.

HTML from email is untrusted. Strip active/embedded content and remote resources
before handing it to the optional TkinterWeb viewer.
"""
from html import escape, unescape
from html.parser import HTMLParser
import re
from urllib.parse import urlsplit

_BLOCKED = {'script', 'iframe', 'frame', 'frameset', 'object', 'embed', 'form', 'input',
            'button', 'textarea', 'select', 'option', 'link', 'meta', 'base', 'svg',
            'math', 'video', 'audio', 'source', 'canvas', 'applet'}
_SKIP_CONTENT = {'script', 'iframe', 'object', 'embed', 'form', 'svg', 'math', 'video', 'audio', 'canvas', 'applet'}
_VOID = {'br', 'hr', 'img', 'wbr', 'area', 'col', 'param'}
_SAFE_ATTRS = {'style', 'class', 'align', 'valign', 'width', 'height', 'cellpadding',
               'cellspacing', 'border', 'colspan', 'rowspan', 'bgcolor', 'color', 'title', 'alt'}


def _clean_css(css):
    # No network fetching, CSS imports, or executable/embedded CSS URLs.
    css = re.sub(r'(?is)@import\s+[^;]+;?', '', css)
    css = re.sub(r'(?is)url\s*\([^)]*\)', 'none', css)
    css = re.sub(r'(?is)expression\s*\([^)]*\)', '', css)
    return css


class _SafeEmailHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.output = []
        self.skip = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if self.skip:
            if tag in _SKIP_CONTENT:
                self.skip.append(tag)
            return
        if tag in _SKIP_CONTENT:
            self.skip.append(tag)
            return
        if tag in _BLOCKED:
            return
        if tag == 'img':
            alt = dict(attrs).get('alt') or 'Hình ảnh bên ngoài đã bị chặn'
            self.output.append('<span>[' + escape(alt) + ']</span>')
            return
        safe = []
        for key, val in attrs:
            if not key or val is None:
                continue
            key = key.lower()
            if key in _SAFE_ATTRS:
                if key == 'style':
                    val = _clean_css(val)
                safe.append(f' {key}="{escape(str(val), quote=True)}"')
            elif key == 'href' and tag == 'a':
                scheme = urlsplit(val.strip()).scheme.lower()
                if scheme in ('https', 'http', 'mailto'):
                    safe.append(f' href="{escape(val, quote=True)}"')
        self.output.append('<' + tag + ''.join(safe) + '>')

    def handle_endtag(self, tag):
        tag = tag.lower()
        if self.skip:
            if tag == self.skip[-1]:
                self.skip.pop()
            return
        if tag not in _BLOCKED and tag not in _VOID:
            self.output.append('</' + tag + '>')

    def handle_data(self, data):
        if not self.skip:
            self.output.append(escape(data))

    def handle_entityref(self, name):
        self.handle_data(unescape('&' + name + ';'))

    def handle_charref(self, name):
        self.handle_data(unescape('&#' + name + ';'))


def sanitize_email_html(source):
    parser = _SafeEmailHTML()
    parser.feed(source or '')
    parser.close()
    return '<html><body>' + ''.join(parser.output) + '</body></html>'


class _PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.skip = []

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'head'):
            self.skip.append(tag)
        elif not self.skip and tag in ('br', 'p', 'div', 'tr', 'li', 'h1', 'h2', 'h3', 'h4'):
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if self.skip and tag == self.skip[-1]:
            self.skip.pop()
        elif not self.skip and tag in ('p', 'div', 'tr', 'li', 'h1', 'h2', 'h3', 'h4'):
            self.parts.append('\n')

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def html_to_plain(source):
    parser = _PlainText()
    parser.feed(source or '')
    parser.close()
    result = ''.join(parser.parts)
    result = re.sub(r'[ \t]+', ' ', result)
    result = re.sub(r'\n[ \t]*\n[ \t]*\n+', '\n\n', result)
    return result.strip()


def looks_like_html(source):
    return bool(re.search(r'(?is)<\s*(?:!doctype\s+html|html|body|div|p|table|h[1-6]|span|br)\b', source or ''))
