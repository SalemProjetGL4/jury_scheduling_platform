import { Download, FileSpreadsheet, FileText, Calendar, Table, User, Building } from 'lucide-react'

const FORMATS = [
  { icon: FileSpreadsheet, label: 'Excel (xlsx)', sub: 'Tableau complet',         color: 'text-green-600 bg-green-50',  iconColor: '#16A34A' },
  { icon: FileText,        label: 'PDF',           sub: 'Planning détaillé',       color: 'text-red-600 bg-red-50',      iconColor: '#DC2626' },
  { icon: Calendar,        label: 'iCal / ICS',    sub: "Importer dans\nGoogle Agenda", color: 'text-blue-600 bg-blue-50', iconColor: '#2563EB' },
  { icon: Table,           label: 'CSV',           sub: 'Données brutes',          color: 'text-gray-600 bg-gray-100',   iconColor: '#4B5563' },
  { icon: User,            label: 'Par jury (PDF)', sub: 'Planning par jury',      color: 'text-purple-600 bg-purple-50',iconColor: '#7C3AED' },
  { icon: Building,        label: 'Par salle (PDF)', sub: 'Planning par salle',   color: 'text-amber-600 bg-amber-50',  iconColor: '#D97706' },
]

export default function Exports() {
  return (
    <div className="space-y-5 max-w-3xl">
      {/* Selected solution summary */}
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Solution sélectionnée</p>
        <div className="flex items-center gap-6 flex-wrap">
          <div>
            <p className="text-sm font-bold text-gray-900">Solution #1 (recommandée)</p>
          </div>
          <div className="flex items-center gap-1">
            <span className="text-xs text-gray-500">Score</span>
            <span className="text-sm font-bold text-green-600 ml-1">94%</span>
          </div>
          {[
            { val: '312', lbl: 'Soutenances' },
            { val: '5',   lbl: 'Jours' },
            { val: '4',   lbl: 'Salles' },
            { val: '0',   lbl: 'Conflits' },
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
          {FORMATS.map(({ icon: Icon, label, sub, color, iconColor }) => (
            <div key={label} className="border border-gray-200 rounded-xl p-4 flex flex-col items-center gap-3 hover:border-blue-300 hover:shadow-sm transition-all">
              <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${color}`}>
                <Icon size={24} style={{ color: iconColor }} />
              </div>
              <div className="text-center">
                <p className="text-sm font-semibold text-gray-900">{label}</p>
                <p className="text-xs text-gray-500 whitespace-pre-line leading-tight mt-0.5">{sub}</p>
              </div>
              <button className="flex items-center gap-1.5 w-full justify-center text-xs font-medium text-blue-600 border border-blue-200 rounded-lg py-2 hover:bg-blue-50 transition-colors">
                <Download size={13} /> Télécharger
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
