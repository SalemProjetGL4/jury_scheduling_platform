import { useState, useEffect } from 'react'
import {
  Users, Calendar, DoorOpen, FileText,
  Pencil, Trash2, Loader2, Plus, Search, X, Upload,
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

// ── Tab 1: Professeurs ────────────────────────────────────────────────────────

const PROF_EMPTY = { name: '', email: '', department_id: '', max_juries: 3 }

function ProfesseursTab() {
  const [professors, setProfessors] = useState([])
  const [loading, setLoading]       = useState(true)
  const [error, setError]           = useState('')
  const [search, setSearch]         = useState('')
  const [showForm, setShowForm]     = useState(false)
  const [editingProf, setEditingProf] = useState(null)
  const [form, setForm]             = useState(PROF_EMPTY)
  const [formError, setFormError]   = useState('')
  const [saving, setSaving]         = useState(false)

  useEffect(() => { load() }, [])

  async function load() {
    setLoading(true)
    setError('')
    try {
      const data = await apiRequest('/professors?limit=200')
      setProfessors(Array.isArray(data) ? data : [])
    } catch (e) {
      setError(e.message || 'Erreur de chargement')
    } finally {
      setLoading(false)
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
    setForm({ name: prof.name, email: prof.email, department_id: prof.department_id, max_juries: prof.max_juries })
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
      } else {
        await apiRequest('/professors', { method: 'POST', body: payload })
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
      await load()
    } catch (e) {
      setError(e.message || 'Erreur lors de la suppression')
    }
  }

  const filtered = professors.filter(p =>
    p.name.toLowerCase().includes(search.toLowerCase()) ||
    p.email.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
        <h2 style={{ margin: 0, fontSize: '15px', fontWeight: 600, color: '#0f172a' }}>
          Professeurs ({professors.length})
        </h2>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <div style={{ position: 'relative' }}>
            <Search size={13} style={{ position: 'absolute', left: '8px', top: '50%', transform: 'translateY(-50%)', color: '#94a3b8', pointerEvents: 'none' }} />
            <input
              placeholder="Rechercher..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              style={{ ...inputStyle, paddingLeft: '28px', width: '200px' }}
            />
          </div>
          <button style={btnPrimary} onClick={openAdd}>
            <Plus size={14} /> Ajouter
          </button>
        </div>
      </div>

      {/* Inline form */}
      {showForm && (
        <div style={{ background: '#f8fafc', border: '0.5px solid #e2e8f0', borderRadius: '8px', padding: '16px', marginBottom: '16px' }}>
          <p style={{ margin: '0 0 12px 0', fontSize: '13px', fontWeight: 600, color: '#0f172a' }}>
            {editingProf ? `Modifier ${editingProf.name}` : 'Nouveau professeur'}
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: '10px', marginBottom: '12px' }}>
            <input placeholder="Nom complet"    value={form.name}          onChange={field('name')}          style={inputStyle} />
            <input placeholder="Email"          value={form.email}         onChange={field('email')}         style={inputStyle} type="email" />
            <input placeholder="Department ID"  value={form.department_id} onChange={field('department_id')} style={inputStyle} type="number" min="1" />
            <input placeholder="Max jurys"      value={form.max_juries}    onChange={field('max_juries')}    style={inputStyle} type="number" min="0" />
          </div>
          <InlineError msg={formError} />
          <div style={{ display: 'flex', gap: '8px', marginTop: '12px' }}>
            <button style={btnPrimary} onClick={handleSave} disabled={saving}>
              {saving ? 'Sauvegarde…' : editingProf ? 'Mettre à jour' : 'Créer'}
            </button>
            <button style={btnGhost} onClick={closeForm}>Annuler</button>
          </div>
        </div>
      )}

      <InlineError msg={error} />

      {loading ? <CenteredSpinner /> : (
        <div style={{ background: '#fff', border: '0.5px solid #e2e8f0', borderRadius: '10px', overflow: 'hidden' }}>
          <table style={tableStyle}>
            <thead>
              <tr>
                <th style={thStyle}>Nom</th>
                <th style={thStyle}>Email</th>
                <th style={thStyle}>Département</th>
                <th style={thStyle}>Max jurys</th>
                <th style={thStyle} />
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 ? (
                <tr><td colSpan={5} style={{ ...tdStyle, textAlign: 'center', color: '#94a3b8' }}>Aucun résultat</td></tr>
              ) : filtered.map(prof => (
                <tr key={prof.id} style={{ transition: 'background 0.1s' }}
                  onMouseEnter={e => { e.currentTarget.style.background = '#f8fafc' }}
                  onMouseLeave={e => { e.currentTarget.style.background = '' }}>
                  <td style={{ ...tdStyle, fontWeight: 500 }}>{prof.name}</td>
                  <td style={{ ...tdStyle, color: '#64748b' }}>{prof.email}</td>
                  <td style={tdStyle}>{prof.department_id}</td>
                  <td style={tdStyle}>{prof.max_juries}</td>
                  <td style={{ ...tdStyle, textAlign: 'right', whiteSpace: 'nowrap' }}>
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
    let totalSlots = 0, created = 0
    for (let i = 0; i < selectedRoomIds.length; i++) {
      const roomId = selectedRoomIds[i]
      const room = rooms.find(r => r.id === roomId)
      setGenProgress(`Salle ${i + 1}/${selectedRoomIds.length} (${room?.name ?? roomId})…`)
      try {
        const res = await apiRequest('/sessions/generate-slots', {
          method: 'POST',
          body: { start_date: startDate, end_date: endDate, room_id: roomId },
        })
        totalSlots += res.slots_created || 0
        created++
      } catch (e) {
        setGenError(`Erreur pour ${room?.name ?? roomId} : ${e.message}`)
        setGenerating(false)
        setGenProgress('')
        return
      }
    }
    setGenProgress('')
    setGenResult({ created, totalSlots })
    setGenerating(false)
    const updated = await apiRequest('/sessions?limit=50').catch(() => null)
    if (Array.isArray(updated)) setSessions(updated)
  }

  async function handleDeleteSession(s) {
    if (!window.confirm(`Supprimer la session #${s.id} (${s.start_date} → ${s.end_date}) ?`)) return
    try {
      await apiRequest(`/sessions/${s.id}`, { method: 'DELETE' })
      setSessions(cur => cur.filter(x => x.id !== s.id))
    } catch (e) {
      alert(e.message || 'Erreur lors de la suppression')
    }
  }

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
        {loading ? <CenteredSpinner /> : sessions.length === 0 ? (
          <p style={{ color: '#94a3b8', fontSize: '13px' }}>Aucune session créée.</p>
        ) : (
          <div style={{ background: '#fff', border: '0.5px solid #e2e8f0', borderRadius: '10px', overflow: 'hidden' }}>
            <table style={tableStyle}>
              <thead>
                <tr>
                  <th style={thStyle}>ID</th>
                  <th style={thStyle}>Statut</th>
                  <th style={thStyle}>Début</th>
                  <th style={thStyle}>Fin</th>
                  <th style={thStyle} />
                </tr>
              </thead>
              <tbody>
                {sessions.map(s => (
                  <tr key={s.id}>
                    <td style={{ ...tdStyle, color: '#64748b' }}>#{s.id}</td>
                    <td style={tdStyle}>
                      <span style={{ background: '#f0fdf4', color: '#166534', fontSize: '11px', padding: '2px 8px', borderRadius: '99px', border: '0.5px solid #bbf7d0' }}>
                        {s.status}
                      </span>
                    </td>
                    <td style={tdStyle}>{s.start_date}</td>
                    <td style={tdStyle}>{s.end_date}</td>
                    <td style={{ ...tdStyle, textAlign: 'right' }}>
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
      await load()
    } catch (e) { alert(e.message || 'Erreur') }
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

      {loading ? <CenteredSpinner /> : rooms.length === 0 ? (
        <p style={{ color: '#94a3b8', fontSize: '13px' }}>Aucune salle. Cliquez sur "Ajouter une salle".</p>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
          {rooms.map(room => (
            <div key={room.id} style={{ background: '#fff', border: '0.5px solid #e2e8f0', borderRadius: '10px', padding: '16px 20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <DoorOpen size={20} style={{ color: '#94a3b8' }} />
                <span style={{ fontWeight: 600, fontSize: '14px', color: '#0f172a' }}>{room.name}</span>
              </div>
              <div style={{ display: 'flex', gap: '4px' }}>
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
  const [projects, setProjects]       = useState([])
  const [loading, setLoading]         = useState(true)
  const [uploading, setUploading]     = useState(false)
  const [uploadResult, setUploadResult] = useState(null)
  const [uploadError, setUploadError] = useState('')
  const [selectedFile, setSelectedFile] = useState(null)
  const [search, setSearch]           = useState('')

  useEffect(() => { loadProjects() }, [])

  async function loadProjects() {
    setLoading(true)
    try {
      const data = await apiRequest('/projects?limit=200')
      setProjects(Array.isArray(data) ? data : [])
    } catch { /* silent */ } finally {
      setLoading(false)
    }
  }

  function handleSelectFile(e) {
    const file = e.target.files?.[0]
    if (file) { setSelectedFile(file); setUploadError(''); setUploadResult(null) }
    e.target.value = ''
  }

  async function handleImport() {
    if (!selectedFile) { setUploadError('Choisissez un fichier.'); return }
    setUploading(true)
    setUploadError('')
    const fd = new FormData()
    fd.append('file', selectedFile)
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

  const filtered = projects.filter(p =>
    p.title.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>

      {/* Upload card */}
      <div style={cardStyle}>
        <h3 style={sectionTitle}>Importer les projets</h3>
        <p style={sectionSub}>
          Format attendu : <code style={{ background: '#f1f5f9', padding: '1px 5px', borderRadius: '4px', fontSize: '11px' }}>title, domain_name, supervisor_email, student_email</code>
        </p>

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

        <InlineError   msg={uploadError} />
        {uploadResult && (
          <InlineSuccess msg={[
            `✓ ${uploadResult.inserted_count ?? 0} projet(s) importé(s)`,
            uploadResult.skipped_duplicates > 0 && `${uploadResult.skipped_duplicates} doublon(s) ignoré(s)`,
            uploadResult.invalid_rows > 0       && `${uploadResult.invalid_rows} ligne(s) rejetée(s)`,
          ].filter(Boolean).join(' · ')} />
        )}

        <div style={{ marginTop: '12px' }}>
          <button
            style={{ ...btnPrimary, opacity: (!selectedFile || uploading) ? 0.6 : 1 }}
            onClick={handleImport}
            disabled={uploading || !selectedFile}
          >
            {uploading ? <><Spinner /> Import en cours…</> : 'Importer'}
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

        {loading ? <CenteredSpinner /> : (
          <div style={{ background: '#fff', border: '0.5px solid #e2e8f0', borderRadius: '10px', overflow: 'hidden' }}>
            <table style={tableStyle}>
              <thead>
                <tr>
                  <th style={thStyle}>Titre</th>
                  <th style={thStyle}>Étudiant</th>
                  <th style={thStyle}>Superviseur</th>
                  <th style={thStyle}>Domaine</th>
                  <th style={thStyle} />
                </tr>
              </thead>
              <tbody>
                {filtered.length === 0 ? (
                  <tr><td colSpan={5} style={{ ...tdStyle, textAlign: 'center', color: '#94a3b8' }}>Aucun projet</td></tr>
                ) : filtered.map(p => (
                  <tr key={p.id}
                    onMouseEnter={e => { e.currentTarget.style.background = '#f8fafc' }}
                    onMouseLeave={e => { e.currentTarget.style.background = '' }}>
                    <td style={{ ...tdStyle, maxWidth: '320px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontWeight: 500 }}
                      title={p.title}>{p.title}</td>
                    <td style={{ ...tdStyle, color: '#64748b' }}>#{p.student_id}</td>
                    <td style={{ ...tdStyle, color: '#64748b' }}>#{p.supervisor_id}</td>
                    <td style={{ ...tdStyle, color: '#64748b' }}>
                      {(p.domain_ids || []).map(id => (
                        <span key={id} style={{ display: 'inline-block', background: '#eff6ff', color: '#1d4ed8', fontSize: '11px', padding: '1px 6px', borderRadius: '99px', border: '0.5px solid #bfdbfe', marginRight: '3px' }}>#{id}</span>
                      ))}
                    </td>
                    <td style={{ ...tdStyle, textAlign: 'right' }}>
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

// ── Root component ────────────────────────────────────────────────────────────

const TABS = [
  { id: 'professors', label: 'Professeurs', Icon: Users },
  { id: 'sessions',   label: 'Sessions',    Icon: Calendar },
  { id: 'rooms',      label: 'Salles',      Icon: DoorOpen },
  { id: 'projects',   label: 'Projets',     Icon: FileText },
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

      {activeTab === 'professors' && <ProfesseursTab />}
      {activeTab === 'sessions'   && <SessionsTab />}
      {activeTab === 'rooms'      && <SallesTab />}
      {activeTab === 'projects'   && <ProjetsTab />}
    </div>
  )
}
