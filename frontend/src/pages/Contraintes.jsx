import { useEffect, useState } from 'react'
import { Plus, Trash2, Shield, Target } from 'lucide-react'
import { apiRequest } from '../services/api'

export default function Contraintes() {
  const [items, setItems] = useState([])
  const [newText, setNewText] = useState('')
  const [newType, setNewType] = useState('soft')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true

    async function loadRules() {
      try {
        setLoading(true)
        const data = await apiRequest('/constraint-rules?limit=200')
        if (active) {
          const normalized = Array.isArray(data)
            ? data.map(rule => ({
              id: rule.id,
              type: rule.type,
              label: rule.name,
              active: rule.enabled,
              weight: rule.weight,
              payload: rule.payload,
            }))
            : []
          setItems(normalized)
          setError('')
        }
      } catch (err) {
        if (active) {
          setError(err.message || 'Impossible de charger les contraintes')
          setItems([])
        }
      } finally {
        if (active) {
          setLoading(false)
        }
      }
    }

    loadRules()

    return () => {
      active = false
    }
  }, [])

  async function toggle(id) {
    const target = items.find(item => item.id === id)
    if (!target) return
    try {
      const updated = await apiRequest(`/constraint-rules/${id}`, {
        method: 'PUT',
        body: { enabled: !target.active },
      })
      setItems(c => c.map(x => x.id === id ? {
        ...x,
        active: updated.enabled,
        label: updated.name,
        type: updated.type,
        weight: updated.weight,
        payload: updated.payload,
      } : x))
      setError('')
    } catch (err) {
      setError(err.message || 'Impossible de mettre a jour la contrainte')
    }
  }

  async function remove(id) {
    try {
      await apiRequest(`/constraint-rules/${id}`, { method: 'DELETE' })
      setItems(c => c.filter(x => x.id !== id))
      setError('')
    } catch (err) {
      setError(err.message || 'Impossible de supprimer la contrainte')
    }
  }

  async function add() {
    if (!newText.trim()) return
    try {
      const created = await apiRequest('/constraint-rules', {
        method: 'POST',
        body: {
          name: newText.trim(),
          type: newType,
          weight: 1,
          payload: {},
          enabled: true,
        },
      })
      setItems(c => [...c, {
        id: created.id,
        type: created.type,
        label: created.name,
        active: created.enabled,
        weight: created.weight,
        payload: created.payload,
      }])
      setNewText('')
      setError('')
    } catch (err) {
      setError(err.message || 'Impossible de creer la contrainte')
    }
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
      {error && (
        <div className="bg-red-50 text-red-600 text-xs border border-red-100 rounded-lg px-4 py-2">
          {error}
        </div>
      )}
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
            disabled={loading}
            className="flex items-center gap-1.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white text-sm font-medium px-4 py-2 rounded-lg"
          >
            <Plus size={15} /> Ajouter
          </button>
        </div>
      </div>
    </div>
  )
}
