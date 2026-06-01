import {
  AlignmentType,
  Document,
  Packer,
  PageBreak,
  Paragraph,
  ShadingType,
  Table,
  TableCell,
  TableRow,
  TextRun,
  VerticalAlign,
  VerticalMergeType,
  WidthType,
} from 'docx'
import { saveAs } from 'file-saver'

// ── constants ─────────────────────────────────────────────────────────────────

const FILIERE_MAP = {
  GL: { filiere_id: 1, label: 'GENIE LOGICIEL (GL)' },
  RT: { filiere_id: 2, label: 'RESEAUX ET TELECOMMUNICATIONS (RT)' },
}

const FR_MONTHS = [
  'Janvier','Février','Mars','Avril','Mai','Juin',
  'Juillet','Août','Septembre','Octobre','Novembre','Décembre',
]

const FR_DAYS = ['Dimanche','Lundi','Mardi','Mercredi','Jeudi','Vendredi','Samedi']

const COL_WIDTHS = [1200, 2400, 5760]   // DXA

const SLOT_LABELS = [
  'Candidat',
  'Sujet',
  'Entreprise',
  'Responsable Entr.',
  'Responsable INSAT',
  'Examinateur',
]

// ── date helpers ──────────────────────────────────────────────────────────────

function monthYear(dateStr) {
  const d = new Date(`${dateStr}T00:00:00`)
  return `${FR_MONTHS[d.getMonth()]} ${d.getFullYear()}`
}

function fullDate(dateStr) {
  const d   = new Date(`${dateStr}T00:00:00`)
  const day = FR_DAYS[d.getDay()]
  const mon = FR_MONTHS[d.getMonth()]
  return `${day} ${String(d.getDate()).padStart(2, '0')} ${mon} ${d.getFullYear()}`
}

function period(timeStr) {
  if (!timeStr) return 'morning'
  return parseInt(timeStr.split(':')[0], 10) < 12 ? 'morning' : 'afternoon'
}

// ── docx helpers ──────────────────────────────────────────────────────────────

function para(text, { bold = false, size = 18, align = AlignmentType.LEFT } = {}) {
  return new Paragraph({
    alignment: align,
    spacing: { before: 20, after: 20 },
    children: [new TextRun({ text: String(text ?? ''), bold, size })],
  })
}

function cell(children, {
  width    = COL_WIDTHS[2],
  bold     = false,
  shading  = null,
  colSpan  = 1,
  vMerge   = null,   // 'restart' | 'continue' | null
  vAlign   = VerticalAlign.CENTER,
} = {}) {
  const paragraphs = typeof children === 'string'
    ? [para(children, { bold, size: 18 })]
    : children

  const opts = {
    children: paragraphs,
    width:    { size: width, type: WidthType.DXA },
    verticalAlign: vAlign,
    margins:  { top: 50, bottom: 50, left: 80, right: 80 },
  }

  if (colSpan > 1) opts.columnSpan = colSpan
  if (shading)     opts.shading = { fill: shading, type: ShadingType.CLEAR, color: 'auto' }
  if (vMerge === 'restart')  opts.verticalMerge = VerticalMergeType.RESTART
  if (vMerge === 'continue') opts.verticalMerge = VerticalMergeType.CONTINUE

  return new TableCell(opts)
}

function row(cells) {
  return new TableRow({ children: cells })
}

// ── group builder ─────────────────────────────────────────────────────────────

function groupAssignments(assignments) {
  const map = new Map()

  for (const a of assignments) {
    const key = `${a.date}__${a.room}__${period(a.time)}`
    if (!map.has(key)) map.set(key, [])
    map.get(key).push(a)
  }

  return [...map.entries()]
    .sort(([ka], [kb]) => ka.localeCompare(kb))
    .map(([, slots]) => {
      slots.sort((a, b) => (a.time ?? '').localeCompare(b.time ?? ''))
      return slots
    })
}

// ── table builder ─────────────────────────────────────────────────────────────

function buildTable(slots) {
  const first      = slots[0]
  const mon_year   = monthYear(first.date)
  const full_date  = fullDate(first.date)
  const room       = first.room ?? ''
  const president  = first.president_name ?? ''

  const rows = []

  // Row 0 — header
  rows.push(row([
    cell(`Salle : ${room}`,           { width: COL_WIDTHS[0], bold: true, shading: 'D9D9D9' }),
    cell(`Session : ${mon_year}`,     { width: COL_WIDTHS[1], bold: true, shading: 'D9D9D9' }),
    cell(`Date : ${full_date}`,       { width: COL_WIDTHS[2], bold: true, shading: 'D9D9D9' }),
  ]))

  // Row 1 — president (3-col span)
  rows.push(row([
    cell(`Président de jury : ${president}`, {
      width: COL_WIDTHS[0] + COL_WIDTHS[1] + COL_WIDTHS[2],
      colSpan: 3,
      bold: true,
      shading: 'EBF3FB',
    }),
  ]))

  // Slot rows (6 per slot)
  const values = (s) => [
    s.student_name          ?? '',
    s.project_title         ?? '',
    s.enterprise            ?? '',
    s.enterprise_supervisor ?? '',
    s.supervisor_name       ?? '',
    s.examiner_name         ?? '',
  ]

  for (const slot of slots) {
    const vals = values(slot)
    const time = slot.time ?? ''

    for (let ri = 0; ri < 6; ri++) {
      rows.push(row([
        // col 0 — time (vertical merge)
        cell(ri === 0 ? time : '', {
          width:  COL_WIDTHS[0],
          bold:   ri === 0,
          vMerge: ri === 0 ? 'restart' : 'continue',
        }),
        // col 1 — label
        cell(SLOT_LABELS[ri], { width: COL_WIDTHS[1] }),
        // col 2 — value
        cell(vals[ri],        { width: COL_WIDTHS[2] }),
      ]))
    }
  }

  return new Table({
    rows,
    width: { size: COL_WIDTHS[0] + COL_WIDTHS[1] + COL_WIDTHS[2], type: WidthType.DXA },
  })
}

// ── document builder ──────────────────────────────────────────────────────────

function buildDoc(assignments, filiereCode) {
  const entry    = FILIERE_MAP[filiereCode]
  if (!entry) throw new Error(`Unknown filiere: ${filiereCode}`)

  const filtered = assignments.filter(a => a.filiere_id === entry.filiere_id)

  if (!filtered.length) {
    return new Document({
      sections: [{
        children: [para(`Aucune soutenance pour la filière ${entry.label}.`)],
      }],
    })
  }

  const groups   = groupAssignments(filtered)
  const children = []

  for (let gi = 0; gi < groups.length; gi++) {
    const slots    = groups[gi]
    const mon_year = monthYear(slots[0].date)

    if (gi > 0) {
      children.push(new Paragraph({ children: [new PageBreak()] }))
    }

    children.push(
      new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { after: 120 },
        children: [
          new TextRun({ text: `PFE Ingénieurs : Session ${mon_year}`, bold: true, size: 28, break: 0 }),
          new TextRun({ text: entry.label,                            bold: true, size: 28, break: 1 }),
        ],
      })
    )

    children.push(buildTable(slots))
  }

  return new Document({ sections: [{ children }] })
}

// ── public API ────────────────────────────────────────────────────────────────

export async function exportToDocx(assignments, filiere, filename) {
  const blob = await Packer.toBlob(buildDoc(assignments, filiere))
  saveAs(blob, `${filename}_${filiere}.docx`)
}

export async function exportBothDocx(assignments, filename) {
  // Generate both blobs in parallel before triggering any download,
  // so the heavy async work is done and both triggers fire close together.
  const [glBlob, rtBlob] = await Promise.all([
    Packer.toBlob(buildDoc(assignments, 'GL')),
    Packer.toBlob(buildDoc(assignments, 'RT')),
  ])
  saveAs(glBlob, `${filename}_GL.docx`)
  await new Promise(r => setTimeout(r, 2000))
  saveAs(rtBlob, `${filename}_RT.docx`)
}

// Returns the two DOCX blobs without downloading — used by the PDF export
// which POSTs each blob to the backend /convert/docx-to-pdf endpoint.
export async function buildBothDocxBlobs(assignments) {
  const [glBlob, rtBlob] = await Promise.all([
    Packer.toBlob(buildDoc(assignments, 'GL')),
    Packer.toBlob(buildDoc(assignments, 'RT')),
  ])
  return { glBlob, rtBlob }
}
