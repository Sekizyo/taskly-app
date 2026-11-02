import { Text } from '../../../design-system'
import type { Todo } from '../types'
import { summarizeTodos } from '../utils/todos'

const plural = (count: number, word: string) =>
  `${count} ${word}${count === 1 ? '' : 's'}`

export function TodoStats({ todos }: { todos: Todo[] }) {
  if (!todos.length) return null
  const { total, completed, active, overdue } = summarizeTodos(todos)
  const parts = [
    plural(total, 'task'),
    `${active} active`,
    `${completed} completed`,
  ]
  if (overdue) parts.push(`${overdue} overdue`)
  return (
    <Text role="status" muted size="small">
      {parts.join(' · ')}
    </Text>
  )
}
