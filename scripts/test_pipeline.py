"""Test full architect + planner pipeline with real OpenRouter."""
import asyncio
import sys

async def main():
    sys.stdout.write("Starting full pipeline test...\n")
    sys.stdout.flush()

    from core.agents.architect import ArchitectAgent
    from core.agents.planner import PlannerAgent
    from core.orchestrator.state import create_initial_state

    state = create_initial_state(
        "test-pipe-1",
        "Create a simple task CRUD with FastAPI, SQLite, HTML UI"
    )

    # Step 1: Architect
    sys.stdout.write("[1/2] Architect...\n")
    sys.stdout.flush()
    agent = ArchitectAgent()
    state = await agent.run(state)
    bp = state.get("project_blueprint")
    sys.stdout.write(f"  Blueprint: {bp.project_name} ({bp.backend}/{bp.database})\n")
    sys.stdout.write(f"  Tokens: {state.get('tokens_used')}\n")
    sys.stdout.flush()

    # Step 2: Planner
    sys.stdout.write("[2/2] Planner...\n")
    sys.stdout.flush()
    planner = PlannerAgent()
    state = await planner.run(state)
    plan = state.get("project_plan")
    if plan:
        sys.stdout.write(f"  Plan: {len(plan.files)} files\n")
        for f in plan.files:
            deps = f" [depends: {','.join(f.dependencies)}]" if f.dependencies else ""
            sys.stdout.write(f"    {f.file_path}{deps}\n")
    else:
        sys.stdout.write(f"  NO PLAN. Error: {state.get('error')}\n")
    sys.stdout.write(f"  Total tokens: {state.get('tokens_used')}\n")
    sys.stdout.write("Done.\n")
    sys.stdout.flush()

if __name__ == "__main__":
    asyncio.run(main())
