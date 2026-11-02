import { act, renderHook } from '@testing-library/react'
import { beforeEach, expect, it, vi } from 'vitest'
import { createQueryWrapper } from '../../../test/queryClient'
import { todoFixture } from '../../../test/todoFixture'
import { todoKeys } from '../api/queryKeys'
import { todosApi } from '../api/todos'
import { useCreateTodoMutation } from './useCreateTodoMutation'

vi.mock('../api/todos', () => ({ todosApi: { create: vi.fn() } }))
beforeEach(() => vi.clearAllMocks())

const saved = { ...todoFixture, id: 9, title: 'New task' }

it('prepends the saved task to the cached list without duplicating it', async () => {
  vi.mocked(todosApi.create).mockResolvedValue(saved)
  const { client, wrapper } = createQueryWrapper()
  client.setQueryData(todoKeys.list, [todoFixture, { ...saved, title: 'Old' }])
  const { result } = renderHook(() => useCreateTodoMutation(), { wrapper })
  await act(() => result.current.mutateAsync(saved))
  expect(todosApi.create).toHaveBeenCalledWith(saved)
  expect(client.getQueryData(todoKeys.list)).toEqual([saved, todoFixture])
})

it('creates the list cache when it was empty', async () => {
  vi.mocked(todosApi.create).mockResolvedValue(saved)
  const { client, wrapper } = createQueryWrapper()
  const { result } = renderHook(() => useCreateTodoMutation(), { wrapper })
  await act(() => result.current.mutateAsync(saved))
  expect(client.getQueryData(todoKeys.list)).toEqual([saved])
})

it('cancels an in-flight list refetch before writing the cache', async () => {
  vi.mocked(todosApi.create).mockResolvedValue(saved)
  const { client, wrapper } = createQueryWrapper()
  const cancel = vi.spyOn(client, 'cancelQueries')
  const { result } = renderHook(() => useCreateTodoMutation(), { wrapper })
  await act(() => result.current.mutateAsync(saved))
  expect(cancel).toHaveBeenCalledWith({ queryKey: todoKeys.list })
})

it('leaves the cache untouched when creation fails', async () => {
  vi.mocked(todosApi.create).mockRejectedValue(new Error('Invalid'))
  const { client, wrapper } = createQueryWrapper()
  client.setQueryData(todoKeys.list, [todoFixture])
  const { result } = renderHook(() => useCreateTodoMutation(), { wrapper })
  await act(() =>
    expect(result.current.mutateAsync(saved)).rejects.toThrow('Invalid'),
  )
  expect(client.getQueryData(todoKeys.list)).toEqual([todoFixture])
})
