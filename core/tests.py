import re
from pathlib import Path

from django.conf import settings
from django.test import TestCase


class TemplateHygieneTests(TestCase):
    """Catch template-syntax footguns before they reach the browser."""

    def test_no_multiline_inline_comments(self):
        """Django's `{# ... #}` is single-line only. Multi-line blocks
        leak the markers + their content as visible text on the page.
        Use `{% comment %} ... {% endcomment %}` for multi-line.
        """
        # Match {# ... #} where the body contains a newline (multi-line block)
        pattern = re.compile(r'\{#([^#]*?\n[\s\S]*?)#\}', re.MULTILINE)
        offenders = []
        for tpl in (Path(settings.BASE_DIR) / 'templates').rglob('*.html'):
            src = tpl.read_text(encoding='utf-8')
            if pattern.search(src):
                offenders.append(str(tpl.relative_to(settings.BASE_DIR)))
        self.assertEqual(
            offenders, [],
            f'Multi-line {{# ... #}} comments leak into rendered HTML — '
            f'use {{% comment %}}...{{% endcomment %}} instead. '
            f'Offending files: {offenders}',
        )
