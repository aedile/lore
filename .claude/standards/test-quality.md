# Test Quality Standards

Rules for the `software-developer` agent. Read before writing any test.

---

## Rule A — Parametrize or Perish
3+ test functions with identical structure differing only in input values MUST be
consolidated into a single `@pytest.mark.parametrize` test. The original test cases
become parametrize entries — no net loss of coverage.

## Rule B — No Tautological Assertions
These assertion patterns are FORBIDDEN as the sole assertion in any test:
- `assert str(None) == "None"` (always true)
- `assert module.__name__ == "module"` (always true)
- `assert isinstance(x, object)` (always true)
- `assert x is not None` without a companion value assertion
- `assert True` (unconditional pass)
- Consecutive redundant assertions on the same value (`assert x > 0; assert x >= 1`)

## Rule C — No Coverage Gaming
Assertions that exist solely to reach a coverage threshold are forbidden. Every
assertion must verify a behavior the test name claims to test. If a line needs
coverage, write a test that exercises the behavior — don't add a `pass` path.

## Rule D — Fixture Reuse
Before creating a new fixture, check `tests/conftest.py` and `tests/fixtures/`.
Do NOT duplicate fixtures locally. If a fixture is used in 2+ test files, move it
to conftest or `tests/fixtures/`.

## Rule E — Test File Size Limit
No test file should exceed 800 lines. If it does, split by feature area. Exempt
with `# gate-exempt: <reason>` at the module level if splitting would harm
readability (e.g., a single integration flow that requires sequential setup).

## Rule F — Helpers Over Duplication
If a helper function (mock builder, request factory, assertion helper) appears in
2+ test files, extract it to `tests/conftest.py` or `tests/helpers/`. The first
occurrence is local; the second triggers extraction.
