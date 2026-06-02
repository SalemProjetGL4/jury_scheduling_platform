import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend,
} from 'recharts'
import { CalendarDays, Download, Star, Lightbulb, AlertTriangle, CheckCircle2 } from 'lucide-react'
import {
  repartitionParJour as mockRepartitionParJour,
  repartitionParSalle as mockRepartitionParSalle,
} from '../data/mockData'
import { apiRequest } from '../services/api'
import { useWorkflow } from '../context/WorkflowContext'
import { ArrowRight } from 'lucide-react'

// ─── helpers ────────────────────────────────────────────────────────────────

function Stars({ n, max = 4 }) {
  return (
    <div className="flex gap-0.5">
      {Array.from({ length: max }).map((_, i) => (
        <Star key={i} size={13}
          className={i < n ? 'text-amber-400 fill-amber-400' : 'text-gray-200 fill-gray-200'} />
      ))}
    </div>
  )
}

const ROOM_COLORS = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#14B8A6']

function fmt(v) {
  if (!v) return ''
  const d = new Date(`${v}T00:00:00`)
  return d.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit' })
}

function countConflicts(assignments) {
  const bySlot = new Map()
  assignments.forEach(a => {
    const list = bySlot.get(a.slot_id) || []; list.push(a); bySlot.set(a.slot_id, list)
  })
  let n = 0
  bySlot.forEach(list => {
    const seen = new Map()
    list.forEach(a => {
      ;[a.examiner_id, a.president_id].forEach(id => {
        if (!id) return
        const c = (seen.get(id) || 0) + 1
        if (c > 1) n++
        seen.set(id, c)
      })
    })
  })
  return n
}

function buildSolutionsFromDB(sessions, slots, assignments) {
  const slotsBySession = new Map()
  slots.forEach(s => { const l = slotsBySession.get(s.session_id) || []; l.push(s); slotsBySession.set(s.session_id, l) })
  const aBySlot = new Map()
  assignments.forEach(a => { const l = aBySlot.get(a.slot_id) || []; l.push(a); aBySlot.set(a.slot_id, l) })

  const derived = sessions.map(session => {
    const ss = slotsBySession.get(session.id) || []
    const aa = ss.flatMap(s => aBySlot.get(s.id) || [])
    const conflicts = countConflicts(aa)
    const score = aa.length ? Math.max(0, 100 - conflicts * 5) : 0
    return {
      id: session.id, label: `#${session.id}`, score, stars: Math.min(4, Math.round(score / 25)),
      conflits: conflicts, jours: new Set(ss.map(s => s.date)).size,
      soutenances: aa.length,
      recommended: false, date: session.start_date,
    }
  })
  if (derived.length) {
    const best = derived.reduce((a, b) => b.score > a.score ? b : a)
    derived.forEach(d => { d.recommended = d.id === best.id })
  }
  return derived
}

function buildChartsFromDB(sessionId, slots, assignments) {
  const slotsById = new Map(slots.map(s => [s.id, s]))
  const ss = slots.filter(s => s.session_id === sessionId)
  const ids = new Set(ss.map(s => s.id))
  const aa = assignments.filter(a => ids.has(a.slot_id))
  const byDate = new Map(), byRoom = new Map()
  aa.forEach(a => {
    const s = slotsById.get(a.slot_id); if (!s) return
    byDate.set(s.date, (byDate.get(s.date) || 0) + 1)
    byRoom.set(s.room, (byRoom.get(s.room) || 0) + 1)
  })
  return {
    repartitionParJour: Array.from(byDate.entries()).sort().map(([d, v]) => ({ jour: fmt(d), value: v })),
    repartitionParSalle: Array.from(byRoom.entries()).map(([r, v], i) => ({ name: `Salle ${r}`, value: v, color: ROOM_COLORS[i % ROOM_COLORS.length] })),
  }
}

// Parse orchestrator solver_result into display rows
function buildSolutionsFromWorkflow(solverResult, reflectorResult) {
  if (!solverResult) return []
  const { status, solutions, assignments } = solverResult
  const source = solutions?.length ? solutions : (assignments?.length ? [{ solution_index: 1, assignments }] : [])

  const rankedSolutions = reflectorResult?.compromised_solutions || []
  const hasReflectorRanking = rankedSolutions.length > 0

  if (hasReflectorRanking) {
    const baseByIndex = new Map(source.map((sol, i) => [Number(sol.solution_index || i + 1), sol]))
    const recommendedIndex = Number(reflectorResult?.recommended_solution_index || 0)

    return [...rankedSolutions]
      .sort((a, b) => (Number(b.rating) || 0) - (Number(a.rating) || 0) || (Number(a.solution_index) || 0) - (Number(b.solution_index) || 0))
      .map((ranked, i) => {
        const solutionIndex = Number(ranked.solution_index || i + 1)
        const base = baseByIndex.get(solutionIndex) || source[i] || {}
        const aa = base.assignments || []
        const score = Math.max(0, Math.min(100, Math.round(Number(ranked.rating) || 0)))
        const conflits = Number(ranked.violations_count ?? aa.filter(a => a.is_conflict).length ?? 0)
        const explanation = ranked.explanation || (conflits > 0 ? `Reflected score with ${conflits} violation(s).` : 'No reflector explanation available.')

        return {
          id: solutionIndex,
          label: `#${solutionIndex}`,
          score,
          stars: Math.min(4, Math.round(score / 25)),
          conflits,
          jours: new Set(aa.map(a => a.date).filter(Boolean)).size,
          soutenances: aa.length,
          recommended: solutionIndex === recommendedIndex,
          date: null,
          rawAssignments: aa,
          status: reflectorResult?.status || status,
          reflectorStatus: reflectorResult?.status || null,
          reflectorRating: ranked.rating,
          reflectorViolations: ranked.violations_count,
          reflectorTotalPenalty: ranked.total_penalty,
          reflectorExplanation: explanation,
        }
      })
  }

  return source.map((sol, i) => {
    const aa = sol.assignments || []
    const conflicts = aa.filter(a => a.is_conflict).length
    const score = Math.max(0, 100 - conflicts * 5 - (sol.total_penalty || 0) / 10)
    return {
      id: Number(sol.solution_index || i + 1), label: `#${Number(sol.solution_index || i + 1)}`, score: Math.round(score),
      stars: Math.min(4, Math.round(score / 25)),
      conflits: conflicts,
      jours: new Set(aa.map(a => a.date).filter(Boolean)).size,
      soutenances: aa.length,
      recommended: i === (solverResult.recommended_index || solverResult.recommended_solution_index || 0),
      date: null, rawAssignments: aa, status,
    }
  })
}

function buildChartsFromWorkflow(sol) {
  if (!sol?.rawAssignments?.length) return { repartitionParJour: [], repartitionParSalle: [] }
  const byDate = new Map(), bySalle = new Map()
  sol.rawAssignments.forEach(a => {
    if (a.date) byDate.set(a.date, (byDate.get(a.date) || 0) + 1)
    if (a.room) bySalle.set(a.room, (bySalle.get(a.room) || 0) + 1)
  })
  return {
    repartitionParJour: Array.from(byDate.entries()).sort().map(([d, v]) => ({ jour: fmt(d), value: v })),
    repartitionParSalle: Array.from(bySalle.entries()).map(([r, v], i) => ({ name: `Salle ${r}`, value: v, color: ROOM_COLORS[i % ROOM_COLORS.length] })),
  }
}

// ─── Reflector suggestions panel ────────────────────────────────────────────

function ReflectorPanel({ reflectorResult }) {
  if (!reflectorResult) return null
  const { status, summary, relaxation_suggestions = [], compromised_solutions = [] } = reflectorResult

  // LLM failure — show a dismissible soft warning, not a full error panel
  const isLlmError = status === 'INFEASIBLE' && summary?.startsWith('LLM error')
  if (isLlmError) return (
    <div className="flex items-start gap-2 px-4 py-3 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-700">
      <AlertTriangle size={13} className="mt-0.5 flex-shrink-0" />
      <span>L'analyse du réflecteur est indisponible (erreur LLM). Les solutions du solveur restent valides.</span>
    </div>
  )

  const statusColor = {
    OPTIMAL:     'bg-green-50  text-green-700  border-green-200',
    FEASIBLE:    'bg-blue-50   text-blue-700   border-blue-200',
    COMPROMISED: 'bg-amber-50  text-amber-700  border-amber-200',
    INFEASIBLE:  'bg-red-50    text-red-700    border-red-200',
  }[status] || 'bg-gray-50 text-gray-700 border-gray-200'

  const StatusIcon = status === 'OPTIMAL' || status === 'FEASIBLE' ? CheckCircle2 : AlertTriangle

  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
      <div className={`flex items-center gap-2 px-5 py-3 border-b ${statusColor}`}>
        <StatusIcon size={16} />
        <p className="text-sm font-semibold">Analyse du réflecteur — {status}</p>
      </div>

      {summary && (
        <p className="px-5 py-3 text-sm text-gray-600 border-b border-gray-100">{summary}</p>
      )}

      {relaxation_suggestions.length > 0 && (
        <div className="px-5 py-4">
          <div className="flex items-center gap-2 mb-3">
            <Lightbulb size={14} className="text-amber-500" />
            <p className="text-xs font-semibold text-gray-700 uppercase tracking-wide">
              Suggestions de relaxation
            </p>
          </div>
          <ul className="space-y-2.5">
            {relaxation_suggestions.map((s, i) => (
              <li key={i} className="rounded-lg border border-gray-100 bg-gray-50 px-3 py-2.5">
                <p className="text-xs font-semibold text-gray-800">{s.constraint}</p>
                <p className="text-xs text-blue-600 mt-0.5">→ {s.action}</p>
                <p className="text-xs text-gray-500 mt-0.5">{s.reason}</p>
              </li>
            ))}
          </ul>
        </div>
      )}

      {compromised_solutions.length > 0 && (
        <div className="px-5 pb-4">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Violations détectées</p>
          {compromised_solutions.map((c, i) => (
            <div key={i} className="text-xs text-gray-600 border-l-2 border-amber-300 pl-2 mb-1.5">
              <span className="font-medium">Solution {i + 1}</span> — score {c.rating}/100, {c.violations_count} violation(s)
              {c.explanation && <span className="text-gray-400"> · {c.explanation}</span>}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ─── Solution detail panel ───────────────────────────────────────────────────

const DETAIL_TABS = ['Aperçu', 'Calendrier', 'Détails', 'Conflits']

function SolutionDetail({ sol, repartitionParJour, repartitionParSalle, onViewCalendar, onExport }) {
  const [tab, setTab] = useState('Aperçu')
  const navigate = useNavigate()

  return (
    <div className="bg-white rounded-xl border border-gray-200 flex flex-col">
      <div className="px-5 py-4 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-gray-900">Solution {sol.label}</h3>
          <span className="text-sm font-bold text-green-600">Score : {sol.score}%</span>
        </div>
      </div>

      <div className="px-5 py-4 space-y-5">
        <div className="grid grid-cols-3 gap-2">
          {[
            { val: sol.soutenances, lbl: 'Soutenances' },
            { val: sol.jours,       lbl: 'Jours'       },
            { val: sol.conflits,    lbl: 'Conflits'    },
          ].map(({ val, lbl }) => (
            <div key={lbl} className="bg-gray-50 rounded-lg px-2 py-2.5 text-center">
              <p className="text-base font-bold text-gray-900">{val}</p>
              <p className="text-[10px] text-gray-500">{lbl}</p>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <p className="text-xs font-semibold text-gray-600 mb-2">Répartition par jour</p>
            <ResponsiveContainer width="100%" height={100}>
              <BarChart data={repartitionParJour} barSize={14}>
                <XAxis dataKey="jour" tick={{ fontSize: 9 }} axisLine={false} tickLine={false} />
                <YAxis hide />
                <Tooltip contentStyle={{ fontSize: 11 }} />
                <Bar dataKey="value" fill="#3B82F6" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div>
            <p className="text-xs font-semibold text-gray-600 mb-2">Répartition par salle</p>
            <ResponsiveContainer width="100%" height={100}>
              <PieChart>
                <Pie data={repartitionParSalle} cx="50%" cy="50%" innerRadius={24} outerRadius={38} dataKey="value" paddingAngle={2}>
                  {repartitionParSalle.map(e => <Cell key={e.name} fill={e.color} />)}
                </Pie>
                <Legend iconType="circle" iconSize={7} formatter={(v, e) => `${v} (${e.payload.value})`} wrapperStyle={{ fontSize: 9 }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="px-5 py-4 border-t border-gray-100 space-y-2">
        <div className="flex gap-2">
          <button onClick={onViewCalendar}
            className="flex-1 flex items-center justify-center gap-1.5 text-xs border border-gray-300 rounded-lg py-2 hover:bg-gray-50 font-medium">
            <CalendarDays size={13} /> Calendrier
          </button>
          <button onClick={onExport}
            className="flex-1 flex items-center justify-center gap-1.5 text-xs border border-gray-300 rounded-lg py-2 hover:bg-gray-50 font-medium">
            <Download size={13} /> Exporter
          </button>
        </div>
        <button className="w-full bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-lg py-2.5 transition-colors">
          Utiliser cette solution
        </button>
      </div>
    </div>
  )
}

// ─── Debug panel (inline) ────────────────────────────────────────────────────

function DebugPanel({ workflowResult }) {
  const [open, setOpen] = useState(false)
  if (!workflowResult) return null
  return (
    <div className="mt-4 border border-gray-200 rounded-xl overflow-hidden text-[11px] font-mono">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-4 py-2 bg-gray-50 hover:bg-gray-100 text-gray-500 text-left"
      >
        <span>Debug — données du workflow</span>
        <span>{open ? '▲' : '▼'}</span>
      </button>
      {open && (
        <div className="p-4 space-y-2 bg-white overflow-auto max-h-80">
          <div className="grid grid-cols-2 gap-x-6 gap-y-1">
            <span className="text-gray-400">final_status</span>
            <span className="font-semibold">{workflowResult.final_status ?? '—'}</span>
            <span className="text-gray-400">solver_result.status</span>
            <span className={workflowResult.solver_result?.status === 'OPTIMAL' ? 'text-green-600 font-semibold' : 'text-red-500 font-semibold'}>
              {workflowResult.solver_result?.status ?? 'null'}
            </span>
            <span className="text-gray-400">solutions count</span>
            <span>{workflowResult.solver_result?.solutions?.length ?? 'undefined'}</span>
            <span className="text-gray-400">assignments count</span>
            <span>{workflowResult.solver_result?.assignments?.length ?? 'undefined'}</span>
            <span className="text-gray-400">reflector_result.status</span>
            <span>{workflowResult.reflector_result?.status ?? 'null'}</span>
            <span className="text-gray-400">errors</span>
            <span className="text-red-500">{(workflowResult.errors || []).join(' · ') || '—'}</span>
          </div>
          <details className="mt-2">
            <summary className="cursor-pointer text-gray-400 hover:text-gray-700">solver_result JSON</summary>
            <pre className="mt-1 text-[10px] text-gray-600 whitespace-pre-wrap break-all bg-gray-50 p-2 rounded">
              {JSON.stringify(workflowResult.solver_result, null, 2)}
            </pre>
          </details>
        </div>
      )}
    </div>
  )
}

// ─── Main page ───────────────────────────────────────────────────────────────

export default function Resultats() {
  const navigate = useNavigate()
  const { result: workflowResult, saveSelectedSolution } = useWorkflow()

  const [activeTab, setActiveTab]         = useState('Solutions générées')
  const [dbSolutions, setDbSolutions]     = useState([])
  const [slots, setSlots]                 = useState([])
  const [assignments, setAssignments]     = useState([])
  const [loadingDb, setLoadingDb]         = useState(true)
  const [dbError, setDbError]             = useState('')
  const [usingMock, setUsingMock]         = useState(false)

  // ── load from DB as fallback ──
  useEffect(() => {
    let active = true
    async function load() {
      try {
        const [sess, sl, ass] = await Promise.all([
          apiRequest('/sessions?limit=200'),
          apiRequest('/slots?limit=200'),
          apiRequest('/assignments?limit=200'),
        ])
        if (!active) return
        const sessions = Array.isArray(sess) ? sess : []
        const safeSlots = Array.isArray(sl) ? sl : []
        const safeAss = Array.isArray(ass) ? ass : []
        if (sessions.length) {
          const derived = buildSolutionsFromDB(sessions, safeSlots, safeAss)
          if (derived.length) { setDbSolutions(derived); setUsingMock(false) }
          setSlots(safeSlots); setAssignments(safeAss)
        }
        setDbError('')
      } catch (e) {
        if (active) setDbError(e.message)
      } finally {
        if (active) setLoadingDb(false)
      }
    }
    load()
    return () => { active = false }
  }, [])

  // Prefer orchestrator result if present
  const wfSolverResult    = workflowResult?.solver_result
  const wfReflectorResult = workflowResult?.reflector_result
  const wfUpdaterResult   = workflowResult?.updater_result
  const hasWorkflow       = Boolean(wfSolverResult)
  const hasUpdaterFallback = Boolean(wfUpdaterResult?.preserved_original)

  const solutions = useMemo(() => {
    if (hasWorkflow) return buildSolutionsFromWorkflow(wfSolverResult, wfReflectorResult)
    return dbSolutions
  }, [hasWorkflow, wfSolverResult, wfReflectorResult, dbSolutions])

  const [selected, setSelected] = useState(null)
  const effectiveSelected = selected ?? solutions[0] ?? null

  const charts = useMemo(() => {
    if (!effectiveSelected) return { repartitionParJour: mockRepartitionParJour, repartitionParSalle: mockRepartitionParSalle }
    if (hasWorkflow) {
      const c = buildChartsFromWorkflow(effectiveSelected)
      return c.repartitionParJour.length ? c : { repartitionParJour: mockRepartitionParJour, repartitionParSalle: mockRepartitionParSalle }
    }
    if (!usingMock && slots.length) {
      const c = buildChartsFromDB(effectiveSelected.id, slots, assignments)
      return c.repartitionParJour.length ? c : { repartitionParJour: mockRepartitionParJour, repartitionParSalle: mockRepartitionParSalle }
    }
    return { repartitionParJour: mockRepartitionParJour, repartitionParSalle: mockRepartitionParSalle }
  }, [effectiveSelected, hasWorkflow, usingMock, slots, assignments])

  const loading = !hasWorkflow && loadingDb
  const displayWorkflowStatus = wfReflectorResult?.status || wfSolverResult?.status

  return (
    <div className="space-y-4">
    <div className="flex gap-5 items-start">
      {/* Left — table */}
      <div className="flex-1 bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="flex border-b border-gray-200 px-5">
          {['Solutions générées', 'Propositions'].map(t => (
            <button key={t} onClick={() => setActiveTab(t)}
              className={`text-sm font-medium py-3 px-2 mr-4 border-b-2 transition-colors ${activeTab === t ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}>
              {t}
            </button>
          ))}
        </div>

        {/* Workflow origin badge */}
        {hasWorkflow && (
          <div className="px-5 py-2 bg-blue-50 border-b border-blue-100 flex items-center gap-2">
            <CheckCircle2 size={13} className="text-blue-500" />
            <span className="text-xs text-blue-700">
              Résultat de la dernière génération — statut : <strong>{displayWorkflowStatus || '—'}</strong>
            </span>
            <button onClick={() => navigate('/generation')} className="ml-auto text-xs text-blue-600 hover:underline">
              Nouvelle génération
            </button>
          </div>
        )}

        {hasUpdaterFallback && (
          <div className="px-5 py-3 bg-amber-50 border-b border-amber-100">
            <p className="text-sm text-amber-800">Impossible de trouver une nouvelle solution avec ces données.</p>
          </div>
        )}

        {/* Propositions tab — show reflector suggestions */}
        {activeTab === 'Propositions' && (
          <div className="px-5 py-5">
            {!wfReflectorResult ? (
              <div className="text-sm text-gray-400 py-4">
                Aucune suggestion disponible. Lancez une génération pour obtenir l'analyse du réflecteur.
              </div>
            ) : (
              <div className="space-y-4 max-w-2xl">
                {/* Status header */}
                {(() => {
                  const { status, summary, relaxation_suggestions = [], compromised_solutions = [] } = wfReflectorResult
                  const statusColor = {
                    OPTIMAL:     'bg-green-50  text-green-700  border-green-200',
                    FEASIBLE:    'bg-blue-50   text-blue-700   border-blue-200',
                    COMPROMISED: 'bg-amber-50  text-amber-700  border-amber-200',
                    INFEASIBLE:  'bg-red-50    text-red-700    border-red-200',
                  }[status] || 'bg-gray-50 text-gray-700 border-gray-200'
                  const Icon = status === 'OPTIMAL' || status === 'FEASIBLE' ? CheckCircle2 : AlertTriangle
                  return (
                    <>
                      <div className={`flex items-center gap-2 px-4 py-2.5 rounded-lg border text-sm font-semibold ${statusColor}`}>
                        <Icon size={15} />
                        Analyse du réflecteur — {status}
                      </div>
                      {summary && <p className="text-sm text-gray-600">{summary}</p>}
                      {relaxation_suggestions.length > 0 && (
                        <div>
                          <div className="flex items-center gap-2 mb-3">
                            <Lightbulb size={14} className="text-amber-500" />
                            <p className="text-xs font-semibold text-gray-700 uppercase tracking-wide">
                              Suggestions de relaxation ({relaxation_suggestions.length})
                            </p>
                          </div>
                          <ul className="space-y-2.5">
                            {relaxation_suggestions.map((s, i) => (
                              <li key={i} className="rounded-lg border border-gray-100 bg-gray-50 px-4 py-3">
                                <div className="flex items-start gap-2">
                                  <ArrowRight size={13} className="text-blue-400 mt-0.5 flex-shrink-0" />
                                  <div>
                                    <p className="text-xs font-semibold text-gray-800">{s.constraint}</p>
                                    <p className="text-xs text-blue-600 mt-0.5">{s.action}</p>
                                    <p className="text-xs text-gray-500 mt-0.5">{s.reason}</p>
                                  </div>
                                </div>
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                      {compromised_solutions.length > 0 && (
                        <div>
                          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Violations détectées</p>
                          {compromised_solutions.map((c, i) => (
                            <div key={i} className="text-xs text-gray-600 border-l-2 border-amber-300 pl-3 mb-2">
                              <span className="font-medium">Solution {i + 1}</span> — score {c.rating}/100, {c.violations_count} violation(s)
                              {c.explanation && <span className="text-gray-400"> · {c.explanation}</span>}
                            </div>
                          ))}
                        </div>
                      )}
                      {relaxation_suggestions.length === 0 && compromised_solutions.length === 0 && (
                        <p className="text-sm text-green-600">Aucune suggestion — la solution est optimale.</p>
                      )}
                    </>
                  )
                })()}
              </div>
            )}
          </div>
        )}

        {activeTab === 'Solutions générées' && <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead>
            <tr className="border-b border-gray-100 bg-gray-50">
              {['Solution', 'Score', 'Conflits', 'Jours', 'Soutenances', 'Actions'].map(h => (
                <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-gray-500 whitespace-nowrap">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading && <tr><td className="px-4 py-10 text-center text-gray-400" colSpan={6}>Chargement…</td></tr>}
            {!loading && solutions.length === 0 && (() => {
              const solverStatus = wfSolverResult?.status
              const finalStatus  = workflowResult?.final_status
              const failedConstraints = wfSolverResult?.failed_constraints || []
              const wfErrors = workflowResult?.errors || []

              if (solverStatus === 'INFEASIBLE') {
                const relaxSuggestions = wfReflectorResult?.relaxation_suggestions || []
                return (
                <tr>
                  <td colSpan={6}>
                    <div className="px-6 py-8 space-y-4">
                      <div className="flex items-center gap-2 text-red-600">
                        <AlertTriangle size={18} />
                        <p className="text-sm font-semibold">Aucune solution trouvée — contraintes incompatibles</p>
                      </div>
                      <p className="text-xs text-gray-500">
                        Le solveur n'a pas pu satisfaire toutes les contraintes obligatoires.
                        Vérifiez les données ou assouplissez les contraintes.
                      </p>

                      {failedConstraints.length > 0 && (
                        <ul className="space-y-1">
                          {failedConstraints.slice(0, 6).map((fc, i) => (
                            <li key={i} className="text-xs text-red-700 bg-red-50 border border-red-100 rounded px-3 py-1.5">
                              <span className="font-medium">{fc.constraint || fc.rule || 'Contrainte'}</span>
                              {fc.reason && <span className="text-red-500"> — {fc.reason}</span>}
                            </li>
                          ))}
                          {failedConstraints.length > 6 && (
                            <li className="text-xs text-gray-400 pl-1">+ {failedConstraints.length - 6} autre(s)…</li>
                          )}
                        </ul>
                      )}

                      {relaxSuggestions.length > 0 && (
                        <div className="border border-amber-200 bg-amber-50 rounded-lg px-4 py-3 space-y-2">
                          <div className="flex items-center gap-2">
                            <Lightbulb size={14} className="text-amber-500 flex-shrink-0" />
                            <p className="text-xs font-semibold text-amber-800 uppercase tracking-wide">
                              Suggestions pour débloquer le solveur
                            </p>
                          </div>
                          <ul className="space-y-2">
                            {relaxSuggestions.map((s, i) => (
                              <li key={i} className="rounded-md border border-amber-100 bg-white px-3 py-2">
                                <p className="text-xs font-semibold text-gray-800">{s.constraint}</p>
                                <p className="text-xs text-blue-600 mt-0.5">→ {s.action}</p>
                                {s.reason && <p className="text-xs text-gray-500 mt-0.5">{s.reason}</p>}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}

                      <button onClick={() => navigate('/generation')}
                        className="mt-1 text-xs bg-blue-600 hover:bg-blue-700 text-white font-semibold px-4 py-2 rounded-lg transition-colors">
                        Modifier les contraintes et relancer
                      </button>
                    </div>
                  </td>
                </tr>
              )}

              if (finalStatus === 'error' || wfErrors.length > 0) return (
                <tr>
                  <td colSpan={6}>
                    <div className="px-6 py-8 space-y-3">
                      <div className="flex items-center gap-2 text-orange-600">
                        <AlertTriangle size={18} />
                        <p className="text-sm font-semibold">Erreur du pipeline</p>
                      </div>
                      {wfErrors.length > 0 && (
                        <ul className="space-y-1">
                          {wfErrors.map((e, i) => (
                            <li key={i} className="text-xs text-orange-700 bg-orange-50 border border-orange-100 rounded px-3 py-1.5">{e}</li>
                          ))}
                        </ul>
                      )}
                      <button onClick={() => navigate('/generation')}
                        className="mt-1 text-xs bg-blue-600 hover:bg-blue-700 text-white font-semibold px-4 py-2 rounded-lg transition-colors">
                        Relancer la génération
                      </button>
                    </div>
                  </td>
                </tr>
              )

              return (
                <tr>
                  <td colSpan={6}>
                    <div className="flex flex-col items-center justify-center py-12 gap-3">
                      <CalendarDays size={36} className="text-gray-300" />
                      <p className="text-sm font-medium text-gray-500">Aucun résultat disponible</p>
                      <p className="text-xs text-gray-400 text-center max-w-xs">
                        Lancez une génération pour obtenir des solutions de planification optimisées.
                      </p>
                      <button onClick={() => navigate('/generation')}
                        className="mt-1 text-xs bg-blue-600 hover:bg-blue-700 text-white font-semibold px-4 py-2 rounded-lg transition-colors">
                        Lancer une génération
                      </button>
                    </div>
                  </td>
                </tr>
              )
            })()}
            {!loading && solutions.map(sol => (
              <tr key={sol.id} onClick={() => setSelected(sol)}
                className={`border-b border-gray-100 hover:bg-gray-50 cursor-pointer ${effectiveSelected?.id === sol.id ? 'bg-blue-50' : ''}`}>
                <td className="px-4 py-3 font-medium text-gray-900 whitespace-nowrap">
                  {sol.label}
                  {sol.recommended && <span className="ml-1.5 text-[10px] bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded">recommandée</span>}
                </td>
                <td className="px-4 py-3 whitespace-nowrap">
                  <span className="font-semibold text-green-600">{sol.score}%</span>
                </td>
                <td className="px-4 py-3 text-gray-600 whitespace-nowrap">{sol.conflits}</td>
                <td className="px-4 py-3 text-gray-600 whitespace-nowrap">{sol.jours}</td>
                <td className="px-4 py-3 text-gray-600 whitespace-nowrap">{sol.soutenances}</td>

                <td className="px-4 py-3 whitespace-nowrap">
                  <div className="flex gap-1.5">
                    <button
                      onClick={e => { e.stopPropagation(); saveSelectedSolution(sol); navigate('/calendrier') }}
                      className="text-xs border border-gray-300 rounded px-2 py-0.5 hover:bg-gray-50">
                      Calendrier
                    </button>
                    <button
                      onClick={e => { e.stopPropagation(); saveSelectedSolution(sol); navigate('/exports') }}
                      className="text-xs border border-gray-300 rounded px-2 py-0.5 hover:bg-gray-50">
                      Exporter
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>}

        {activeTab === 'Solutions générées' && dbError && (
          <div className="px-5 py-2 text-xs text-amber-600 bg-amber-50 border-t border-amber-100">
            {dbError} — affichage des données de démonstration.
          </div>
        )}

      </div>

      {/* Right — detail + reflector */}
      <div className="w-80 flex-shrink-0 space-y-4">
        {effectiveSelected
          ? <SolutionDetail
              sol={effectiveSelected}
              repartitionParJour={charts.repartitionParJour}
              repartitionParSalle={charts.repartitionParSalle}
              onViewCalendar={() => { saveSelectedSolution(effectiveSelected); navigate('/calendrier') }}
              onExport={() => { saveSelectedSolution(effectiveSelected); navigate('/exports') }}
            />
          : <div className="bg-white rounded-xl border border-gray-200 p-4 text-sm text-gray-400">Aucune solution sélectionnée.</div>
        }
        <ReflectorPanel reflectorResult={wfReflectorResult} />
      </div>
    </div>

    <DebugPanel workflowResult={workflowResult} />
    </div>
  )
}
