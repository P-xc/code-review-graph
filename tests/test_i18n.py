"""Tests for the visualization UI language.

Only the generated page is translated. JSON/tool output and node names stay
as they are — agents match on those strings, and identifiers come from the
analyzed source.
"""
from __future__ import annotations

import pytest

from code_review_graph.i18n import EN, ZH, Translator, detect_language, normalize


class TestLanguageResolution:
    def test_supported_locales(self) -> None:
        assert normalize("zh") == ZH
        assert normalize("zh_CN") == ZH
        assert normalize("zh_CN.UTF-8") == ZH
        assert normalize("zh-Hans") == ZH
        assert normalize("en") == EN
        assert normalize("en_US.UTF-8") == EN

    def test_unknown_locale_falls_back_to_english(self) -> None:
        assert normalize("ja_JP") == EN
        assert normalize("fr") == EN
        assert normalize("") == EN
        assert normalize(None) == EN

    def test_detect_never_returns_unknown(self) -> None:
        assert detect_language() in (EN, ZH)
        assert detect_language("zh") == ZH
        assert detect_language("en") == EN

    @pytest.mark.parametrize("explicit", ["zh", "en"])
    def test_explicit_wins(self, explicit: str) -> None:
        assert detect_language(explicit) == explicit


class TestTranslator:
    def test_english_and_chinese_differ(self) -> None:
        en, zh = Translator(EN), Translator(ZH)
        assert en("stats.nodes") == "Nodes"
        assert zh("stats.nodes") == "节点"

    def test_every_english_key_has_a_chinese_value(self) -> None:
        """A half-translated page is worse than an English one."""
        from code_review_graph.i18n import _MESSAGES

        missing = [k for k in _MESSAGES[EN] if k not in _MESSAGES[ZH]]
        assert not missing, f"untranslated keys: {missing}"

    def test_unknown_key_renders_itself_not_blank(self) -> None:
        t = Translator(ZH)
        assert t("does.not.exist") == "does.not.exist"

    def test_values_never_empty(self) -> None:
        from code_review_graph.i18n import _MESSAGES

        for lang, table in _MESSAGES.items():
            for key, value in table.items():
                assert value, f"{lang}.{key} is empty"


class TestMarkerSubstitution:
    def test_all_markers_are_substituted(self) -> None:
        """A leftover __T[...]__ in the page would be visible to the user."""
        import re

        from code_review_graph.visualization import _MARKER_RE, _apply_translations

        sample = '<h3>__T[stats.nodes]__</h3><title>__T[page.title]__</title>'
        out = _apply_translations(sample, Translator(ZH))
        assert not _MARKER_RE.search(out)
        assert "节点" in out
        assert "代码审查图谱" in out

    def test_substitution_ignores_non_markers(self) -> None:
        from code_review_graph.visualization import _apply_translations

        sample = "plain text with no markers"
        assert _apply_translations(sample, Translator(ZH)) == sample
