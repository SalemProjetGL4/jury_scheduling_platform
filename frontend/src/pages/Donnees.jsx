import { useState } from 'react'
import { Upload, CheckCircle2, FileText, Trash2 } from 'lucide-react'
import { apiRequest } from '../services/api'

const FILE_TYPES = [
  {
    id: 'project',
    label: 'Projets des etudiants',
    accept: '.csv,.xlsx',
    example: 'projets.csv',
    templateName: 'modele-projets.csv',
    templateHeaders: ['title', 'domain_name', 'supervisor_email', 'student_email'],
  },
  {
    id: 'professor',
    label: 'Professeurs',
    accept: '.csv,.xlsx',
    example: 'professeurs.csv',
    templateName: 'modele-professeurs.csv',
    templateHeaders: ['name', 'email', 'department', 'max_juries', 'preferences'],
  },
]

function buildCsvTemplate(headers) {
  return `${headers.join(',')}\n`
}

function downloadTemplate(type) {
  const csv = buildCsvTemplate(type.templateHeaders)
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = type.templateName
  anchor.click()
  URL.revokeObjectURL(url)
}

function DropZone({
  type,
  uploaded,
  fileName,
  selectedFile,
  uploading,
  onSelectFile,
  onImport,
  onRemove,
  onDownloadTemplate,
}) {
  return (
    <div className="border border-gray-200 rounded-xl p-4 hover:border-blue-300 transition-colors">
      <div className="flex items-center justify-between mb-3">
        <p className="text-sm font-medium text-gray-800">{type.label}</p>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => onDownloadTemplate(type)}
            className="text-[11px] font-medium text-blue-600 hover:text-blue-700"
          >
            Télécharger le modèle
          </button>
          {uploaded && <CheckCircle2 size={16} className="text-green-500" />}
        </div>
      </div>
      {uploaded ? (
        <div className="flex items-center gap-2 text-sm text-gray-600 bg-gray-50 rounded-lg px-3 py-2">
          <FileText size={15} className="text-blue-500" />
          <span className="flex-1 truncate">{fileName || type.example}</span>
          <button onClick={() => onRemove(type.id)} className="text-gray-400 hover:text-red-500">
            <Trash2 size={14} />
          </button>
        </div>
      ) : selectedFile ? (
        <div className="space-y-3">
          <div className="flex items-center gap-2 text-sm text-gray-600 bg-gray-50 rounded-lg px-3 py-2">
            <FileText size={15} className="text-blue-500" />
            <span className="flex-1 truncate">{selectedFile.name}</span>
            <button onClick={() => onRemove(type.id)} className="text-gray-400 hover:text-red-500">
              <Trash2 size={14} />
            </button>
          </div>
          <button
            type="button"
            onClick={() => onImport(type.id)}
            disabled={uploading}
            className="w-full rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-blue-300"
          >
            Importer le CSV
          </button>
        </div>
      ) : (
        <label className="flex flex-col items-center gap-2 border-2 border-dashed border-gray-200 rounded-lg p-5 cursor-pointer hover:bg-blue-50 hover:border-blue-300 transition-all">
          <Upload size={22} className="text-gray-400" />
          <span className="text-xs text-gray-500 text-center">
            Glissez-déposez ou <span className="text-blue-600 font-medium">parcourez</span>
          </span>
          <span className="text-[10px] text-gray-400">.CSV ou .XLSX</span>
          <span className="text-[10px] text-gray-400">Puis cliquez sur Importer le CSV</span>
          <input
            type="file"
            accept={type.accept}
            className="hidden"
            disabled={uploading}
            onChange={event => onSelectFile(type.id, event)}
          />
        </label>
      )}
    </div>
  )
}

export default function Donnees() {
  const [uploaded, setUploaded] = useState({ project: false, professor: false })
  const [uploadedFiles, setUploadedFiles] = useState({ project: '', professor: '' })
  const [selectedFiles, setSelectedFiles] = useState({ project: null, professor: null })
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState('')
  const [uploadSuccess, setUploadSuccess] = useState('')

  function handleSelectFile(id, event) {
    const file = event?.target?.files?.[0]
    if (!file) {
      return
    }

    setSelectedFiles(current => ({ ...current, [id]: file }))
    setUploaded(current => ({ ...current, [id]: false }))
    setUploadedFiles(current => ({ ...current, [id]: '' }))
    setUploadError('')
    setUploadSuccess('')

    if (event?.target) {
      event.target.value = ''
    }
  }

  async function handleImport(id) {
    const file = selectedFiles[id]
    if (!file) {
      setUploadError('Choisissez un fichier avant d’importer.')
      return
    }

    setUploading(true)
    setUploadError('')

    const formData = new FormData()
    formData.append('file', file)

    const endpoint = id === 'professor' ? '/professors/import' : '/projects/import'

    try {
      const report = await apiRequest(endpoint, { method: 'POST', body: formData })
      setUploaded(current => ({ ...current, [id]: false }))
      setUploadedFiles(current => ({ ...current, [id]: '' }))
      setSelectedFiles(current => ({ ...current, [id]: null }))
      const label = id === 'professor' ? 'professeurs' : 'projets'
      const parts = [`${report.inserted_count || 0} ligne(s) ajoutée(s) dans la table ${label}.`]
      if (report.updated_count) {
        parts.push(`${report.updated_count} ligne(s) mise(s) à jour.`)
      }
      if (report.skipped_duplicates) {
        parts.push(`${report.skipped_duplicates} doublon(s) ignoré(s).`)
      }
      if (report.invalid_rows) {
        parts.push(`${report.invalid_rows} ligne(s) rejetée(s).`)
      }
      setUploadSuccess(parts.join(' '))
    } catch (err) {
      setUploadError(err.message || 'Upload failed.')
      setUploaded(current => ({ ...current, [id]: false }))
    } finally {
      setUploading(false)
    }
  }

  function handleRemove(id) {
    setUploaded(current => ({ ...current, [id]: false }))
    setUploadedFiles(current => ({ ...current, [id]: '' }))
    setSelectedFiles(current => ({ ...current, [id]: null }))
    setUploadError('')
    setUploadSuccess('')
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
              selectedFile={selectedFiles[t.id]}
              uploading={uploading}
              onSelectFile={handleSelectFile}
              onImport={handleImport}
              onRemove={handleRemove}
              onDownloadTemplate={downloadTemplate}
            />
          ))}
        </div>
        {uploadError && (
          <div className="mt-4 text-xs text-red-600 bg-red-50 border border-red-100 rounded-lg px-3 py-2">
            {uploadError}
          </div>
        )}
        {uploadSuccess && (
          <div className="mt-4 text-xs text-green-700 bg-green-50 border border-green-100 rounded-lg px-3 py-2">
            {uploadSuccess}
          </div>
        )}
      </div>

    </div>
  )
}
