"""Tests for the C/C++ #include resolution fix.

Before the fix, `_do_resolve_module` had no c/cpp branch, so every include
kept its bare module string. A bare string is not a node qualified name, so
the impact traversal could never cross a file boundary on a C/C++ repo.
"""
from __future__ import annotations

from pathlib import Path

from code_review_graph.parser import CodeParser

FIXTURES = Path(__file__).parent / "fixtures"


class TestCIncludeResolution:
    """`#include "x.h"` and `#include <x.h>` resolve to real indexed files."""

    def setup_method(self) -> None:
        root = FIXTURES / "c_include_resolution"
        self.root = root
        parser = CodeParser(repo_root=root)
        main = root / "src" / "main.c"
        self.nodes, self.edges = parser.parse_file(main)
        self.imports = [e for e in self.edges if e.kind == "IMPORTS_FROM"]

    def _targets(self) -> list[str]:
        return [e.target for e in self.imports]

    def test_quote_include_resolves_to_sibling_header(self) -> None:
        """#include "sibling.h" -> the header next to the including file."""
        resolved = [
            t for t in self._targets()
            if t.replace("\\", "/").endswith("src/sibling.h")
        ]
        assert resolved, f"no resolved sibling.h in {self._targets()}"

    def test_quote_include_resolves_relative_subdirectory(self) -> None:
        """#include "nested/deep.h" -> the header one directory down."""
        resolved = [
            t for t in self._targets()
            if t.replace("\\", "/").endswith("src/nested/deep.h")
        ]
        assert resolved, f"no resolved nested/deep.h in {self._targets()}"

    def test_system_header_stays_bare(self) -> None:
        """<stdio.h> is not in this repo: it must keep its bare string."""
        assert "stdio.h" in self._targets()

    def test_resolved_targets_are_absolute_paths(self) -> None:
        """Only real, repo-internal files may become edge targets."""
        for target in self._targets():
            if target == "stdio.h":
                continue
            assert len(target) > 2 and target[1] == ":", (
                f"include target is not an absolute path: {target!r}"
            )

    def test_every_include_emits_exactly_one_edge(self) -> None:
        assert len(self.imports) == 3
