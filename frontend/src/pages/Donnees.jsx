import { useState } from 'react'
import { Upload, CheckCircle2, FileText, Trash2 } from 'lucide-react'
import { apiRequest } from '../services/api'

const FILE_TYPES = [
  { id: 'project', label: 'Projets des etudiants', accept: '.csv,.xlsx', example: 'projets.csv' },
]

function DropZone({ type, uploaded, fileName, uploading, onUpload, onRemove }) {
  return (
    <div className="border border-gray-200 rounded-xl p-4 hover:border-blue-300 transition-colors">
      <div className="flex items-center justify-between mb-3">
        <p className="text-sm font-medium text-gray-800">{type.label}</p>
        {uploaded && <CheckCircle2 size={16} className="text-green-500" />}
      </div>
      {uploaded ? (
        <div className="flex items-center gap-2 text-sm text-gray-600 bg-gray-50 rounded-lg px-3 py-2">
          <FileText size={15} className="text-blue-500" />
          <span className="flex-1 truncate">{fileName || type.example}</span>
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
          {uploading && <span className="text-[10px] text-blue-500">Televersement...</span>}
          <input
            type="file"
            accept={type.accept}
            className="hidden"
            disabled={uploading}
            onChange={event => onUpload(type.id, event)}
          />
        </label>
      )}
    </div>
  )
}

export default function Donnees() {
  const [uploaded, setUploaded] = useState({ project: false })
  const [uploadedFiles, setUploadedFiles] = useState({ project: '' })
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState('')

  async function handleUpload(id, event) {
    const file = event?.target?.files?.[0]
    if (!file) {
      return
    }

    setUploading(true)
    setUploadError('')

    const formData = new FormData()
    formData.append('file', file)

    try {
      await apiRequest('/projects/import', { method: 'POST', body: formData })
      setUploaded(current => ({ ...current, [id]: true }))
      setUploadedFiles(current => ({ ...current, [id]: file.name }))
    } catch (err) {
      setUploadError(err.message || 'Upload failed.')
      setUploaded(current => ({ ...current, [id]: false }))
    } finally {
      setUploading(false)
      if (event?.target) {
        event.target.value = ''
      }
    }
  }

  function handleRemove(id) {
    setUploaded(current => ({ ...current, [id]: false }))
    setUploadedFiles(current => ({ ...current, [id]: '' }))
    setUploadError('')
  }

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
              fileName={uploadedFiles[t.id]}
              uploading={uploading}
              onUpload={handleUpload}
              onRemove={handleRemove}
            />
          ))}
        </div>
        {uploadError && (
          <div className="mt-4 text-xs text-red-600 bg-red-50 border border-red-100 rounded-lg px-3 py-2">
            {uploadError}
          </div>
        )}
      </div>

    </div>
  )
}
