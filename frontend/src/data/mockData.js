export const JURY_COLORS = {
  1: { bg: 'bg-blue-100',   text: 'text-blue-800',   dot: '#3B82F6', border: 'border-blue-200' },
  2: { bg: 'bg-green-100',  text: 'text-green-800',  dot: '#10B981', border: 'border-green-200' },
  3: { bg: 'bg-purple-100', text: 'text-purple-800', dot: '#8B5CF6', border: 'border-purple-200' },
  4: { bg: 'bg-amber-100',  text: 'text-amber-800',  dot: '#F59E0B', border: 'border-amber-200' },
  5: { bg: 'bg-red-100',    text: 'text-red-800',    dot: '#EF4444', border: 'border-red-200' },
}

export const solutions = [
  { id: 1, label: '#1 (recommandée)', score: 94, stars: 4, conflits: 0, jours: 5, salles: 4, soutenances: 312, recommended: true, date: '20 Mai 2024 à 14:32' },
  { id: 2, label: '#2', score: 90, stars: 3, conflits: 1, jours: 5, salles: 3, soutenances: 312, recommended: false, date: '20 Mai 2024 à 14:32' },
  { id: 3, label: '#3', score: 87, stars: 3, conflits: 2, jours: 4, salles: 4, soutenances: 312, recommended: false, date: '20 Mai 2024 à 14:32' },
]

export const repartitionParJour = [
  { jour: '20/05', value: 68 },
  { jour: '21/05', value: 64 },
  { jour: '22/05', value: 62 },
  { jour: '23/05', value: 66 },
  { jour: '24/05', value: 62 },
]

export const repartitionParSalle = [
  { name: 'Salle A', value: 78, color: '#3B82F6' },
  { name: 'Salle B', value: 78, color: '#10B981' },
  { name: 'Salle C', value: 78, color: '#F59E0B' },
  { name: 'Salle D', value: 78, color: '#EF4444' },
]

export const salles = [
  { id: 'A', label: 'Salle A', places: 50 },
  { id: 'B', label: 'Salle B', places: 40 },
  { id: 'C', label: 'Salle C', places: 30 },
  { id: 'D', label: 'Salle D', places: 30 },
]

export const days = [
  { key: 'lun', label: 'Lun.', date: '20/05' },
  { key: 'mar', label: 'Mar.', date: '21/05' },
  { key: 'mer', label: 'Mer.', date: '22/05' },
  { key: 'jeu', label: 'Jeu.', date: '23/05' },
  { key: 'ven', label: 'Ven.', date: '24/05' },
]

// Events: { id, salle, day, start, end, prof, jury }
export const calendarEvents = [
  { id: 1,  salle: 'A', day: 'lun', start: '09:00', end: '10:00', prof: 'Amine Benali',   jury: 1 },
  { id: 2,  salle: 'A', day: 'lun', start: '10:00', end: '11:00', prof: 'Sara Khalfi',    jury: 2 },
  { id: 3,  salle: 'A', day: 'mar', start: '09:00', end: '10:00', prof: 'Youssef Hadj',   jury: 1 },
  { id: 4,  salle: 'A', day: 'mer', start: '10:00', end: '11:00', prof: 'Nadia Bouzid',   jury: 2 },
  { id: 5,  salle: 'A', day: 'jeu', start: '14:00', end: '16:00', prof: 'Islam Charfi',   jury: 1 },
  { id: 6,  salle: 'B', day: 'lun', start: '14:00', end: '15:00', prof: 'Ikram Saidi',    jury: 3 },
  { id: 7,  salle: 'B', day: 'mar', start: '10:00', end: '11:00', prof: 'Mehdi Tarek',    jury: 4 },
  { id: 8,  salle: 'B', day: 'jeu', start: '10:00', end: '11:00', prof: 'Lina Benyahia',  jury: 3 },
  { id: 9,  salle: 'B', day: 'mer', start: '13:00', end: '14:00', prof: 'Riad Hamdi',     jury: 2 },
  { id: 10, salle: 'C', day: 'mar', start: '09:00', end: '10:00', prof: 'Fares Boulem',   jury: 5 },
  { id: 11, salle: 'C', day: 'mer', start: '09:00', end: '10:00', prof: 'Diha Touati',    jury: 5 },
  { id: 12, salle: 'C', day: 'jeu', start: '16:00', end: '18:00', prof: 'Karim Abid',     jury: 5 },
  { id: 13, salle: 'D', day: 'lun', start: '15:00', end: '16:00', prof: 'Mohamed Ali',    jury: 5 },
  { id: 14, salle: 'D', day: 'jeu', start: '15:00', end: '16:00', prof: 'Karim Abid',     jury: 5 },
  { id: 15, salle: 'D', day: 'ven', start: '09:00', end: '10:00', prof: 'Asma Fergani',   jury: 4 },
  { id: 16, salle: 'D', day: 'ven', start: '14:00', end: '15:00', prof: 'Wissem Bouri',   jury: 3 },
]

export const professors = [
  { id: 1, nom: 'Amine Benali',  departement: 'Info', specialite: 'IA',       maxJurys: 5 },
  { id: 2, nom: 'Sara Khalfi',   departement: 'Info', specialite: 'Réseaux',  maxJurys: 4 },
  { id: 3, nom: 'Youssef Hadj',  departement: 'Info', specialite: 'IA',       maxJurys: 6 },
  { id: 4, nom: 'Nadia Bouzid',  departement: 'Math', specialite: 'Algèbre',  maxJurys: 3 },
  { id: 5, nom: 'Islam Charfi',  departement: 'Info', specialite: 'Web',      maxJurys: 5 },
  { id: 6, nom: 'Ikram Saidi',   departement: 'Info', specialite: 'BD',       maxJurys: 4 },
  { id: 7, nom: 'Mehdi Tarek',   departement: 'Math', specialite: 'Stats',    maxJurys: 4 },
  { id: 8, nom: 'Lina Benyahia', departement: 'Info', specialite: 'Systèmes', maxJurys: 5 },
]

export const constraints = [
  { id: 1, type: 'hard', label: 'Amine Benali indisponible le Lundi matin',      active: true  },
  { id: 2, type: 'soft', label: 'Équilibrer la charge entre les jurys',           active: true  },
  { id: 3, type: 'hard', label: 'Pas plus de 3 soutenances par jury par jour',   active: true  },
  { id: 4, type: 'soft', label: 'Privilégier la Salle A pour Jury 1',             active: false },
  { id: 5, type: 'hard', label: 'Éviter les conflits de salle entre jurys',       active: true  },
]
