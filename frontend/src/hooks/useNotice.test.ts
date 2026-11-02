import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { useNotice } from './useNotice'

beforeEach(() => vi.useFakeTimers())
afterEach(() => vi.useRealTimers())

it('starts without a notice and exposes a notification callback', () => {
  const { result } = renderHook(() => useNotice())
  expect(result.current.message).toBe('')
  expect(result.current.notify).toEqual(expect.any(Function))
})

it('shows a notice and hides it after four seconds', () => {
  const { result } = renderHook(() => useNotice())
  act(() => result.current.notify('Task deleted.'))
  expect(result.current.message).toBe('Task deleted.')
  act(() => vi.advanceTimersByTime(3999))
  expect(result.current.message).toBe('Task deleted.')
  act(() => vi.advanceTimersByTime(1))
  expect(result.current.message).toBe('')
})

it('restarts the timer for a new notice, even with the same text', () => {
  const { result } = renderHook(() => useNotice())
  act(() => result.current.notify('Saved.'))
  act(() => vi.advanceTimersByTime(3000))
  act(() => result.current.notify('Saved.'))
  act(() => vi.advanceTimersByTime(3000))
  expect(result.current.message).toBe('Saved.')
  act(() => vi.advanceTimersByTime(1000))
  expect(result.current.message).toBe('')
})

it('keeps a stable notify callback between renders', () => {
  const { result, rerender } = renderHook(() => useNotice())
  const first = result.current.notify
  rerender()
  expect(result.current.notify).toBe(first)
})
