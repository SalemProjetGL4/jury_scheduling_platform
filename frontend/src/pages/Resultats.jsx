import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend,
} from 'recharts'
import { CalendarDays, Download, Star } from 'lucide-react'
import { solutions, repartitionParJour, repartitionParSalle } from '../data/mockData'

function Stars({ n, max = 4 }) {
  return (
    <div className="flex gap-0.5">
      {Array.from({ length: max }).map((_, i) => (
        <Star
          key={i}
          size={13}
          className={i < n ? 'text-amber-400 fill-amber-400' : 'text-gray-200 fill-gray-200'}
        />
      ))}
    </div>
  )
}

const DETAIL_TABS = ['Aperçu', 'Calendrier', 'Détails', 'Conflits']

function SolutionDetail({ sol }) {
  const [tab, setTab] = useState('Aperçu')
  const navigate = useNavigate()

  return (
    <div className="bg-white rounded-xl border border-gray-200 flex flex-col h-full">
      {/* Header */}
      <div className="px-5 py-4 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-gray-900">Solution {sol.label}</h3>
          <span className="text-sm font-bold text-green-600">Score : {sol.score}%</span>
        </div>
        <div className="flex gap-1 mt-3">
          {DETAIL_TABS.map(t => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`text-xs px-3 py-1.5 rounded-md font-medium transition-colors ${
                tab === t ? 'bg-blue-600 text-white' : 'text-gray-600 hover:bg-gray-100'
              }`}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-5 py-4 space-y-5">
        {/* Quick stats */}
        <div className="grid grid-cols-4 gap-3">
          {[
            { icon: '📋', val: '312',        lbl: 'Soutenances' },
            { icon: '📅', val: '5',           lbl: 'Jours planifiés\nDu 20/05 au 24/05' },
            { icon: '🏫', val: '4',           lbl: 'Salles utilisées' },
            { icon: 'ℹ️', val: '0',           lbl: 'Conflit détecté' },
          ].map(({ icon, val, lbl }) => (
            <div key={lbl} className="bg-gray-50 rounded-lg px-3 py-3 text-center">
              <p className="text-lg font-bold text-gray-900">{val}</p>
              <p className="text-[10px] text-gray-500 whitespace-pre-line leading-tight mt-0.5">{lbl}</p>
            </div>
          ))}
        </div>

        {/* Charts row */}
        <div className="grid grid-cols-2 gap-4">
          {/* Bar chart */}
          <div>
            <p className="text-xs font-semibold text-gray-600 mb-2">Répartition par jour</p>
            <ResponsiveContainer width="100%" height={110}>
              <BarChart data={repartitionParJour} barSize={16}>
                <XAxis dataKey="jour" tick={{ fontSize: 10 }} axisLine={false} tickLine={false} />
                <YAxis hide />
                <Tooltip contentStyle={{ fontSize: 11 }} />
                <Bar dataKey="value" fill="#3B82F6" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Donut chart */}
          <div>
            <p className="text-xs font-semibold text-gray-600 mb-2">Répartition par salle</p>
            <ResponsiveContainer width="100%" height={110}>
              <PieChart>
                <Pie
                  data={repartitionParSalle}
                  cx="50%"
                  cy="50%"
                  innerRadius={28}
                  outerRadius={45}
                  dataKey="value"
                  paddingAngle={2}
                >
                  {repartitionParSalle.map((entry) => (
                    <Cell key={entry.name} fill={entry.color} />
                  ))}
                </Pie>
                <Legend
                  iconType="circle"
                  iconSize={8}
                  formatter={(v, e) => `${v} (${e.payload.value})`}
                  wrapperStyle={{ fontSize: 10 }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Actions */}
      <div className="px-5 py-4 border-t border-gray-100 space-y-2">
        <div className="flex gap-2">
          <button
            onClick={() => navigate('/calendrier')}
            className="flex-1 flex items-center justify-center gap-1.5 text-xs border border-gray-300 rounded-lg py-2 hover:bg-gray-50 font-medium"
          >
            <CalendarDays size={13} /> Voir le calendrier
          </button>
          <button
            onClick={() => navigate('/exports')}
            className="flex-1 flex items-center justify-center gap-1.5 text-xs border border-gray-300 rounded-lg py-2 hover:bg-gray-50 font-medium"
          >
            <Download size={13} /> Exporter
          </button>
        </div>
        <button className="w-full bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-lg py-2.5 transition-colors">
          Utiliser cette solution
        </button>
      </div>
    </div>
  )
}

export default function Resultats() {
  const [activeTab, setActiveTab] = useState('Solutions générées')
  const [selected, setSelected] = useState(solutions[0])

  return (
    <div className="flex gap-5 items-start">
      {/* Left — solutions table */}
      <div className="flex-1 bg-white rounded-xl border border-gray-200 overflow-hidden">
        {/* Tabs */}
        <div className="flex border-b border-gray-200 px-5">
          {['Solutions générées', 'Propositions'].map(t => (
            <button
              key={t}
              onClick={() => setActiveTab(t)}
              className={`text-sm font-medium py-3 px-2 mr-4 border-b-2 transition-colors ${
                activeTab === t
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              {t}
            </button>
          ))}
        </div>

        {/* Table */}
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-100 bg-gray-50">
              {['Solution', 'Score', 'Conflits', 'Jours', 'Salles', 'Soutenances', 'Actions'].map(h => (
                <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-gray-500">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {solutions.map(sol => (
              <tr
                key={sol.id}
                className={`border-b border-gray-100 hover:bg-gray-50 cursor-pointer ${selected.id === sol.id ? 'bg-blue-50' : ''}`}
                onClick={() => setSelected(sol)}
              >
                <td className="px-4 py-3 font-medium text-gray-900">
                  #{sol.id}
                  {sol.recommended && (
                    <span className="ml-1.5 text-[10px] bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded">recommandée</span>
                  )}
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-1.5">
                    <span className="font-semibold text-green-600">{sol.score}%</span>
                    <Stars n={sol.stars} />
                  </div>
                </td>
                <td className="px-4 py-3 text-gray-600">{sol.conflits}</td>
                <td className="px-4 py-3 text-gray-600">{sol.jours}</td>
                <td className="px-4 py-3 text-gray-600">{sol.salles}</td>
                <td className="px-4 py-3 text-gray-600">{sol.soutenances}</td>
                <td className="px-4 py-3">
                  <div className="flex gap-1.5">
                    <button className="text-xs text-blue-600 font-medium hover:underline">Voir</button>
                    <button className="text-xs border border-gray-300 rounded px-2 py-0.5 hover:bg-gray-50">Calendrier</button>
                    <button
                      className="text-xs bg-blue-600 text-white rounded px-2 py-0.5 hover:bg-blue-700"
                      onClick={e => { e.stopPropagation(); setSelected(sol) }}
                    >
                      Sélectionner
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        <div className="px-5 py-3 flex items-center justify-between">
          <button className="text-xs text-gray-600 border border-gray-300 rounded-lg px-3 py-1.5 hover:bg-gray-50">
            Comparer les solutions
          </button>
          <button className="text-xs text-gray-400 border border-gray-200 rounded-lg px-3 py-1.5" disabled>
            Solution sélectionnée
          </button>
        </div>
      </div>

      {/* Right — detail panel */}
      <div className="w-80 flex-shrink-0">
        <SolutionDetail sol={selected} />
      </div>
    </div>
  )
}
