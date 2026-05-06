import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { CheckCircle2, Circle, Loader2 } from 'lucide-react'
import { apiRequest } from '../services/api'

const STEPS = [
  { n: 1, label: 'Données',              sub: 'Importées',      done: true  },
  { n: 2, label: 'Contraintes',          sub: 'Définies',       done: true  },
  { n: 3, label: 'Prompt (optionnel)',   sub: 'Décrire votre demande', active: true },
  { n: 4, label: 'Lancer la génération', sub: 'Optimiser et générer', done: false },
]

const SUGGESTIONS = [
  'Éviter les conflits',
  'Équilibrer la charge',
  'Privilégier certaines salles',
  'Autres…',
]

export default function Generation() {
  const navigate = useNavigate()
  const [step, setStep] = useState(3)
  const [prompt, setPrompt] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  function formatIsoDate(date) {
    return date.toISOString().slice(0, 10)
  }

  function addDays(date, days) {
    const next = new Date(date)
    next.setDate(next.getDate() + days)
    return next
  }

  async function handleLaunch() {
    setLoading(true)
    setError('')
    try {
      const today = new Date()
      const startDate = formatIsoDate(today)
      const endDate = formatIsoDate(addDays(today, 4))

      await apiRequest('/sessions', {
        method: 'POST',
        body: {
          status: 'planned',
          start_date: startDate,
          end_date: endDate,
        },
      })

      navigate('/resultats')
    } catch (err) {
      setError(err.message || 'Impossible de lancer la generation')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex gap-6 items-start">
      {/* Left progress panel */}
      <div className="w-56 flex-shrink-0 bg-white rounded-xl border border-gray-200 p-5">
        <div className="space-y-4">
          {STEPS.map((s) => {
            const isActive = s.n === step
            const isDone   = s.done
            return (
              <div key={s.n} className="flex items-start gap-3">
                <div className="flex flex-col items-center">
                  {isDone ? (
                    <CheckCircle2 size={20} className="text-green-500 mt-0.5" />
                  ) : isActive ? (
                    <div className="w-5 h-5 rounded-full border-2 border-blue-600 bg-blue-600 flex items-center justify-center mt-0.5">
                      <span className="text-white text-[10px] font-bold">{s.n}</span>
                    </div>
                  ) : (
                    <Circle size={20} className="text-gray-300 mt-0.5" />
                  )}
                  {s.n < STEPS.length && (
                    <div className={`w-0.5 h-8 mt-1 ${isDone ? 'bg-green-200' : 'bg-gray-200'}`} />
                  )}
                </div>
                <div>
                  <p className={`text-sm font-medium ${isActive ? 'text-blue-600' : isDone ? 'text-gray-800' : 'text-gray-400'}`}>
                    {s.label}
                  </p>
                  <p className={`text-xs ${isDone ? 'text-green-600' : isActive ? 'text-blue-400' : 'text-gray-400'}`}>
                    {s.sub}
                  </p>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Right content */}
      <div className="flex-1 bg-white rounded-xl border border-gray-200 p-6">
        <h2 className="text-base font-semibold text-gray-900 mb-1">Décrivez votre demande (en langage naturel)</h2>
        <p className="text-sm text-gray-500 mb-5">Indiquez ce que vous souhaitez changer ou améliorer dans la répartition.</p>

        <textarea
          rows={5}
          value={prompt}
          onChange={e => setPrompt(e.target.value)}
          placeholder={
            'Éviter que les soutenances de l\'encadrant Amine Benali soient le même jour.\n' +
            'Privilégier la salle A pour les soutenances du jury 1.\n' +
            'Limiter les soutenances après 16h.'
          }
          className="w-full border border-gray-300 rounded-lg px-4 py-3 text-sm text-gray-700 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-400 resize-none"
        />

        {error && (
          <div className="mt-4 text-xs text-red-600 bg-red-50 border border-red-100 rounded-lg px-3 py-2">
            {error}
          </div>
        )}

        {/* Suggestion chips */}
        <div className="flex items-center gap-2 mt-3 flex-wrap">
          <span className="text-xs text-gray-500">Suggestions :</span>
          {SUGGESTIONS.map(s => (
            <button
              key={s}
              onClick={() => setPrompt(p => p ? `${p}\n${s}` : s)}
              className="text-xs border border-gray-300 rounded-full px-3 py-1 hover:bg-gray-50 text-gray-600"
            >
              {s}
            </button>
          ))}
        </div>

        {/* Footer nav */}
        <div className="flex justify-between mt-8">
          <button
            onClick={() => setStep(s => Math.max(1, s - 1))}
            className="text-sm text-gray-600 border border-gray-300 rounded-lg px-5 py-2 hover:bg-gray-50"
          >
            Précédent
          </button>
          <button
            onClick={handleLaunch}
            disabled={loading}
            className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white text-sm font-semibold px-6 py-2 rounded-lg transition-colors"
          >
            {loading && <Loader2 size={15} className="animate-spin" />}
            {loading ? 'Génération en cours…' : 'Lancer la génération'}
          </button>
        </div>
      </div>
    </div>
  )
}
