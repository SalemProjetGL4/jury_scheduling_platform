import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { WorkflowProvider } from './context/WorkflowContext'
import Sidebar from './components/Sidebar'
import Dashboard from './pages/Dashboard'
import Donnees from './pages/Donnees'
import Contraintes from './pages/Contraintes'
import Generation from './pages/Generation'
import Resultats from './pages/Resultats'
import Calendrier from './pages/Calendrier'
import Exports from './pages/Exports'

function PageShell({ title, subtitle, children }) {
  return (
    <div className="ml-56 min-h-screen flex flex-col">
      {/* Top bar */}
      <header className="bg-white border-b border-gray-200 px-8 py-4 flex items-center justify-between sticky top-0 z-20">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">{title}</h1>
          {subtitle && <p className="text-sm text-gray-500 mt-0.5">{subtitle}</p>}
        </div>
        <div className="flex items-center gap-3">
          <div className="text-right">
            <p className="text-sm font-medium text-gray-900">Admin</p>
            <p className="text-xs text-gray-500">Département Info</p>
          </div>
          <div className="w-9 h-9 rounded-full bg-blue-600 flex items-center justify-center text-white text-sm font-semibold">
            A
          </div>
        </div>
      </header>
      <main className="flex-1 p-8">{children}</main>
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
    <WorkflowProvider>
      <Sidebar />
      <Routes>
        <Route path="/" element={
          <PageShell title="Tableau de bord" subtitle="Planifiez et optimisez la répartition des soutenances PFE.">
            <Dashboard />
          </PageShell>
        } />
        <Route path="/donnees" element={
          <PageShell title="Données" subtitle="Importez vos fichiers de données.">
            <Donnees />
          </PageShell>
        } />
        <Route path="/contraintes" element={
          <PageShell title="Contraintes" subtitle="Définissez les règles de planification.">
            <Contraintes />
          </PageShell>
        } />
        <Route path="/generation" element={
          <PageShell title="Génération" subtitle="Décrivez ce que vous souhaitez changer ou améliorer.">
            <Generation />
          </PageShell>
        } />
        <Route path="/resultats" element={
          <PageShell title="Résultats" subtitle="Choisissez la meilleure solution pour votre planning.">
            <Resultats />
          </PageShell>
        } />
        <Route path="/calendrier" element={
          <PageShell title="Calendrier" subtitle="Visualisez la répartition des soutenances.">
            <Calendrier />
          </PageShell>
        } />
        <Route path="/exports" element={
          <PageShell title="Exports" subtitle="Téléchargez la solution sélectionnée dans différents formats.">
            <Exports />
          </PageShell>
        } />
        <Route path="/parametres" element={
          <PageShell title="Paramètres" subtitle="Configuration de l'application.">
            <div className="bg-white rounded-xl p-8 text-gray-500">Paramètres à venir…</div>
          </PageShell>
        } />
      </Routes>
    </WorkflowProvider>
    </BrowserRouter>
  )
}
