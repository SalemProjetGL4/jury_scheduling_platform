import { useState } from 'react'
import { ChevronLeft, ChevronRight, SlidersHorizontal } from 'lucide-react'
import { calendarEvents, salles, days, JURY_COLORS } from '../data/mockData'

function EventCard({ event }) {
  const c = JURY_COLORS[event.jury]
  return (
    <div className={`rounded-md px-2 py-1.5 text-xs border mb-1 ${c.bg} ${c.text} ${c.border}`}>
      <p className="font-semibold truncate">{event.prof}</p>
      <p className="opacity-75">{event.start} - {event.end}</p>
      <p className="opacity-60">Jury {event.jury}</p>
    </div>
  )
}

export default function Calendrier() {
  const [view, setView] = useState('Semaine')

  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
      {/* Calendar toolbar */}
      <div className="flex items-center gap-3 px-5 py-3 border-b border-gray-200 flex-wrap">
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
          {salles.map(s => <option key={s.id}>Salle {s.id}</option>)}
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
            {salles.map((salle, si) => (
              <tr key={salle.id} className={si < salles.length - 1 ? 'border-b border-gray-200' : ''}>
                {/* Room label */}
                <td className="px-4 py-3 align-top border-r border-gray-100">
                  <p className="font-semibold text-gray-800">{salle.label}</p>
                  <p className="text-gray-400">({salle.places} places)</p>
                </td>
                {/* Day cells */}
                {days.map(day => {
                  const events = calendarEvents.filter(
                    e => e.salle === salle.id && e.day === day.key
                  )
                  return (
                    <td key={day.key} className="px-2 py-2 align-top min-w-[120px]">
                      {events.map(ev => <EventCard key={ev.id} event={ev} />)}
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
