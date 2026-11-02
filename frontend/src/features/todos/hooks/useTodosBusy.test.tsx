import { useMutation } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import { expect, it } from 'vitest'
import { createQueryWrapper } from '../../../test/queryClient'
import { todoKeys } from '../api/queryKeys'
import { useTodosBusy } from './useTodosBusy'

function useScenario(mutationKey: readonly string[], release: Promise<void>) {
  const busy = useTodosBusy()
  const mutation = useMutation({ mutationKey, mutationFn: () => release })
  return { busy, mutation }
}

it('is busy only while a task mutation is running', async () => {
  let finish!: () => void
  const release = new Promise<void>((resolve) => (finish = resolve))
  const { wrapper } = createQueryWrapper()
  const { result } = renderHook(() => useScenario(todoKeys.update, release), {
    wrapper,
  })
  expect(result.current.busy).toBe(false)
  act(() => result.current.mutation.mutate())
  await waitFor(() => expect(result.current.busy).toBe(true))
  await act(async () => finish())
  await waitFor(() => expect(result.current.busy).toBe(false))
})

it('ignores mutations outside the todos key space', async () => {
  const { wrapper } = createQueryWrapper()
  const { result } = renderHook(
    () => useScenario(['settings', 'save'], new Promise<void>(() => {})),
    { wrapper },
  )
  act(() => result.current.mutation.mutate())
  await waitFor(() => expect(result.current.mutation.isPending).toBe(true))
  expect(result.current.busy).toBe(false)
})
