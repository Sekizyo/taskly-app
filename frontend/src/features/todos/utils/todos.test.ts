import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { formatDate, isOverdue, selectTodos, validateTodo } from './todos'
import type { Todo } from '../types'

const base: Todo = {
  id: 1,
  title: 'Sprint plan',
  description: '',
  priority: 'medium',
  completed: false,
  due_date: null,
  created_at: '2026-10-01T12:00:00Z',
  updated_at: '2026-10-01T12:00:00Z',
}

describe('selectTodos', () => {
  it('combines status with a case-insensitive search in the description', () => {
    const matching = { ...base, description: 'Discuss the API' }
    const todos = [
      matching,
      { ...matching, id: 2, completed: true },
      { ...base, id: 3 },
    ]
    expect(selectTodos(todos, 'active', ' api ', 'newest')).toEqual([matching])
  })

  it('sorts by priority without changing the source array', () => {
    const high: Todo = { ...base, id: 2, priority: 'high' }
    const todos = [base, high]
    expect(selectTodos(todos, 'all', '', 'priority')).toEqual([high, base])
    expect(todos).toEqual([base, high])
  })

  it('shows only completed tasks for the completed filter', () => {
    const done = { ...base, id: 2, completed: true }
    expect(selectTodos([base, done], 'completed', '', 'newest')).toEqual([done])
  })

  it('sorts by due date with undated tasks last and newer ids first on ties', () => {
    const soon = { ...base, id: 2, due_date: '2026-10-02' }
    const later = { ...base, id: 3, due_date: '2026-12-01' }
    const sameDay = { ...base, id: 4, due_date: '2026-10-02' }
    expect(
      selectTodos([base, later, soon, sameDay], 'all', '', 'due').map(
        (todo) => todo.id,
      ),
    ).toEqual([4, 2, 3, 1])
  })

  it('sorts newest first by creation time, then by id', () => {
    const older = { ...base, id: 5, created_at: '2026-09-01T12:00:00Z' }
    const twin = { ...base, id: 2 }
    expect(
      selectTodos([older, base, twin], 'all', '', 'newest').map(
        (todo) => todo.id,
      ),
    ).toEqual([2, 1, 5])
  })
})

describe('validateTodo', () => {
  const input = {
    title: 'Task',
    description: '',
    priority: 'low' as const,
    due_date: null,
    completed: false,
  }

  it('accepts a valid task', () => {
    expect(validateTodo({ ...input, due_date: '2028-02-29' })).toEqual({})
  })

  it.each([
    [{ title: '  ' }, { title: 'Enter a task title.' }],
    [
      { title: 'x'.repeat(121) },
      { title: 'The title must be at most 120 characters.' },
    ],
    [
      { description: 'x'.repeat(2001) },
      { description: 'The description must be at most 2000 characters.' },
    ],
    [{ due_date: '2026-02-30' }, { due_date: 'Enter a valid date.' }],
    [{ due_date: '26-1-1' }, { due_date: 'Enter a valid date.' }],
    [{ due_date: 'not-a-date' }, { due_date: 'Enter a valid date.' }],
  ])('reports %o as %o', (override, errors) => {
    expect(validateTodo({ ...input, ...override })).toEqual(errors)
  })

  it('measures limits after trimming whitespace', () => {
    expect(validateTodo({ ...input, title: ` ${'x'.repeat(120)} ` })).toEqual(
      {},
    )
  })
})

describe('isOverdue', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date(2026, 9, 15, 9, 0))
  })
  afterEach(() => vi.useRealTimers())

  it.each([
    ['2026-10-14', false, true],
    ['2026-10-15', false, false],
    ['2026-10-16', false, false],
    ['2026-10-14', true, false],
    [null, false, false],
  ])('due %s, completed %s → %s', (due_date, completed, expected) => {
    expect(isOverdue({ ...base, due_date, completed })).toBe(expected)
  })
})

describe('formatDate', () => {
  it('formats an ISO date in British style', () => {
    expect(formatDate('2026-10-05')).toBe('5 Oct 2026')
  })
})
