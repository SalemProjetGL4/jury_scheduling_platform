import { useState, useEffect, useRef } from 'react'
import {
  Users, Calendar, DoorOpen, FileText,
  Pencil, Trash2, Loader2, Plus, Search, X, Upload,
  Clock, AlertTriangle, Download,
} from 'lucide-react'
import { apiRequest } from '../services/api'

// ── Shared styles ─────────────────────────────────────────────────────────────

const btnPrimary = {
  background: '#2563eb', color: '#fff', border: 'none',
  borderRadius: '6px', padding: '7px 16px', fontSize: '13px',
  fontWeight: 500, cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: '5px',
}
const btnGhost = {
  background: 'none', color: '#64748b', border: '0.5px solid #e2e8f0',
  borderRadius: '6px', padding: '7px 16px', fontSize: '13px', cursor: 'pointer',
}
const btnIcon = {
  background: 'none', border: 'none', cursor: 'pointer',
  color: '#94a3b8', padding: '4px', borderRadius: '4px', fontSize: '16px',
  display: 'inline-flex', alignItems: 'center',
}
const tableStyle = { width: '100%', borderCollapse: 'collapse', fontSize: '13px' }
const thStyle = {
  textAlign: 'left', padding: '10px 12px', color: '#94a3b8',
  fontWeight: 500, borderBottom: '0.5px solid #e2e8f0', fontSize: '12px',
}
const tdStyle = { padding: '10px 12px', color: '#0f172a', borderBottom: '0.5px solid #f1f5f9' }
const inputStyle = {
  width: '100%', padding: '7px 10px', border: '0.5px solid #e2e8f0',
  borderRadius: '6px', fontSize: '13px', outline: 'none', boxSizing: 'border-box',
}
const labelStyle = { display: 'block', fontSize: '12px', fontWeight: 500, color: '#64748b', marginBottom: '5px' }
const cardStyle = {
  background: '#fff', border: '0.5px solid #e2e8f0', borderRadius: '10px', padding: '20px',
}
const sectionTitle = { margin: '0 0 4px 0', fontSize: '14px', fontWeight: 600, color: '#0f172a' }
const sectionSub   = { margin: '0 0 16px 0', fontSize: '12px', color: '#64748b' }

// ── Helper ────────────────────────────────────────────────────────────────────

function countSlotsPreview(startDate, endDate) {
  if (!startDate || !endDate) return null
  const start = new Date(startDate + 'T00:00:00')
  const end   = new Date(endDate   + 'T00:00:00')
  if (end < start) return null
  let slots = 0, days = 0
  for (const d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
    const dow = d.getDay()
    if (dow === 0) continue
    days++
    slots += 4
    if (dow !== 6) slots += 4
  }
  return { slots, days }
}

function InlineError({ msg }) {
  if (!msg) return null
  return (
    <div style={{ color: '#dc2626', fontSize: '12px', background: '#fef2f2', border: '0.5px solid #fecaca', borderRadius: '6px', padding: '8px 12px', marginTop: '8px' }}>
      {msg}
    </div>
  )
}

function InlineSuccess({ msg }) {
  if (!msg) return null
  return (
    <div style={{ color: '#166534', fontSize: '12px', background: '#f0fdf4', border: '0.5px solid #bbf7d0', borderRadius: '6px', padding: '8px 12px', marginTop: '8px' }}>
      {msg}
    </div>
  )
}

function Spinner() {
  return <Loader2 size={20} className="animate-spin" style={{ color: '#94a3b8' }} />
}

function CenteredSpinner() {
  return <div style={{ display: 'flex', justifyContent: 'center', padding: '32px' }}><Spinner /></div>
}

function downloadCsv(filename, rows) {
  const csv = rows.join('\n') + '\n'
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

// ── Tab 1: Professeurs ────────────────────────────────────────────────────────

const PROF_EMPTY = { name: '', email: '', department_id: '', max_juries: 3, domain_ids: [] }

function DomainChip({ name, onRemove }) {
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: '4px',
      background: '#eff6ff', border: '0.5px solid #bfdbfe', borderRadius: '99px',
      padding: '2px 8px', fontSize: '11px', color: '#1d4ed8', fontWeight: 500,
    }}>
      {name}
      {onRemove && (
        <button
          onClick={onRemove}
          style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '0', lineHeight: 1, color: '#60a5fa', display: 'flex', alignItems: 'center' }}
          title="Retirer"
        >
          <X size={10} />
        </button>
      )}
    </span>
  )
}

function ProfesseursTab() {
  const [professors, setProfessors] = useState([])
  const [domains, setDomains]       = useState([])
  const [loading, setLoading]       = useState(true)
  const [error, setError]           = useState('')
  const [uploading, setUploading]   = useState(false)
  const [uploadSuccess, setUploadSuccess] = useState('')
  const [uploadErrors, setUploadErrors]   = useState([])
  const [search, setSearch]         = useState('')
  const [showForm, setShowForm]     = useState(false)
  const [editingProf, setEditingProf] = useState(null)
  const [form, setForm]             = useState(PROF_EMPTY)
  const [formError, setFormError]   = useState('')
  const [saving, setSaving]         = useState(false)
  const [selectedProfIds, setSelectedProfIds] = useState(new Set())
  const [deleting, setDeleting]     = useState(false)
  const [deleteResult, setDeleteResult] = useState('')

  const csvInputRef       = useRef(null)
  const headerCheckboxRef = useRef(null)

  useEffect(() => { load() }, [])

  async function load() {
    setLoading(true)
    setError('')
    try {
      const [profData, domData] = await Promise.all([
        apiRequest('/professors?limit=200'),
        apiRequest('/domains?limit=200'),
      ])
      setProfessors(Array.isArray(profData) ? profData : [])
      setDomains(Array.isArray(domData) ? domData : [])
    } catch (e) {
      setError(e.message || 'Erreur de chargement')
    } finally {
      setLoading(false)
    }
  }

  function openCsvPicker() {
    setUploadSuccess('')
    setUploadErrors([])
    if (csvInputRef.current) {
      csvInputRef.current.value = ''
      csvInputRef.current.click()
    }
  }

  async function handleCsvSelected(e) {
    const file = e.target.files && e.target.files[0]
    if (!file) return

    setUploading(true)
    setUploadSuccess('')
    setUploadErrors([])
    setError('')

    try {
      const formData = new FormData()
      formData.append('file', file)
      const result = await apiRequest('/professors/upload-csv', { method: 'POST', body: formData })
      const inserted = Number(result?.inserted || 0)
      const skipped  = Number(result?.skipped || 0)
      const errs     = Array.isArray(result?.errors) ? result.errors : []
      setUploadSuccess(`Import terminé : ${inserted} inséré(s), ${skipped} ignoré(s).`)
      setUploadErrors(errs)
      await load()
    } catch (err) {
      setError(err.message || 'Erreur lors de l\'upload CSV')
    } finally {
      setUploading(false)
    }
  }

  function openAdd() {
    setEditingProf(null)
    setForm(PROF_EMPTY)
    setFormError('')
    setShowForm(true)
  }

  function openEdit(prof) {
    setEditingProf(prof)
    setForm({
      name: prof.name,
      email: prof.email,
      department_id: prof.department_id,
      max_juries: prof.max_juries,
      domain_ids: Array.isArray(prof.domain_ids) ? [...prof.domain_ids] : [],
    })
    setFormError('')
    setShowForm(true)
  }

  function closeForm() {
    setShowForm(false)
    setEditingProf(null)
    setFormError('')
  }

  function field(key) {
    return e => setForm(f => ({ ...f, [key]: e.target.value }))
  }

  function addDomain(domainId) {
    const id = Number(domainId)
    if (!id || form.domain_ids.includes(id)) return
    setForm(f => ({ ...f, domain_ids: [...f.domain_ids, id] }))
  }

  function removeDomain(domainId) {
    setForm(f => ({ ...f, domain_ids: f.domain_ids.filter(id => id !== domainId) }))
  }

  async function syncDomains(professorId, oldIds, newIds) {
    const toAdd    = newIds.filter(id => !oldIds.includes(id))
    const toRemove = oldIds.filter(id => !newIds.includes(id))
    await Promise.all([
      ...toAdd.map(id    => apiRequest(`/professors/${professorId}/domains/${id}`, { method: 'POST' })),
      ...toRemove.map(id => apiRequest(`/professors/${professorId}/domains/${id}`, { method: 'DELETE' })),
    ])
  }

  async function handleSave() {
    if (!form.name.trim() || !form.email.trim() || !form.department_id) {
      setFormError('Nom, email et département sont requis.')
      return
    }
    setSaving(true)
    setFormError('')
    const payload = {
      name: form.name,
      email: form.email,
      department_id: Number(form.department_id),
      max_juries: Number(form.max_juries) || 3,
    }
    try {
      if (editingProf) {
        await apiRequest(`/professors/${editingProf.id}`, { method: 'PUT', body: payload })
        await syncDomains(editingProf.id, editingProf.domain_ids || [], form.domain_ids)
      } else {
        const created = await apiRequest('/professors', { method: 'POST', body: payload })
        await syncDomains(created.id, [], form.domain_ids)
      }
      closeForm()
      await load()
    } catch (e) {
      setFormError(e.message || 'Erreur lors de la sauvegarde')
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete(prof) {
    if (!window.confirm(`Supprimer ${prof.name} ?`)) return
    try {
      await apiRequest(`/professors/${prof.id}`, { method: 'DELETE' })
      setSelectedProfIds(prev => { const n = new Set(prev); n.delete(prof.id); return n })
      await load()
    } catch (e) {
      setError(e.message || 'Erreur lors de la suppression')
    }
  }

  function toggleProfSelection(id) {
    setSelectedProfIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id); else next.add(id)
      return next
    })
  }

  function handleProfHeaderCheckbox() {
    if (allVisibleSelected) {
      setSelectedProfIds(prev => { const n = new Set(prev); visibleIds.forEach(id => n.delete(id)); return n })
    } else {
      setSelectedProfIds(prev => new Set([...prev, ...visibleIds]))
    }
  }

  async function handleBulkDelete() {
    const n = selectedProfIds.size
    if (!window.confirm(`Supprimer ${n} professeur(s) ? Cette action est irréversible.`)) return
    setDeleting(true)
    setDeleteResult('')
    try {
      await Promise.all([...selectedProfIds].map(id => apiRequest(`/professors/${id}`, { method: 'DELETE' })))
      setSelectedProfIds(new Set())
      setDeleteResult(`${n} professeur(s) supprimé(s).`)
      await load()
    } catch (e) {
      setError(e.message || 'Erreur lors de la suppression')
    } finally {
      setDeleting(false)
    }
  }

  const domainMap = Object.fromEntries(domains.map(d => [d.id, d.name]))
  const availableDomains = domains.filter(d => !form.domain_ids.includes(d.id))

  const filtered = professors.filter(p =>
    p.name.toLowerCase().includes(search.toLowerCase()) ||
    p.email.toLowerCase().includes(search.toLowerCase())
  )
  const visibleIds            = filtered.map(p => p.id)
  const selectedVisibleCount  = visibleIds.filter(id => selectedProfIds.has(id)).length
  const allVisibleSelected    = visibleIds.length > 0 && selectedVisibleCount === visibleIds.length

  useEffect(() => {
    if (!headerCheckboxRef.current) return
    headerCheckboxRef.current.indeterminate = selectedVisibleCount > 0 && !allVisibleSelected
  }, [selectedProfIds, filtered])

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px' }}>
        <h2 style={{ margin: 0, fontSize: '15px', fontWeight: 600, color: '#0f172a' }}>
          Professeurs ({professors.length})
        </h2>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'flex-start' }}>
          <input
            ref={csvInputRef}
            type="file"
            accept=".csv,text/csv"
            onChange={handleCsvSelected}
            style={{ display: 'none' }}
          />
          <div style={{ position: 'relative' }}>
            <Search size={13} style={{ position: 'absolute', left: '8px', top: '50%', transform: 'translateY(-50%)', color: '#94a3b8', pointerEvents: 'none' }} />
            <input
              placeholder="Rechercher..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              style={{ ...inputStyle, paddingLeft: '28px', width: '200px' }}
            />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '4px' }}>
            <div style={{ display: 'flex', gap: '6px' }}>
              <button style={{ ...btnGhost, minWidth: '140px', justifyContent: 'center' }} onClick={openCsvPicker} disabled={uploading}>
                <Upload size={14} /> {uploading ? 'Upload…' : 'Importer CSV'}
              </button>
              <button style={btnGhost} onClick={() => downloadCsv('professors_template.csv', [
                'name,email,department_id,max_juries,preferences,domains',
                'Jean Dupont,jean.dupont@univ.fr,1,3,IA;ML,Machine Learning;Intelligence Artificielle',
              ])}>
                <Download size={14} /> Modèle CSV
              </button>
            </div>
            <span style={{ fontSize: '11px', color: '#94a3b8' }}>
              Colonnes&nbsp;:&nbsp;
              <code style={{ background: '#f1f5f9', padding: '1px 4px', borderRadius: '3px', fontSize: '10px' }}>
                name, email, department_id, max_juries, preferences, domains
              </code>
              &nbsp;— préférences et domaines séparés par «&nbsp;;&nbsp;»
            </span>
          </div>
          <button style={btnPrimary} onClick={openAdd}>
            <Plus size={14} /> Ajouter
          </button>
        </div>
      </div>

      <InlineSuccess msg={uploadSuccess} />
      {uploadErrors.length > 0 && (
        <div style={{ color: '#dc2626', fontSize: '12px', background: '#fef2f2', border: '0.5px solid #fecaca', borderRadius: '6px', padding: '8px 12px', marginTop: '8px' }}>
          <div style={{ fontWeight: 600, marginBottom: '4px' }}>Erreurs ({uploadErrors.length})</div>
          <div style={{ display: 'grid', gap: '2px' }}>
            {uploadErrors.map((msg, idx) => (
              <div key={idx}>{String(msg)}</div>
            ))}
          </div>
        </div>
      )}

      {/* Modal — add / edit */}
      {showForm && (
        <div
          onClick={closeForm}
          style={{ position: 'fixed', inset: 0, background: 'rgba(15,23,42,0.35)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
        >
          <div
            onClick={e => e.stopPropagation()}
            style={{ background: '#fff', borderRadius: '12px', padding: '24px', width: '560px', maxWidth: '95vw', boxShadow: '0 20px 60px rgba(0,0,0,0.15)', border: '0.5px solid #e2e8f0' }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '18px' }}>
              <p style={{ margin: 0, fontSize: '14px', fontWeight: 600, color: '#0f172a' }}>
                {editingProf ? `Modifier ${editingProf.name}` : 'Nouveau professeur'}
              </p>
              <button onClick={closeForm} style={{ ...btnIcon, color: '#64748b' }}><X size={16} /></button>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginBottom: '12px' }}>
              <div>
                <label style={labelStyle}>Nom complet</label>
                <input value={form.name} onChange={field('name')} style={inputStyle} placeholder="Jean Dupont" />
              </div>
              <div>
                <label style={labelStyle}>Email</label>
                <input value={form.email} onChange={field('email')} style={inputStyle} type="email" placeholder="jean@univ.fr" />
              </div>
              <div>
                <label style={labelStyle}>Department ID</label>
                <input value={form.department_id} onChange={field('department_id')} style={inputStyle} type="number" min="1" placeholder="1" />
              </div>
              <div>
                <label style={labelStyle}>Max jurys</label>
                <input value={form.max_juries} onChange={field('max_juries')} style={inputStyle} type="number" min="0" placeholder="3" />
              </div>
            </div>

            <div style={{ marginBottom: '16px' }}>
              <label style={labelStyle}>Domaines</label>
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
                <select
                  value=""
                  onChange={e => { addDomain(e.target.value); e.target.value = '' }}
                  style={{ ...inputStyle, width: 'auto', minWidth: '200px' }}
                >
                  <option value="">— Ajouter un domaine —</option>
                  {availableDomains.map(d => (
                    <option key={d.id} value={d.id}>{d.name}</option>
                  ))}
                </select>
                {form.domain_ids.map(id => (
                  <DomainChip key={id} name={domainMap[id] ?? `#${id}`} onRemove={() => removeDomain(id)} />
                ))}
                {form.domain_ids.length === 0 && (
                  <span style={{ fontSize: '12px', color: '#94a3b8' }}>Aucun domaine sélectionné</span>
                )}
              </div>
            </div>

            <InlineError msg={formError} />
            <div style={{ display: 'flex', gap: '8px', marginTop: '16px' }}>
              <button style={btnPrimary} onClick={handleSave} disabled={saving}>
                {saving ? 'Sauvegarde…' : editingProf ? 'Mettre à jour' : 'Créer'}
              </button>
              <button style={btnGhost} onClick={closeForm}>Annuler</button>
            </div>
          </div>
        </div>
      )}

      <InlineError msg={error} />
      {deleteResult && <InlineSuccess msg={`✓ ${deleteResult}`} />}

      {selectedProfIds.size > 0 && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '10px 14px', background: '#fef9c3', border: '0.5px solid #fde047', borderRadius: '6px', marginBottom: '12px' }}>
          <span style={{ fontSize: '13px', color: '#713f12', fontWeight: 500 }}>
            {selectedProfIds.size} professeur(s) sélectionné(s)
          </span>
          <button onClick={handleBulkDelete} disabled={deleting}
            style={{ background: '#dc2626', color: '#fff', border: 'none', borderRadius: '6px', padding: '5px 12px', fontSize: '12px', fontWeight: 500, cursor: deleting ? 'not-allowed' : 'pointer', opacity: deleting ? 0.7 : 1, display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
            <Trash2 size={13} />{deleting ? 'Suppression…' : 'Supprimer la sélection'}
          </button>
          <button onClick={() => setSelectedProfIds(new Set())}
            style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '12px', color: '#92400e' }}>
            Désélectionner tout
          </button>
        </div>
      )}

      {loading ? <CenteredSpinner /> : (
        <div style={{ background: '#fff', border: '0.5px solid #e2e8f0', borderRadius: '10px', overflow: 'hidden' }}>
          <table style={tableStyle}>
            <thead>
              <tr>
                <th style={{ ...thStyle, width: '36px', textAlign: 'center' }}>
                  <input type="checkbox" ref={headerCheckboxRef} checked={allVisibleSelected}
                    onChange={handleProfHeaderCheckbox} style={{ cursor: 'pointer' }} />
                </th>
                <th style={thStyle}>Nom</th>
                <th style={thStyle}>Email</th>
                <th style={thStyle}>Département</th>
                <th style={thStyle}>Max jurys</th>
                <th style={thStyle}>Domaines</th>
                <th style={thStyle} />
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 ? (
                <tr><td colSpan={7} style={{ ...tdStyle, textAlign: 'center', color: '#94a3b8' }}>Aucun résultat</td></tr>
              ) : filtered.map(prof => (
                <tr key={prof.id}
                  onClick={() => toggleProfSelection(prof.id)}
                  style={{ cursor: 'pointer', background: selectedProfIds.has(prof.id) ? '#eff6ff' : undefined, transition: 'background 0.1s' }}
                  onMouseEnter={e => { if (!selectedProfIds.has(prof.id)) e.currentTarget.style.background = '#f8fafc' }}
                  onMouseLeave={e => { e.currentTarget.style.background = selectedProfIds.has(prof.id) ? '#eff6ff' : '' }}>
                  <td style={{ ...tdStyle, width: '36px', textAlign: 'center' }} onClick={e => e.stopPropagation()}>
                    <input type="checkbox" checked={selectedProfIds.has(prof.id)}
                      onChange={() => toggleProfSelection(prof.id)} style={{ cursor: 'pointer' }} />
                  </td>
                  <td style={{ ...tdStyle, fontWeight: 500 }}>{prof.name}</td>
                  <td style={{ ...tdStyle, color: '#64748b' }}>{prof.email}</td>
                  <td style={tdStyle}>{prof.department_id}</td>
                  <td style={tdStyle}>{prof.max_juries}</td>
                  <td style={tdStyle}>
                    <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                      {(prof.domain_ids || []).length === 0
                        ? <span style={{ color: '#94a3b8', fontSize: '12px' }}>—</span>
                        : (prof.domain_ids || []).map(id => (
                            <DomainChip key={id} name={domainMap[id] ?? `#${id}`} />
                          ))
                      }
                    </div>
                  </td>
                  <td style={{ ...tdStyle, textAlign: 'right', whiteSpace: 'nowrap' }} onClick={e => e.stopPropagation()}>
                    <button style={btnIcon} onClick={() => openEdit(prof)} title="Modifier">
                      <Pencil size={14} />
                    </button>
                    <button style={{ ...btnIcon, color: '#ef4444' }} onClick={() => handleDelete(prof)} title="Supprimer">
                      <Trash2 size={14} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ── Tab 2: Sessions ───────────────────────────────────────────────────────────

function SessionsTab() {
  const [sessions, setSessions]           = useState([])
  const [rooms, setRooms]                 = useState([])
  const [loading, setLoading]             = useState(true)
  const [startDate, setStartDate]         = useState('')
  const [endDate, setEndDate]             = useState('')
  const [selectedRoomIds, setSelectedRoomIds] = useState([])
  const [generating, setGenerating]       = useState(false)
  const [genProgress, setGenProgress]     = useState('')
  const [genResult, setGenResult]         = useState(null)
  const [genError, setGenError]           = useState('')
  const [selectedSessionIds, setSelectedSessionIds] = useState(new Set())
  const [deletingSessions, setDeletingSessions] = useState(false)
  const sessHeaderRef = useRef(null)

  useEffect(() => {
    Promise.all([
      apiRequest('/sessions?limit=50'),
      apiRequest('/rooms'),
    ]).then(([sessData, roomData]) => {
      setSessions(Array.isArray(sessData) ? sessData : [])
      const roomList = Array.isArray(roomData) ? roomData : []
      setRooms(roomList)
      setSelectedRoomIds(roomList.map(r => r.id))
    }).catch(() => {}).finally(() => setLoading(false))
  }, [])

  function toggleRoom(id) {
    setSelectedRoomIds(cur => cur.includes(id) ? cur.filter(x => x !== id) : [...cur, id])
  }

  const preview = countSlotsPreview(startDate, endDate)

  async function handleGenerate() {
    if (!startDate || !endDate) { setGenError('Choisissez les deux dates.'); return }
    if (selectedRoomIds.length === 0) { setGenError('Sélectionnez au moins une salle.'); return }
    setGenerating(true)
    setGenError('')
    setGenResult(null)
    setGenProgress('Génération en cours…')
    try {
      const res = await apiRequest('/sessions/generate-slots', {
        method: 'POST',
        body: { start_date: startDate, end_date: endDate, room_ids: selectedRoomIds },
      })
      setGenProgress('')
      setGenResult({ created: 1, totalSlots: res.slots_created || 0 })
    } catch (e) {
      setGenError(e.message)
      setGenerating(false)
      setGenProgress('')
      return
    }
    setGenerating(false)
    const updated = await apiRequest('/sessions?limit=50').catch(() => null)
    if (Array.isArray(updated)) setSessions(updated)
  }

  async function handleDeleteSession(s) {
    if (!window.confirm(`Supprimer la session #${s.id} (${s.start_date} → ${s.end_date}) ?`)) return
    try {
      await apiRequest(`/sessions/${s.id}`, { method: 'DELETE' })
      setSessions(cur => cur.filter(x => x.id !== s.id))
      setSelectedSessionIds(prev => { const n = new Set(prev); n.delete(s.id); return n })
    } catch (e) {
      alert(e.message || 'Erreur lors de la suppression')
    }
  }

  function toggleSessionSelection(id) {
    setSelectedSessionIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id); else next.add(id)
      return next
    })
  }

  function handleSessHeaderCheckbox() {
    const all = sessions.every(s => selectedSessionIds.has(s.id))
    if (all) {
      setSelectedSessionIds(prev => { const n = new Set(prev); sessions.forEach(s => n.delete(s.id)); return n })
    } else {
      setSelectedSessionIds(prev => new Set([...prev, ...sessions.map(s => s.id)]))
    }
  }

  async function handleBulkDeleteSessions() {
    const n = selectedSessionIds.size
    if (!window.confirm(`Supprimer ${n} session(s) ? Cette action est irréversible.`)) return
    setDeletingSessions(true)
    try {
      await Promise.all([...selectedSessionIds].map(id => apiRequest(`/sessions/${id}`, { method: 'DELETE' })))
      setSessions(cur => cur.filter(s => !selectedSessionIds.has(s.id)))
      setSelectedSessionIds(new Set())
    } catch (e) {
      alert(e.message || 'Erreur lors de la suppression')
    } finally {
      setDeletingSessions(false)
    }
  }

  const allSessionsSelected = sessions.length > 0 && sessions.every(s => selectedSessionIds.has(s.id))
  const someSessionsSelected = sessions.some(s => selectedSessionIds.has(s.id))

  useEffect(() => {
    if (!sessHeaderRef.current) return
    sessHeaderRef.current.indeterminate = someSessionsSelected && !allSessionsSelected
  }, [selectedSessionIds, sessions])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>

      {/* Create card */}
      <div style={cardStyle}>
        <h3 style={sectionTitle}>Créer une session</h3>
        <p style={sectionSub}>
          4 créneaux matin (08h–12h) + 4 après-midi (13h–17h) par jour ouvré, samedi matin seulement.
        </p>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '16px' }}>
          <div>
            <label style={labelStyle}>Date de début</label>
            <input type="date" value={startDate}
              onChange={e => { setStartDate(e.target.value); setGenError(''); setGenResult(null) }}
              style={inputStyle} />
          </div>
          <div>
            <label style={labelStyle}>Date de fin</label>
            <input type="date" value={endDate} min={startDate || undefined}
              onChange={e => { setEndDate(e.target.value); setGenError(''); setGenResult(null) }}
              style={inputStyle} />
          </div>
        </div>

        <div style={{ marginBottom: '16px' }}>
          <label style={labelStyle}>Salles</label>
          <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', marginTop: '6px' }}>
            {rooms.map(room => (
              <label key={room.id} style={{ display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer', fontSize: '13px', color: '#0f172a', userSelect: 'none' }}>
                <input
                  type="checkbox"
                  checked={selectedRoomIds.includes(room.id)}
                  onChange={() => toggleRoom(room.id)}
                  style={{ cursor: 'pointer' }}
                />
                {room.name}
              </label>
            ))}
          </div>
        </div>

        {preview && (
          <div style={{ background: '#eff6ff', border: '0.5px solid #bfdbfe', borderRadius: '6px', padding: '10px 14px', fontSize: '12px', color: '#1e40af', marginBottom: '16px' }}>
            ~<strong>{preview.slots} créneaux</strong> / salle × {selectedRoomIds.length} salle(s) = ~<strong>{preview.slots * selectedRoomIds.length} créneaux</strong> au total
          </div>
        )}

        {genError    && <InlineError   msg={genError} />}
        {genProgress && <div style={{ color: '#2563eb', fontSize: '12px', marginTop: '8px' }}>{genProgress}</div>}
        {genResult   && (
          <InlineSuccess msg={`✓ ${genResult.created} session(s) créée(s) — ${genResult.totalSlots} créneaux générés`} />
        )}

        <div style={{ marginTop: '16px' }}>
          <button
            style={{ ...btnPrimary, opacity: (generating || !startDate || !endDate || selectedRoomIds.length === 0) ? 0.6 : 1 }}
            onClick={handleGenerate}
            disabled={generating || !startDate || !endDate || selectedRoomIds.length === 0}
          >
            {generating ? <><Spinner /> Génération…</> : 'Générer les créneaux'}
          </button>
        </div>
      </div>

      {/* Existing sessions */}
      <div>
        <h3 style={{ ...sectionTitle, marginBottom: '12px' }}>Sessions existantes ({sessions.length})</h3>

        {selectedSessionIds.size > 0 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '10px 14px', background: '#fef9c3', border: '0.5px solid #fde047', borderRadius: '6px', marginBottom: '12px' }}>
            <span style={{ fontSize: '13px', color: '#713f12', fontWeight: 500 }}>{selectedSessionIds.size} session(s) sélectionnée(s)</span>
            <button onClick={handleBulkDeleteSessions} disabled={deletingSessions}
              style={{ background: '#dc2626', color: '#fff', border: 'none', borderRadius: '6px', padding: '5px 12px', fontSize: '12px', fontWeight: 500, cursor: deletingSessions ? 'not-allowed' : 'pointer', opacity: deletingSessions ? 0.7 : 1, display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
              <Trash2 size={13} />{deletingSessions ? 'Suppression…' : 'Supprimer la sélection'}
            </button>
            <button onClick={() => setSelectedSessionIds(new Set())}
              style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '12px', color: '#92400e' }}>
              Désélectionner tout
            </button>
          </div>
        )}

        {loading ? <CenteredSpinner /> : sessions.length === 0 ? (
          <p style={{ color: '#94a3b8', fontSize: '13px' }}>Aucune session créée.</p>
        ) : (
          <div style={{ background: '#fff', border: '0.5px solid #e2e8f0', borderRadius: '10px', overflow: 'hidden' }}>
            <table style={tableStyle}>
              <thead>
                <tr>
                  <th style={{ ...thStyle, width: '36px', textAlign: 'center' }}>
                    <input type="checkbox" ref={sessHeaderRef} checked={allSessionsSelected}
                      onChange={handleSessHeaderCheckbox} style={{ cursor: 'pointer' }} />
                  </th>
                  <th style={thStyle}>ID</th>
                  <th style={thStyle}>Statut</th>
                  <th style={thStyle}>Début</th>
                  <th style={thStyle}>Fin</th>
                  <th style={thStyle} />
                </tr>
              </thead>
              <tbody>
                {sessions.map(s => (
                  <tr key={s.id}
                    onClick={() => toggleSessionSelection(s.id)}
                    style={{ cursor: 'pointer', background: selectedSessionIds.has(s.id) ? '#eff6ff' : undefined, transition: 'background 0.1s' }}
                    onMouseEnter={e => { if (!selectedSessionIds.has(s.id)) e.currentTarget.style.background = '#f8fafc' }}
                    onMouseLeave={e => { e.currentTarget.style.background = selectedSessionIds.has(s.id) ? '#eff6ff' : '' }}>
                    <td style={{ ...tdStyle, width: '36px', textAlign: 'center' }} onClick={e => e.stopPropagation()}>
                      <input type="checkbox" checked={selectedSessionIds.has(s.id)}
                        onChange={() => toggleSessionSelection(s.id)} style={{ cursor: 'pointer' }} />
                    </td>
                    <td style={{ ...tdStyle, color: '#64748b' }}>#{s.id}</td>
                    <td style={tdStyle}>
                      <span style={{ background: '#f0fdf4', color: '#166534', fontSize: '11px', padding: '2px 8px', borderRadius: '99px', border: '0.5px solid #bbf7d0' }}>
                        {s.status}
                      </span>
                    </td>
                    <td style={tdStyle}>{s.start_date}</td>
                    <td style={tdStyle}>{s.end_date}</td>
                    <td style={{ ...tdStyle, textAlign: 'right' }} onClick={e => e.stopPropagation()}>
                      <button style={{ ...btnIcon, color: '#ef4444' }} onClick={() => handleDeleteSession(s)} title="Supprimer">
                        <Trash2 size={14} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Tab 3: Salles ─────────────────────────────────────────────────────────────

function SallesTab() {
  const [rooms, setRooms]             = useState([])
  const [loading, setLoading]         = useState(true)
  const [showForm, setShowForm]       = useState(false)
  const [editingRoom, setEditingRoom] = useState(null)
  const [form, setForm]               = useState({ name: '' })
  const [formError, setFormError]     = useState('')
  const [saving, setSaving]           = useState(false)
  const [selectedRoomIds, setSelectedRoomIds] = useState(new Set())
  const [deletingRooms, setDeletingRooms]     = useState(false)

  useEffect(() => { load() }, [])

  async function load() {
    setLoading(true)
    try {
      const data = await apiRequest('/rooms')
      setRooms(Array.isArray(data) ? data : [])
    } catch { /* silent */ } finally {
      setLoading(false)
    }
  }

  function openAdd() {
    setEditingRoom(null)
    setForm({ name: '' })
    setFormError('')
    setShowForm(true)
  }

  function openEdit(room) {
    setEditingRoom(room)
    setForm({ name: room.name })
    setFormError('')
    setShowForm(true)
  }

  function closeForm() { setShowForm(false); setEditingRoom(null); setFormError('') }

  async function handleSave() {
    if (!form.name.trim()) { setFormError('Le nom est requis.'); return }
    setSaving(true)
    setFormError('')
    try {
      if (editingRoom) {
        await apiRequest(`/rooms/${editingRoom.id}`, { method: 'PUT', body: { name: form.name } })
      } else {
        await apiRequest('/rooms', { method: 'POST', body: { name: form.name } })
      }
      closeForm()
      await load()
    } catch (e) {
      setFormError(e.message || 'Erreur')
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete(room) {
    if (!window.confirm(`Supprimer la salle "${room.name}" ?`)) return
    try {
      await apiRequest(`/rooms/${room.id}`, { method: 'DELETE' })
      setSelectedRoomIds(prev => { const n = new Set(prev); n.delete(room.id); return n })
      await load()
    } catch (e) { alert(e.message || 'Erreur') }
  }

  function toggleRoomSelection(id) {
    setSelectedRoomIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id); else next.add(id)
      return next
    })
  }

  async function handleBulkDeleteRooms() {
    const n = selectedRoomIds.size
    if (!window.confirm(`Supprimer ${n} salle(s) ? Cette action est irréversible.`)) return
    setDeletingRooms(true)
    try {
      await Promise.all([...selectedRoomIds].map(id => apiRequest(`/rooms/${id}`, { method: 'DELETE' })))
      setSelectedRoomIds(new Set())
      await load()
    } catch (e) { alert(e.message || 'Erreur lors de la suppression') }
    finally { setDeletingRooms(false) }
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
        <h2 style={{ margin: 0, fontSize: '15px', fontWeight: 600, color: '#0f172a' }}>
          Salles ({rooms.length})
        </h2>
        <button style={btnPrimary} onClick={openAdd}>
          <Plus size={14} /> Ajouter une salle
        </button>
      </div>

      {showForm && (
        <div style={{ background: '#f8fafc', border: '0.5px solid #e2e8f0', borderRadius: '8px', padding: '16px', marginBottom: '16px' }}>
          <p style={{ margin: '0 0 10px 0', fontSize: '13px', fontWeight: 600, color: '#0f172a' }}>
            {editingRoom ? `Modifier "${editingRoom.name}"` : 'Nouvelle salle'}
          </p>
          <div style={{ display: 'flex', gap: '10px', alignItems: 'flex-start' }}>
            <input
              placeholder="Nom de la salle"
              value={form.name}
              onChange={e => setForm({ name: e.target.value })}
              onKeyDown={e => e.key === 'Enter' && handleSave()}
              style={{ ...inputStyle, flex: 1 }}
              autoFocus
            />
            <button style={btnPrimary} onClick={handleSave} disabled={saving}>
              {saving ? 'Sauvegarde…' : editingRoom ? 'Mettre à jour' : 'Créer'}
            </button>
            <button style={btnGhost} onClick={closeForm}>Annuler</button>
          </div>
          <InlineError msg={formError} />
        </div>
      )}

      {selectedRoomIds.size > 0 && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '10px 14px', background: '#fef9c3', border: '0.5px solid #fde047', borderRadius: '6px', marginBottom: '12px' }}>
          <span style={{ fontSize: '13px', color: '#713f12', fontWeight: 500 }}>{selectedRoomIds.size} salle(s) sélectionnée(s)</span>
          <button onClick={handleBulkDeleteRooms} disabled={deletingRooms}
            style={{ background: '#dc2626', color: '#fff', border: 'none', borderRadius: '6px', padding: '5px 12px', fontSize: '12px', fontWeight: 500, cursor: deletingRooms ? 'not-allowed' : 'pointer', opacity: deletingRooms ? 0.7 : 1, display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
            <Trash2 size={13} />{deletingRooms ? 'Suppression…' : 'Supprimer la sélection'}
          </button>
          <button onClick={() => setSelectedRoomIds(new Set())}
            style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '12px', color: '#92400e' }}>
            Désélectionner tout
          </button>
        </div>
      )}

      {loading ? <CenteredSpinner /> : rooms.length === 0 ? (
        <p style={{ color: '#94a3b8', fontSize: '13px' }}>Aucune salle. Cliquez sur "Ajouter une salle".</p>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
          {rooms.map(room => (
            <div key={room.id}
              onClick={() => toggleRoomSelection(room.id)}
              style={{ background: selectedRoomIds.has(room.id) ? '#eff6ff' : '#fff', border: selectedRoomIds.has(room.id) ? '0.5px solid #93c5fd' : '0.5px solid #e2e8f0', borderRadius: '10px', padding: '16px 20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: 'pointer', transition: 'background 0.1s, border-color 0.1s' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <input type="checkbox" checked={selectedRoomIds.has(room.id)}
                  onChange={() => toggleRoomSelection(room.id)}
                  onClick={e => e.stopPropagation()} style={{ cursor: 'pointer' }} />
                <DoorOpen size={20} style={{ color: '#94a3b8' }} />
                <span style={{ fontWeight: 600, fontSize: '14px', color: '#0f172a' }}>{room.name}</span>
              </div>
              <div style={{ display: 'flex', gap: '4px' }} onClick={e => e.stopPropagation()}>
                <button style={btnIcon} onClick={() => openEdit(room)} title="Modifier">
                  <Pencil size={14} />
                </button>
                <button style={{ ...btnIcon, color: '#ef4444' }} onClick={() => handleDelete(room)} title="Supprimer">
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Tab 4: Projets ────────────────────────────────────────────────────────────

function ProjetsTab() {
  const [projects, setProjects]                   = useState([])
  const [sessions, setSessions]                   = useState([])
  const [loading, setLoading]                     = useState(true)
  const [uploading, setUploading]                 = useState(false)
  const [uploadResult, setUploadResult]           = useState(null)
  const [uploadError, setUploadError]             = useState('')
  const [selectedFile, setSelectedFile]           = useState(null)
  const [selectedSessionId, setSelectedSessionId] = useState('')
  const [filterSessionId, setFilterSessionId]     = useState('')
  const [search, setSearch]                       = useState('')
  const [professors, setProfessors]               = useState([])
  const [students, setStudents]                   = useState([])
  const [domains, setDomains]                     = useState([])
  const [selectedProjectIds, setSelectedProjectIds] = useState(new Set())
  const [deleting, setDeleting]                   = useState(false)
  const [deleteResult, setDeleteResult]           = useState('')
  const headerCheckboxRef                         = useRef(null)

  useEffect(() => {
    Promise.all([
      apiRequest('/projects?limit=200').catch(() => []),
      apiRequest('/sessions?limit=50').catch(() => []),
      apiRequest('/professors?limit=200').catch(() => []),
      apiRequest('/students?limit=200').catch(() => []),
      apiRequest('/domains?limit=200').catch(() => []),
    ]).then(([projData, sessData, profData, studData, domData]) => {
      setProjects(Array.isArray(projData) ? projData : [])
      setSessions(Array.isArray(sessData) ? sessData : [])
      setProfessors(Array.isArray(profData) ? profData : [])
      setStudents(Array.isArray(studData) ? studData : [])
      setDomains(Array.isArray(domData) ? domData : [])
    }).finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    setSelectedProjectIds(new Set())
    setDeleteResult('')
  }, [filterSessionId])

  async function loadProjects() {
    try {
      const data = await apiRequest('/projects?limit=200')
      setProjects(Array.isArray(data) ? data : [])
    } catch { /* silent */ }
  }

  function handleSelectFile(e) {
    const file = e.target.files?.[0]
    if (file) { setSelectedFile(file); setUploadError(''); setUploadResult(null) }
    e.target.value = ''
  }

  async function handleImport() {
    if (!selectedSessionId) { setUploadError('Veuillez sélectionner une session.'); return }
    if (!selectedFile) { setUploadError('Choisissez un fichier.'); return }
    setUploading(true)
    setUploadError('')
    const fd = new FormData()
    fd.append('file', selectedFile)
    fd.append('session_id', selectedSessionId)
    try {
      const report = await apiRequest('/projects/import', { method: 'POST', body: fd })
      setUploadResult(report)
      setSelectedFile(null)
      await loadProjects()
    } catch (e) {
      setUploadError(e.message || "Erreur lors de l'import.")
    } finally {
      setUploading(false)
    }
  }

  async function handleDelete(project) {
    if (!window.confirm(`Supprimer le projet "${project.title}" ?`)) return
    try {
      await apiRequest(`/projects/${project.id}`, { method: 'DELETE' })
      setProjects(cur => cur.filter(p => p.id !== project.id))
    } catch (e) { alert(e.message || 'Erreur') }
  }

  function handleHeaderCheckbox() {
    if (allVisibleSelected) {
      setSelectedProjectIds(prev => {
        const next = new Set(prev)
        visibleIds.forEach(id => next.delete(id))
        return next
      })
    } else {
      setSelectedProjectIds(prev => new Set([...prev, ...visibleIds]))
    }
  }

  function toggleProjectSelection(id) {
    setSelectedProjectIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  function selectAllInSession() {
    const sid = parseInt(filterSessionId, 10)
    setSelectedProjectIds(new Set(projects.filter(p => p.session_id === sid).map(p => p.id)))
  }

  async function handleBulkDelete() {
    const n = selectedProjectIds.size
    if (!window.confirm(`Supprimer ${n} projet(s) sélectionné(s) ? Cette action est irréversible.`)) return
    setDeleting(true)
    setDeleteResult('')
    try {
      await Promise.all([...selectedProjectIds].map(id =>
        apiRequest(`/projects/${id}`, { method: 'DELETE' })
      ))
      await loadProjects()
      setSelectedProjectIds(new Set())
      setDeleteResult(`${n} projet(s) supprimé(s).`)
    } catch (e) {
      alert(e.message || 'Erreur lors de la suppression')
    } finally {
      setDeleting(false)
    }
  }

  const sortedSessions = [...sessions].sort((a, b) =>
    (b.start_date || '').localeCompare(a.start_date || '')
  )

  const professorMap = Object.fromEntries(professors.map(p => [p.id, p.name]))
  const studentMap   = Object.fromEntries(students.map(s => [s.id, s.name]))
  const domainMap    = Object.fromEntries(domains.map(d => [d.id, d.name]))
  const sessionMap   = Object.fromEntries(sessions.map(s => [s.id, `Session ${s.id} — ${s.start_date}`]))

  const filtered = projects
    .filter(p => filterSessionId === '' || p.session_id === parseInt(filterSessionId, 10))
    .filter(p => p.title.toLowerCase().includes(search.toLowerCase()))

  const visibleIds = filtered.map(p => p.id)
  const selectedVisibleCount = visibleIds.filter(id => selectedProjectIds.has(id)).length
  const allVisibleSelected = visibleIds.length > 0 && selectedVisibleCount === visibleIds.length

  useEffect(() => {
    if (!headerCheckboxRef.current) return
    headerCheckboxRef.current.indeterminate = selectedVisibleCount > 0 && !allVisibleSelected
  }, [selectedProjectIds, filtered])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>

      {/* Upload card */}
      <div style={cardStyle}>
        <h3 style={sectionTitle}>Importer les projets</h3>
        <p style={sectionSub}>
          Colonnes requises :&nbsp;
          <code style={{ background: '#f1f5f9', padding: '1px 5px', borderRadius: '4px', fontSize: '11px' }}>
            student_name, student_email, filiere, project_title, domain, supervisor_name
          </code>
          <br />
          Colonnes optionnelles :&nbsp;
          <code style={{ background: '#f1f5f9', padding: '1px 5px', borderRadius: '4px', fontSize: '11px' }}>
            enterprise, enterprise_supervisor
          </code>
          <br />
          Formats acceptés : .csv, .xlsx — Le superviseur doit exister dans la base de données (recherche par nom exact).
        </p>

        {/* Session selector */}
        <div style={{ marginBottom: '12px' }}>
          <label style={labelStyle}>Session</label>
          <select
            value={selectedSessionId}
            onChange={e => { setSelectedSessionId(e.target.value); setUploadError('') }}
            style={inputStyle}
          >
            <option value="">— Sélectionner une session —</option>
            {sortedSessions.map(s => (
              <option key={s.id} value={s.id}>
                Session {s.id} — {s.start_date} → {s.end_date}
              </option>
            ))}
          </select>
        </div>

        {selectedFile ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', background: '#f8fafc', border: '0.5px solid #e2e8f0', borderRadius: '6px', padding: '10px 14px', marginBottom: '12px' }}>
            <FileText size={16} style={{ color: '#2563eb', flexShrink: 0 }} />
            <span style={{ flex: 1, fontSize: '13px', color: '#0f172a', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{selectedFile.name}</span>
            <button style={btnIcon} onClick={() => { setSelectedFile(null); setUploadResult(null); setUploadError('') }}>
              <X size={14} />
            </button>
          </div>
        ) : (
          <label style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px', border: '2px dashed #e2e8f0', borderRadius: '8px', padding: '24px', cursor: 'pointer', marginBottom: '12px', transition: 'border-color 0.15s' }}
            onMouseEnter={e => { e.currentTarget.style.borderColor = '#93c5fd' }}
            onMouseLeave={e => { e.currentTarget.style.borderColor = '#e2e8f0' }}
          >
            <Upload size={24} style={{ color: '#94a3b8' }} />
            <span style={{ fontSize: '13px', color: '#64748b' }}>Glissez-déposez ou <span style={{ color: '#2563eb', fontWeight: 500 }}>parcourez</span></span>
            <span style={{ fontSize: '11px', color: '#94a3b8' }}>.CSV ou .XLSX</span>
            <input type="file" accept=".csv,.xlsx" style={{ display: 'none' }} onChange={handleSelectFile} />
          </label>
        )}

        <InlineError msg={uploadError} />

        {uploadResult && (
          <div style={{ marginTop: '8px' }}>
            <InlineSuccess msg={`✓ ${uploadResult.created ?? 0} projet(s) créé(s)${(uploadResult.skipped ?? 0) > 0 ? ` · ${uploadResult.skipped} ligne(s) ignorée(s)` : ''}`} />
            {uploadResult.issues && uploadResult.issues.length > 0 && (
              <div style={{ marginTop: '6px', display: 'flex', flexDirection: 'column', gap: '3px' }}>
                {uploadResult.issues.map((issue, i) => (
                  <div key={i} style={{ color: '#92400e', fontSize: '12px', background: '#fffbeb', border: '0.5px solid #fde68a', borderRadius: '6px', padding: '6px 12px', display: 'flex', alignItems: 'flex-start', gap: '6px' }}>
                    <AlertTriangle size={13} style={{ flexShrink: 0, marginTop: '1px' }} />
                    {issue}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        <div style={{ marginTop: '12px', display: 'flex', gap: '8px', alignItems: 'center' }}>
          <button
            style={{ ...btnPrimary, opacity: (!selectedFile || uploading) ? 0.6 : 1 }}
            onClick={handleImport}
            disabled={uploading || !selectedFile}
          >
            {uploading ? <><Spinner /> Import en cours…</> : 'Importer'}
          </button>
          <button style={btnGhost} onClick={() => downloadCsv('projects_template.csv', [
            'student_name,student_email,filiere,project_title,domain,supervisor_name,enterprise,enterprise_supervisor',
            'Marie Curie,marie.curie@gmail.com,GL,Système de planification,Génie Logiciel,Prof. Martin,LabCo,Jean Martin',
          ])}>
            <Download size={14} /> Modèle CSV
          </button>
        </div>
      </div>

      {/* Projects list */}
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
          <h3 style={{ ...sectionTitle, marginBottom: 0 }}>Projets existants ({projects.length})</h3>
          <div style={{ position: 'relative' }}>
            <Search size={13} style={{ position: 'absolute', left: '8px', top: '50%', transform: 'translateY(-50%)', color: '#94a3b8', pointerEvents: 'none' }} />
            <input
              placeholder="Rechercher par titre…"
              value={search}
              onChange={e => setSearch(e.target.value)}
              style={{ ...inputStyle, paddingLeft: '28px', width: '220px' }}
            />
          </div>
        </div>

        {/* Session filter */}
        <div style={{ display: 'flex', alignItems: 'flex-end', gap: '12px', marginBottom: '12px' }}>
          <div style={{ flex: '0 0 300px' }}>
            <label style={labelStyle}>Filtrer par session</label>
            <select
              value={filterSessionId}
              onChange={e => setFilterSessionId(e.target.value)}
              style={inputStyle}
            >
              <option value="">Toutes les sessions</option>
              {sortedSessions.map(s => (
                <option key={s.id} value={s.id}>
                  Session {s.id} — {s.start_date} → {s.end_date}
                </option>
              ))}
            </select>
          </div>
          <span style={{ fontSize: '12px', color: '#94a3b8', paddingBottom: '8px' }}>
            {filtered.length} projet(s) affiché(s)
          </span>
          {filterSessionId && (
            <button
              onClick={selectAllInSession}
              style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '12px', color: '#2563eb', fontWeight: 500, paddingBottom: '8px' }}
            >
              Tout sélectionner ({projects.filter(p => p.session_id === parseInt(filterSessionId, 10)).length})
            </button>
          )}
        </div>

        {deleteResult && <InlineSuccess msg={`✓ ${deleteResult}`} />}

        {selectedProjectIds.size > 0 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '10px 14px', background: '#fef9c3', border: '0.5px solid #fde047', borderRadius: '6px', marginBottom: '12px' }}>
            <span style={{ fontSize: '13px', color: '#713f12', fontWeight: 500 }}>
              {selectedProjectIds.size} projet(s) sélectionné(s)
            </span>
            <button
              onClick={handleBulkDelete}
              disabled={deleting}
              style={{ background: '#dc2626', color: '#fff', border: 'none', borderRadius: '6px', padding: '5px 12px', fontSize: '12px', fontWeight: 500, cursor: deleting ? 'not-allowed' : 'pointer', opacity: deleting ? 0.7 : 1, display: 'inline-flex', alignItems: 'center', gap: '4px' }}
            >
              <Trash2 size={13} />
              {deleting ? 'Suppression en cours…' : 'Supprimer la sélection'}
            </button>
            <button
              onClick={() => setSelectedProjectIds(new Set())}
              style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '12px', color: '#92400e' }}
            >
              Désélectionner tout
            </button>
          </div>
        )}

        {loading ? <CenteredSpinner /> : (
          <div style={{ background: '#fff', border: '0.5px solid #e2e8f0', borderRadius: '10px', overflow: 'hidden' }}>
            <table style={tableStyle}>
              <thead>
                <tr>
                  <th style={{ ...thStyle, width: '36px', textAlign: 'center' }}>
                    <input
                      type="checkbox"
                      ref={headerCheckboxRef}
                      checked={allVisibleSelected}
                      onChange={handleHeaderCheckbox}
                      style={{ cursor: 'pointer' }}
                    />
                  </th>
                  <th style={thStyle}>Titre</th>
                  <th style={thStyle}>Étudiant</th>
                  <th style={thStyle}>Superviseur</th>
                  <th style={thStyle}>Domaine</th>
                  <th style={thStyle}>Session</th>
                  <th style={thStyle} />
                </tr>
              </thead>
              <tbody>
                {filtered.length === 0 ? (
                  <tr><td colSpan={7} style={{ ...tdStyle, textAlign: 'center', color: '#94a3b8' }}>Aucun projet</td></tr>
                ) : filtered.map(p => (
                  <tr key={p.id}
                    onClick={() => toggleProjectSelection(p.id)}
                    style={{ cursor: 'pointer' }}
                    onMouseEnter={e => { e.currentTarget.style.background = selectedProjectIds.has(p.id) ? '#eff6ff' : '#f8fafc' }}
                    onMouseLeave={e => { e.currentTarget.style.background = selectedProjectIds.has(p.id) ? '#eff6ff' : '' }}>
                    <td style={{ ...tdStyle, width: '36px', textAlign: 'center' }} onClick={e => e.stopPropagation()}>
                      <input
                        type="checkbox"
                        checked={selectedProjectIds.has(p.id)}
                        onChange={() => toggleProjectSelection(p.id)}
                        style={{ cursor: 'pointer' }}
                      />
                    </td>
                    <td style={{ ...tdStyle, maxWidth: '320px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontWeight: 500 }}
                      title={p.title}>{p.title}</td>
                    <td style={{ ...tdStyle, color: '#64748b' }}>{studentMap[p.student_id] ?? `#${p.student_id}`}</td>
                    <td style={{ ...tdStyle, color: '#64748b' }}>{professorMap[p.supervisor_id] ?? `#${p.supervisor_id}`}</td>
                    <td style={{ ...tdStyle, color: '#64748b' }}>
                      {(p.domain_ids || []).length === 0
                        ? '—'
                        : (p.domain_ids || []).map(id => domainMap[id] ?? `#${id}`).join(', ')
                      }
                    </td>
                    <td style={{ ...tdStyle, color: '#64748b' }}>{sessionMap[p.session_id] ?? '—'}</td>
                    <td style={{ ...tdStyle, textAlign: 'right' }} onClick={e => e.stopPropagation()}>
                      <button style={{ ...btnIcon, color: '#ef4444' }} onClick={() => handleDelete(p)} title="Supprimer">
                        <Trash2 size={14} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Tab 5: Indisponibilités ───────────────────────────────────────────────────

const PERIOD_LABELS = { morning: 'Matin', afternoon: 'Après-midi', full_day: 'Journée entière' }
const UNAVAIL_EMPTY = { professor_id: '', date: '', period: 'morning' }

function IndisponibilitesTab() {
  const [unavailabilities, setUnavailabilities] = useState([])
  const [professors, setProfessors]             = useState([])
  const [loading, setLoading]                   = useState(true)
  const [error, setError]                       = useState('')
  const [showForm, setShowForm]                 = useState(false)
  const [form, setForm]                         = useState(UNAVAIL_EMPTY)
  const [formError, setFormError]               = useState('')
  const [saving, setSaving]                     = useState(false)
  const [selectedUnavailIds, setSelectedUnavailIds] = useState(new Set())
  const [deletingUnavails, setDeletingUnavails]     = useState(false)
  const unavailHeaderRef = useRef(null)

  useEffect(() => { load() }, [])

  async function load() {
    setLoading(true)
    setError('')
    try {
      const [uData, pData] = await Promise.all([
        apiRequest('/unavailabilities?limit=200'),
        apiRequest('/professors?limit=200'),
      ])
      setUnavailabilities(Array.isArray(uData) ? uData : [])
      setProfessors(Array.isArray(pData) ? pData : [])
    } catch (e) {
      setError(e.message || 'Erreur de chargement')
    } finally {
      setLoading(false)
    }
  }

  function openAdd() { setForm(UNAVAIL_EMPTY); setFormError(''); setShowForm(true) }
  function closeForm() { setShowForm(false); setFormError('') }

  async function handleSave() {
    if (!form.professor_id || !form.date || !form.period) {
      setFormError('Tous les champs sont requis.')
      return
    }
    setSaving(true)
    setFormError('')
    try {
      await apiRequest('/unavailabilities', {
        method: 'POST',
        body: { professor_id: Number(form.professor_id), date: form.date, period: form.period },
      })
      closeForm()
      await load()
    } catch (e) {
      setFormError(e.message || 'Erreur lors de la sauvegarde')
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete(item) {
    if (!window.confirm('Supprimer cette indisponibilité ?')) return
    try {
      await apiRequest(`/unavailabilities/${item.id}`, { method: 'DELETE' })
      setSelectedUnavailIds(prev => { const n = new Set(prev); n.delete(item.id); return n })
      await load()
    } catch (e) {
      setError(e.message || 'Erreur lors de la suppression')
    }
  }

  function toggleUnavailSelection(id) {
    setSelectedUnavailIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id); else next.add(id)
      return next
    })
  }

  function handleUnavailHeaderCheckbox() {
    const allSel = sorted.every(u => selectedUnavailIds.has(u.id))
    if (allSel) {
      setSelectedUnavailIds(prev => { const n = new Set(prev); sorted.forEach(u => n.delete(u.id)); return n })
    } else {
      setSelectedUnavailIds(prev => new Set([...prev, ...sorted.map(u => u.id)]))
    }
  }

  async function handleBulkDeleteUnavails() {
    const n = selectedUnavailIds.size
    if (!window.confirm(`Supprimer ${n} indisponibilité(s) ?`)) return
    setDeletingUnavails(true)
    try {
      await Promise.all([...selectedUnavailIds].map(id => apiRequest(`/unavailabilities/${id}`, { method: 'DELETE' })))
      setSelectedUnavailIds(new Set())
      await load()
    } catch (e) { setError(e.message || 'Erreur') }
    finally { setDeletingUnavails(false) }
  }

  const profMap = new Map(professors.map(p => [p.id, p.name]))
  const sorted  = [...unavailabilities].sort((a, b) => {
    const na = profMap.get(a.professor_id) ?? ''
    const nb = profMap.get(b.professor_id) ?? ''
    return na.localeCompare(nb) || a.date.localeCompare(b.date)
  })
  const allUnavailSelected  = sorted.length > 0 && sorted.every(u => selectedUnavailIds.has(u.id))
  const someUnavailSelected = sorted.some(u => selectedUnavailIds.has(u.id))

  useEffect(() => {
    if (!unavailHeaderRef.current) return
    unavailHeaderRef.current.indeterminate = someUnavailSelected && !allUnavailSelected
  }, [selectedUnavailIds, sorted.length])

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
        <h2 style={{ margin: 0, fontSize: '15px', fontWeight: 600, color: '#0f172a' }}>
          Indisponibilités ({unavailabilities.length})
        </h2>
        <button style={btnPrimary} onClick={openAdd}>
          <Plus size={14} /> Ajouter
        </button>
      </div>

      {showForm && (
        <div style={{ background: '#f8fafc', border: '0.5px solid #e2e8f0', borderRadius: '8px', padding: '16px', marginBottom: '16px' }}>
          <p style={{ margin: '0 0 12px 0', fontSize: '13px', fontWeight: 600, color: '#0f172a' }}>Nouvelle indisponibilité</p>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '10px', marginBottom: '12px' }}>
            <div>
              <label style={labelStyle}>Professeur</label>
              <select
                value={form.professor_id}
                onChange={e => setForm(f => ({ ...f, professor_id: e.target.value }))}
                style={inputStyle}
              >
                <option value="">— Choisir —</option>
                {professors.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
            </div>
            <div>
              <label style={labelStyle}>Date</label>
              <input
                type="date"
                value={form.date}
                onChange={e => setForm(f => ({ ...f, date: e.target.value }))}
                style={inputStyle}
              />
            </div>
            <div>
              <label style={labelStyle}>Période</label>
              <select
                value={form.period}
                onChange={e => setForm(f => ({ ...f, period: e.target.value }))}
                style={inputStyle}
              >
                <option value="morning">Matin</option>
                <option value="afternoon">Après-midi</option>
                <option value="full_day">Journée entière</option>
              </select>
            </div>
          </div>
          <InlineError msg={formError} />
          <div style={{ display: 'flex', gap: '8px', marginTop: '12px' }}>
            <button style={btnPrimary} onClick={handleSave} disabled={saving}>
              {saving ? 'Sauvegarde…' : 'Créer'}
            </button>
            <button style={btnGhost} onClick={closeForm}>Annuler</button>
          </div>
        </div>
      )}

      <InlineError msg={error} />

      {selectedUnavailIds.size > 0 && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '10px 14px', background: '#fef9c3', border: '0.5px solid #fde047', borderRadius: '6px', marginBottom: '12px' }}>
          <span style={{ fontSize: '13px', color: '#713f12', fontWeight: 500 }}>{selectedUnavailIds.size} indisponibilité(s) sélectionnée(s)</span>
          <button onClick={handleBulkDeleteUnavails} disabled={deletingUnavails}
            style={{ background: '#dc2626', color: '#fff', border: 'none', borderRadius: '6px', padding: '5px 12px', fontSize: '12px', fontWeight: 500, cursor: deletingUnavails ? 'not-allowed' : 'pointer', opacity: deletingUnavails ? 0.7 : 1, display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
            <Trash2 size={13} />{deletingUnavails ? 'Suppression…' : 'Supprimer la sélection'}
          </button>
          <button onClick={() => setSelectedUnavailIds(new Set())}
            style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '12px', color: '#92400e' }}>
            Désélectionner tout
          </button>
        </div>
      )}

      {loading ? <CenteredSpinner /> : (
        <div style={{ background: '#fff', border: '0.5px solid #e2e8f0', borderRadius: '10px', overflow: 'hidden' }}>
          <table style={tableStyle}>
            <thead>
              <tr>
                <th style={{ ...thStyle, width: '36px', textAlign: 'center' }}>
                  <input type="checkbox" ref={unavailHeaderRef} checked={allUnavailSelected}
                    onChange={handleUnavailHeaderCheckbox} style={{ cursor: 'pointer' }} />
                </th>
                <th style={thStyle}>Professeur</th>
                <th style={thStyle}>Date</th>
                <th style={thStyle}>Période</th>
                <th style={thStyle} />
              </tr>
            </thead>
            <tbody>
              {sorted.length === 0 ? (
                <tr><td colSpan={5} style={{ ...tdStyle, textAlign: 'center', color: '#94a3b8' }}>Aucune indisponibilité</td></tr>
              ) : sorted.map(item => (
                <tr key={item.id}
                  onClick={() => toggleUnavailSelection(item.id)}
                  style={{ cursor: 'pointer', background: selectedUnavailIds.has(item.id) ? '#eff6ff' : undefined, transition: 'background 0.1s' }}
                  onMouseEnter={e => { if (!selectedUnavailIds.has(item.id)) e.currentTarget.style.background = '#f8fafc' }}
                  onMouseLeave={e => { e.currentTarget.style.background = selectedUnavailIds.has(item.id) ? '#eff6ff' : '' }}>
                  <td style={{ ...tdStyle, width: '36px', textAlign: 'center' }} onClick={e => e.stopPropagation()}>
                    <input type="checkbox" checked={selectedUnavailIds.has(item.id)}
                      onChange={() => toggleUnavailSelection(item.id)} style={{ cursor: 'pointer' }} />
                  </td>
                  <td style={{ ...tdStyle, fontWeight: 500 }}>{profMap.get(item.professor_id) ?? `#${item.professor_id}`}</td>
                  <td style={tdStyle}>{item.date}</td>
                  <td style={tdStyle}>{PERIOD_LABELS[item.period] ?? item.period}</td>
                  <td style={{ ...tdStyle, textAlign: 'right' }} onClick={e => e.stopPropagation()}>
                    <button style={{ ...btnIcon, color: '#ef4444' }} onClick={() => handleDelete(item)} title="Supprimer">
                      <Trash2 size={14} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ── Tab 6: Conflits ───────────────────────────────────────────────────────────

const CONFLICT_EMPTY = { professor_a: '', professor_b: '' }

function ConflitsTab() {
  const [conflicts, setConflicts]   = useState([])
  const [professors, setProfessors] = useState([])
  const [loading, setLoading]       = useState(true)
  const [error, setError]           = useState('')
  const [showForm, setShowForm]     = useState(false)
  const [form, setForm]             = useState(CONFLICT_EMPTY)
  const [formError, setFormError]   = useState('')
  const [saving, setSaving]         = useState(false)
  const [selectedConflictIds, setSelectedConflictIds] = useState(new Set())
  const [deletingConflicts, setDeletingConflicts]     = useState(false)
  const conflictHeaderRef = useRef(null)

  useEffect(() => { load() }, [])

  async function load() {
    setLoading(true)
    setError('')
    try {
      const [cData, pData] = await Promise.all([
        apiRequest('/conflicts/resolved'),
        apiRequest('/professors?limit=200'),
      ])
      setConflicts(Array.isArray(cData) ? cData : [])
      setProfessors(Array.isArray(pData) ? pData : [])
    } catch (e) {
      setError(e.message || 'Erreur de chargement')
    } finally {
      setLoading(false)
    }
  }

  function openAdd() { setForm(CONFLICT_EMPTY); setFormError(''); setShowForm(true) }
  function closeForm() { setShowForm(false); setFormError('') }

  async function handleSave() {
    if (!form.professor_a || !form.professor_b) {
      setFormError('Sélectionnez les deux professeurs.')
      return
    }
    if (form.professor_a === form.professor_b) {
      setFormError('Les deux professeurs doivent être différents.')
      return
    }
    setSaving(true)
    setFormError('')
    try {
      await apiRequest('/conflicts/safe-create', {
        method: 'POST',
        body: { professor_a: Number(form.professor_a), professor_b: Number(form.professor_b) },
      })
      closeForm()
      await load()
    } catch (e) {
      setFormError(e.message || 'Erreur lors de la sauvegarde')
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete(item) {
    if (!window.confirm('Supprimer ce conflit ?')) return
    try {
      await apiRequest(`/conflicts/${item.id}`, { method: 'DELETE' })
      setSelectedConflictIds(prev => { const n = new Set(prev); n.delete(item.id); return n })
      await load()
    } catch (e) {
      setError(e.message || 'Erreur lors de la suppression')
    }
  }

  function toggleConflictSelection(id) {
    setSelectedConflictIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id); else next.add(id)
      return next
    })
  }

  function handleConflictHeaderCheckbox() {
    const allSel = conflicts.every(c => selectedConflictIds.has(c.id))
    if (allSel) {
      setSelectedConflictIds(prev => { const n = new Set(prev); conflicts.forEach(c => n.delete(c.id)); return n })
    } else {
      setSelectedConflictIds(prev => new Set([...prev, ...conflicts.map(c => c.id)]))
    }
  }

  async function handleBulkDeleteConflicts() {
    const n = selectedConflictIds.size
    if (!window.confirm(`Supprimer ${n} conflit(s) ?`)) return
    setDeletingConflicts(true)
    try {
      await Promise.all([...selectedConflictIds].map(id => apiRequest(`/conflicts/${id}`, { method: 'DELETE' })))
      setSelectedConflictIds(new Set())
      await load()
    } catch (e) { setError(e.message || 'Erreur') }
    finally { setDeletingConflicts(false) }
  }

  const allConflictsSelected  = conflicts.length > 0 && conflicts.every(c => selectedConflictIds.has(c.id))
  const someConflictsSelected = conflicts.some(c => selectedConflictIds.has(c.id))

  useEffect(() => {
    if (!conflictHeaderRef.current) return
    conflictHeaderRef.current.indeterminate = someConflictsSelected && !allConflictsSelected
  }, [selectedConflictIds, conflicts.length])

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
        <h2 style={{ margin: 0, fontSize: '15px', fontWeight: 600, color: '#0f172a' }}>
          Conflits ({conflicts.length})
        </h2>
        <button style={btnPrimary} onClick={openAdd}>
          <Plus size={14} /> Ajouter un conflit
        </button>
      </div>

      {showForm && (
        <div style={{ background: '#f8fafc', border: '0.5px solid #e2e8f0', borderRadius: '8px', padding: '16px', marginBottom: '16px' }}>
          <p style={{ margin: '0 0 12px 0', fontSize: '13px', fontWeight: 600, color: '#0f172a' }}>Nouveau conflit</p>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginBottom: '12px' }}>
            <div>
              <label style={labelStyle}>Professeur A</label>
              <select
                value={form.professor_a}
                onChange={e => setForm(f => ({ ...f, professor_a: e.target.value }))}
                style={inputStyle}
              >
                <option value="">— Choisir —</option>
                {professors.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
            </div>
            <div>
              <label style={labelStyle}>Professeur B</label>
              <select
                value={form.professor_b}
                onChange={e => setForm(f => ({ ...f, professor_b: e.target.value }))}
                style={inputStyle}
              >
                <option value="">— Choisir —</option>
                {professors.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
            </div>
          </div>
          <InlineError msg={formError} />
          <div style={{ display: 'flex', gap: '8px', marginTop: '12px' }}>
            <button style={btnPrimary} onClick={handleSave} disabled={saving}>
              {saving ? 'Sauvegarde…' : 'Ajouter le conflit'}
            </button>
            <button style={btnGhost} onClick={closeForm}>Annuler</button>
          </div>
        </div>
      )}

      <InlineError msg={error} />

      {selectedConflictIds.size > 0 && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '10px 14px', background: '#fef9c3', border: '0.5px solid #fde047', borderRadius: '6px', marginBottom: '12px' }}>
          <span style={{ fontSize: '13px', color: '#713f12', fontWeight: 500 }}>{selectedConflictIds.size} conflit(s) sélectionné(s)</span>
          <button onClick={handleBulkDeleteConflicts} disabled={deletingConflicts}
            style={{ background: '#dc2626', color: '#fff', border: 'none', borderRadius: '6px', padding: '5px 12px', fontSize: '12px', fontWeight: 500, cursor: deletingConflicts ? 'not-allowed' : 'pointer', opacity: deletingConflicts ? 0.7 : 1, display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
            <Trash2 size={13} />{deletingConflicts ? 'Suppression…' : 'Supprimer la sélection'}
          </button>
          <button onClick={() => setSelectedConflictIds(new Set())}
            style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '12px', color: '#92400e' }}>
            Désélectionner tout
          </button>
        </div>
      )}

      {loading ? <CenteredSpinner /> : (
        <div style={{ background: '#fff', border: '0.5px solid #e2e8f0', borderRadius: '10px', overflow: 'hidden' }}>
          <table style={tableStyle}>
            <thead>
              <tr>
                <th style={{ ...thStyle, width: '36px', textAlign: 'center' }}>
                  <input type="checkbox" ref={conflictHeaderRef} checked={allConflictsSelected}
                    onChange={handleConflictHeaderCheckbox} style={{ cursor: 'pointer' }} />
                </th>
                <th style={thStyle}>Professeur A</th>
                <th style={thStyle}>Professeur B</th>
                <th style={thStyle} />
              </tr>
            </thead>
            <tbody>
              {conflicts.length === 0 ? (
                <tr><td colSpan={4} style={{ ...tdStyle, textAlign: 'center', color: '#94a3b8' }}>Aucun conflit enregistré</td></tr>
              ) : conflicts.map(item => (
                <tr key={item.id}
                  onClick={() => toggleConflictSelection(item.id)}
                  style={{ cursor: 'pointer', background: selectedConflictIds.has(item.id) ? '#eff6ff' : undefined, transition: 'background 0.1s' }}
                  onMouseEnter={e => { if (!selectedConflictIds.has(item.id)) e.currentTarget.style.background = '#f8fafc' }}
                  onMouseLeave={e => { e.currentTarget.style.background = selectedConflictIds.has(item.id) ? '#eff6ff' : '' }}>
                  <td style={{ ...tdStyle, width: '36px', textAlign: 'center' }} onClick={e => e.stopPropagation()}>
                    <input type="checkbox" checked={selectedConflictIds.has(item.id)}
                      onChange={() => toggleConflictSelection(item.id)} style={{ cursor: 'pointer' }} />
                  </td>
                  <td style={{ ...tdStyle, fontWeight: 500 }}>{item.professor_a_name}</td>
                  <td style={{ ...tdStyle, fontWeight: 500 }}>{item.professor_b_name}</td>
                  <td style={{ ...tdStyle, textAlign: 'right' }} onClick={e => e.stopPropagation()}>
                    <button style={{ ...btnIcon, color: '#ef4444' }} onClick={() => handleDelete(item)} title="Supprimer">
                      <Trash2 size={14} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ── Root component ────────────────────────────────────────────────────────────

const TABS = [
  { id: 'professors',       label: 'Professeurs',      Icon: Users },
  { id: 'sessions',         label: 'Sessions',         Icon: Calendar },
  { id: 'rooms',            label: 'Salles',           Icon: DoorOpen },
  { id: 'projects',         label: 'Projets',          Icon: FileText },
  { id: 'indisponibilites', label: 'Indisponibilités', Icon: Clock },
  { id: 'conflits',         label: 'Conflits',         Icon: AlertTriangle },
]

export default function Donnees() {
  const [activeTab, setActiveTab] = useState('professors')

  return (
    <div style={{ padding: '24px', maxWidth: '1100px', margin: '0 auto' }}>

      {/* Tab bar */}
      <div style={{ display: 'flex', gap: '4px', borderBottom: '0.5px solid #e2e8f0', marginBottom: '24px' }}>
        {TABS.map(({ id, label, Icon }) => {
          const active = activeTab === id
          return (
            <button key={id} onClick={() => setActiveTab(id)} style={{
              padding: '8px 18px', border: 'none', background: 'none', cursor: 'pointer',
              borderBottom: active ? '2px solid #2563eb' : '2px solid transparent',
              color: active ? '#2563eb' : '#64748b',
              fontWeight: active ? 600 : 400,
              fontSize: '14px', marginBottom: '-1px',
              display: 'flex', alignItems: 'center', gap: '6px',
              transition: 'color 0.15s',
            }}>
              <Icon size={15} aria-hidden />
              {label}
            </button>
          )
        })}
      </div>

      {activeTab === 'professors'       && <ProfesseursTab />}
      {activeTab === 'sessions'         && <SessionsTab />}
      {activeTab === 'rooms'            && <SallesTab />}
      {activeTab === 'projects'         && <ProjetsTab />}
      {activeTab === 'indisponibilites' && <IndisponibilitesTab />}
      {activeTab === 'conflits'         && <ConflitsTab />}
    </div>
  )
}
