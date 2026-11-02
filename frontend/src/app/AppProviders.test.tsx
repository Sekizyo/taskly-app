import { QueryClient, useQueryClient } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { useTheme } from 'styled-components'
import { expect, it } from 'vitest'
import { theme } from '../design-system'
import { queryClient } from '../lib/queryClient'
import { AppProviders } from './AppProviders'

let seen: { client?: QueryClient; theme?: unknown } = {}

function Probe() {
  seen = { client: useQueryClient(), theme: useTheme() }
  return <p>App content</p>
}

it('renders children with the shared query client and design-system theme', () => {
  render(
    <AppProviders>
      <Probe />
    </AppProviders>,
  )
  expect(screen.getByText('App content')).toBeVisible()
  expect(seen.client).toBe(queryClient)
  expect(seen.theme).toBe(theme)
})

it('accepts an injected query client', () => {
  const client = new QueryClient()
  render(
    <AppProviders client={client}>
      <Probe />
    </AppProviders>,
  )
  expect(seen.client).toBe(client)
})
