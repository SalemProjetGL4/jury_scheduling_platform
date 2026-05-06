import { useState } from 'react'
import { Plus, Trash2, Shield, Target } from 'lucide-react'
import { constraints as initialConstraints } from '../data/mockData'

export default function Contraintes() {
  const [items, setItems] = useState(initialConstraints)
  const [newText, setNewText] = useState('')
  const [newType, setNewType] = useState('soft')

  function toggle(id) {
    setItems(c => c.map(x => x.id === id ? { ...x, active: !x.active } : x))
  }
  function remove(id) {
    setItems(c => c.filter(x => x.id !== id))
  }
  function add() {
    if (!newText.trim()) return
    setItems(c => [...c, { id: Date.now(), type: newType, label: newText.trim(), active: true }])
    setNewText('')
  }

  const hard = items.filter(x => x.type === 'hard')
  const soft = items.filter(x => x.type === 'soft')

  function Section({ title, icon: Icon, color, items: list }) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className={`flex items-center gap-2 px-5 py-4 border-b border-gray-200 ${color}`}>
          <Icon size={16} />
          <h3 className="text-sm font-semibold">{title}</h3>
          <span className="ml-auto text-xs opacity-70">{list.filter(x => x.active).length}/{list.length} actives</span>
        </div>
        <ul className="divide-y divide-gray-100">
          {list.map(c => (
            <li key={c.id} className="flex items-center gap-3 px-5 py-3 hover:bg-gray-50">
              <input
                type="checkbox"
                checked={c.active}
                onChange={() => toggle(c.id)}
                className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
              />
              <span className={`flex-1 text-sm ${c.active ? 'text-gray-800' : 'text-gray-400 line-through'}`}>
                {c.label}
              </span>
              <button onClick={() => remove(c.id)} className="text-gray-300 hover:text-red-400">
                <Trash2 size={14} />
              </button>
            </li>
          ))}
          {list.length === 0 && (
            <li className="px-5 py-4 text-sm text-gray-400 italic">Aucune contrainte</li>
          )}
        </ul>
      </div>
    )
  }

  return (
    <div className="space-y-5 max-w-2xl">
      <Section title="Contraintes dures" icon={Shield} color="text-red-700 bg-red-50" items={hard} />
      <Section title="Contraintes souples" icon={Target} color="text-blue-700 bg-blue-50" items={soft} />

      {/* Add new */}
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <p className="text-sm font-semibold text-gray-700 mb-3">Ajouter une contrainte</p>
        <div className="flex gap-2">
          <select
            value={newType}
            onChange={e => setNewType(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-400"
          >
            <option value="hard">Dure</option>
            <option value="soft">Souple</option>
          </select>
          <input
            type="text"
            value={newText}
            onChange={e => setNewText(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && add()}
            placeholder="Décrivez la contrainte…"
            className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
          />
          <button
            onClick={add}
            className="flex items-center gap-1.5 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium px-4 py-2 rounded-lg"
          >
            <Plus size={15} /> Ajouter
          </button>
        </div>
      </div>
    </div>
  )
}
