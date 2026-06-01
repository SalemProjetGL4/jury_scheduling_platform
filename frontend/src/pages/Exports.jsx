import { useEffect, useState } from 'react'
import { Download, FileText, FileJson, FileType, Table, Building, Loader2, Archive } from 'lucide-react'
import { saveAs } from 'file-saver'
import { apiRequest } from '../services/api'
import { exportToCSV, exportToJSON, enrichAssignments } from '../utils/exportUtils'
import { exportBothDocx, buildBothDocxBlobs } from '../utils/docxExport'
import { useWorkflow } from '../context/WorkflowContext'

const FORMATS = [
  { icon: FileText,        label: 'PDF',           sub: 'Planning détaillé',       color: 'text-red-600 bg-red-50',      iconColor: '#DC2626' },
  { icon: Table,           label: 'CSV',           sub: 'Données brutes',          color: 'text-gray-600 bg-gray-100',   iconColor: '#4B5563' },
  { icon: FileJson,        label: 'JSON',          sub: 'Export brut JSON',         color: 'text-teal-600 bg-teal-50',    iconColor: '#0D9488' },
  { icon: FileType,        label: 'Word (docx)',   sub: 'Planning GL + RT',         color: 'text-indigo-600 bg-indigo-50',iconColor: '#4338CA' },
{ icon: Building,        label: 'Par salle (PDF)', sub: 'Planning par salle',   color: 'text-amber-600 bg-amber-50',    iconColor: '#D97706' },
  { icon: Archive,         label: 'ZIP par prof.',  sub: 'Planning XLSX\npar professeur', color: 'text-emerald-600 bg-emerald-50', iconColor: '#059669' },
]

const DEFAULT_SUMMARY = {
  label: 'Solution #1 (recommandée)',
  score: '94%',
  soutenances: 312,
  jours: 5,
  salles: 4,
  conflits: 0,
}

function countConflicts(assignments) {
  const bySlot = new Map()
  assignments.forEach(assignment => {
    const list = bySlot.get(assignment.slot_id) || []
    list.push(assignment)
    bySlot.set(assignment.slot_id, list)
  })

  let conflicts = 0
  bySlot.forEach(list => {
    const seen = new Map()
    list.forEach(assignment => {
      ;[assignment.examiner_id, assignment.president_id].forEach(id => {
        if (!id) return
        const count = (seen.get(id) || 0) + 1
        if (count > 1) {
          conflicts += 1
        }
        seen.set(id, count)
      })
    })
  })

  return conflicts
}

function buildSummary(session, slots, assignments) {
  if (!session) return DEFAULT_SUMMARY
  const sessionSlots = slots.filter(slot => slot.session_id === session.id)
  const slotIds = new Set(sessionSlots.map(slot => slot.id))
  const sessionAssignments = assignments.filter(item => slotIds.has(item.slot_id))
  const uniqueDates = new Set(sessionSlots.map(slot => slot.date))
  const uniqueRooms = new Set(sessionSlots.map(slot => slot.room))
  const conflicts = countConflicts(sessionAssignments)
  const scoreValue = sessionAssignments.length ? Math.max(0, 100 - conflicts * 5) : null

  return {
    label: `Session #${session.id}`,
    score: scoreValue === null ? '—' : `${scoreValue}%`,
    soutenances: sessionAssignments.length,
    jours: uniqueDates.size,
    salles: uniqueRooms.size,
    conflits: conflicts,
  }
}

export default function Exports() {
  const { selectedSolution } = useWorkflow()
  const assignments = selectedSolution?.rawAssignments ?? []
  const disabled = assignments.length === 0

  const year = selectedSolution?.date
    ? new Date(selectedSolution.date).getFullYear()
    : new Date().getFullYear()
  const solutionNumber = selectedSolution?.id ?? 1
  const filename = `pfe_session${year}_juriq_solution${solutionNumber}`

  const [summary, setSummary]           = useState(DEFAULT_SUMMARY)
  const [error, setError]               = useState('')
  const [professors, setProfessors]     = useState([])
  const [projects, setProjects]         = useState([])
  const [students, setStudents]         = useState([])
  const [domains, setDomains]           = useState([])
  const [slots, setSlots]               = useState([])
  const [loadingLookup, setLoadingLookup] = useState(true)
  const [loadingDocx, setLoadingDocx]     = useState(false)
  const [loadingZip,  setLoadingZip]      = useState(false)
  const [loadingPdf,  setLoadingPdf]      = useState(false)

  useEffect(() => {
    let active = true

    async function loadData() {
      try {
        const [sessionsData, slotsData, assignmentsData, professorsData, projectsData, studentsData, domainsData] = await Promise.all([
          apiRequest('/sessions?limit=200'),
          apiRequest('/slots?limit=200'),
          apiRequest('/assignments?limit=200'),
          apiRequest('/professors?limit=200'),
          apiRequest('/projects?limit=200'),
          apiRequest('/students?limit=200'),
          apiRequest('/domains?limit=200'),
        ])

        if (!active) return

        const sessions    = Array.isArray(sessionsData)    ? sessionsData    : []
        const safeSlots   = Array.isArray(slotsData)       ? slotsData       : []
        const safeAssign  = Array.isArray(assignmentsData) ? assignmentsData : []

        if (sessions.length > 0) {
          const latest = sessions
            .slice()
            .sort((a, b) => new Date(b.start_date) - new Date(a.start_date))[0]
          setSummary(buildSummary(latest, safeSlots, safeAssign))
        }

        setSlots(safeSlots)
        setProfessors(Array.isArray(professorsData) ? professorsData : [])
        setProjects(Array.isArray(projectsData)     ? projectsData   : [])
        setStudents(Array.isArray(studentsData)     ? studentsData   : [])
        setDomains(Array.isArray(domainsData)       ? domainsData    : [])
        setError('')
      } catch (err) {
        if (active) setError(err.message || 'Impossible de charger le résumé')
      } finally {
        if (active) setLoadingLookup(false)
      }
    }

    loadData()

    return () => { active = false }
  }, [])

  function sanitizeName(name) {
    return name
      .normalize('NFD').replace(/[̀-ͯ]/g, '')
      .replace(/\s+/g, '_')
      .replace(/[^a-zA-Z0-9_-]/g, '')
  }

  async function handlePdfExport() {
    if (disabled || loadingLookup || loadingPdf) return
    setLoadingPdf(true)
    try {
      const enriched = enrichAssignments(assignments, { professors, projects, slots, students, domains })
      const { glBlob, rtBlob } = await buildBothDocxBlobs(enriched)
      const base = `pfe_session${year}_juriq_solution${solutionNumber}`

      for (const [blob, filiere] of [[glBlob, 'GL'], [rtBlob, 'RT']]) {
        const form = new FormData()
        form.append('file', blob, `${base}_${filiere}.docx`)

        const res = await fetch('/api/convert/docx-to-pdf', { method: 'POST', body: form })
        if (!res.ok) {
          const msg = await res.text()
          throw new Error(msg || `Conversion failed (${res.status})`)
        }

        const pdfBlob = await res.blob()
        saveAs(pdfBlob, `${base}_${filiere}.pdf`)
        if (filiere === 'GL') await new Promise(r => setTimeout(r, 500))
      }
    } catch (err) {
      console.error('[PDF export]', err)
    } finally {
      setLoadingPdf(false)
    }
  }

  async function handleWordExport() {
    if (disabled || loadingLookup || loadingDocx) return
    setLoadingDocx(true)
    try {
      const enriched = enrichAssignments(assignments, { professors, projects, slots, students, domains })
      await exportBothDocx(enriched, `pfe_session${year}_juriq_solution${solutionNumber}`)
    } catch (err) {
      console.error('[DOCX export]', err)
    } finally {
      setLoadingDocx(false)
    }
  }

  async function downloadProfessorZip() {
    if (disabled || loadingLookup || loadingZip) return
    setLoadingZip(true)
    try {
      const enriched = enrichAssignments(assignments, { professors, projects, slots, students, domains })

      // Group enriched rows by professor name across all three roles
      const byProf = new Map()
      const addRow = (name, row, role) => {
        if (!name || name === '—') return
        if (!byProf.has(name)) byProf.set(name, [])
        byProf.get(name).push({ ...row, role })
      }
      enriched.forEach(row => {
        addRow(row.president_name,  row, 'Président')
        addRow(row.examiner_name,   row, 'Examinateur')
        addRow(row.supervisor_name, row, 'Encadrant')
      })

      const [{ default: JSZip }, { buildProfessorWorkbook }] = await Promise.all([
        import('jszip'),
        import('../utils/professorExport'),
      ])

      const zip = new JSZip()
      for (const [profName, rows] of byProf) {
        const wb     = await buildProfessorWorkbook(profName, rows)
        const buffer = await wb.xlsx.writeBuffer()
        zip.file(`${sanitizeName(profName)}_planning.xlsx`, buffer)
      }

      const blob         = await zip.generateAsync({ type: 'blob' })
      const sessionLabel = selectedSolution?.id ? `session${selectedSolution.id}` : `session_${year}`
      saveAs(blob, `planning_jury_${sessionLabel}.zip`)
    } catch (err) {
      console.error('[ZIP export]', err)
    } finally {
      setLoadingZip(false)
    }
  }

  return (
    <div className="space-y-5 max-w-3xl">
      {/* Selected solution summary */}
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Solution sélectionnée</p>
        <p className="text-sm font-bold text-gray-900 mb-3">
          {selectedSolution ? `PFE Session ${year} — Juriq Solution ${solutionNumber}` : 'Aucun planning sélectionné'}
        </p>
        {error && (
          <div className="mb-3 text-xs text-red-600 bg-red-50 border border-red-100 rounded-lg px-3 py-2">
            {error}
          </div>
        )}
        <div className="flex items-center gap-6 flex-wrap">
          <div className="flex items-center gap-1">
            <span className="text-xs text-gray-500">Score</span>
            <span className="text-sm font-bold text-green-600 ml-1">
              {selectedSolution ? `${selectedSolution.score}%` : summary.score}
            </span>
          </div>
          {[
            { val: selectedSolution?.soutenances ?? summary.soutenances, lbl: 'Soutenances' },
            { val: selectedSolution?.jours       ?? summary.jours,       lbl: 'Jours' },
            { val: selectedSolution?.salles      ?? summary.salles,      lbl: 'Salles' },
            { val: selectedSolution?.conflits    ?? summary.conflits,    lbl: 'Conflits' },
          ].map(({ val, lbl }) => (
            <div key={lbl} className="text-center">
              <p className="text-base font-bold text-gray-900">{val}</p>
              <p className="text-xs text-gray-500">{lbl}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Formats */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <p className="text-sm font-semibold text-gray-700 mb-4">Formats disponibles</p>
        <div className="grid grid-cols-3 gap-4">
          {FORMATS.map(({ icon: Icon, label, sub, color, iconColor }) => {
            const isCSV  = label === 'CSV'
            const isJSON = label === 'JSON'
            const isWord = label === 'Word (docx)'
            const isZip  = label === 'ZIP par prof.'
            const isPdf  = label === 'PDF'
            const lookup = { professors, projects, slots, students, domains, filename }
            const clientExport = isCSV
              ? () => exportToCSV(assignments, lookup)
              : isJSON
              ? () => exportToJSON(assignments, lookup)
              : isWord
              ? handleWordExport
              : isZip
              ? downloadProfessorZip
              : isPdf
              ? handlePdfExport
              : undefined
            const btnDisabled = (isCSV || isJSON) ? (disabled || loadingLookup)
              : isWord ? (disabled || loadingLookup || loadingDocx)
              : isZip  ? (disabled || loadingLookup || loadingZip)
              : isPdf  ? (disabled || loadingLookup || loadingPdf)
              : false
            return (
              <div key={label} className="border border-gray-200 rounded-xl p-4 flex flex-col items-center gap-3 hover:border-blue-300 hover:shadow-sm transition-all">
                <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${color}`}>
                  <Icon size={24} style={{ color: iconColor }} />
                </div>
                <div className="text-center">
                  <p className="text-sm font-semibold text-gray-900">{label}</p>
                  <p className="text-xs text-gray-500 whitespace-pre-line leading-tight mt-0.5">{sub}</p>
                </div>
                <button
                  onClick={clientExport}
                  disabled={btnDisabled}
                  title={btnDisabled ? ((loadingDocx && isWord) || (loadingZip && isZip) || (loadingPdf && isPdf) ? 'Génération en cours…' : loadingLookup ? 'Chargement des données…' : 'Aucun planning généré') : ''}
                  className={`flex items-center gap-1.5 w-full justify-center text-xs font-medium text-blue-600 border border-blue-200 rounded-lg py-2 hover:bg-blue-50 transition-colors${btnDisabled ? ' opacity-40 cursor-not-allowed' : ''}`}
                >
                  {(isWord && loadingDocx) || (isZip && loadingZip) || (isPdf && loadingPdf)
                    ? <Loader2 size={13} className="animate-spin" />
                    : <Download size={13} />
                  }
                  {(isWord && loadingDocx) || (isZip && loadingZip) || (isPdf && loadingPdf) ? 'Génération…' : 'Télécharger'}
                </button>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
