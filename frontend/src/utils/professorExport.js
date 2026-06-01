import ExcelJS from 'exceljs'

// ARGB hex colors (ExcelJS prefix 'FF' = full opacity)
const ROLE_BG = {
  'Président':   'FFDCFCE7',  // green-100
  'Examinateur': 'FFF3E8FF',  // purple-100
  'Encadrant':   'FFDBEAFE',  // blue-100
}
const HEADER_BG = 'FFDBEAFE'  // blue-100  — date column headers
const PERIOD_BG = 'FFF3F4F6'  // gray-100  — time label column
const TITLE_BG  = 'FFFEF9C3'  // yellow-100 — professor name title row

// assignments: enriched rows from enrichAssignments() + a `role` field added by the caller
export async function buildProfessorWorkbook(professorName, assignments) {
  const workbook = new ExcelJS.Workbook()
  workbook.creator = 'Juriq'

  const sheet = workbook.addWorksheet('Planning')

  const uniqueDates = [...new Set(assignments.map(a => a.date).filter(Boolean))].sort()
  const uniqueTimes = [...new Set(assignments.map(a => a.time).filter(Boolean))].sort()
  const colCount    = uniqueDates.length + 1  // time col + one per date

  sheet.columns = [
    { width: 14 },
    ...uniqueDates.map(() => ({ width: 24 })),
  ]

  // ── Row 1: professor name — merged across all columns ────────────────────────
  sheet.addRow([professorName, ...Array(uniqueDates.length).fill('')])
  sheet.mergeCells(1, 1, 1, colCount)
  sheet.getRow(1).height = 28
  const titleCell = sheet.getRow(1).getCell(1)
  titleCell.font      = { bold: true, size: 14 }
  titleCell.alignment = { horizontal: 'center', vertical: 'middle' }
  titleCell.fill      = { type: 'pattern', pattern: 'solid', fgColor: { argb: TITLE_BG } }

  // ── Row 2: header — "Heure" + one date column per unique date ─────────────────
  const headerRow = sheet.addRow(['Heure', ...uniqueDates.map(formatDateHeader)])
  headerRow.height = 20

  const heureCell = headerRow.getCell(1)
  heureCell.font      = { bold: true }
  heureCell.alignment = { horizontal: 'center', vertical: 'middle' }
  heureCell.fill      = { type: 'pattern', pattern: 'solid', fgColor: { argb: PERIOD_BG } }

  uniqueDates.forEach((_, i) => {
    const c = headerRow.getCell(i + 2)
    c.font      = { bold: true }
    c.alignment = { horizontal: 'center', vertical: 'middle' }
    c.fill      = { type: 'pattern', pattern: 'solid', fgColor: { argb: HEADER_BG } }
  })

  // ── Rows 3+: one row per unique HH:MM time slot ───────────────────────────────
  for (const timeLabel of uniqueTimes) {
    const rowValues = [
      timeLabel,
      ...uniqueDates.map(date => {
        const rows = assignments.filter(a => a.date === date && a.time === timeLabel)
        return rows.length ? rows.map(buildCellText).join('\n─────\n') : ''
      }),
    ]

    const dataRow = sheet.addRow(rowValues)
    dataRow.height = 80

    const labelCell = dataRow.getCell(1)
    labelCell.font      = { bold: true }
    labelCell.fill      = { type: 'pattern', pattern: 'solid', fgColor: { argb: PERIOD_BG } }
    labelCell.alignment = { vertical: 'middle', horizontal: 'center' }

    uniqueDates.forEach((date, i) => {
      const cell = dataRow.getCell(i + 2)
      cell.alignment = { wrapText: true, vertical: 'top' }
      const rows = assignments.filter(a => a.date === date && a.time === timeLabel)
      if (rows.length) {
        const argb = ROLE_BG[rows[0].role] ?? 'FFFFFFFF'
        cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb } }
      }
    })
  }

  return workbook
}

// ── helpers ───────────────────────────────────────────────────────────────────

function buildCellText(a) {
  return [
    a.project_title,
    a.student_name,
    a.room,
    a.role,
    a.enterprise || null,
  ].filter(Boolean).join('\n')
}

function formatDateHeader(dateStr) {
  if (!dateStr) return ''
  const d  = new Date(`${dateStr}T00:00:00`)
  const wd = d.toLocaleDateString('fr-FR', { weekday: 'short' })
  const dm = d.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit' })
  return `${wd.charAt(0).toUpperCase()}${wd.slice(1)} ${dm}`
}
