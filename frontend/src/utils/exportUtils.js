export function enrichAssignments(assignments, { professors = [], projects = [], slots = [], students = [], domains = [] } = {}) {
  const profMap    = new Map(professors.map(p => [p.id, p]))
  const projectMap = new Map(projects.map(p => [p.id, p]))
  const slotMap    = new Map(slots.map(s => [s.id, s]))
  const studentMap = new Map(students.map(s => [s.id, s]))
  const domainMap  = new Map(domains.map(d => [d.id, d]))

  return assignments.map(a => {
    // DB assignments use slot_id; workflow assignments mis-name the slot key as session_id
    const slot = slotMap.get(a.slot_id) ?? slotMap.get(a.session_id)

    const project    = projectMap.get(a.project_id)
    const student    = project ? studentMap.get(project.student_id) : null
    const supervisor = project ? profMap.get(project.supervisor_id) : null
    const domain     = project ? domainMap.get(project.domain_ids?.[0]) : null

    // DB assignments: president_id / examiner_id
    // Workflow assignments: roles.president / roles.examiner
    const president = profMap.get(a.president_id ?? a.roles?.president)
    const examiner  = profMap.get(a.examiner_id  ?? a.roles?.examiner)

    const date = a.date ?? (slot?.start_time ? slot.start_time.slice(0, 10) : '')
    const room = a.room ?? slot?.room ?? ''

    let time = ''
    if (slot?.start_time) {
      time = slot.start_time.slice(11, 16)
    } else if (a.period) {
      time = deriveTimeFromPeriod(a.period, slot?.slot_number)
    }

    return {
      date,
      time,
      room,
      project_title:         project?.title                  ?? '',
      domain:                domain?.name                    ?? '',
      student_name:          student?.name                   ?? '',
      supervisor_name:       supervisor?.name                ?? '',
      president_name:        president?.name                 ?? '',
      examiner_name:         examiner?.name                  ?? '',
      enterprise:            project?.enterprise             ?? '',
      enterprise_supervisor: project?.enterprise_supervisor  ?? '',
      filiere_id:            student?.filiere_id             ?? null,
    }
  })
}

function deriveTimeFromPeriod(period, slotNumber) {
  const morningStarts   = ['08:00', '09:00', '10:00', '11:00']
  const afternoonStarts = ['13:00', '14:00', '15:00', '16:00']
  if (period === 'morning') {
    return morningStarts[Math.max(0, (slotNumber ?? 1) - 1)] ?? '08:00'
  }
  if (period === 'afternoon') {
    return afternoonStarts[Math.max(0, ((slotNumber ?? 5) - 5))] ?? '13:00'
  }
  return period === 'morning' ? 'Matin' : 'Après-midi'
}

export function exportToCSV(assignments, { professors, projects, slots, students, domains, filename = 'juriq-schedule' } = {}) {
  const rows   = enrichAssignments(assignments, { professors, projects, slots, students, domains })
  const header = 'date,time,room,project_title,domain,student_name,supervisor_name,president_name,examiner_name,enterprise,enterprise_supervisor'
  const lines  = rows.map(r =>
    [r.date, r.time, r.room,
     csvEscape(r.project_title), csvEscape(r.domain),
     csvEscape(r.student_name),  csvEscape(r.supervisor_name),
     csvEscape(r.president_name), csvEscape(r.examiner_name),
     csvEscape(r.enterprise), csvEscape(r.enterprise_supervisor)].join(',')
  )
  const blob = new Blob([[header, ...lines].join('\n')], { type: 'text/csv' })
  triggerDownload(blob, `${filename}.csv`)
}

export function exportToJSON(assignments, { professors, projects, slots, students, domains, filename = 'juriq-schedule' } = {}) {
  const rows = enrichAssignments(assignments, { professors, projects, slots, students, domains })
  const blob = new Blob([JSON.stringify(rows, null, 2)], { type: 'application/json' })
  triggerDownload(blob, `${filename}.json`)
}

function csvEscape(val) {
  if (!val) return ''
  const str = String(val)
  return str.includes(',') || str.includes('"') || str.includes('\n')
    ? `"${str.replace(/"/g, '""')}"`
    : str
}

function triggerDownload(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a   = document.createElement('a')
  a.href     = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
