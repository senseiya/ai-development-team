"""Test architect agent with real OpenRouter call."""
import asyncio
import sys

async def main():
    sys.stdout.write("Starting architect test...\n")
    sys.stdout.flush()

    from core.agents.architect import ArchitectAgent
    from core.orchestrator.state import create_initial_state

    state = create_initial_state(
        "test-arch-1",
        "Create a simple task CRUD with FastAPI, SQLite, HTML UI"
    )

    sys.stdout.write("State created. Running architect...\n")
    sys.stdout.flush()

    agent = ArchitectAgent()
    result = await agent.run(state)
    bp = result.get("project_blueprint")

    if bp:
        sys.stdout.write(f"Blueprint: {bp.project_name}\n")
        sys.stdout.write(f"Backend: {bp.backend}\n")
        sys.stdout.write(f"Database: {bp.database}\n")
    else:
        sys.stdout.write(f"NO BLUEPRINT. Error: {result.get('error')}\n")
        sys.stdout.write(f"Status: {result.get('status')}\n")

    sys.stdout.write(f"Tokens: {result.get('tokens_used')}\n")
    sys.stdout.write("Done.\n")
    sys.stdout.flush()

if __name__ == "__main__":
    asyncio.run(main())
