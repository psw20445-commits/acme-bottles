# Contributing to ACME Bottles Production Manager

Thank you for your interest in contributing to the ACME Bottles Production Manager! We welcome contributions from the community to help improve this supply chain and production scheduling system.

Please read through these guidelines to understand our development workflow, coding standards, and how to submit contributions.

---

## Code of Conduct

By participating in this project, you agree to maintain a respectful, welcoming, and collaborative environment. Please report any unacceptable behavior to the project maintainers.

## How Can I Contribute?

### 1. Reporting Bugs
* Check the [Issues](https://github.com/psw20445-commits/acme-bottles/issues) tab to see if the bug has already been reported.
* If not, open a new issue using the **Bug Report** template.
* Provide a clear description of the bug, steps to reproduce, expected behavior, and screenshots if applicable.

### 2. Suggesting Features
* Open a new issue using the **Feature Request** template.
* Explain the use case, why this feature would be valuable, and how you envision it working.

### 3. Submitting Pull Requests
* Fork the repository and create a new branch from `main` (e.g., `feature/your-feature-name` or `bugfix/issue-number`).
* Ensure your code adheres to the project's style guidelines.
* **Make sure all unit tests pass** before submitting your PR.
* Write clear, concise commit messages.
* Submit your Pull Request using the provided PR template.

---

## Local Development Setup

### Prerequisites
* Python 3.10 or newer
* Git

### Installation
1. Fork and clone the repository:
   ```bash
   git clone https://github.com/psw20445-commits/acme-bottles.git
   cd acme-bottles
   ```

2. Run the application locally to verify setup:
   ```bash
   python server/app.py
   ```
   Open `http://127.0.0.1:8000` in your web browser. The database will seed automatically.

### Running Tests
We enforce strict test coverage for our scheduling engine. Run tests using:
```bash
python -m unittest discover -s server/tests
```

If you modify the scheduling logic in `server/scheduler.py`, you **must** add corresponding unit tests in `server/tests/` to verify your changes.

---

## CI/CD and Quality Gates
Every Pull Request triggers a GitHub Actions workflow that:
1. Lints the Python codebase.
2. Runs all unit tests in `server/tests`.
3. Verifies schema integrity.

PRs will not be merged unless all checks pass.

Thank you for helping make ACME Bottles better!
