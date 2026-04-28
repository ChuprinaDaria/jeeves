---
name: run-tests
description: Run backend pytest suite with correct Django settings and paths
---

Run backend tests from the correct working directory.

**All tests:**
```bash
cd /home/dchuprina/jeevs/backend && pytest -v
```

**Single app:**
```bash
cd /home/dchuprina/jeevs/backend && pytest Jeeves/{app_name}/tests/ -v
```

**Single test by name:**
```bash
cd /home/dchuprina/jeevs/backend && pytest -v -k "test_name"
```

**With coverage:**
```bash
cd /home/dchuprina/jeevs/backend && pytest --cov=Jeeves -v
```

Prerequisites: Docker services must be running (PostgreSQL on 5433, Redis on 6380).
Start them with: `cd /home/dchuprina/jeevs/backend && docker compose up -d postgres redis`
