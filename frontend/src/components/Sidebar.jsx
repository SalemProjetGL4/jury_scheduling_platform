import { NavLink } from 'react-router-dom'
import {
  CalendarDays, LayoutDashboard, Database, SlidersHorizontal,
  Sparkles, BarChart2, Download, Activity,
} from 'lucide-react'

const navItems = [
  { to: '/',            icon: LayoutDashboard,    label: 'Tableau de bord' },
  { to: '/donnees',     icon: Database,           label: 'Données' },
  { to: '/contraintes', icon: SlidersHorizontal,  label: 'Contraintes' },
  { to: '/generation',  icon: Sparkles,           label: 'Génération' },
  { to: '/resultats',   icon: BarChart2,          label: 'Résultats' },
  { to: '/calendrier',  icon: CalendarDays,       label: 'Calendrier' },
  { to: '/exports',     icon: Download,           label: 'Exports' },
]

export default function Sidebar() {
  return (
    <aside className="fixed inset-y-0 left-0 w-56 bg-white border-r border-gray-200 flex flex-col z-30">
      {/* Logo */}
      <div className="flex items-center gap-2 px-5 py-5 border-b border-gray-100">
        <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
          <CalendarDays size={18} className="text-white" />
        </div>
        <span className="font-semibold text-gray-900 text-sm leading-tight">PFE Soutenances</span>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
        {navItems.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
              }`
            }
          >
            <Icon size={18} />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Bottom */}
      <div className="px-3 py-4 border-t border-gray-100">
        <NavLink
          to="/monitoring"
          className={({ isActive }) =>
            `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
              isActive
                ? 'bg-blue-600 text-white'
                : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
            }`
          }
        >
          <Activity size={18} />
          Monitoring
        </NavLink>
      </div>
    </aside>
  )
}
