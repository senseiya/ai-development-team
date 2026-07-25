"""Retry failed file generations."""
import asyncio
import sys
from pathlib import Path

OUTPUT = Path(__file__).resolve().parent / "output" / "crud_full"

async def main():
    sys.stdout.write("Retrying failed file generations...\n\n"); sys.stdout.flush()

    from core.agents.coder import CoderAgent
    from core.agents.context_builder import ContextBuilder
    from core.agents.syntax_validator import SyntaxValidator
    from core.agents.repair_agent import RepairAgent
    from core.agents.artifact_manager import ArtifactManager
    from core.orchestrator.state import create_initial_state, ProjectPlan, ProjectBlueprint, FileTask, FileStatus

    state = create_initial_state("retry-crud", "")
    state["workspace_path"] = str(OUTPUT)

    # Reconstruct plan from output
    bp = ProjectBlueprint(
        project_name="task-manager-lite",
        project_type="fullstack",
        backend="FastAPI",
        backend_language="python",
        database="SQLite",
        orm="SQLAlchemy",
        api_style="REST",
        architecture="layered",
        patterns=["Repository"],
        directory_structure=["src/", "src/models/", "src/api/", "src/services/", "src/templates/", "static/", "tests/"],
        frontend="HTMX",
    )

    plan = ProjectPlan(project_name="task-manager-lite")
    plan.files = [
        FileTask(file_path="src/api/routes.py", description="REST API routes for CRUD operations"),
        FileTask(file_path="src/templates/index.html", description="HTML template for task UI"),
        FileTask(file_path="static/style.css", description="CSS styles for the UI"),
    ]

    artifact_mgr = ArtifactManager(str(OUTPUT))
    validator = SyntaxValidator()
    repair_agent = RepairAgent()
    coder = CoderAgent()
    ctx_builder = ContextBuilder(plan, bp)

    for ft in plan.files:
        ft.status = FileStatus.GENERATING
        sys.stdout.write(f"  {ft.file_path}... "); sys.stdout.flush()

        content = await coder.generate_file(ft, ctx_builder, state)
        if not content:
            ft.status = FileStatus.FAILED
            sys.stdout.write("FAIL (no content)\n"); sys.stdout.flush()
            continue

        vr = validator.validate(ft.file_path, content)
        if vr.is_valid:
            ft.status = FileStatus.DONE; ft.content = content
            artifact_mgr.save_file(ft.file_path, content)
            artifact_mgr.save_file_status(ft)
            sys.stdout.write(f"OK ({len(content)}b)\n"); sys.stdout.flush()
        else:
            sys.stdout.write(f"SYNTAX: {vr.error_message}\n"); sys.stdout.flush()

    sys.stdout.write(f"\nTokens: {state.get('tokens_used')}\n")
    if OUTPUT.exists():
        for p in sorted(OUTPUT.rglob("*")):
            if p.is_file() and ".ai_artifacts" not in str(p):
                sys.stdout.write(f"  {p.relative_to(OUTPUT)} ({p.stat().st_size}b)\n")
    sys.stdout.flush()

if __name__ == "__main__":
    asyncio.run(main())