"""Tests for ContextBuilder."""

from __future__ import annotations

import pytest

from core.agents.context_builder import ContextBuilder, FileContext
from core.orchestrator.state import FileStatus, FileTask, ProjectPlan


@pytest.fixture
def simple_plan() -> ProjectPlan:
    return ProjectPlan(
        project_name="test-project",
        project_description="A test project",
        files=[
            FileTask(
                file_path="base.py",
                description="Base module",
                status=FileStatus.DONE,
                content="class Base:\n    pass",
            ),
            FileTask(file_path="app.py", description="App module", dependencies=["base.py"]),
        ],
    )


@pytest.fixture
def builder(simple_plan: ProjectPlan) -> ContextBuilder:
    return ContextBuilder(simple_plan)


class TestFileContext:
    def test_to_prompt_basic(self):
        ctx = FileContext(
            file_path="main.py",
            description="Main entry point",
            project_name="test",
            project_description="A test",
        )
        prompt = ctx.to_prompt()
        assert "main.py" in prompt
        assert "Main entry point" in prompt
        assert "test" in prompt

    def test_to_prompt_with_deps(self):
        ctx = FileContext(
            file_path="app.py",
            description="App",
            project_name="test",
            project_description="A test",
            dependencies_content={"base.py": "class Base: pass"},
        )
        prompt = ctx.to_prompt()
        assert "base.py" in prompt
        assert "class Base: pass" in prompt

    def test_to_prompt_with_existing_files(self):
        ctx = FileContext(
            file_path="app.py",
            description="App",
            project_name="test",
            project_description="A test",
            existing_files=["base.py", "config.py"],
        )
        prompt = ctx.to_prompt()
        assert "base.py" in prompt
        assert "config.py" in prompt


class TestContextBuilder:
    def test_build_context_no_deps(self, simple_plan):
        builder = ContextBuilder(simple_plan)
        task = FileTask(file_path="independent.py", description="Independent module")
        ctx = builder.build_context(task)
        assert ctx.file_path == "independent.py"
        assert ctx.dependencies_content == {}
        assert len(ctx.existing_files) == 1  # base.py is done

    def test_build_context_with_deps(self, simple_plan):
        builder = ContextBuilder(simple_plan)
        task = simple_plan.files[1]  # app.py depends on base.py
        ctx = builder.build_context(task)
        assert "base.py" in ctx.dependencies_content
        assert ctx.dependencies_content["base.py"] == "class Base:\n    pass"

    def test_build_context_excludes_self(self, simple_plan):
        builder = ContextBuilder(simple_plan)
        task = simple_plan.files[0]  # base.py
        ctx = builder.build_context(task)
        assert "base.py" not in ctx.existing_files

    def test_extract_interface(self, simple_plan):
        builder = ContextBuilder(simple_plan)
        content = """import os
from typing import List

class MyClass:
    def __init__(self, name: str):
        self.name = name

    def do_something(self) -> None:
        pass

def helper() -> int:
    return 42
"""
        iface = builder._extract_interface(content)
        assert "import os" in iface
        assert "from typing import List" in iface
        assert "class MyClass:" in iface
        assert "def do_something" in iface
        assert "def helper" in iface
        # Should not include method bodies
        assert "self.name = name" not in iface
        assert "return 42" not in iface

    def test_build_context_dep_not_done(self):
        plan = ProjectPlan(
            project_name="test",
            project_description="test",
            files=[
                FileTask(file_path="base.py", description="Base", status=FileStatus.PENDING),
                FileTask(file_path="app.py", description="App", dependencies=["base.py"]),
            ],
        )
        builder = ContextBuilder(plan)
        ctx = builder.build_context(plan.files[1])
        assert ctx.dependencies_content == {}
