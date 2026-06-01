# ACME Bottles Production Manager

A compact supply chain and production scheduling system for a plastic bottle manufacturer.

The app manages purchase orders, raw material supply orders, and a production status page for ACME Bottles. The scheduling logic follows explicit business constraints: two products, two dedicated production lines, FIFO processing, fixed production rates, and material availability from current and incoming supplies.

## Why This Shape

I optimized for correctness, clarity, and fast local execution. The backend uses Python's standard library HTTP server and SQLite so the system can run without installing external packages. The frontend is a dependency-free operational dashboard with production status, purchase orders, supplies, and creation modals.

The core production logic is isolated in `server/scheduler.py` and covered by unit tests. That was intentional: the important part of this project is not visual fidelity, but proving that the business rules are translated into reliable software behavior.

## Features

- Create purchase orders and persist them to SQLite
- List purchase orders in reverse chronological order
- Create supply orders with material type, quantity, supplier, tracking number, and ETA
- List supply orders in reverse chronological order
- Show remaining material inventory and incoming supply summaries
- Calculate production status for both production lines
- Display FIFO order schedule with expected start and completion time
- Mark orders as `Completed`, `In Production`, `Pending`, `Delay expected`, or `Unable to fulfill`
- Unit tests for the scheduling rules

## Business Rules Implemented

Products:

- `1-Liter Bottle`
- `1-Gallon Bottle`

Production lines:

- `1-Liter Production Line`: 2,000 bottles/hour
- `1-Gallon Production Line`: 1,500 bottles/hour

Material requirements:

| Product | PET Resin | PTA | Ethylene Glycol |
| --- | ---: | ---: | ---: |
| 1-Liter Bottle | 20g | 15g | 10g |
| 1-Gallon Bottle | 65g | 45g | 20g |

Scheduling:

- Purchase orders are processed FIFO by order date.
- Each order is assigned to the dedicated line for its product.
- Prior queued orders on the same line push the expected start time.
- Material requirements are consumed in FIFO order.
- Future supply ETAs can delay production.
- If current plus incoming supplies cannot cover an order, it is marked `Unable to fulfill`.

## Run Locally

Prerequisite: Python 3.10 or newer.

From the repository root:

```powershell
python server\app.py
```

On macOS or Linux, use:

```bash
python3 server/app.py
```

Then open:

```txt
http://127.0.0.1:8000
```

The app seeds the SQLite database automatically on first run. To reset the demo data:

```powershell
python server\seed.py
```

On macOS or Linux:

```bash
python3 server/seed.py
```

The generated SQLite file is stored under `data/` and is intentionally ignored by Git. A fresh clone will recreate and seed the database on first run.

Optional runtime settings:

```powershell
$env:ACME_PORT=8001
$env:ACME_PLANNING_NOW="2026-02-17T09:00:00Z"
python server\app.py
```

## Run Tests

```powershell
python -m unittest discover -s server\tests
```

On macOS or Linux:

```bash
python3 -m unittest discover -s server/tests
```

The test suite encodes ten business invariants directly as unit tests:
material requirement calculations, dedicated line assignment, FIFO sequencing on the same line,
independent line parallelism, delayed-supply status, unable-to-fulfill detection,
FIFO material depletion blocking downstream orders, status transitions around the planning
timestamp, inventory on-hand vs. incoming cutoff, and subtraction of materials reserved by
started orders. The scheduling module is intentionally
decoupled from the database and HTTP layer so each invariant can be verified in isolation.

## Navigation

- `Production Status`: current line status, FIFO schedule, expected start, ETA, and fulfillment status
- `Purchase Orders`: reverse chronological purchase order list and new PO modal
- `Supplies`: material inventory cards, supply order list, and new supply order modal

Demo data uses a fixed planning timestamp of `2026-02-17T09:00:00Z`. With the seeded data,
the first two purchase orders are completed, `PO-2026-0003` and `PO-2026-0004` are in production,
`PO-2026-0005` demonstrates `Delay expected` based on future supply ETAs, and `PO-2026-0006`
demonstrates `Unable to fulfill` when total available and incoming supplies are still insufficient.
To reset the demo back to this state, run `python server\seed.py`.

## Architecture

```txt
public/
  index.html      Static UI shell
  styles.css      Operational dashboard styling
  app.js          API client, table rendering, modal flows
server/
  app.py          HTTP server, API routes, static file serving
  db.py           SQLite connection and schema creation
  seed.py         Demo data
  scheduler.py    Production scheduling and material logic
  tests/          Unit tests for scheduling behavior
data/
  acme_bottles.sqlite3  Local database, generated at runtime
```

## API Endpoints

- `GET /api/meta`: returns product options, material options, and the active planning timestamp.
- `GET /api/purchase-orders`: returns purchase orders in reverse chronological order for the list view.
- `POST /api/purchase-orders`: creates a purchase order and persists it to SQLite.
- `GET /api/supplies`: returns supply orders and material inventory summaries.
- `POST /api/supplies`: creates a supply order with material, quantity, tracking number, and ETA.
- `GET /api/production-status`: calculates the FIFO production schedule, current line status, expected start, ETA, and fulfillment state.
- `POST /api/reset`: resets the local SQLite database to the seeded demo state.

## Tradeoffs

- I treated the domain constraints as the source of truth when sample screen labels and business rules differed. ACME manufactures only `1-Liter Bottle` and `1-Gallon Bottle`, so the app only allows those two products.
- I used SQLite instead of PostgreSQL to keep the project runnable with no setup. The database boundary is still real and can be migrated to PostgreSQL behind the same API shape.
- The UI is intentionally practical rather than pixel-perfect. It preserves the workflow and information architecture of an operations dashboard while keeping the implementation compact.
- Status values are calculated at read time instead of stored, so changes to orders or supplies immediately recalculate the schedule.
- Inventory cards show received materials minus materials reserved by orders that have already started, while incoming supply remains visible separately.
- The planning date is fixed at `2026-02-17T09:00:00Z` for deterministic demo behavior and repeatable test results.
- PO numbers are scoped by the order year, so a long-running installation starts a new sequence when orders move into a new calendar year.
- I added order-date indexes and transaction-guarded PO number generation, but did not add pagination or materialized schedule caching because the current dataset is intentionally small. In a production deployment, I would add cursor pagination and recalculate schedules on writes or through a background job.
- I did not include Docker because the app has no external dependencies. For a customer deployment, I would add a `Dockerfile`, environment-specific configuration, and a production web server rather than Python's built-in HTTP server.

## Tools Used

- Python standard library: `http.server`, `sqlite3`, `unittest`
- Vanilla HTML, CSS, and JavaScript
- PowerShell for local verification commands
- OpenAI Codex for implementation, refactoring, and code review
- Google Antigravity for browser-based interaction checks and manual UI verification
- A lightweight prompt-to-test verification harness to keep the scheduling rules, edge cases, and review criteria explicit during iteration

## AI-Assisted Workflow

I used AI assistance for implementation speed, but treated generated code as untrusted until it passed a small verification harness:

- Requirements were restated as explicit invariants: product catalog, material requirements, dedicated production lines, FIFO sequencing, delayed supply, and unable-to-fulfill behavior.
- The scheduling logic was isolated from UI and database code so it could be tested directly.
- Unit tests were expanded around the invariants, including independent production lines, material depletion across FIFO orders, status transitions around the planning timestamp, and inventory cutoff behavior.
- Browser walkthroughs were used to verify the operational workflow: purchase order creation, supply order creation, inventory updates, and production status rendering.

## Notable Prompts Used

- "Design a compact supply chain and production scheduling system for a plastic bottle manufacturer with two products, two dedicated production lines, FIFO order processing, and material availability constraints. Keep the scheduling logic testable and separate from the UI."
- "Use the business rules as a prompt and test harness: list the invariants the implementation must preserve, including material requirements, line assignment, FIFO sequencing, delayed supply, and unable-to-fulfill cases. Turn those invariants into unit tests."
- "Review the code and README as a release candidate: check for private paths, generated files, unclear tradeoffs, fragile execution steps, brittle edge cases, and wording that would make the repository look overly context-specific."
- "Open the local app in a browser, walk through purchase order creation, supply order creation, and the production status page, then report any UI or workflow issues that would block manual verification."
