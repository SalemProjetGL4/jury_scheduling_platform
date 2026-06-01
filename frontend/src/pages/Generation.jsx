import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { CheckCircle2, Circle, Loader2, XCircle } from 'lucide-react'
import { scheduleWorkflow, pollUntilDone, enrichSolverResult } from '../services/orchestratorApi'
import { apiRequest } from '../services/api'
import { useWorkflow } from '../context/WorkflowContext'

const WIZARD_STEPS = [
  { n: 1, label: 'Données',              sub: 'Importées'            },
  { n: 2, label: 'Contraintes',          sub: 'Définies'             },
  { n: 3, label: 'Prompt (optionnel)',   sub: 'Décrire votre demande' },
  { n: 4, label: 'Lancer la génération', sub: 'Optimiser et générer'  },
]

const NODE_LABELS = {
  translator:   'Traduction des contraintes',
  orchestrator: 'Analyse de la demande',
  solver:       'Résolution (OR-Tools)',
  updater:      'Mise a jour des donnees',
  reflector:    'Analyse de qualite',
}

// Canonical execution order per route
const ROUTE_SEQUENCES = {
  EDIT:     ['translator', 'orchestrator', 'updater'],
  GENERATE: ['translator', 'orchestrator', 'solver', 'reflector'],
  default:  ['translator', 'orchestrator'], // route not yet determined — show only common steps
}

// Build the display node list in chronological (execution) order.
// Nodes that actually ran come first (in history order), then expected
// future nodes for the inferred route.
function buildDisplayNodes(nodeHistory, currentNode, hintRoute = null) {
  const ranKeys = new Set([
    ...nodeHistory.map(e => e.node).filter(k => NODE_LABELS[k]),
    ...(currentNode && NODE_LABELS[currentNode] ? [currentNode] : []),
  ])

  const isEdit     = ranKeys.has('updater')
  const isGenerate = ranKeys.has('solver') || ranKeys.has('reflector')
  const sequence   = isEdit ? ROUTE_SEQUENCES.EDIT
                   : isGenerate ? ROUTE_SEQUENCES.GENERATE
                   : (hintRoute && ROUTE_SEQUENCES[hintRoute]) ? ROUTE_SEQUENCES[hintRoute]
                   : ROUTE_SEQUENCES.default

  const seen    = new Set()
  const ordered = []

  // 1. Nodes in history order
  for (const entry of nodeHistory) {
    if (NODE_LABELS[entry.node] && !seen.has(entry.node)) {
      seen.add(entry.node)
      ordered.push(entry.node)
    }
  }
  // 2. Currently running node (if not yet in history)
  if (currentNode && NODE_LABELS[currentNode] && !seen.has(currentNode)) {
    seen.add(currentNode)
    ordered.push(currentNode)
  }
  // 3. Expected future nodes (pending)
  for (const key of sequence) {
    if (!seen.has(key)) ordered.push(key)
  }

  return ordered.map(key => ({ key, label: NODE_LABELS[key] }))
}

const SUGGESTIONS = [
  'Éviter les conflits',
  'Équilibrer la charge',
  'Privilégier certaines salles',
  'Limiter les soutenances après 16h',
]

function nodeStatus(nodeName, nodeHistory, currentNode) {
  const entry = [...nodeHistory].reverse().find(e => e.node === nodeName)
  if (!entry) return currentNode === nodeName ? 'running' : 'pending'
  if (entry.status === 'success') return 'success'
  if (entry.status === 'failed') return 'failed'
  return 'running'
}

function parseIsoMs(value) {
  if (!value) return null
  const ms = Date.parse(value)
  return Number.isNaN(ms) ? null : ms
}

function formatDuration(ms, live = false) {
  if (ms == null) return '—'
  const totalSeconds = Math.max(0, Math.floor(ms / 1000))
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  if (live) return `${minutes > 0 ? `${minutes}:` : ''}${String(seconds).padStart(minutes > 0 ? 2 : 1, '0')}s`
  if (minutes > 0) return `${minutes}m ${seconds}s`
  return `${seconds}s`
}

function findNodeEntry(nodeHistory, nodeName) {
  return [...nodeHistory].reverse().find(e => e.node === nodeName)
}

function computePipelineMeta(nodeHistory, currentNode, displayNodes) {
  const pipelineKeys = new Set(displayNodes.map(n => n.key))
  const relevant = nodeHistory.filter(e => pipelineKeys.has(e.node))
  const completed = relevant.filter(e => e.started_at && e.ended_at)

  const completedDurations = completed
    .map(e => {
      const startMs = parseIsoMs(e.started_at)
      const endMs = parseIsoMs(e.ended_at)
      return startMs && endMs ? Math.max(0, endMs - startMs) : null
    })
    .filter(ms => ms != null)

  const avgMs = completedDurations.length
    ? completedDurations.reduce((sum, ms) => sum + ms, 0) / completedDurations.length
    : null

  const startedMs = relevant.map(e => parseIsoMs(e.started_at)).filter(Boolean)
  const endedMs = relevant.map(e => parseIsoMs(e.ended_at)).filter(Boolean)
  let elapsedMs = null
  if (startedMs.length) {
    const start = Math.min(...startedMs)
    const currentEntry = currentNode ? findNodeEntry(relevant, currentNode) : null
    const runningEnd = currentEntry && !currentEntry.ended_at
      ? Date.now()
      : (endedMs.length ? Math.max(...endedMs) : Date.now())
    elapsedMs = Math.max(0, runningEnd - start)
  }

  const totalEstimatedMs = avgMs ? avgMs * displayNodes.length : null
  const etaMs = totalEstimatedMs != null && elapsedMs != null
    ? Math.max(0, totalEstimatedMs - elapsedMs)
    : null

  const currentIndex = displayNodes.findIndex(n => n.key === currentNode)
  const lastCompleted = completed.length ? completed[completed.length - 1] : null
  const stepKey = currentIndex >= 0 ? currentNode : lastCompleted?.node
  const stepIndex = displayNodes.findIndex(n => n.key === stepKey)
  const total = displayNodes.length
  const stepLabel = stepIndex >= 0
    ? `Etape ${stepIndex + 1}/${total} — ${displayNodes[stepIndex].label}`
    : `Etape 0/${total}`

  return {
    stepLabel,
    etaLabel: etaMs != null ? formatDuration(etaMs) : '—',
    elapsedLabel: elapsedMs != null ? formatDuration(elapsedMs) : '—',
  }
}

export default function Generation() {
  const navigate = useNavigate()
  const { result: workflowResult, saveResult, clearResult, saveStatus, clearStatus, saveSessionId } = useWorkflow()

  const [prompt, setPrompt] = useState('')
  const [phase, setPhase] = useState('idle') // idle | running | done | error
  const [statusPayload, setStatusPayload] = useState(null)
  const [error, setError] = useState('')
  const abortRef = useRef(null)
  const [, setTick] = useState(0)

  // Force a re-render every second while running so timers update live
  useEffect(() => {
    if (phase !== 'running') return
    const id = setInterval(() => setTick(t => t + 1), 1000)
    return () => clearInterval(id)
  }, [phase])

  const hasSolution = Boolean(
    workflowResult?.solver_result?.solutions?.length || workflowResult?.solver_result?.assignments?.length,
  )
  const [mode, setMode] = useState(hasSolution ? 'edit' : 'new')
  const [sessions, setSessions] = useState([])
  const [selectedSessionId, setSelectedSessionId] = useState('')
  const [loadingSessions, setLoadingSessions] = useState(false)

  useEffect(() => {
    if (!hasSolution && mode === 'edit') setMode('new')
  }, [hasSolution, mode])

  useEffect(() => {
    async function fetchSessions() {
      setLoadingSessions(true)
      try {
        const data = await apiRequest('/sessions?limit=200')
        if (Array.isArray(data) && data.length > 0) {
          const sorted = [...data].sort((a, b) => new Date(b.start_date) - new Date(a.start_date))
          setSessions(sorted)
          const firstId = sorted[0]?.id
          setSelectedSessionId(firstId != null ? String(firstId) : '')
        } else {
          setSessions([])
          setSelectedSessionId('')
        }
      } catch { setSessions([]); setSelectedSessionId('') } finally { setLoadingSessions(false) }
    }
    fetchSessions()
  }, [])

  async function handleLaunch() {
    const sessionId = parseInt(selectedSessionId, 10)
    if (!selectedSessionId || isNaN(sessionId) || sessionId <= 0) {
      setError("Veuillez sélectionner une session valide avant de lancer la génération.")
      return
    }
    if (!prompt.trim()) return
    setError('')
    setPhase('running')
    setStatusPayload(null)
    const oldSolverResult = hasSolution && mode === 'edit'
      ? workflowResult?.solver_result
      : null
    saveSessionId(selectedSessionId)
    clearResult()   // wipe the previous result so Results page never shows stale data
    clearStatus()

    const controller = new AbortController()
    abortRef.current = controller

    try {
      const { request_id } = await scheduleWorkflow(
        prompt.trim(),
        null,
        oldSolverResult,
        requestedRoute,
        sessionId,
      )

      const result = await pollUntilDone(
        request_id,
        (status) => { setStatusPayload(status); saveStatus(status) },
        controller.signal,
      )

      saveResult(enrichSolverResult(result))
      setPhase('done')
      setTimeout(() => { navigate('/resultats'); setPhase('idle') }, 600)
    } catch (err) {
      if (err.name === 'AbortError') return
      setError(err.message || 'Impossible de lancer la génération')
      setPhase('error')
    }
  }

  function handleCancel() {
    abortRef.current?.abort()
    setPhase('idle')
    setStatusPayload(null)
  }

  const nodeHistory = statusPayload?.node_history || []
  const currentNode = statusPayload?.current_node || ''
  const finalStatus = statusPayload?.final_status || 'running'
  const requestedRoute = hasSolution && mode === 'edit' ? 'EDIT' : 'GENERATE'
  const displayNodes = buildDisplayNodes(nodeHistory, currentNode, requestedRoute)
  const pipelineMeta = computePipelineMeta(nodeHistory, currentNode, displayNodes)

  return (
    <div className="flex gap-6 items-start">
      {/* Left: wizard steps */}
      <div className="w-56 flex-shrink-0 bg-white rounded-xl border border-gray-200 p-5">
        <div className="space-y-4">
          {WIZARD_STEPS.map((s) => {
            const isActive = s.n === 3
            const isDone = s.n < 3
            return (
              <div key={s.n} className="flex items-start gap-3">
                <div className="flex flex-col items-center">
                  {isDone
                    ? <CheckCircle2 size={20} className="text-green-500 mt-0.5" />
                    : isActive
                      ? <div className="w-5 h-5 rounded-full bg-blue-600 flex items-center justify-center mt-0.5">
                          <span className="text-white text-[10px] font-bold">{s.n}</span>
                        </div>
                      : <Circle size={20} className="text-gray-300 mt-0.5" />}
                  {s.n < WIZARD_STEPS.length && (
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

      {/* Right: content */}
      <div className="flex-1 bg-white rounded-xl border border-gray-200 p-6 space-y-5">
        <div>
          <h2 className="text-base font-semibold text-gray-900 mb-1">
            Décrivez votre demande (en langage naturel)
          </h2>
          <p className="text-sm text-gray-500">
            Indiquez ce que vous souhaitez changer ou améliorer dans la répartition.
          </p>
        </div>

        {hasSolution && (
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-500">Mode :</span>
            <button
              type="button"
              onClick={() => setMode('edit')}
              disabled={phase === 'running'}
              className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
                mode === 'edit'
                  ? 'bg-blue-600 text-white border-blue-600'
                  : 'text-gray-600 border-gray-300 hover:bg-gray-50'
              } ${phase === 'running' ? 'opacity-50' : ''}`}
            >
              Modifier la solution
            </button>
            <button
              type="button"
              onClick={() => setMode('new')}
              disabled={phase === 'running'}
              className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
                mode === 'new'
                  ? 'bg-blue-600 text-white border-blue-600'
                  : 'text-gray-600 border-gray-300 hover:bg-gray-50'
              } ${phase === 'running' ? 'opacity-50' : ''}`}
            >
              Nouvelle génération
            </button>
          </div>
        )}

        {/* Session selector */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Session à planifier</label>
          {loadingSessions ? (
            <div className="flex items-center gap-2 text-sm text-gray-500">
              <Loader2 size={14} className="animate-spin" /> Chargement…
            </div>
          ) : sessions.length === 0 ? (
            <p className="text-sm text-amber-600 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
              Aucune session disponible. Créez d'abord une session dans l'onglet Données.
            </p>
          ) : (
            <select
              value={selectedSessionId}
              onChange={e => setSelectedSessionId(e.target.value)}
              disabled={phase === 'running' || phase === 'done'}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-400 disabled:opacity-60 disabled:bg-gray-50"
            >
              {sessions.map(s => (
                <option key={s.id} value={String(s.id)}>
                  Session {s.id} — {s.start_date} → {s.end_date} ({s.status})
                </option>
              ))}
            </select>
          )}
        </div>

        <textarea
          rows={5}
          value={prompt}
          onChange={e => setPrompt(e.target.value)}
          disabled={phase === 'running'}
          placeholder={
            "Éviter que les soutenances de l'encadrant Amine Benali soient le même jour.\n" +
            'Privilégier la salle A pour les soutenances du jury 1.\n' +
            'Limiter les soutenances après 16h.'
          }
          className="w-full border border-gray-300 rounded-lg px-4 py-3 text-sm text-gray-700 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-400 resize-none disabled:opacity-60"
        />

        {/* Suggestions */}
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs text-gray-500">Suggestions :</span>
          {SUGGESTIONS.map(s => (
            <button
              key={s}
              disabled={phase === 'running'}
              onClick={() => setPrompt(p => p ? `${p}\n${s}` : s)}
              className="text-xs border border-gray-300 rounded-full px-3 py-1 hover:bg-gray-50 text-gray-600 disabled:opacity-40"
            >
              {s}
            </button>
          ))}
        </div>

        {/* Pipeline progress (visible while running or after) */}
        {phase !== 'idle' && (
          <div className="border border-gray-200 rounded-xl p-4 bg-gray-50">
            <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                Pipeline en cours
              </p>
              <div className="flex items-center gap-3 text-[11px] text-gray-500">
                <span>{pipelineMeta.stepLabel}</span>
                <span className="text-gray-300">•</span>
                <span>ETA ~ {pipelineMeta.etaLabel}</span>
                <span className="text-gray-300">•</span>
                <span>Ecoule {pipelineMeta.elapsedLabel}</span>
              </div>
            </div>
            <div className="space-y-2">
              {displayNodes.map(node => {
                const st = nodeStatus(node.key, nodeHistory, currentNode)
                const entry = findNodeEntry(nodeHistory, node.key)
                const startMs = parseIsoMs(entry?.started_at)
                const endMs = parseIsoMs(entry?.ended_at)
                const durationMs = startMs && endMs ? Math.max(0, endMs - startMs) : null
                const runningElapsed = st === 'running' && startMs ? Date.now() - startMs : null
                const statusLabel = st === 'success'
                  ? 'Terminee'
                  : st === 'running'
                    ? 'En cours'
                    : st === 'failed'
                      ? 'Echec'
                      : 'En attente'
                return (
                  <div
                    key={node.key}
                    className={`flex items-center justify-between gap-2.5 rounded-lg px-2 py-1 ${
                      st === 'running'
                        ? 'bg-blue-50 border border-blue-200'
                        : 'border border-transparent'
                    }`}
                  >
                    <div className="flex items-center gap-2.5">
                    {st === 'success' && <CheckCircle2 size={15} className="text-green-500 flex-shrink-0" />}
                    {st === 'running' && <Loader2 size={15} className="text-blue-500 animate-spin flex-shrink-0" />}
                    {st === 'failed'  && <XCircle size={15} className="text-red-400 flex-shrink-0" />}
                    {st === 'pending' && <Circle size={15} className="text-gray-300 flex-shrink-0" />}
                    <span className={`text-xs ${
                      st === 'success' ? 'text-gray-700' :
                      st === 'running' ? 'text-blue-600 font-medium' :
                      st === 'failed'  ? 'text-red-500' :
                      'text-gray-400'
                    }`}>
                      {node.label}
                    </span>
                    </div>
                    <div className="flex items-center gap-2 text-[11px]">
                      <span className={st === 'running' ? 'text-blue-500 font-medium' : 'text-gray-400'}>
                        {statusLabel}
                      </span>
                      <span className="text-gray-300">•</span>
                      <span className={`tabular-nums ${st === 'running' ? 'text-blue-600 font-semibold' : 'text-gray-400'}`}>
                        {st === 'running'
                          ? formatDuration(runningElapsed, true)
                          : formatDuration(durationMs)
                        }
                      </span>
                    </div>
                  </div>
                )
              })}
            </div>

            {phase === 'done' && finalStatus !== 'running' && (
              <p className={`mt-3 text-xs font-medium ${
                finalStatus === 'success' ? 'text-green-600' :
                finalStatus === 'infeasible' ? 'text-amber-600' :
                'text-red-600'
              }`}>
                {finalStatus === 'success'    ? '✓ Génération terminée — redirection…'  :
                 finalStatus === 'infeasible' ? '⚠ Aucune solution trouvée — voir les suggestions du réflecteur' :
                 '✗ Une erreur est survenue'}
              </p>
            )}
          </div>
        )}

        {/* Backend errors */}
        {(error || statusPayload?.errors?.length > 0) && (
          <div className="text-xs text-red-600 bg-red-50 border border-red-100 rounded-lg px-3 py-2">
            {error || statusPayload.errors.join(' · ')}
          </div>
        )}

        {/* Footer */}
        <div className="flex justify-between pt-2">
          <button
            onClick={() => navigate('/contraintes')}
            className="text-sm text-gray-600 border border-gray-300 rounded-lg px-5 py-2 hover:bg-gray-50"
          >
            Précédent
          </button>

          {phase === 'running' ? (
            <button
              onClick={handleCancel}
              className="flex items-center gap-2 bg-red-50 hover:bg-red-100 text-red-600 border border-red-200 text-sm font-medium px-5 py-2 rounded-lg"
            >
              Annuler
            </button>
          ) : (
            <button
              onClick={handleLaunch}
              disabled={!prompt.trim() || phase === 'running' || sessions.length === 0 || !selectedSessionId || isNaN(parseInt(selectedSessionId, 10))}
              className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-semibold px-6 py-2 rounded-lg transition-colors"
            >
              {phase === 'running' && <Loader2 size={15} className="animate-spin" />}
              Lancer la génération
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
