import { useEffect, useState } from 'react'
import { ChevronLeft, ChevronRight, SlidersHorizontal } from 'lucide-react'
import { calendarEvents as mockEvents, salles as mockRooms, days as mockDays, JURY_COLORS } from '../data/mockData'
import { apiRequest } from '../services/api'

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

function buildCalendarData(slots, assignments, professors) {
  const slotsById = new Map(slots.map(slot => [slot.id, slot]))
  const profById = new Map(professors.map(prof => [prof.id, prof]))

  const uniqueDates = Array.from(new Set(slots.map(slot => slot.date))).sort()
  const uniqueRooms = Array.from(new Set(slots.map(slot => slot.room)))

  const days = uniqueDates.map(date => ({
    key: date,
    label: formatWeekdayShort(date),
    date: formatDateShort(date),
  }))

  const rooms = uniqueRooms.map(room => ({
    id: room,
    label: `Salle ${room}`,
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

export default function Calendrier() {
  const [view, setView] = useState('Semaine')
  const [days, setDays] = useState(mockDays)
  const [rooms, setRooms] = useState(mockRooms)
  const [events, setEvents] = useState(mockEvents)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true

    async function loadCalendar() {
      try {
        const [slotsData, assignmentsData, professorsData] = await Promise.all([
          apiRequest('/slots?limit=200'),
          apiRequest('/assignments?limit=200'),
          apiRequest('/professors?limit=200'),
        ])

        if (!active) return

        const safeSlots = Array.isArray(slotsData) ? slotsData : []
        const safeAssignments = Array.isArray(assignmentsData) ? assignmentsData : []
        const safeProfessors = Array.isArray(professorsData) ? professorsData : []

        if (safeSlots.length > 0 && safeAssignments.length > 0) {
          const data = buildCalendarData(safeSlots, safeAssignments, safeProfessors)
          setDays(data.days.length ? data.days : mockDays)
          setRooms(data.rooms.length ? data.rooms : mockRooms)
          setEvents(data.events.length ? data.events : mockEvents)
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

  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
      {/* Calendar toolbar */}
      <div className="flex items-center gap-3 px-5 py-3 border-b border-gray-200 flex-wrap">
        {error && (
          <span className="text-xs text-red-600 bg-red-50 border border-red-100 rounded-md px-2 py-1">
            {error}
          </span>
        )}
        <div className="flex items-center gap-1">
          <button className="p-1.5 rounded hover:bg-gray-100"><ChevronLeft size={16} /></button>
          <button className="p-1.5 rounded hover:bg-gray-100"><ChevronRight size={16} /></button>
        </div>
        <span className="text-sm font-semibold text-gray-700 min-w-[140px]">20 – 24 Mai 2024</span>
        <button className="text-xs border border-gray-300 rounded-md px-3 py-1.5 hover:bg-gray-50">
          Aujourd'hui
        </button>
        <div className="flex-1" />
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
      <div className="overflow-x-auto">
        <table className="w-full table-fixed text-xs">
          <colgroup>
            <col className="w-36" />
            {days.map(d => <col key={d.key} />)}
          </colgroup>

          {/* Day headers */}
          <thead>
            <tr className="border-b border-gray-200 bg-gray-50">
              <th className="text-left px-4 py-3 text-gray-400 font-normal" />
              {days.map(d => (
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
                {days.map(day => {
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
    </div>
  )
}
