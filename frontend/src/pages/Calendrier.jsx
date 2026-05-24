import { useEffect, useState } from 'react'
import { ChevronLeft, ChevronRight, SlidersHorizontal, X, CalendarDays } from 'lucide-react'
import { JURY_COLORS } from '../data/mockData'
import { apiRequest } from '../services/api'
import { useWorkflow } from '../context/WorkflowContext'
import { useNavigate } from 'react-router-dom'

function EventCard({ event }) {
  const c = JURY_COLORS[event.jury] || JURY_COLORS[1]
  return (
    <div className={`rounded-md px-2 py-1.5 text-xs border mb-1 ${c.bg} ${c.text} ${c.border}`}>
      <p className="font-semibold truncate">{event.prof}</p>
      <p className="opacity-75">{event.start} - {event.end}</p>
      <p className="opacity-60">Jury {event.jury}</p>
    </div>
  )
}

function formatDateShort(value) {
  if (!value) return ''
  const date = new Date(`${value}T00:00:00`)
  return date.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit' })
}

function formatWeekdayShort(value) {
  if (!value) return ''
  const date = new Date(`${value}T00:00:00`)
  const label = date.toLocaleDateString('fr-FR', { weekday: 'short' })
  return label.charAt(0).toUpperCase() + label.slice(1)
}

function slotTime(period, slotNumber) {
  const base = period === 'afternoon' ? 14 : 9
  const startHour = base + Math.max(0, slotNumber - 1)
  const endHour = startHour + 1
  const pad = value => String(value).padStart(2, '0')
  return {
    start: `${pad(startHour)}:00`,
    end: `${pad(endHour)}:00`,
  }
}

function parseDate(value) {
  if (!value) return null
  const date = new Date(`${value}T00:00:00`)
  if (Number.isNaN(date.getTime())) {
    return null
  }
  return date
}

function startOfWeek(date) {
  const day = date.getDay()
  const diff = (day + 6) % 7
  const start = new Date(date)
  start.setDate(date.getDate() - diff)
  start.setHours(0, 0, 0, 0)
  return start
}

function endOfWeek(start) {
  const end = new Date(start)
  end.setDate(start.getDate() + 6)
  return end
}

function formatRangeLabel(start, end) {
  if (!start || !end) return 'Semaine'
  const startLabel = start.toLocaleDateString('fr-FR', { day: '2-digit', month: 'short' })
  const endLabel = end.toLocaleDateString('fr-FR', { day: '2-digit', month: 'short', year: 'numeric' })
  const cap = text => text.charAt(0).toUpperCase() + text.slice(1)
  return `${cap(startLabel)} – ${cap(endLabel)}`
}

function buildWeeksFromDays(days) {
  if (!days.length) return []
  const parsed = days.map(day => ({ day, date: parseDate(day.key) }))
  if (parsed.some(item => !item.date)) {
    return [{ key: 'all', label: 'Semaine', start: null, end: null, days }]
  }

  const weeks = new Map()
  parsed
    .sort((a, b) => a.date - b.date)
    .forEach(item => {
      const start = startOfWeek(item.date)
      const key = start.toISOString().slice(0, 10)
      if (!weeks.has(key)) {
        const end = endOfWeek(start)
        weeks.set(key, {
          key,
          start,
          end,
          label: formatRangeLabel(start, end),
          days: [],
        })
      }
      weeks.get(key).days.push(item.day)
    })

  return Array.from(weeks.values()).sort((a, b) => a.start - b.start)
}

function findWeekIndexForDate(weeks, value) {
  const date = parseDate(value)
  if (!date) return -1
  return weeks.findIndex(week => week.start && week.end && date >= week.start && date <= week.end)
}

function formatRoomLabel(room) {
  const text = String(room ?? '').trim()
  if (!text) return 'Salle'
  if (text.toLowerCase().startsWith('salle')) return text
  return `Salle ${text}`
}

function buildCalendarData(slots, assignments, professors) {
  const slotsById = new Map(slots.map(slot => [slot.id, slot]))
  const profById = new Map(professors.map(prof => [prof.id, prof]))

  const uniqueDates = Array.from(new Set(slots.map(slot => slot.date))).sort()
  const uniqueRooms = Array.from(new Set(slots.map(slot => slot.room)))
    .sort((a, b) => String(a).localeCompare(String(b)))

  const days = uniqueDates.map(date => ({
    key: date,
    label: formatWeekdayShort(date),
    date: formatDateShort(date),
  }))

  const rooms = uniqueRooms.map(room => ({
    id: room,
    label: formatRoomLabel(room),
    places: null,
  }))

  const events = assignments.map(assignment => {
    const slot = slotsById.get(assignment.slot_id)
    if (!slot) return null
    const { start, end } = slotTime(slot.period, slot.slot_number)
    const president = profById.get(assignment.president_id)
    const examiner = profById.get(assignment.examiner_id)
    const profName = president?.name || examiner?.name || `Prof #${assignment.president_id || assignment.examiner_id}`

    return {
      id: assignment.id || `${assignment.slot_id}-${assignment.project_id}`,
      salle: slot.room,
      day: slot.date,
      start,
      end,
      prof: profName,
      jury: ((assignment.id || 0) % 5) + 1,
    }
  }).filter(Boolean)

  return { days, rooms, events }
}

function buildCalendarFromSolution(rawAssignments) {
  const uniqueDates = [...new Set(rawAssignments.map(a => a.date).filter(Boolean))].sort()
  const uniqueRooms = [...new Set(rawAssignments.map(a => String(a.room ?? a.session_id ?? 'A')).filter(Boolean))].sort((a, b) => a.localeCompare(b))

  const days = uniqueDates.map(date => ({
    key: date,
    label: formatWeekdayShort(date),
    date: formatDateShort(date),
  }))

  const rooms = uniqueRooms.map(r => ({
    id: r,
    label: formatRoomLabel(r),
    places: null,
  }))

  const events = rawAssignments.map((a, i) => {
    if (!a.date) return null
    const room = String(a.room ?? a.session_id ?? 'A')
    const start = a.start_time || a.slot_start || `${String(9 + (i % 7)).padStart(2, '0')}:00`
    const end   = a.end_time   || a.slot_end   || `${String(10 + (i % 7)).padStart(2, '0')}:00`
    const prof  = a.examiner_name || a.president_name
      || (a.examiner_id ? `Prof #${a.examiner_id}` : null)
      || (a.president_id ? `Président #${a.president_id}` : null)
      || `Projet #${a.project_id ?? i}`
    return {
      id: a.id ?? i,
      salle: room,
      day: a.date,
      start,
      end,
      prof,
      jury: ((Number(a.examiner_id || a.president_id || i) % 5) + 1),
    }
  }).filter(Boolean)

  return { days, rooms, events }
}

function buildSessionOptions(sessions, slots, assignments) {
  const slotToSession = new Map(slots.map(slot => [slot.id, slot.session_id]))
  const counts = new Map()

  assignments.forEach(item => {
    const sessionId = slotToSession.get(item.slot_id)
    if (!sessionId) return
    counts.set(sessionId, (counts.get(sessionId) || 0) + 1)
  })

  return sessions.map(session => ({
    id: session.id,
    label: `Session #${session.id}`,
    count: counts.get(session.id) || 0,
    range: formatRangeLabel(parseDate(session.start_date), parseDate(session.end_date)),
  }))
}

export default function Calendrier() {
  const { selectedSolution, clearSelectedSolution } = useWorkflow()
  const navigate = useNavigate()

  const [view, setView] = useState('Semaine')
  const [rooms, setRooms] = useState([])
  const [events, setEvents] = useState([])
  const [weeks, setWeeks] = useState([])
  const [weekIndex, setWeekIndex] = useState(0)
  const [sessions, setSessions] = useState([])
  const [selectedSessionId, setSelectedSessionId] = useState(null)
  const [sessionOptions, setSessionOptions] = useState([])
  const [slots, setSlots] = useState([])
  const [assignments, setAssignments] = useState([])
  const [professors, setProfessors] = useState([])
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true

    async function loadCalendar() {
      try {
        const [sessionsData, slotsData, assignmentsData, professorsData] = await Promise.all([
          apiRequest('/sessions?limit=200'),
          apiRequest('/slots?limit=200'),
          apiRequest('/assignments?limit=200'),
          apiRequest('/professors?limit=200'),
        ])

        if (!active) return

        const safeSessions = Array.isArray(sessionsData) ? sessionsData : []
        const safeSlots = Array.isArray(slotsData) ? slotsData : []
        const safeAssignments = Array.isArray(assignmentsData) ? assignmentsData : []
        const safeProfessors = Array.isArray(professorsData) ? professorsData : []

        const sortedSessions = safeSessions
          .slice()
          .sort((a, b) => new Date(a.start_date) - new Date(b.start_date))

        setSessions(sortedSessions)
        setSlots(safeSlots)
        setAssignments(safeAssignments)
        setProfessors(safeProfessors)

        if (sortedSessions.length > 0) {
          const latestSession = sortedSessions[sortedSessions.length - 1]
          setSelectedSessionId(current => current ?? latestSession.id)
        }

        setError('')
      } catch (err) {
        if (active) {
          setError(err.message || 'Impossible de charger le calendrier')
        }
      }
    }

    loadCalendar()

    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    // Don't override calendar if a specific solution is pinned
    if (selectedSolution?.rawAssignments?.length) return

    if (!slots.length) {
      setWeeks([])
      setRooms([])
      setEvents([])
      setSessionOptions([])
      return
    }

    const options = buildSessionOptions(sessions, slots, assignments)
    setSessionOptions(options)

    const activeSessionId = selectedSessionId ?? options[options.length - 1]?.id
    const sessionSlots = activeSessionId
      ? slots.filter(slot => slot.session_id === activeSessionId)
      : slots
    const slotIds = new Set(sessionSlots.map(slot => slot.id))
    const sessionAssignments = assignments.filter(item => slotIds.has(item.slot_id))
    const data = buildCalendarData(sessionSlots, sessionAssignments, professors)

    setRooms(data.rooms)
    setEvents(data.events)

    const nextWeeks = buildWeeksFromDays(data.days)
    setWeeks(nextWeeks)
    setWeekIndex(current => Math.min(current, Math.max(0, nextWeeks.length - 1)))
  }, [sessions, slots, assignments, professors, selectedSessionId, selectedSolution])

  useEffect(() => {
    setWeekIndex(0)
  }, [selectedSessionId])

  // Load solution pinned from Resultats page
  useEffect(() => {
    if (!selectedSolution?.rawAssignments?.length) return
    const { days, rooms: solRooms, events: solEvents } = buildCalendarFromSolution(selectedSolution.rawAssignments)
    setRooms(solRooms)
    setEvents(solEvents)
    setWeeks(buildWeeksFromDays(days))
    setWeekIndex(0)
  }, [selectedSolution])

  const activeWeek = weeks[weekIndex] || weeks[0]
  const visibleDays = activeWeek?.days || []
  const weekLabel = activeWeek?.label || 'Semaine'
  const selectedSession = sessionOptions.find(session => session.id === selectedSessionId)
  const canPrev = weekIndex > 0
  const canNext = weekIndex < weeks.length - 1

  function handleToday() {
    const todayKey = new Date().toISOString().slice(0, 10)
    const index = findWeekIndexForDate(weeks, todayKey)
    if (index >= 0) {
      setWeekIndex(index)
    }
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
      {/* Solution origin banner */}
      {selectedSolution && (
        <div className="flex items-center gap-2 px-5 py-2 bg-blue-50 border-b border-blue-100">
          <span className="text-xs text-blue-700 font-medium">
            Affichage de la solution {selectedSolution.label} — score {selectedSolution.score}%
          </span>
          <button
            onClick={clearSelectedSolution}
            className="ml-auto flex items-center gap-1 text-xs text-blue-500 hover:text-blue-700"
          >
            <X size={12} /> Fermer
          </button>
        </div>
      )}

      {/* Calendar toolbar */}
      <div className="flex items-center gap-3 px-5 py-3 border-b border-gray-200 flex-wrap">
        {error && (
          <span className="text-xs text-red-600 bg-red-50 border border-red-100 rounded-md px-2 py-1">
            {error}
          </span>
        )}
        <div className="flex items-center gap-1">
          <button
            className="p-1.5 rounded hover:bg-gray-100 disabled:opacity-40"
            onClick={() => setWeekIndex(idx => Math.max(0, idx - 1))}
            disabled={!canPrev}
          >
            <ChevronLeft size={16} />
          </button>
          <button
            className="p-1.5 rounded hover:bg-gray-100 disabled:opacity-40"
            onClick={() => setWeekIndex(idx => Math.min(weeks.length - 1, idx + 1))}
            disabled={!canNext}
          >
            <ChevronRight size={16} />
          </button>
        </div>
        <span className="text-sm font-semibold text-gray-700 min-w-[160px]">{weekLabel}</span>
        {selectedSession && (
          <span className="text-xs text-gray-500">{selectedSession.label} · {selectedSession.count} PFE</span>
        )}
        <button
          className="text-xs border border-gray-300 rounded-md px-3 py-1.5 hover:bg-gray-50"
          onClick={handleToday}
        >
          Aujourd'hui
        </button>
        <div className="flex-1" />
        {sessionOptions.length > 0 && (
          <select
            className="text-xs border border-gray-300 rounded-md px-2 py-1.5 bg-white"
            value={selectedSessionId ?? ''}
            onChange={event => setSelectedSessionId(Number(event.target.value))}
          >
            {sessionOptions.map(option => (
              <option key={option.id} value={option.id}>
                {option.label} · {option.count} PFE
              </option>
            ))}
          </select>
        )}
        <select className="text-xs border border-gray-300 rounded-md px-2 py-1.5 bg-white">
          <option>Toutes les salles</option>
          {rooms.map(s => <option key={s.id}>{s.label}</option>)}
        </select>
        <select className="text-xs border border-gray-300 rounded-md px-2 py-1.5 bg-white">
          <option>Tous les jurys</option>
          {[1,2,3,4,5].map(n => <option key={n}>Jury {n}</option>)}
        </select>
        <div className="flex rounded-md border border-gray-300 overflow-hidden">
          {['Semaine', 'Jour'].map(v => (
            <button
              key={v}
              onClick={() => setView(v)}
              className={`text-xs px-3 py-1.5 ${view === v ? 'bg-blue-600 text-white' : 'bg-white text-gray-600 hover:bg-gray-50'}`}
            >
              {v}
            </button>
          ))}
        </div>
        <button className="flex items-center gap-1.5 text-xs border border-gray-300 rounded-md px-3 py-1.5 hover:bg-gray-50">
          <SlidersHorizontal size={13} /> Filtres
        </button>
      </div>

      {/* Grid */}
      {visibleDays.length === 0 || rooms.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 gap-3">
          <CalendarDays size={40} className="text-gray-300" />
          <p className="text-sm font-medium text-gray-500">Aucun calendrier disponible</p>
          <p className="text-xs text-gray-400 text-center max-w-xs">
            {selectedSolution
              ? "La solution sélectionnée ne contient pas de données de calendrier."
              : "Lancez une génération pour obtenir un planning, puis cliquez sur « Calendrier » depuis la page Résultats."}
          </p>
          {!selectedSolution && (
            <button
              onClick={() => navigate('/generation')}
              className="mt-1 text-xs bg-blue-600 hover:bg-blue-700 text-white font-semibold px-4 py-2 rounded-lg transition-colors"
            >
              Lancer une génération
            </button>
          )}
        </div>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full table-fixed text-xs">
              <colgroup>
                <col className="w-36" />
                {visibleDays.map(d => <col key={d.key} />)}
              </colgroup>

              {/* Day headers */}
              <thead>
                <tr className="border-b border-gray-200 bg-gray-50">
                  <th className="text-left px-4 py-3 text-gray-400 font-normal" />
                  {visibleDays.map(d => (
                    <th key={d.key} className="text-center px-3 py-3 font-semibold text-gray-700">
                      {d.label} <span className="text-gray-400 font-normal">{d.date}</span>
                    </th>
                  ))}
                </tr>
              </thead>

              <tbody>
                {rooms.map((salle, si) => (
                  <tr key={salle.id} className={si < rooms.length - 1 ? 'border-b border-gray-200' : ''}>
                    {/* Room label */}
                    <td className="px-4 py-3 align-top border-r border-gray-100">
                      <p className="font-semibold text-gray-800">{salle.label}</p>
                      <p className="text-gray-400">({salle.places ?? '—'} places)</p>
                    </td>
                    {/* Day cells */}
                    {visibleDays.map(day => {
                      const dayEvents = events.filter(
                        e => e.salle === salle.id && e.day === day.key
                      )
                      return (
                        <td key={day.key} className="px-2 py-2 align-top min-w-[120px]">
                          {dayEvents.map(ev => <EventCard key={ev.id} event={ev} />)}
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Legend */}
          <div className="flex items-center gap-5 px-5 py-3 border-t border-gray-200">
            {Object.entries(JURY_COLORS).map(([n, c]) => (
              <div key={n} className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full inline-block" style={{ backgroundColor: c.dot }} />
                <span className="text-xs text-gray-600">Jury {n}</span>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
