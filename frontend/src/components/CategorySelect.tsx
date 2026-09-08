import type { Category } from '../api/types'

export default function CategorySelect({
  categories,
  value,
  onChange,
}: {
  categories: Category[]
  value: string
  onChange: (value: string) => void
}) {
  const roots = categories.filter((row) => row.parent_id === null)
  const childrenOf = (id: number) => categories.filter((row) => row.parent_id === id)

  return (
    <select value={value} onChange={(event) => onChange(event.target.value)}>
      <option value="">Sans categorie</option>
      {roots.map((root) => {
        const children = childrenOf(root.id)
        if (children.length === 0) {
          return (
            <option key={root.id} value={root.id}>
              {root.name}
            </option>
          )
        }
        return (
          <optgroup key={root.id} label={root.name}>
            <option value={root.id}>{root.name}</option>
            {children.map((child) => (
              <option key={child.id} value={child.id}>
                {child.name}
              </option>
            ))}
          </optgroup>
        )
      })}
    </select>
  )
}
