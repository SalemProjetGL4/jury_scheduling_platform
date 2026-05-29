import { useEffect, useMemo, useState } from 'react'
import { Activity, AlertTriangle, CheckCircle2, Circle, Clock, Server } from 'lucide-react'
import { useWorkflow } from '../context/WorkflowContext'
import { getServiceHealth } from '../services/orchestratorApi'

const AGENTS = [
  {
    key: 'translator',
    label: 'Translator',
    summary: 'Interprete les contraintes et construit le payload.',
    serviceKey: 'translator',
  },
  {
    key: 'orchestrator',
    label: 'Orchestrator',
    summary: 'Applique le routage demande par le client.',
    serviceKey: 'orchestrator',
  },
  {
    key: 'solver',
    label: 'Solver',
    summary: 'Calcule les solutions et le statut global.',
    serviceKey: 'solver',
  },
  {
    key: 'reflector',
    label: 'Reflector',
    summary: 'Analyse la qualite des solutions.',
    serviceKey: 'reflector',
  },
  {
    key: 'translator_refine',
    label: 'Translator Refine',
    summary: 'Refine les contraintes selon les suggestions.',
    serviceKey: 'translator',
  },
  {
    key: 'solver_refine',
    label: 'Solver Refine',
    summary: 'Relance le solveur avec contraintes refinees.',
    serviceKey: 'solver',
  },
  {
    key: 'updater',
    label: 'Updater',
    summary: 'Applique les modifications sur une solution existante.',
    serviceKey: 'updater',
  },
]

function statusTone(status) {
  if (status === 'success') return { label: 'OK', color: 'bg-emerald-100 text-emerald-700 border-emerald-200' }
  if (status === 'failed') return { label: 'Erreur', color: 'bg-rose-100 text-rose-700 border-rose-200' }
  if (status === 'running') return { label: 'En cours', color: 'bg-blue-100 text-blue-700 border-blue-200' }
  return { label: 'Inactif', color: 'bg-gray-100 text-gray-600 border-gray-200' }
}

function serviceTone(status) {
  if (status === 'ok') return { label: 'Up', color: 'bg-emerald-100 text-emerald-700 border-emerald-200' }
  if (status === 'down') return { label: 'Down', color: 'bg-rose-100 text-rose-700 border-rose-200' }
  return { label: 'Unknown', color: 'bg-gray-100 text-gray-600 border-gray-200' }
}

function formatTime(value) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export default function Monitoring() {
  const { result: workflowResult, status: workflowStatus } = useWorkflow()
  const [serviceHealth, setServiceHealth] = useState(null)
  const [healthError, setHealthError] = useState('')

  useEffect(() => {
    let active = true

    async function loadHealth() {
      try {
        const data = await getServiceHealth()
        if (!active) return
        setServiceHealth(data)
        setHealthError('')
      } catch (err) {
        if (!active) return
        setHealthError(err.message || 'Impossible de charger le statut des services')
      }
    }

    loadHealth()
    const timer = setInterval(loadHealth, 10000)

    return () => {
      active = false
      clearInterval(timer)
    }
  }, [])

  const liveStatus = workflowStatus?.final_status === 'running' ? workflowStatus : null
  const activePayload = liveStatus || workflowResult

  const history = activePayload?.node_history || []
  const lastStatus = activePayload?.final_status || '—'
  const route = activePayload?.route || '—'
  const requestId = activePayload?.request_id || '—'
  const currentNode = activePayload?.current_node || null

  const historyByNode = useMemo(() => {
    const map = new Map()
    history.forEach(entry => {
      if (!entry?.node) return
      map.set(entry.node, entry)
    })
    return map
  }, [history])

  const errorList = activePayload?.errors || []

  function resolveStatus(entry, nodeKey) {
    if (entry?.status) return entry.status
    if (currentNode === nodeKey && lastStatus === 'running') return 'running'
    return 'pending'
  }

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-slate-200 overflow-hidden">
        <div className="bg-gradient-to-br from-slate-900 via-slate-800 to-slate-700 px-6 py-5 text-white">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.2em] text-slate-300">Monitoring agents</p>
              <h2 className="text-2xl font-semibold" style={{ fontFamily: 'Space Grotesk, ui-sans-serif, system-ui' }}>
                Supervision du workflow
              </h2>
            </div>
            <div className="flex items-center gap-2">
              <Server size={18} className="text-slate-300" />
              <span className="text-xs text-slate-300">Derniere exection</span>
            </div>
          </div>
          <div className="mt-4 grid grid-cols-3 gap-3">
            {[
              { label: 'Request ID', value: requestId },
              { label: 'Route', value: route },
              { label: 'Statut final', value: lastStatus },
            ].map(item => (
              <div key={item.label} className="rounded-xl bg-white/10 border border-white/10 px-4 py-3">
                <p className="text-[11px] uppercase tracking-wide text-slate-300">{item.label}</p>
                <p className="text-sm font-semibold text-white break-all">{item.value}</p>
              </div>
            ))}
          </div>
        </div>
        <div className="bg-white px-6 py-4 text-sm text-slate-600">
          {activePayload
            ? 'Les agents ci-dessous reprennent le statut du dernier workflow orchestre.'
            : 'Aucune execution en memoire. Lancez une generation pour alimenter le monitoring.'}
        </div>
      </section>

      <section className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {AGENTS.map(agent => {
          const entry = historyByNode.get(agent.key)
          const tone = statusTone(resolveStatus(entry, agent.key))
          const svcStatus = serviceHealth?.[agent.serviceKey]?.status
          const svcTone = serviceTone(svcStatus)
          return (
            <div key={agent.key} className="bg-white rounded-2xl border border-slate-200 px-5 py-4 shadow-sm">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h3 className="text-sm font-semibold text-slate-900">{agent.label}</h3>
                  <p className="text-xs text-slate-500 mt-1">{agent.summary}</p>
                </div>
                <div className="flex flex-col items-end gap-1">
                  <span className={`text-[11px] uppercase tracking-wide border px-2 py-1 rounded-full ${tone.color}`}>
                    {tone.label}
                  </span>
                  <span className={`text-[10px] uppercase tracking-wide border px-2 py-1 rounded-full ${svcTone.color}`}>
                    {svcTone.label}
                  </span>
                </div>
              </div>
              <div className="mt-4 space-y-2 text-xs text-slate-600">
                <div className="flex items-center justify-between">
                  <span>Debut</span>
                  <span className="font-medium text-slate-800">{formatTime(entry?.started_at)}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>Fin</span>
                  <span className="font-medium text-slate-800">{formatTime(entry?.ended_at)}</span>
                </div>
                <div className="flex items-center gap-2 text-[11px] text-slate-500">
                  <Activity size={12} />
                  {entry?.summary || 'Aucune information disponible'}
                </div>
              </div>
            </div>
          )
        })}
      </section>

      <section className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-white rounded-2xl border border-slate-200 p-5">
          <div className="flex items-center gap-2 mb-4">
            <Clock size={16} className="text-slate-500" />
            <h3 className="text-sm font-semibold text-slate-900">Chronologie des noeuds</h3>
          </div>
          {history.length === 0 ? (
            <p className="text-xs text-slate-500">Aucune trace disponible pour le moment.</p>
          ) : (
            <div className="space-y-3">
              {history.map((entry, idx) => {
                const icon = entry.status === 'success'
                  ? <CheckCircle2 size={14} className="text-emerald-500" />
                  : entry.status === 'failed'
                    ? <AlertTriangle size={14} className="text-rose-500" />
                    : <Circle size={12} className="text-blue-500" />
                return (
                  <div key={`${entry.node}-${idx}`} className="flex items-start gap-3">
                    <div className="mt-0.5">{icon}</div>
                    <div className="flex-1">
                      <div className="flex items-center justify-between">
                        <p className="text-xs font-semibold text-slate-900">{entry.node}</p>
                        <p className="text-[11px] text-slate-500">
                          {formatTime(entry.started_at)} → {formatTime(entry.ended_at)}
                        </p>
                      </div>
                      {entry.summary && (
                        <p className="text-[11px] text-slate-500 mt-1">{entry.summary}</p>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        <div className="bg-white rounded-2xl border border-slate-200 p-5">
          <div className="flex items-center gap-2 mb-4">
            <AlertTriangle size={16} className="text-amber-500" />
            <h3 className="text-sm font-semibold text-slate-900">Alertes et erreurs</h3>
          </div>
          {healthError && (
            <div className="text-xs text-amber-700 bg-amber-50 border border-amber-100 rounded-lg px-3 py-2 mb-3">
              {healthError}
            </div>
          )}
          {errorList.length === 0 ? (
            <p className="text-xs text-slate-500">Aucune alerte detectee.</p>
          ) : (
            <ul className="space-y-2">
              {errorList.map((err, idx) => (
                <li key={`${idx}-${err}`} className="text-xs text-rose-700 bg-rose-50 border border-rose-100 rounded-lg px-3 py-2">
                  {err}
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
    </div>
  )
}
