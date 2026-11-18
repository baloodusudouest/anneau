// 0.11 : la carte de la maison (reprise d'Atlas). Les données viennent de /api/carte : la carte fabriquée par le coffre,
// avec sur chaque service le voyant de sa tuile. Tout est calculé à partir de cet objet, rien n'est gardé ailleurs.

// Nature d'un flux → trait et couleur. Un flux avec « retour » est un échange : flèche à deux pointes.
export const NATURES = {
  donnees: { nom: 'Informations (sens de la flèche)', trait: '', couleur: '#9fb7d0' },
  echange: { nom: 'Échange (dans les deux sens)', trait: '', couleur: '#e0a46b' },
  commande: { nom: 'Demande d’agir', trait: '7 4', couleur: '#63cbd9' },
  cookie: { nom: 'Connexion commune', trait: '2 4', couleur: '#e2c98a' },
  acces: { nom: 'Accès', trait: '1 5', couleur: '#7a7268' },
  maj: { nom: 'Mise à jour d’image', trait: '8 5', couleur: '#8a8278' },
}
export const FOND = new Set(['cookie', 'acces', 'maj'])
export const nature = (f) => (f.echange && f.nature === 'donnees' ? 'echange' : f.nature)
const INFOS = new Set(['donnees', 'commande'])

export const VOYANTS = {
  ok: { nom: 'en service', couleur: 'var(--valide)' },
  panne: { nom: 'en panne', couleur: 'var(--lave)' },
  eteint: { nom: 'éteint', couleur: 'var(--or-sourd)' },
  inconnu: { nom: 'pas encore sondé', couleur: 'var(--or-sourd)' },
  '': { nom: 'sans tuile', couleur: 'transparent' },
}

export function couleur(s) {
  return s.famille === 'maison' ? (s.couleur || 'var(--app)') : s.famille === 'stockage' ? '#8a8278' : '#7f93ab'
}

export function indexer(carte) {
  return {
    parId: Object.fromEntries(carte.services.map((s) => [s.id, s])),
    machines: Object.fromEntries(carte.machines.map((m) => [m.id, m])),
  }
}

export const voisins = (carte, id) =>
  new Set([id, ...carte.flux.filter((f) => f.de === id || f.vers === id).flatMap((f) => [f.de, f.vers])])

// Ce qui nourrit un service, ce qu'il écrit, ce qu'il échange ; le reste (accès, cookie, mises à jour) à part.
export function circulation(carte, id) {
  const r = { nourrit: [], ecrit: [], echange: [], autres: [] }
  for (const f of carte.flux) {
    if (f.de !== id && f.vers !== id) continue
    const avec = f.de === id ? f.vers : f.de
    if (!INFOS.has(f.nature)) r.autres.push({ f, avec, sens: f.de === id ? 'vers' : 'depuis' })
    else if (f.echange) r.echange.push({ f, avec, recoit: (f.vers === id ? f.infos : f.retour) || [], envoie: (f.de === id ? f.infos : f.retour) || [] })
    else if (f.vers === id) r.nourrit.push({ f, avec, infos: f.infos || [] })
    else r.ecrit.push({ f, avec, infos: f.infos || [] })
  }
  return r
}

// Adresse de la note du service dans le coffre Obsidian (ouvre l'appli Obsidian si elle est installée)
export const lienNote = (s) => (s.note ? 'obsidian://open?vault=' + encodeURIComponent('Maison') + '&file=' + encodeURIComponent(s.note) : '')
