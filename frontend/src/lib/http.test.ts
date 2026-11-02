import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { request } from './http'

const fetchMock = vi.fn<typeof fetch>()

beforeEach(() => vi.stubGlobal('fetch', fetchMock))
afterEach(() => {
  vi.unstubAllGlobals()
  fetchMock.mockReset()
})

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status })
}

it('prefixes the API path, merges headers and returns the JSON body', async () => {
  fetchMock.mockResolvedValue(jsonResponse([{ id: 1 }]))
  await expect(
    request('/todos', { method: 'POST', headers: { 'X-Trace': 'abc' } }),
  ).resolves.toEqual([{ id: 1 }])
  expect(fetchMock).toHaveBeenCalledWith('/api/todos', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Trace': 'abc' },
  })
})

it('resolves to undefined for 204 No Content without parsing a body', async () => {
  fetchMock.mockResolvedValue(new Response(null, { status: 204 }))
  await expect(request('/todos/1', { method: 'DELETE' })).resolves.toBe(
    undefined,
  )
})

it('explains validation limits for 422 responses', async () => {
  fetchMock.mockResolvedValue(jsonResponse({ detail: [{ msg: 'bad' }] }, 422))
  await expect(request('/todos')).rejects.toThrow(
    'Check the task details: title up to 120 characters, description up to 2000 characters, and a valid due date.',
  )
})

it('surfaces a string detail from the server', async () => {
  fetchMock.mockResolvedValue(jsonResponse({ detail: 'Task not found.' }, 404))
  await expect(request('/todos/9')).rejects.toThrow('Task not found.')
})

it.each([
  ['a non-JSON body', new Response('<html>oops</html>', { status: 500 })],
  ['a non-string detail', jsonResponse({ detail: { code: 1 } }, 500)],
])('falls back to a generic message for %s', async (_, response) => {
  fetchMock.mockResolvedValue(response)
  await expect(request('/todos')).rejects.toThrow(
    'The operation failed. Please try again.',
  )
})

it('replaces network failures with a friendly message', async () => {
  fetchMock.mockRejectedValue(new TypeError('Failed to fetch'))
  await expect(request('/todos')).rejects.toThrow(
    'Cannot connect to the server. Please try again.',
  )
})

it('rethrows the original error when the request was aborted', async () => {
  const controller = new AbortController()
  const abortError = new DOMException('Aborted', 'AbortError')
  controller.abort()
  fetchMock.mockRejectedValue(abortError)
  await expect(request('/todos', { signal: controller.signal })).rejects.toBe(
    abortError,
  )
})
