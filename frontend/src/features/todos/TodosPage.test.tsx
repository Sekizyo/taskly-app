import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, expect, it, vi } from 'vitest'
import { todoFixture } from '../../test/todoFixture'
import { useNotice } from '../../hooks/useNotice'
import { DeleteTodoDialog } from './components/DeleteTodoDialog'
import { TodoEditor } from './components/TodoEditor'
import { TodoList } from './components/TodoList'
import { TodosHeader } from './components/TodosHeader'
import { useTodoFilters } from './hooks/useTodoFilters'
import { useTodosBusy } from './hooks/useTodosBusy'
import { useTodosQuery } from './hooks/useTodosQuery'
import { useUpdateTodoMutation } from './hooks/useUpdateTodoMutation'
import { TodosPage } from './TodosPage'

vi.mock('../../design-system', () => import('../../design-system/mocks'))
vi.mock('../../hooks/useNotice', () => ({ useNotice: vi.fn() }))
vi.mock('./hooks/useTodoFilters', () => ({ useTodoFilters: vi.fn() }))
vi.mock('./hooks/useTodosBusy', () => ({ useTodosBusy: vi.fn() }))
vi.mock('./hooks/useTodosQuery', () => ({ useTodosQuery: vi.fn() }))
vi.mock('./hooks/useUpdateTodoMutation', () => ({
  useUpdateTodoMutation: vi.fn(),
}))
vi.mock('./components/TodosHeader', () => ({
  TodosHeader: vi.fn(() => <h1>Tasks</h1>),
}))
vi.mock('./components/TodoFilters', () => ({ TodoFilters: () => null }))
vi.mock('./components/TodoList', () => ({
  TodoList: vi.fn(() => <p>Task list</p>),
}))
vi.mock('./components/TodoEditor', () => ({
  TodoEditor: vi.fn(() => <p>Editor</p>),
}))
vi.mock('./components/DeleteTodoDialog', () => ({
  DeleteTodoDialog: vi.fn(() => <p>Delete dialog</p>),
}))
vi.mock('../../components/SuccessNotice', () => ({ SuccessNotice: () => null }))

const lastProps = <P,>(component: (props: P) => unknown) =>
  vi.mocked(component).mock.lastCall![0]

function setup({
  busy = false,
  query = {},
  mutation = {},
}: {
  busy?: boolean
  query?: Record<string, unknown>
  mutation?: Record<string, unknown>
} = {}) {
  const notify = vi.fn()
  const mutateAsync = vi.fn()
  const reset = vi.fn()
  const refetch = vi.fn().mockResolvedValue(undefined)
  vi.mocked(useTodosQuery).mockReturnValue({
    data: [todoFixture],
    isPending: false,
    isFetching: false,
    isError: false,
    error: null,
    refetch,
    ...query,
  } as unknown as ReturnType<typeof useTodosQuery>)
  vi.mocked(useUpdateTodoMutation).mockReturnValue({
    error: null,
    reset,
    mutateAsync,
    ...mutation,
  } as unknown as ReturnType<typeof useUpdateTodoMutation>)
  vi.mocked(useTodosBusy).mockReturnValue(busy)
  vi.mocked(useNotice).mockReturnValue({ message: '', notify })
  vi.mocked(useTodoFilters).mockReturnValue({
    filter: 'all',
    search: '',
    sort: 'newest',
    visible: [todoFixture],
    setFilter: vi.fn(),
    setSearch: vi.fn(),
    setSort: vi.fn(),
  })
  render(<TodosPage />)
  return { notify, mutateAsync, reset, refetch }
}

beforeEach(() => vi.clearAllMocks())

it('displays a query failure and resets mutation errors before retrying', async () => {
  const user = userEvent.setup()
  const { refetch, reset } = setup({
    query: {
      data: [],
      isError: true,
      error: new Error('The server is unavailable.'),
    },
  })
  expect(screen.getByTestId('alert')).toHaveTextContent(
    'The server is unavailable.',
  )
  await user.click(screen.getByRole('button', { name: 'Try again' }))
  await waitFor(() => expect(refetch).toHaveBeenCalledTimes(1))
  expect(reset).toHaveBeenCalledTimes(1)
  expect(reset.mock.invocationCallOrder[0]).toBeLessThan(
    refetch.mock.invocationCallOrder[0],
  )
})

it('shows a toggle error and disables retry while refetching', () => {
  setup({
    query: { isFetching: true },
    mutation: { error: new Error('Could not update.') },
  })
  expect(screen.getByTestId('alert')).toHaveTextContent('Could not update.')
  expect(screen.getByRole('button', { name: 'Try again' })).toBeDisabled()
})

it('passes list state to the task list and disables creation while loading', () => {
  setup({ query: { data: undefined, isPending: true } })
  expect(lastProps(TodoList)).toMatchObject({
    todos: [todoFixture],
    hasTodos: false,
    loading: true,
    failed: false,
    busy: false,
  })
  expect(lastProps(TodosHeader).disabled).toBe(true)
  expect(screen.queryByTestId('alert')).not.toBeInTheDocument()
})

it.each([
  [false, true, 'Another task complete. Well done!'],
  [true, false, 'Task marked as active.'],
])(
  'toggling a task with completed=%s saves %s and notifies',
  async (completed, next, message) => {
    const { mutateAsync, notify } = setup()
    const todo = { ...todoFixture, completed }
    mutateAsync.mockResolvedValue({ ...todo, completed: next })
    act(() => lastProps(TodoList).onToggle(todo))
    await waitFor(() => expect(notify).toHaveBeenCalledWith(message))
    expect(mutateAsync).toHaveBeenCalledWith({
      id: todo.id,
      input: { completed: next },
    })
  },
)

it('does not notify when toggling fails', async () => {
  const { mutateAsync, notify } = setup()
  mutateAsync.mockRejectedValue(new Error('Could not update.'))
  act(() => lastProps(TodoList).onToggle(todoFixture))
  await waitFor(() => expect(mutateAsync).toHaveBeenCalledTimes(1))
  expect(notify).not.toHaveBeenCalled()
})

it('ignores toggles while another task operation is running', () => {
  const { mutateAsync } = setup({ busy: true })
  act(() => lastProps(TodoList).onToggle(todoFixture))
  expect(mutateAsync).not.toHaveBeenCalled()
})

it('opens the editor for a new task and closes it after saving', () => {
  const { notify } = setup()
  expect(screen.queryByText('Editor')).not.toBeInTheDocument()
  act(() => lastProps(TodosHeader).onCreate())
  expect(lastProps(TodoEditor).todo).toBe('new')
  act(() => lastProps(TodoEditor).onSaved('New task added.'))
  expect(notify).toHaveBeenCalledWith('New task added.')
  expect(screen.queryByText('Editor')).not.toBeInTheDocument()
})

it('opens the editor for an existing task and closes it on cancel', () => {
  setup()
  act(() => lastProps(TodoList).onEdit(todoFixture))
  expect(lastProps(TodoEditor).todo).toBe(todoFixture)
  act(() => lastProps(TodoEditor).onClose())
  expect(screen.queryByText('Editor')).not.toBeInTheDocument()
})

it('opens the empty-state create action in the editor', () => {
  setup()
  act(() => lastProps(TodoList).onCreate())
  expect(lastProps(TodoEditor).todo).toBe('new')
})

it('confirms deletion and notifies once the task is deleted', () => {
  const { notify } = setup()
  act(() => lastProps(TodoList).onDelete(todoFixture))
  expect(lastProps(DeleteTodoDialog).todo).toBe(todoFixture)
  act(() => lastProps(DeleteTodoDialog).onDeleted())
  expect(notify).toHaveBeenCalledWith('Task deleted.')
  expect(screen.queryByText('Delete dialog')).not.toBeInTheDocument()
})

it('closes the delete confirmation without notifying', () => {
  const { notify } = setup()
  act(() => lastProps(TodoList).onDelete(todoFixture))
  act(() => lastProps(DeleteTodoDialog).onClose())
  expect(screen.queryByText('Delete dialog')).not.toBeInTheDocument()
  expect(notify).not.toHaveBeenCalled()
})
