---
name: react-unit-tests
description: Conventions and patterns for writing Vitest + React Testing Library unit tests for the Taskly React/TypeScript frontend – components, hooks, React Query mutations, the fetch wrapper, design-system mocks. Use whenever creating or updating frontend/src/**/*.test.ts(x).
---

# Frontend unit tests (Vitest + Testing Library)

Stack: React 19, TypeScript (strict), @tanstack/react-query 5, styled-components,
Vitest 4 (jsdom), @testing-library/react + user-event + jest-dom. Tests are colocated:
`Foo.tsx` → `Foo.test.tsx`. Global setup: `src/test/setup.ts` (jest-dom matchers,
`cleanup` after each test).

## Style (match the existing tests)

- Import test APIs explicitly: `import { expect, it, vi } from 'vitest'`
  (add `describe`, `beforeEach` only when used).
- Top-level `it('<behaviour in words>', ...)`; group with `describe` only for several
  cases of one function.
- Query by role/label/text the way a user would (`getByRole('button', { name })`),
  never by class names or test IDs – except `getByTestId('alert')` provided by the
  design-system mocks.
- `const user = userEvent.setup()` and `await user.click(...)`; never `fireEvent` for
  user interactions.
- Prettier: single quotes, no semicolons, trailing commas (`.prettierrc.json`). Run
  `scripts/agent/run_tests.sh format .test-agent/run <frontend/src/...test.tsx ...>` on
  every test file you touch.
- Must type-check: `scripts/agent/run_tests.sh typecheck .test-agent/run` (tsc includes
  test files). Cast partial hook results as `as unknown as ReturnType<typeof useX>` like
  existing tests do.
- Shared helpers in `src/test/` are read-only for the PR workflow (only `*.test.ts(x)`
  files may change); define small helpers locally inside the test file instead.

## Reuse before you write

- `src/test/queryClient.tsx` – `createQueryWrapper()` for React Query hooks.
- `src/test/todoFixture.ts` – a valid `Todo`. Derive variants with spread:
  `{ ...todoFixture, id: 8, completed: true }`.
- `src/design-system/mocks.tsx` – lightweight stand-ins for every design-system
  component. In component tests:
  `vi.mock('../../../design-system', () => import('../../../design-system/mocks'))`
  (adjust the relative path).
- Isolate a component from its children/hooks with `vi.mock('./Child', () => ({ Child: () => <p>Child</p> }))`
  and `vi.mock('../hooks/useX', () => ({ useX: vi.fn() }))` + `vi.mocked(useX).mockReturnValue(...)`.

## Patterns by kind

**Presentational component** – render with props, assert visible text/roles for each
branch (e.g. `hasTodos` true/false), click callbacks with `vi.fn()` and assert calls.

**Container component using hooks** – mock the hooks module; cover success path
(callback + notice), pending/disabled state, and error path (alert shown, callbacks
not called). Use `waitFor` for async handlers.

**Plain hook (`useState` etc.)** – `renderHook(() => useX(args))`, mutate through
`act(() => result.current.setY(...))`, assert `result.current`.

**React Query hook** – real `QueryClient` per test, no mocking of React Query:

```tsx
import { createQueryWrapper } from '../../../test/queryClient'
const { client, wrapper } = createQueryWrapper() // retries disabled, isolated cache
const { result } = renderHook(() => useX(), { wrapper })
```

Mock the API layer: `vi.mock('../api/todos', () => ({ todosApi: { list: vi.fn(), create: vi.fn(), update: vi.fn(), remove: vi.fn() } }))`.
Seed cache with `client.setQueryData(todoKeys.list, [...])`, run
`await act(() => result.current.mutateAsync(...))`, assert
`client.getQueryData(todoKeys.list)`. Such tests need JSX → name them `.test.tsx`.

**`lib/http.ts` (fetch wrapper)** – `vi.stubGlobal('fetch', vi.fn())` and
`vi.unstubAllGlobals()` in `afterEach`; build responses with
`new Response(JSON.stringify(body), { status })`. Cover: ok JSON, 204 → `undefined`,
422 message, `detail` string, non-JSON error body, network failure, aborted signal
rethrows the original error, header merging.

**Timers** – `vi.useFakeTimers()` + `act(() => vi.advanceTimersByTime(ms))`; restore
with `vi.useRealTimers()` in `afterEach`.

## Run

From the repository root:

```sh
scripts/agent/run_tests.sh frontend .test-agent/run src/path/Foo.test.tsx   # focused
scripts/agent/run_tests.sh frontend .test-agent/run                          # full suite + coverage
scripts/agent/run_tests.sh typecheck .test-agent/run
```

Focused paths are relative to `frontend/` (e.g. `src/lib/http.test.ts`).
