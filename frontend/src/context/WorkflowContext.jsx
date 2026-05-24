import { createContext, useContext, useState } from 'react'

const WorkflowContext = createContext(null)

function load(key) {
  try { const raw = localStorage.getItem(key); return raw ? JSON.parse(raw) : null } catch { return null }
}

export function WorkflowProvider({ children }) {
  const [result, setResult] = useState(() => load('juriq_workflow_result'))
  const [selectedSolution, setSelectedSolution] = useState(() => load('juriq_selected_solution'))

  function saveResult(data) {
    console.group('[WorkflowContext] saveResult')
    console.log('raw data:', data)
    console.log('solver_result:', data?.solver_result)
    console.log('reflector_result:', data?.reflector_result)
    console.log('solver_result.solutions:', data?.solver_result?.solutions)
    console.log('solver_result.assignments:', data?.solver_result?.assignments)
    console.groupEnd()
    setResult(data)
    try { localStorage.setItem('juriq_workflow_result', JSON.stringify(data)) } catch { /* quota */ }
  }

  function clearResult() {
    setResult(null)
    try { localStorage.removeItem('juriq_workflow_result') } catch { /* ok */ }
  }

  function saveSelectedSolution(sol) {
    setSelectedSolution(sol)
    try { localStorage.setItem('juriq_selected_solution', JSON.stringify(sol)) } catch { /* quota */ }
  }

  function clearSelectedSolution() {
    setSelectedSolution(null)
    try { localStorage.removeItem('juriq_selected_solution') } catch { /* ok */ }
  }

  return (
    <WorkflowContext.Provider value={{ result, saveResult, clearResult, selectedSolution, saveSelectedSolution, clearSelectedSolution }}>
      {children}
    </WorkflowContext.Provider>
  )
}

export function useWorkflow() {
  const ctx = useContext(WorkflowContext)
  if (!ctx) throw new Error('useWorkflow must be inside WorkflowProvider')
  return ctx
}
