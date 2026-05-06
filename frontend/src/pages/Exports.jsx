import { useEffect, useState } from 'react'
import { Download, FileSpreadsheet, FileText, Calendar, Table, User, Building } from 'lucide-react'
import { apiRequest } from '../services/api'

const FORMATS = [
  { icon: FileSpreadsheet, label: 'Excel (xlsx)', sub: 'Tableau complet',         color: 'text-green-600 bg-green-50',  iconColor: '#16A34A' },
  { icon: FileText,        label: 'PDF',           sub: 'Planning détaillé',       color: 'text-red-600 bg-red-50',      iconColor: '#DC2626' },
  { icon: Calendar,        label: 'iCal / ICS',    sub: "Importer dans\nGoogle Agenda", color: 'text-blue-600 bg-blue-50', iconColor: '#2563EB' },
  { icon: Table,           label: 'CSV',           sub: 'Données brutes',          color: 'text-gray-600 bg-gray-100',   iconColor: '#4B5563' },
  { icon: User,            label: 'Par jury (PDF)', sub: 'Planning par jury',      color: 'text-purple-600 bg-purple-50',iconColor: '#7C3AED' },
  { icon: Building,        label: 'Par salle (PDF)', sub: 'Planning par salle',   color: 'text-amber-600 bg-amber-50',  iconColor: '#D97706' },
]

const DEFAULT_SUMMARY = {
  label: 'Solution #1 (recommandée)',
  score: '94%',
  soutenances: 312,
  jours: 5,
  salles: 4,
  conflits: 0,
}

function countConflicts(assignments) {
  const bySlot = new Map()
  assignments.forEach(assignment => {
    const list = bySlot.get(assignment.slot_id) || []
    list.push(assignment)
    bySlot.set(assignment.slot_id, list)
  })

  let conflicts = 0
  bySlot.forEach(list => {
    const seen = new Map()
    list.forEach(assignment => {
      ;[assignment.examiner_id, assignment.president_id].forEach(id => {
        if (!id) return
        const count = (seen.get(id) || 0) + 1
        if (count > 1) {
          conflicts += 1
        }
        seen.set(id, count)
      })
    })
  })

  return conflicts
}

function buildSummary(session, slots, assignments) {
  if (!session) return DEFAULT_SUMMARY
  const sessionSlots = slots.filter(slot => slot.session_id === session.id)
  const slotIds = new Set(sessionSlots.map(slot => slot.id))
  const sessionAssignments = assignments.filter(item => slotIds.has(item.slot_id))
  const uniqueDates = new Set(sessionSlots.map(slot => slot.date))
  const uniqueRooms = new Set(sessionSlots.map(slot => slot.room))
  const conflicts = countConflicts(sessionAssignments)
  const scoreValue = sessionAssignments.length ? Math.max(0, 100 - conflicts * 5) : null

  return {
    label: `Session #${session.id}`,
    score: scoreValue === null ? '—' : `${scoreValue}%`,
    soutenances: sessionAssignments.length,
    jours: uniqueDates.size,
    salles: uniqueRooms.size,
    conflits: conflicts,
  }
}

export default function Exports() {
  const [summary, setSummary] = useState(DEFAULT_SUMMARY)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true

    async function loadSummary() {
      try {
        const [sessionsData, slotsData, assignmentsData] = await Promise.all([
          apiRequest('/sessions?limit=200'),
          apiRequest('/slots?limit=200'),
          apiRequest('/assignments?limit=200'),
        ])

        if (!active) return

        const sessions = Array.isArray(sessionsData) ? sessionsData : []
        const slots = Array.isArray(slotsData) ? slotsData : []
        const assignments = Array.isArray(assignmentsData) ? assignmentsData : []

        if (sessions.length > 0) {
          const latest = sessions
            .slice()
            .sort((a, b) => new Date(b.start_date) - new Date(a.start_date))[0]
          setSummary(buildSummary(latest, slots, assignments))
        }

        setError('')
      } catch (err) {
        if (active) {
          setError(err.message || 'Impossible de charger le resume')
        }
      }
    }

    loadSummary()

    return () => {
      active = false
    }
  }, [])

  return (
    <div className="space-y-5 max-w-3xl">
      {/* Selected solution summary */}
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Solution sélectionnée</p>
        {error && (
          <div className="mb-3 text-xs text-red-600 bg-red-50 border border-red-100 rounded-lg px-3 py-2">
            {error}
          </div>
        )}
        <div className="flex items-center gap-6 flex-wrap">
          <div>
            <p className="text-sm font-bold text-gray-900">{summary.label}</p>
          </div>
          <div className="flex items-center gap-1">
            <span className="text-xs text-gray-500">Score</span>
            <span className="text-sm font-bold text-green-600 ml-1">{summary.score}</span>
          </div>
          {[
            { val: summary.soutenances, lbl: 'Soutenances' },
            { val: summary.jours,       lbl: 'Jours' },
            { val: summary.salles,      lbl: 'Salles' },
            { val: summary.conflits,    lbl: 'Conflits' },
          ].map(({ val, lbl }) => (
            <div key={lbl} className="text-center">
              <p className="text-base font-bold text-gray-900">{val}</p>
              <p className="text-xs text-gray-500">{lbl}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Formats */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <p className="text-sm font-semibold text-gray-700 mb-4">Formats disponibles</p>
        <div className="grid grid-cols-3 gap-4">
          {FORMATS.map(({ icon: Icon, label, sub, color, iconColor }) => (
            <div key={label} className="border border-gray-200 rounded-xl p-4 flex flex-col items-center gap-3 hover:border-blue-300 hover:shadow-sm transition-all">
              <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${color}`}>
                <Icon size={24} style={{ color: iconColor }} />
              </div>
              <div className="text-center">
                <p className="text-sm font-semibold text-gray-900">{label}</p>
                <p className="text-xs text-gray-500 whitespace-pre-line leading-tight mt-0.5">{sub}</p>
              </div>
              <button className="flex items-center gap-1.5 w-full justify-center text-xs font-medium text-blue-600 border border-blue-200 rounded-lg py-2 hover:bg-blue-50 transition-colors">
                <Download size={13} /> Télécharger
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
