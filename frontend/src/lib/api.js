// Appels à l'API du socle. Une réponse 401 renvoie à l'écran de connexion.
export class ErreurApi extends Error {
  constructor(message, statut) {
    super(message)
    this.statut = statut
  }
}

async function appel(methode, chemin, corps, texte = false) {
  const r = await fetch(chemin, {
    method: methode,
    headers: corps ? { 'Content-Type': texte ? 'text/plain' : 'application/json' } : undefined,
    body: corps ? (texte ? corps : JSON.stringify(corps)) : undefined,
    credentials: 'same-origin',
  })
  let donnees = null
  try { donnees = await r.json() } catch { /* réponse sans contenu */ }
  if (!r.ok) throw new ErreurApi(donnees?.detail || `Le serveur a répondu ${r.status}.`, r.status)
  return donnees
}

export const api = {
  get: (chemin) => appel('GET', chemin),
  post: (chemin, corps) => appel('POST', chemin, corps ?? {}),
  put: (chemin, corps) => appel('PUT', chemin, corps ?? {}),
  postTexte: (chemin, texte) => appel('POST', chemin, texte, true),
}
