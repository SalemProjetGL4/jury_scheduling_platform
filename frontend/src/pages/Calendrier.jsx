import { useEffect, useMemo, useState } from 'react'
import { ChevronLeft, ChevronRight, SlidersHorizontal, X, CalendarDays } from 'lucide-react'
import { apiRequest } from '../services/api'
import { useWorkflow } from '../context/WorkflowContext'
import { useNavigate } from 'react-router-dom'

const PERIOD_CONFIG = {
  morning:   { label: 'Matin',      icon: '☀',  accent: '#2563eb' },
  afternoon: { label: 'Après-midi', icon: '🌤', accent: '#7c3aed' },
}

const ROLE_COLORS = {
  supervisor: { bg: '#eff6ff', text: '#1e40af', label: 'Enc.'  },
  president:  { bg: '#f0fdf4', text: '#166534', label: 'Prés.' },
  examiner:   { bg: '#faf5ff', text: '#6b21a8', label: 'Exam.' },
}

const SLOT_TIMES = {
  1: ['08:00', '09:00'], 2: ['09:00', '10:00'], 3: ['10:00', '11:00'], 4: ['11:00', '12:00'],
  5: ['13:00', '14:00'], 6: ['14:00', '15:00'], 7: ['15:00', '16:00'], 8: ['16:00', '17:00'],
}
function slotToTime(slotNumber) {
  return SLOT_TIMES[slotNumber] ?? ['--:--', '--:--']
}

function isoToHHMM(iso) {
  if (!iso) return '--:--'
  const t = iso.slice(11, 16)
  return t.length === 5 ? t : '--:--'
}

// ── SlotGroup ────────────────────────────────────────────────────────────────
// Renders one time-slot card that may contain multiple simultaneous defenses
// (one per room). Clicking opens a modal showing all defenses in that slot.

function SlotGroup({ slot }) {
  const [open, setOpen] = useState(false)
  const count = slot.events.length
  const first = slot.events[0]
  const accentColor = first?.period === 'afternoon' ? '#7c3aed' : '#2563eb'

  return (
    <>
      <div
        onClick={() => setOpen(true)}
        style={{
          background: '#fff',
          border: '0.5px solid #e2e8f0',
          borderLeft: `3px solid ${accentColor}`,
          borderRadius: '6px',
          padding: '8px 10px',
          marginBottom: '6px',
          cursor: 'pointer',
          transition: 'box-shadow 0.15s',
        }}
        onMouseEnter={e => { e.currentTarget.style.boxShadow = '0 2px 8px rgba(0,0,0,0.08)' }}
        onMouseLeave={e => { e.currentTarget.style.boxShadow = 'none' }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
          <span style={{ fontSize: '11px', fontWeight: 600, color: '#0f172a' }}>{slot.start} – {slot.end}</span>
          {count > 1 && (
            <span style={{ fontSize: '10px', background: '#eff6ff', color: '#1e40af', border: '0.5px solid #bfdbfe', borderRadius: '99px', padding: '1px 7px' }}>
              {count} salles
            </span>
          )}
        </div>

        {count === 1 ? (
          <>
            <p style={{ margin: 0, fontSize: '12px', fontWeight: 600, color: '#0f172a', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {first.studentName}
            </p>
            <p style={{ margin: 0, fontSize: '11px', color: '#64748b', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', marginTop: '2px' }}>
              {first.projectTitle}
            </p>
            <span style={{ fontSize: '10px', color: '#94a3b8', marginTop: '3px', display: 'block' }}>{first.room}</span>
          </>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', marginTop: '2px' }}>
            {slot.events.map((e, i) => (
              <div key={i} style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ fontSize: '11px', color: '#475569', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '60%' }}>{e.studentName}</span>
                <span style={{ fontSize: '10px', color: '#94a3b8' }}>{e.room}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {open && (
        <div
          onClick={() => setOpen(false)}
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.35)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}
        >
          <div
            onClick={e => e.stopPropagation()}
            style={{
              background: '#fff', borderRadius: '12px', padding: '24px',
              width: count === 1 ? '380px' : '480px', maxWidth: '90vw',
              boxShadow: '0 8px 32px rgba(0,0,0,0.18)',
              maxHeight: '80vh', overflowY: 'auto',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <span style={{ fontSize: '15px', fontWeight: 700, color: '#0f172a' }}>{slot.start} – {slot.end}</span>
              <button onClick={() => setOpen(false)} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '18px', color: '#94a3b8' }}>✕</button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {slot.events.map((e, i) => (
                <div key={i} style={{ borderTop: i === 0 ? 'none' : '0.5px solid #e2e8f0', paddingTop: i === 0 ? 0 : '16px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: '10px' }}>
                    <p style={{ margin: 0, fontSize: '14px', fontWeight: 700, color: '#0f172a' }}>{e.studentName}</p>
                    <span style={{ fontSize: '11px', background: '#f1f5f9', color: '#475569', padding: '2px 8px', borderRadius: '99px' }}>{e.room}</span>
                  </div>
                  <p style={{ margin: 0, fontSize: '12px', color: '#64748b', marginBottom: '10px' }}>{e.projectTitle}</p>
                  {[
                    { label: 'Encadrant',   value: e.supervisorName },
                    { label: 'Président',   value: e.presidentName  },
                    { label: 'Examinateur', value: e.examinerName   },
                  ].map(({ label, value }) => (
                    <div key={label} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '5px' }}>
                      <span style={{ fontSize: '12px', color: '#94a3b8' }}>{label}</span>
                      <span style={{ fontSize: '12px', color: '#0f172a', fontWeight: 500 }}>{value ?? '—'}</span>
                    </div>
                  ))}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </>
  )
}

// ── helpers ──────────────────────────────────────────────────────────────────

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
  if (Number.isNaN(date.getTime())) return null
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
        weeks.set(key, { key, start, end, label: formatRangeLabel(start, end), days: [] })
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

function slotDateKey(slot) {
  if (slot.date) return slot.date
  if (slot.start_time) return slot.start_time.slice(0, 10)
  return null
}

function slotPeriodKey(slot) {
  if (slot.period) return slot.period
  if (slot.start_time) return parseInt(slot.start_time.slice(11, 13), 10) < 12 ? 'morning' : 'afternoon'
  return 'morning'
}

function buildCalendarData(slots, assignments, professors, projects = [], students = []) {
  const slotsById   = new Map(slots.map(slot => [slot.id, slot]))
  const profById    = new Map(professors.map(prof => [prof.id, prof]))
  const projectById = new Map(projects.map(p => [p.id, p]))
  const studentById = new Map(students.map(s => [s.id, s]))

  const uniqueDates = Array.from(new Set(slots.map(slot => slotDateKey(slot)).filter(Boolean))).sort()
  const uniqueRooms = Array.from(new Set(slots.map(slot => slot.room)))
    .sort((a, b) => String(a).localeCompare(String(b)))

  const days = uniqueDates.map(date => ({
    key: date, label: formatWeekdayShort(date), date: formatDateShort(date),
  }))

  const rooms = uniqueRooms.map(room => ({
    id: room, label: formatRoomLabel(room), places: null,
  }))

  const events = assignments.map(assignment => {
    const slot     = slotsById.get(assignment.slot_id)
    if (!slot) return null

    const start = isoToHHMM(slot.start_time)
    const end   = isoToHHMM(slot.end_time)

    const president  = profById.get(assignment.president_id)
    const examiner   = profById.get(assignment.examiner_id)
    const project    = projectById.get(assignment.project_id)
    const student    = project ? studentById.get(project.student_id) : null
    const supervisor = project ? profById.get(project.supervisor_id) : null

    const studentName    = student?.name    ?? `Étudiant #${assignment.project_id}`
    const projectTitle   = project?.title   ?? `Projet #${assignment.project_id}`
    const presidentName  = president?.name  ?? `Prof. #${assignment.president_id}`
    const examinerName   = examiner?.name   ?? `Prof. #${assignment.examiner_id}`
    const supervisorName = supervisor?.name ?? (project ? `Prof. #${project.supervisor_id}` : '—')

    const dateKey   = slotDateKey(slot)
    const periodKey = slotPeriodKey(slot)

    return {
      id: assignment.id || `${assignment.slot_id}-${assignment.project_id}`,
      salle: slot.room, room: slot.room,
      day: dateKey, period: periodKey,
      start, end,
      prof: studentName, title: projectTitle,
      juryInfo: `Enc: ${supervisorName} · Prés: ${presidentName} · Exam: ${examinerName}`,
      studentName, projectTitle, supervisorName, presidentName, examinerName,
      jury: ((assignment.id || 0) % 5) + 1,
    }
  }).filter(Boolean)

  return { days, rooms, events }
}

function abbrevName(name) {
  if (!name) return null
  const parts = name.trim().split(/\s+/)
  if (parts.length < 2) return name
  return `${parts[0][0]}. ${parts[parts.length - 1]}`
}

const PERIOD_ORDER = ['morning', 'afternoon']
const PERIOD_LABELS = {
  morning:   'Matin (09:00 – 12:00)',
  afternoon: 'Après-midi (14:00 – 17:00)',
}

function buildCalendarFromSolution(rawAssignments, {
  slotsById    = new Map(),
  profsById    = new Map(),
  projectsById = new Map(),
  studentsById = new Map(),
} = {}) {
  if (!rawAssignments?.length) return { days: [], rooms: [], events: [] }

  const uniqueDates = [...new Set(rawAssignments.map(a => a.date).filter(Boolean))].sort()
  const usedPeriods = PERIOD_ORDER.filter(p => rawAssignments.some(a => a.period === p))

  const days = uniqueDates.map(date => ({
    key: date, label: formatWeekdayShort(date), date: formatDateShort(date),
  }))

  const rooms = usedPeriods.map(p => ({
    id: p, label: PERIOD_LABELS[p] || p, places: null,
  }))

  const events = rawAssignments.filter(a => a.date && a.period).map((a, i) => {
    const slot = slotsById.get(a.session_id)

    let start, end
    if (slot?.start_time) {
      start = isoToHHMM(slot.start_time)
      end   = isoToHHMM(slot.end_time)
    } else {
      ;[start, end] = slotToTime(slot?.slot_number)
    }

    const room = slot?.room ?? `Salle ${slot?.room_id ?? '?'}`

    const supervisorProf = profsById.get(a.roles?.supervisor)
    const presidentProf  = profsById.get(a.roles?.president)
    const examinerProf   = profsById.get(a.roles?.examiner)

    const project = projectsById.get(a.project_id)
    const student = project ? studentsById.get(project.student_id) : null

    const studentName    = student?.name      ?? `Étudiant #${a.project_id ?? i}`
    const projectTitle   = project?.title     ?? `Projet #${a.project_id ?? i}`
    const supervisorName = supervisorProf?.name ?? (a.roles?.supervisor ? `Prof. #${a.roles.supervisor}` : '—')
    const presidentName  = presidentProf?.name  ?? (a.roles?.president  ? `Prof. #${a.roles.president}`  : '—')
    const examinerName   = examinerProf?.name   ?? (a.roles?.examiner   ? `Prof. #${a.roles.examiner}`   : '—')

    return {
      id: a.project_id ?? i,
      day: a.date, period: a.period,
      start, end, room,
      studentName, projectTitle, supervisorName, presidentName, examinerName,
      prof: studentName, title: projectTitle,
      juryInfo: `Enc: ${supervisorName} · Prés: ${presidentName} · Exam: ${examinerName}`,
      salle: a.period,
      jury: ((Number(a.roles?.president || a.roles?.examiner || a.project_id || i) % 5) + 1),
    }
  })

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

// ── Main component ────────────────────────────────────────────────────────────

export default function Calendrier() {
  const { selectedSolution, clearSelectedSolution, result: workflowResult } = useWorkflow()
  const navigate = useNavigate()

  const [view, setView]                     = useState('Semaine')
  const [rooms, setRooms]                   = useState([])
  const [events, setEvents]                 = useState([])
  const [weeks, setWeeks]                   = useState([])
  const [weekIndex, setWeekIndex]           = useState(0)
  const [sessions, setSessions]             = useState([])
  const [selectedSessionId, setSelectedSessionId] = useState(null)
  const [sessionOptions, setSessionOptions] = useState([])
  const [slots, setSlots]                   = useState([])
  const [assignments, setAssignments]       = useState([])
  const [professors, setProfessors]         = useState([])
  const [projects, setProjects]             = useState([])
  const [students, setStudents]             = useState([])
  const [error, setError]                   = useState('')
  const [selectedRoom, setSelectedRoom]     = useState('all')

  useEffect(() => {
    let active = true

    async function loadCalendar() {
      try {
        const [sessionsData, slotsData, assignmentsData, professorsData, projectsData, studentsData] = await Promise.all([
          apiRequest('/sessions?limit=200'),
          apiRequest('/slots?limit=200'),
          apiRequest('/assignments?limit=200'),
          apiRequest('/professors?limit=200'),
          apiRequest('/projects?limit=200'),
          apiRequest('/students?limit=200'),
        ])

        if (!active) return

        const safeSessions    = Array.isArray(sessionsData)    ? sessionsData    : []
        const safeSlots       = Array.isArray(slotsData)       ? slotsData       : []
        const safeAssignments = Array.isArray(assignmentsData) ? assignmentsData : []
        const safeProfessors  = Array.isArray(professorsData)  ? professorsData  : []
        const safeProjects    = Array.isArray(projectsData)    ? projectsData    : []
        const safeStudents    = Array.isArray(studentsData)    ? studentsData    : []

        const sortedSessions = safeSessions
          .slice()
          .sort((a, b) => new Date(a.start_date) - new Date(b.start_date))

        setSessions(sortedSessions)
        setSlots(safeSlots)
        setAssignments(safeAssignments)
        setProfessors(safeProfessors)
        setProjects(safeProjects)
        setStudents(safeStudents)

        if (sortedSessions.length > 0) {
          const latestSession = sortedSessions[sortedSessions.length - 1]
          setSelectedSessionId(current => current ?? latestSession.id)
        }

        setError('')
      } catch (err) {
        if (active) setError(err.message || 'Impossible de charger le calendrier')
      }
    }

    loadCalendar()
    return () => { active = false }
  }, [])

  useEffect(() => {
    if (selectedSolution?.rawAssignments?.length) return
    if (workflowResult?.solver_result?.assignments?.length) return

    if (!slots.length) {
      setWeeks([]); setRooms([]); setEvents([]); setSessionOptions([])
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
    const data = buildCalendarData(sessionSlots, sessionAssignments, professors, projects, students)

    setRooms(data.rooms)
    setEvents(data.events)

    const nextWeeks = buildWeeksFromDays(data.days)
    setWeeks(nextWeeks)
    setWeekIndex(current => Math.min(current, Math.max(0, nextWeeks.length - 1)))
  }, [sessions, slots, assignments, professors, projects, students, selectedSessionId, selectedSolution, workflowResult])

  useEffect(() => { setWeekIndex(0) }, [selectedSessionId])

  useEffect(() => {
    const rawAssignments =
      selectedSolution?.rawAssignments?.length ? selectedSolution.rawAssignments
      : workflowResult?.solver_result?.assignments?.length ? workflowResult.solver_result.assignments
      : null

    if (!rawAssignments) return

    const slotsById    = new Map(slots.map(s => [s.id, s]))
    const profsById    = new Map(professors.map(p => [p.id, p]))
    const projectsById = new Map(projects.map(p => [p.id, p]))
    const studentsById = new Map(students.map(s => [s.id, s]))

    const { days, rooms: solRooms, events: solEvents } = buildCalendarFromSolution(
      rawAssignments,
      { slotsById, profsById, projectsById, studentsById },
    )
    setRooms(solRooms)
    setEvents(solEvents)
    setWeeks(buildWeeksFromDays(days))
    setWeekIndex(0)
  }, [selectedSolution, workflowResult, slots, professors, projects, students])

  const activeWeek     = weeks[weekIndex] || weeks[0]
  const visibleDays    = activeWeek?.days || []
  const weekLabel      = activeWeek?.label || 'Semaine'
  const selectedSession = sessionOptions.find(session => session.id === selectedSessionId)
  const canPrev = weekIndex > 0
  const canNext = weekIndex < weeks.length - 1

  // Build calendarData as a stable memo so downstream memos only recompute when events change.
  const calendarData = useMemo(() => {
    const data = {}
    const dayKeys = visibleDays.map(d => d.key)
    for (const ev of events) {
      const d = ev.day
      if (!dayKeys.includes(d)) continue
      const period = (ev.salle === 'morning' || ev.salle === 'afternoon')
        ? ev.salle
        : (ev.start && parseInt(ev.start.split(':')[0], 10) < 12 ? 'morning' : 'afternoon')
      if (!data[d]) data[d] = { morning: [], afternoon: [] }
      data[d][period].push(ev)
    }
    return data
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [events, visibleDays])

  // Unique room values across all currently visible events.
  const allRooms = useMemo(() => {
    const roomSet = new Set()
    Object.values(calendarData).forEach(periods =>
      Object.values(periods).forEach(evs =>
        evs.forEach(e => e.room && roomSet.add(e.room))
      )
    )
    return ['all', ...Array.from(roomSet).sort()]
  }, [calendarData])

  // Filter by selected room, then group into time-slot buckets.
  const groupedCalendar = useMemo(() => {
    const result = {}
    Object.entries(calendarData).forEach(([date, periods]) => {
      result[date] = {}
      Object.entries(periods).forEach(([period, evs]) => {
        const filtered = selectedRoom === 'all'
          ? evs
          : evs.filter(e => e.room === selectedRoom)

        const bySlot = {}
        filtered.forEach(e => {
          const key = `${e.start}-${e.end}`
          if (!bySlot[key]) bySlot[key] = { start: e.start, end: e.end, events: [] }
          bySlot[key].events.push(e)
        })

        result[date][period] = Object.values(bySlot).sort((a, b) =>
          a.start.localeCompare(b.start)
        )
      })
    })
    return result
  }, [calendarData, selectedRoom])

  const dayKeys = visibleDays.map(d => d.key)
  const totalAssignments = selectedSolution?.rawAssignments?.length
    ?? workflowResult?.solver_result?.assignments?.length
    ?? 0
  const solutionScore = selectedSolution?.score ?? null

  function handleToday() {
    const todayKey = new Date().toISOString().slice(0, 10)
    const index = findWeekIndexForDate(weeks, todayKey)
    if (index >= 0) setWeekIndex(index)
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
      {/* Solution origin banner */}
      {(selectedSolution || workflowResult?.solver_result?.assignments?.length > 0) && (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 20px', background: '#f0fdf4', borderBottom: '0.5px solid #bbf7d0' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '13px', fontWeight: 600, color: '#166534' }}>✓ Solution valide</span>
            <span style={{ fontSize: '12px', color: '#4ade80', background: '#dcfce7', padding: '2px 8px', borderRadius: '99px', border: '0.5px solid #bbf7d0' }}>
              {totalAssignments} soutenances planifiées
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <span style={{ fontSize: '11px', color: '#86efac' }}>Score : {solutionScore ?? '100'}%</span>
            {selectedSolution && (
              <button
                onClick={clearSelectedSolution}
                style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '11px', color: '#4ade80', background: 'none', border: 'none', cursor: 'pointer' }}
              >
                <X size={12} /> Fermer
              </button>
            )}
          </div>
        </div>
      )}

      {/* Calendar toolbar */}
      <div className="flex items-center gap-3 px-5 py-3 border-b border-gray-200 flex-wrap">
        {error && (
          <span className="text-xs text-red-600 bg-red-50 border border-red-100 rounded-md px-2 py-1">{error}</span>
        )}
        <div className="flex items-center gap-1">
          <button
            className="p-1.5 rounded hover:bg-gray-100 disabled:opacity-40"
            onClick={() => setWeekIndex(idx => Math.max(0, idx - 1))}
            disabled={!canPrev}
          ><ChevronLeft size={16} /></button>
          <button
            className="p-1.5 rounded hover:bg-gray-100 disabled:opacity-40"
            onClick={() => setWeekIndex(idx => Math.min(weeks.length - 1, idx + 1))}
            disabled={!canNext}
          ><ChevronRight size={16} /></button>
        </div>
        <span className="text-sm font-semibold text-gray-700 min-w-[160px]">{weekLabel}</span>
        {selectedSession && (
          <span className="text-xs text-gray-500">{selectedSession.label} · {selectedSession.count} PFE</span>
        )}
        <button
          className="text-xs border border-gray-300 rounded-md px-3 py-1.5 hover:bg-gray-50"
          onClick={handleToday}
        >Aujourd'hui</button>
        <div className="flex-1" />
        {sessionOptions.length > 0 && (
          <select
            className="text-xs border border-gray-300 rounded-md px-2 py-1.5 bg-white"
            value={selectedSessionId ?? ''}
            onChange={ev => setSelectedSessionId(Number(ev.target.value))}
          >
            {sessionOptions.map(option => (
              <option key={option.id} value={option.id}>
                {option.label} · {option.count} PFE
              </option>
            ))}
          </select>
        )}

        {/* Room filter — pill buttons derived from visible events */}
        {allRooms.length > 1 && (
          <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
            <span style={{ fontSize: '12px', color: '#94a3b8', marginRight: '4px' }}>Salle :</span>
            {allRooms.map(room => (
              <button
                key={room}
                onClick={() => setSelectedRoom(room)}
                style={{
                  fontSize: '12px',
                  padding: '4px 12px',
                  borderRadius: '99px',
                  border: '0.5px solid',
                  borderColor: selectedRoom === room ? '#2563eb' : '#e2e8f0',
                  background: selectedRoom === room ? '#eff6ff' : '#fff',
                  color: selectedRoom === room ? '#1e40af' : '#64748b',
                  cursor: 'pointer',
                  fontWeight: selectedRoom === room ? 600 : 400,
                  transition: 'all 0.15s',
                }}
              >
                {room === 'all' ? 'Toutes' : room}
              </button>
            ))}
          </div>
        )}

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
            >{v}</button>
          ))}
        </div>
        <button className="flex items-center gap-1.5 text-xs border border-gray-300 rounded-md px-3 py-1.5 hover:bg-gray-50">
          <SlidersHorizontal size={13} /> Filtres
        </button>
      </div>

      {/* Grid */}
      {dayKeys.length === 0 ? (
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
            >Lancer une génération</button>
          )}
        </div>
      ) : (
        <>
          <div style={{ overflowX: 'auto', padding: '16px' }}>
            {/* Day column headers */}
            <div style={{ display: 'grid', gridTemplateColumns: `140px repeat(${dayKeys.length}, minmax(160px, 1fr))`, gap: '8px', marginBottom: '8px' }}>
              <div />
              {dayKeys.map(day => (
                <div key={day} style={{ textAlign: 'center', padding: '8px', background: '#f8fafc', borderRadius: '6px', border: '0.5px solid #e2e8f0' }}>
                  <p style={{ margin: 0, fontSize: '11px', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                    {new Date(`${day}T00:00:00`).toLocaleDateString('fr-FR', { weekday: 'short' })}
                  </p>
                  <p style={{ margin: 0, fontSize: '14px', fontWeight: 600, color: '#0f172a' }}>
                    {new Date(`${day}T00:00:00`).toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit' })}
                  </p>
                </div>
              ))}
            </div>

            {/* Morning row */}
            <div style={{ display: 'grid', gridTemplateColumns: `140px repeat(${dayKeys.length}, minmax(160px, 1fr))`, gap: '8px', marginBottom: '8px' }}>
              <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'flex-start', padding: '12px 8px', background: '#eff6ff', borderRadius: '6px', border: '0.5px solid #bfdbfe' }}>
                <p style={{ margin: 0, fontSize: '11px', fontWeight: 600, color: '#1e40af' }}>☀ Matin</p>
                <p style={{ margin: 0, fontSize: '10px', color: '#3b82f6', marginTop: '2px' }}>08:00–12:00</p>
              </div>
              {dayKeys.map(day => (
                <div key={day} style={{ background: '#f8fafc', borderRadius: '6px', border: '0.5px solid #e2e8f0', padding: '8px', minHeight: '80px' }}>
                  {(groupedCalendar[day]?.morning || []).map(slot => (
                    <SlotGroup key={`${slot.start}-${slot.end}`} slot={slot} />
                  ))}
                </div>
              ))}
            </div>

            {/* Afternoon row */}
            <div style={{ display: 'grid', gridTemplateColumns: `140px repeat(${dayKeys.length}, minmax(160px, 1fr))`, gap: '8px' }}>
              <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'flex-start', padding: '12px 8px', background: '#faf5ff', borderRadius: '6px', border: '0.5px solid #e9d5ff' }}>
                <p style={{ margin: 0, fontSize: '11px', fontWeight: 600, color: '#6b21a8' }}>🌤 Après-midi</p>
                <p style={{ margin: 0, fontSize: '10px', color: '#7c3aed', marginTop: '2px' }}>13:00–17:00</p>
              </div>
              {dayKeys.map(day => (
                <div key={day} style={{ background: '#f8fafc', borderRadius: '6px', border: '0.5px solid #e2e8f0', padding: '8px', minHeight: '80px' }}>
                  {(groupedCalendar[day]?.afternoon || []).map(slot => (
                    <SlotGroup key={`${slot.start}-${slot.end}`} slot={slot} />
                  ))}
                </div>
              ))}
            </div>
          </div>

          {/* Legend */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px', padding: '12px 20px', borderTop: '0.5px solid #e2e8f0' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <div style={{ width: '10px', height: '10px', borderRadius: '2px', background: '#eff6ff', border: '1px solid #bfdbfe' }} />
              <span style={{ fontSize: '11px', color: '#64748b' }}>Matin</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <div style={{ width: '10px', height: '10px', borderRadius: '2px', background: '#faf5ff', border: '1px solid #e9d5ff' }} />
              <span style={{ fontSize: '11px', color: '#64748b' }}>Après-midi</span>
            </div>
            <span style={{ fontSize: '11px', color: '#cbd5e1', marginLeft: 'auto' }}>
              {events.length} soutenance{events.length !== 1 ? 's' : ''} affichée{events.length !== 1 ? 's' : ''}
            </span>
          </div>
        </>
      )}
    </div>
  )
}
