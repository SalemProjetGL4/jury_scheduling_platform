import { useEffect, useState } from 'react'
import { Upload, CheckCircle2, FileText, Trash2 } from 'lucide-react'
import { apiRequest } from '../services/api'

const FILE_TYPES = [
  { id: 'prof',    label: 'Encadrants / Professeurs', accept: '.csv,.xlsx', example: 'professeurs.csv' },
  { id: 'project', label: 'Projets PFE',              accept: '.csv,.xlsx', example: 'projets.csv' },
  { id: 'rooms',   label: 'Salles disponibles',       accept: '.csv,.xlsx', example: 'salles.csv' },
  { id: 'slots',   label: 'Créneaux horaires',        accept: '.csv,.xlsx', example: 'creneaux.csv' },
]

function DropZone({ type, uploaded, onUpload, onRemove }) {
  return (
    <div className="border border-gray-200 rounded-xl p-4 hover:border-blue-300 transition-colors">
      <div className="flex items-center justify-between mb-3">
        <p className="text-sm font-medium text-gray-800">{type.label}</p>
        {uploaded && <CheckCircle2 size={16} className="text-green-500" />}
      </div>
      {uploaded ? (
        <div className="flex items-center gap-2 text-sm text-gray-600 bg-gray-50 rounded-lg px-3 py-2">
          <FileText size={15} className="text-blue-500" />
          <span className="flex-1 truncate">{type.example}</span>
          <button onClick={() => onRemove(type.id)} className="text-gray-400 hover:text-red-500">
            <Trash2 size={14} />
          </button>
        </div>
      ) : (
        <label className="flex flex-col items-center gap-2 border-2 border-dashed border-gray-200 rounded-lg p-5 cursor-pointer hover:bg-blue-50 hover:border-blue-300 transition-all">
          <Upload size={22} className="text-gray-400" />
          <span className="text-xs text-gray-500 text-center">
            Glissez-déposez ou <span className="text-blue-600 font-medium">parcourez</span>
          </span>
          <span className="text-[10px] text-gray-400">.CSV ou .XLSX</span>
          <input type="file" accept={type.accept} className="hidden" onChange={() => onUpload(type.id)} />
        </label>
      )}
    </div>
  )
}

export default function Donnees() {
  const [uploaded, setUploaded] = useState({ prof: true, project: false, rooms: true, slots: false })
  const [professors, setProfessors] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true

    async function loadProfessors() {
      try {
        setLoading(true)
        const data = await apiRequest('/professors?limit=200')
        if (active) {
          setProfessors(Array.isArray(data) ? data : [])
          setError('')
        }
      } catch (err) {
        if (active) {
          setError(err.message || 'Impossible de charger les professeurs')
          setProfessors([])
        }
      } finally {
        if (active) {
          setLoading(false)
        }
      }
    }

    loadProfessors()

    return () => {
      active = false
    }
  }, [])

  return (
    <div className="space-y-6 max-w-3xl">
      {/* Upload grid */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h2 className="text-base font-semibold text-gray-900 mb-1">Importer les fichiers</h2>
        <p className="text-sm text-gray-500 mb-5">Chargez vos données au format CSV ou Excel.</p>
        <div className="grid grid-cols-2 gap-4">
          {FILE_TYPES.map(t => (
            <DropZone
              key={t.id}
              type={t}
              uploaded={uploaded[t.id]}
              onUpload={id => setUploaded(u => ({ ...u, [id]: true }))}
              onRemove={id => setUploaded(u => ({ ...u, [id]: false }))}
            />
          ))}
        </div>
      </div>

      {/* Professors table */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-200">
          <p className="text-sm font-semibold text-gray-900">Encadrants importés ({professors.length})</p>
        </div>
        {error && (
          <div className="px-5 py-3 text-xs text-red-600 bg-red-50 border-b border-red-100">
            {error}
          </div>
        )}
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-100">
              {['Nom', 'Département', 'Préférences', 'Max jurys'].map(h => (
                <th key={h} className="text-left px-5 py-3 text-xs font-semibold text-gray-500">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td className="px-5 py-4 text-gray-400" colSpan={4}>Chargement…</td>
              </tr>
            )}
            {!loading && professors.length === 0 && (
              <tr>
                <td className="px-5 py-4 text-gray-400" colSpan={4}>Aucun encadrant trouvé.</td>
              </tr>
            )}
            {!loading && professors.map(p => (
              <tr key={p.id} className="border-b border-gray-100 hover:bg-gray-50">
                <td className="px-5 py-3 font-medium text-gray-900">{p.name}</td>
                <td className="px-5 py-3 text-gray-600">Dept #{p.department_id}</td>
                <td className="px-5 py-3 text-gray-600">{p.preferences?.length ? p.preferences.join(', ') : '—'}</td>
                <td className="px-5 py-3 text-gray-600">{p.max_juries}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
