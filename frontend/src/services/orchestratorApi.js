const ORCHESTRATOR_URL = (
  import.meta.env.VITE_ORCHESTRATOR_URL || 'http://localhost:8011'
).replace(/\/$/, '')

async function orcFetch(path, options = {}) {
  const { method = 'GET', body } = options
  const headers = {}
  let bodyData

  if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
    bodyData = JSON.stringify(body)
  }

  const res = await fetch(`${ORCHESTRATOR_URL}${path}`, { method, headers, body: bodyData })

  if (!res.ok) {
    let detail = `Erreur orchestrateur ${res.status}`
    try {
      const json = await res.json()
      detail = json?.detail || JSON.stringify(json) || detail
    } catch {
      detail = (await res.text()) || detail
    }
    throw new Error(detail)
  }

  return res.json()
}

// POST /workflows/schedule → { request_id, status }
export function scheduleWorkflow(prompt, userId = null, oldSolverResult = null, requestedRoute = null) {
  return orcFetch('/workflows/schedule', {
    method: 'POST',
    body: { prompt, user_id: userId, old_solver_result: oldSolverResult, requested_route: requestedRoute },
  })
}

// GET /workflows/:id/status → { request_id, final_status, current_node, node_history, errors, ... }
export function getWorkflowStatus(requestId) {
  return orcFetch(`/workflows/${requestId}/status`)
}

// GET /workflows/:id/result → full SchedulingState
export function getWorkflowResult(requestId) {
  return orcFetch(`/workflows/${requestId}/result`)
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

// Enrich solver assignments with professor names, student names, room, and project title
// by looking them up in db_snapshot (which is part of the workflow state returned by /result).
export function enrichSolverResult(workflowState) {
  const { db_snapshot, solver_result } = workflowState || {}
  if (!solver_result?.assignments?.length || !db_snapshot) return workflowState

  const slotMap = new Map((db_snapshot.sessions || []).map(s => [s.id, s]))
  const profMap = new Map((db_snapshot.professors || []).map(p => [p.id, p]))
  const projMap = new Map((db_snapshot.projects || []).map(p => [p.id, p]))

  const enrichedAssignments = solver_result.assignments.map(a => {
    const slot      = slotMap.get(a.session_id)
    const project   = projMap.get(a.project_id)
    const president = profMap.get(a.roles?.president)
    const examiner  = profMap.get(a.roles?.examiner)
    const supervisor = profMap.get(a.roles?.supervisor)
    return {
      ...a,
      room:             slot?.room            ?? '2B6-4',
      president_id:     a.roles?.president    ?? null,
      examiner_id:      a.roles?.examiner     ?? null,
      supervisor_id:    a.roles?.supervisor   ?? null,
      president_name:   president?.name       ?? null,
      examiner_name:    examiner?.name        ?? null,
      supervisor_name:  supervisor?.name      ?? null,
      project_title:    project?.title        ?? null,
      student_name:     project?.student_name ?? null,
    }
  })

  return {
    ...workflowState,
    solver_result: { ...solver_result, assignments: enrichedAssignments },
  }
}

// Polls every 2 s until final_status !== 'running', then returns the full result.
// onStatus(statusPayload) is called on each poll tick.
// Pass an AbortSignal to cancel.
export async function pollUntilDone(requestId, onStatus, signal) {
  while (true) {
    if (signal?.aborted) throw new DOMException('Polling aborted', 'AbortError')

    const status = await getWorkflowStatus(requestId)
    console.log('[orchestratorApi] poll tick:', status?.final_status, '— node:', status?.current_node)
    onStatus(status)

    if (status.final_status !== 'running') {
      const result = await getWorkflowResult(requestId)
      console.group('[orchestratorApi] final result')
      console.log('full result:', result)
      console.log('top-level keys:', Object.keys(result || {}))
      console.log('solver_result:', result?.solver_result)
      console.log('solver_result keys:', Object.keys(result?.solver_result || {}))
      console.log('solutions array:', result?.solver_result?.solutions)
      console.groupEnd()
      return result
    }

    await sleep(2000)
    if (signal?.aborted) throw new DOMException('Polling aborted', 'AbortError')
  }
}
