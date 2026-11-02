import { beforeEach, expect, it, vi } from 'vitest'
import { request } from '../../../lib/http'
import { todoFixture } from '../../../test/todoFixture'
import { todosApi } from './todos'

vi.mock('../../../lib/http', () => ({ request: vi.fn() }))
beforeEach(() => vi.clearAllMocks())

it('passes the abort signal when fetching tasks', async () => {
  const signal = new AbortController().signal
  vi.mocked(request).mockResolvedValue([todoFixture])
  await expect(todosApi.list(signal)).resolves.toEqual([todoFixture])
  expect(request).toHaveBeenCalledWith('/todos', { signal })
})

it('sends only writable task fields on creation', async () => {
  vi.mocked(request).mockResolvedValue(todoFixture)
  await expect(todosApi.create(todoFixture)).resolves.toEqual(todoFixture)
  expect(request).toHaveBeenCalledWith('/todos', {
    method: 'POST',
    body: JSON.stringify({
      title: todoFixture.title,
      description: '',
      priority: 'medium',
      due_date: null,
      completed: false,
    }),
  })
})

it('patches a task with only the provided fields', async () => {
  vi.mocked(request).mockResolvedValue(todoFixture)
  await expect(
    todosApi.update(7, { completed: true, due_date: null }),
  ).resolves.toEqual(todoFixture)
  const [path, init] = vi.mocked(request).mock.calls[0]
  expect(path).toBe('/todos/7')
  expect(init?.method).toBe('PATCH')
  expect(JSON.parse(init?.body as string)).toEqual({
    completed: true,
    due_date: null,
  })
})

it('never sends read-only fields when patching from a full task', async () => {
  vi.mocked(request).mockResolvedValue(todoFixture)
  await todosApi.update(7, todoFixture)
  const body = JSON.parse(vi.mocked(request).mock.calls[0][1]?.body as string)
  expect(Object.keys(body).sort()).toEqual([
    'completed',
    'description',
    'due_date',
    'priority',
    'title',
  ])
})

it('deletes a task by id', async () => {
  vi.mocked(request).mockResolvedValue(undefined)
  await expect(todosApi.remove(7)).resolves.toBeUndefined()
  expect(request).toHaveBeenCalledWith('/todos/7', { method: 'DELETE' })
})
