import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'
import { todoFixture } from '../../../test/todoFixture'
import type { Todo } from '../types'
import { TodoList } from './TodoList'

vi.mock('../../../design-system', () => import('../../../design-system/mocks'))
vi.mock('./TodoEmptyState', () => ({
  TodoEmptyState: ({ hasTodos }: { hasTodos: boolean }) => (
    <p>Empty task list{hasTodos ? ' (filtered)' : ''}</p>
  ),
}))
vi.mock('./TodoItem', () => ({
  TodoItem: ({
    todo,
    busy,
    onToggle,
    onEdit,
    onDelete,
  }: {
    todo: Todo
    busy: boolean
    onToggle: () => void
    onEdit: () => void
    onDelete: () => void
  }) => (
    <li>
      {todo.title}
      <button disabled={busy} onClick={onToggle}>
        Toggle {todo.id}
      </button>
      <button onClick={onEdit}>Edit {todo.id}</button>
      <button onClick={onDelete}>Delete {todo.id}</button>
    </li>
  ),
}))

function makeProps() {
  return {
    todos: [] as Todo[],
    hasTodos: false,
    failed: false,
    busy: false,
    onCreate: vi.fn(),
    onToggle: vi.fn(),
    onEdit: vi.fn(),
    onDelete: vi.fn(),
  }
}

it('shows loading feedback before showing an empty list', () => {
  const props = makeProps()
  const { rerender } = render(<TodoList {...props} loading />)
  expect(screen.getByRole('status')).toHaveTextContent('Loading your tasks…')
  expect(screen.queryByText('Empty task list')).not.toBeInTheDocument()
  rerender(<TodoList {...props} loading={false} />)
  expect(screen.queryByRole('status')).not.toBeInTheDocument()
  expect(screen.getByText('Empty task list')).toBeVisible()
})

it('explains that the list is unavailable when loading failed and nothing is cached', () => {
  render(<TodoList {...makeProps()} loading={false} failed />)
  expect(
    screen.getByRole('heading', {
      name: 'The task list is temporarily unavailable',
    }),
  ).toBeVisible()
  expect(screen.queryByText('Empty task list')).not.toBeInTheDocument()
})

it('keeps showing cached tasks when a refetch failed', () => {
  const props = { ...makeProps(), todos: [todoFixture], hasTodos: true }
  render(<TodoList {...props} loading={false} failed />)
  expect(screen.getByText(todoFixture.title)).toBeVisible()
})

it('shows the filtered empty state when tasks exist but none are visible', () => {
  render(<TodoList {...makeProps()} hasTodos loading={false} />)
  expect(screen.getByText('Empty task list (filtered)')).toBeVisible()
})

it('renders each task and forwards actions with the matching task', async () => {
  const user = userEvent.setup()
  const second = { ...todoFixture, id: 8, title: 'Second task' }
  const props = { ...makeProps(), todos: [todoFixture, second], hasTodos: true }
  render(<TodoList {...props} loading={false} />)
  expect(screen.getAllByRole('listitem')).toHaveLength(2)
  await user.click(screen.getByRole('button', { name: 'Toggle 8' }))
  await user.click(screen.getByRole('button', { name: 'Edit 7' }))
  await user.click(screen.getByRole('button', { name: 'Delete 8' }))
  expect(props.onToggle).toHaveBeenCalledWith(second)
  expect(props.onEdit).toHaveBeenCalledWith(todoFixture)
  expect(props.onDelete).toHaveBeenCalledWith(second)
})

it('passes the busy state down to task items', () => {
  const props = { ...makeProps(), todos: [todoFixture], hasTodos: true }
  render(<TodoList {...props} loading={false} busy />)
  expect(screen.getByRole('button', { name: 'Toggle 7' })).toBeDisabled()
})
