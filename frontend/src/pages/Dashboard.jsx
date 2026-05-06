import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { FileText, SlidersHorizontal, Sparkles, BarChart2, ArrowRight, Plus } from 'lucide-react'
import { apiRequest } from '../services/api'

const steps = [
  { n: 1, icon: FileText,           label: 'Données',     sub: 'Importer les fichiers',    to: '/donnees'     },
  { n: 2, icon: SlidersHorizontal,  label: 'Contraintes', sub: 'Définir les règles',        to: '/contraintes' },
  { n: 3, icon: Sparkles,           label: 'Génération',  sub: "Lancer l'optimisation",    to: '/generation'  },
  { n: 4, icon: BarChart2,          label: 'Résultats',   sub: 'Voir les solutions',        to: '/resultats'   },
]

const DEFAULT_STATS = [
  { value: '312', label: 'Soutenances' },
  { value: '5',   label: 'Jours' },
  { value: '4',   label: 'Salles' },
  { value: '0',   label: 'Conflit' },
  { value: '94%', label: 'Score moyen', green: true },
]

function formatDateLabel(value) {
  if (!value) return ''
  const date = new Date(`${value}T00:00:00`)
  return date.toLocaleDateString('fr-FR', { day: '2-digit', month: 'short', year: 'numeric' })
}

function buildSessionSummary(session, slots, assignments) {
  if (!session) return null
  const sessionSlots = slots.filter(slot => slot.session_id === session.id)
  const slotIds = new Set(sessionSlots.map(slot => slot.id))
  const sessionAssignments = assignments.filter(item => slotIds.has(item.slot_id))
  const uniqueDates = new Set(sessionSlots.map(slot => slot.date))
  const uniqueRooms = new Set(sessionSlots.map(slot => slot.room))

  return {
    label: `Session #${session.id}`,
    date: formatDateLabel(session.start_date),
    soutenances: sessionAssignments.length,
    jours: uniqueDates.size,
    salles: uniqueRooms.size,
  }
}

export default function Dashboard() {
  const navigate = useNavigate()
  const [stats, setStats] = useState(DEFAULT_STATS)
  const [lastSession, setLastSession] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true

    async function loadStats() {
      try {
        const [assignments, slots, sessions, conflicts] = await Promise.all([
          apiRequest('/assignments?limit=200'),
          apiRequest('/slots?limit=200'),
          apiRequest('/sessions?limit=200'),
          apiRequest('/conflicts?limit=200'),
        ])

        if (!active) return

        const safeAssignments = Array.isArray(assignments) ? assignments : []
        const safeSlots = Array.isArray(slots) ? slots : []
        const safeSessions = Array.isArray(sessions) ? sessions : []
        const safeConflicts = Array.isArray(conflicts) ? conflicts : []

        const uniqueDates = new Set(safeSlots.map(slot => slot.date))
        const uniqueRooms = new Set(safeSlots.map(slot => slot.room))
        const score = safeAssignments.length
          ? Math.max(0, 100 - safeConflicts.length * 5)
          : null

        setStats([
          { value: `${safeAssignments.length}`, label: 'Soutenances' },
          { value: `${uniqueDates.size}`, label: 'Jours' },
          { value: `${uniqueRooms.size}`, label: 'Salles' },
          { value: `${safeConflicts.length}`, label: 'Conflit' },
          { value: score === null ? '—' : `${score}%`, label: 'Score moyen', green: true },
        ])

        const latest = safeSessions
          .slice()
          .sort((a, b) => new Date(b.start_date) - new Date(a.start_date))[0]
        setLastSession(buildSessionSummary(latest, safeSlots, safeAssignments))
        setError('')
      } catch (err) {
        if (active) {
          setError(err.message || 'Impossible de charger les statistiques')
        }
      }
    }

    loadStats()

    return () => {
      active = false
    }
  }, [])

  return (
    <div className="space-y-6 max-w-4xl">
      {/* New generation card */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h2 className="text-base font-semibold text-gray-900 mb-1">Commencer une nouvelle génération</h2>
        <p className="text-sm text-gray-500 mb-6">Importez vos données, définissez vos contraintes et générez la meilleure répartition.</p>

        {/* Wizard steps */}
        <div className="flex items-start gap-2 mb-6">
          {steps.map((step, i) => {
            const Icon = step.icon
            return (
              <div key={step.n} className="flex items-center gap-2">
                <button
                  onClick={() => navigate(step.to)}
                  className="flex flex-col items-center gap-2 group"
                >
                  <div className="w-14 h-14 rounded-xl border-2 border-blue-200 bg-blue-50 flex items-center justify-center group-hover:bg-blue-100 transition-colors">
                    <Icon size={24} className="text-blue-600" />
                  </div>
                  <div className="text-center">
                    <p className="text-xs font-semibold text-blue-600">{step.n}. {step.label}</p>
                    <p className="text-xs text-gray-400">{step.sub}</p>
                  </div>
                </button>
                {i < steps.length - 1 && (
                  <ArrowRight size={18} className="text-gray-300 mt-3 flex-shrink-0" />
                )}
              </div>
            )
          })}
        </div>

        <button
          onClick={() => navigate('/generation')}
          className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
        >
          <Plus size={16} />
          Nouvelle génération
        </button>
      </div>

      {/* Stats + Last generation */}
      <div className="grid grid-cols-5 gap-4">
        {/* Stats */}
        <div className="col-span-3 bg-white rounded-xl border border-gray-200 p-6">
          <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-4">Résumé rapide</h3>
          {error && (
            <p className="text-xs text-red-600 mb-3">{error}</p>
          )}
          <div className="flex items-center divide-x divide-gray-100">
            {stats.map((s) => (
              <div key={s.label} className="flex-1 px-4 first:pl-0 text-center">
                <p className={`text-3xl font-bold ${s.green ? 'text-green-600' : 'text-gray-900'}`}>{s.value}</p>
                <p className="text-xs text-gray-500 mt-1">{s.label}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Last generation */}
        <div className="col-span-2 bg-white rounded-xl border border-gray-200 p-5 flex flex-col justify-between">
          <div>
            <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">Dernière génération</h3>
            <div className="flex items-center justify-between mb-1">
              <span className="text-sm font-semibold text-gray-900">{lastSession ? lastSession.label : 'Solution #1'}</span>
              <span className="text-sm font-bold text-green-600">{stats[4]?.value || '94%'}</span>
            </div>
            <p className="text-xs text-gray-400 mb-2">{lastSession ? lastSession.date : '20 Mai 2024 à 14:32'}</p>
            <p className="text-xs text-gray-500">
              {lastSession
                ? `${lastSession.soutenances} soutenances · ${lastSession.jours} jours · ${lastSession.salles} salles`
                : '312 soutenances · 5 jours · 4 salles'}
            </p>
          </div>
          <button
            onClick={() => navigate('/resultats')}
            className="mt-4 w-full text-center text-sm font-medium text-blue-600 border border-blue-200 rounded-lg py-2 hover:bg-blue-50 transition-colors"
          >
            Voir les résultats
          </button>
        </div>
      </div>
    </div>
  )
}
