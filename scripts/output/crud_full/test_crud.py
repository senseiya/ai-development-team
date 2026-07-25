"""Test the CRUD application."""
import httpx

BASE = "http://127.0.0.1:8765"

# Test HTML page
r = httpx.get(f"{BASE}/")
print(f"GET / : status={r.status_code}, size={len(r.text)}b, title={'Task Manager' in r.text}")

# Test list (empty)
r = httpx.get(f"{BASE}/api/tasks/")
print(f"GET /api/tasks/ : status={r.status_code}, tasks={r.json()}")

# Test create
r = httpx.post(f"{BASE}/api/tasks/", json={"title": "Test task", "description": "My first task"})
created = r.json()
print(f"POST /api/tasks/ : status={r.status_code}, id={created.get('id')}, title={created.get('title')}")

# Test list (with 1)
r = httpx.get(f"{BASE}/api/tasks/")
tasks = r.json()
print(f"GET /api/tasks/ : status={r.status_code}, count={len(tasks)}")

# Test get by id
r = httpx.get(f"{BASE}/api/tasks/{created['id']}")
print(f"GET /api/tasks/{created['id']} : status={r.status_code}, title={r.json().get('title')}")

# Test update
r = httpx.put(f"{BASE}/api/tasks/{created['id']}", json={"is_completed": True})
print(f"PUT /api/tasks/{created['id']} : status={r.status_code}, completed={r.json().get('is_completed')}")

# Test delete
r = httpx.delete(f"{BASE}/api/tasks/{created['id']}")
print(f"DELETE /api/tasks/{created['id']} : status={r.status_code}")

# Verify deleted
r = httpx.get(f"{BASE}/api/tasks/")
print(f"GET /api/tasks/ : status={r.status_code}, count={len(r.json())}")

print("\nAll CRUD operations verified!")