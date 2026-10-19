"""Tests for C++ type-alias nodes.

`alias_declaration` used to appear in the parser only as evidence that a .h
is C++ rather than C, so `using int_t = integer<int>;` created no node at
all. Across ten cloned repos 455 aliases contributed nothing, and calls
against them stayed unresolved (int_t: 159 unresolved calls in type_safe).
"""
from __future__ import annotations

from pathlib import Path

from code_review_graph.parser import CodeParser

FIXTURES = Path(__file__).parent / "fixtures"


class TestCppTypeAlias:
    def setup_method(self) -> None:
        root = FIXTURES / "cpp_type_alias"
        parser = CodeParser(repo_root=root)
        self.nodes, self.edges = parser.parse_file(root / "sample.cpp")

    def _typed(self, name: str) -> list:
        return [
            n for n in self.nodes
            if n.name == name and n.kind == "Type"
            and n.extra.get("cpp_kind") == "alias_declaration"
        ]

    def test_namespace_scope_alias(self) -> None:
        """`using int_t = integer<int>;` is addressable."""
        assert self._typed("int_t"), (
            f"missing; nodes={[(n.kind, n.name) for n in self.nodes]}"
        )

    def test_alias_to_primitive(self) -> None:
        assert self._typed("flag")

    def test_alias_template(self) -> None:
        """`template <typename T> using ptr = T*;` is recorded too."""
        assert self._typed("ptr")

    def test_alias_inside_namespace(self) -> None:
        assert self._typed("size_type")

    def test_member_alias(self) -> None:
        """A class member alias is reachable, not swallowed by the class."""
        assert self._typed("value_type")

    def test_alias_does_not_displace_functions(self) -> None:
        """Adding aliases must not reclassify ordinary functions."""
        fn = [n for n in self.nodes if n.name in ("add", "get")
              and n.kind == "Function"]
        assert len(fn) >= 2, [n.name for n in fn]

    def test_class_still_a_class(self) -> None:
        kinds = {n.name: n.kind for n in self.nodes if n.name == "Wrapper"}
        assert kinds.get("Wrapper") in ("Class", "Type"), kinds
