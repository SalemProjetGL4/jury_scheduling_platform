import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { CheckCircle2, Circle, Loader2, XCircle } from 'lucide-react'
import { scheduleWorkflow, pollUntilDone, enrichSolverResult } from '../services/orchestratorApi'
import { useWorkflow } from '../context/WorkflowContext'

const WIZARD_STEPS = [
  { n: 1, label: 'Données',              sub: 'Importées'            },
  { n: 2, label: 'Contraintes',          sub: 'Définies'             },
  { n: 3, label: 'Prompt (optionnel)',   sub: 'Décrire votre demande' },
  { n: 4, label: 'Lancer la génération', sub: 'Optimiser et générer'  },
]

const PIPELINE_NODES = [
  { key: 'translator',   label: 'Traduction des contraintes' },
  { key: 'orchestrator', label: 'Analyse de la demande'      },
  { key: 'solver',       label: 'Résolution (OR-Tools)'      },
  { key: 'updater',      label: 'Mise a jour des donnees'    },
  { key: 'reflector',    label: 'Analyse de qualite'         },
]

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

function formatDuration(ms) {
  if (ms == null) return '—'
  const totalSeconds = Math.max(0, Math.round(ms / 1000))
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  if (minutes > 0) return `${minutes}m ${seconds}s`
  return `${seconds}s`
}

function findNodeEntry(nodeHistory, nodeName) {
  return [...nodeHistory].reverse().find(e => e.node === nodeName)
}

function computePipelineMeta(nodeHistory, currentNode) {
  const pipelineKeys = new Set(PIPELINE_NODES.map(n => n.key))
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

  const totalEstimatedMs = avgMs ? avgMs * PIPELINE_NODES.length : null
  const etaMs = totalEstimatedMs != null && elapsedMs != null
    ? Math.max(0, totalEstimatedMs - elapsedMs)
    : null

  const currentIndex = PIPELINE_NODES.findIndex(n => n.key === currentNode)
  const lastCompleted = completed.length ? completed[completed.length - 1] : null
  const stepKey = currentIndex >= 0 ? currentNode : lastCompleted?.node
  const stepIndex = PIPELINE_NODES.findIndex(n => n.key === stepKey)
  const stepLabel = stepIndex >= 0
    ? `Etape ${stepIndex + 1}/${PIPELINE_NODES.length} — ${PIPELINE_NODES[stepIndex].label}`
    : `Etape 0/${PIPELINE_NODES.length}`

  return {
    stepLabel,
    etaLabel: etaMs != null ? formatDuration(etaMs) : '—',
    elapsedLabel: elapsedMs != null ? formatDuration(elapsedMs) : '—',
  }
}

export default function Generation() {
  const navigate = useNavigate()
  const { result: workflowResult, saveResult, clearResult, saveStatus, clearStatus } = useWorkflow()

  const [prompt, setPrompt] = useState('')
  const [phase, setPhase] = useState('idle') // idle | running | done | error
  const [statusPayload, setStatusPayload] = useState(null)
  const [error, setError] = useState('')
  const abortRef = useRef(null)
  const hasSolution = Boolean(
    workflowResult?.solver_result?.solutions?.length || workflowResult?.solver_result?.assignments?.length,
  )
  const [mode, setMode] = useState(hasSolution ? 'edit' : 'new')

  useEffect(() => {
    if (!hasSolution && mode === 'edit') setMode('new')
  }, [hasSolution, mode])

  async function handleLaunch() {
    if (!prompt.trim()) return
    setError('')
    setPhase('running')
    setStatusPayload(null)
    const requestedRoute = hasSolution && mode === 'edit' ? 'EDIT' : 'GENERATE'
    const oldSolverResult = hasSolution && mode === 'edit'
      ? workflowResult?.solver_result
      : null
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
  const pipelineMeta = computePipelineMeta(nodeHistory, currentNode)

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
              {PIPELINE_NODES.map(node => {
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
                    <div className="flex items-center gap-2 text-[11px] text-gray-400">
                      <span>{statusLabel}</span>
                      <span className="text-gray-300">•</span>
                      <span>
                        {st === 'running'
                          ? `~ ${formatDuration(runningElapsed)}`
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
              disabled={!prompt.trim() || phase === 'running'}
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
