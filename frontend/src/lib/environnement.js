// 0.10 (repris d'Atlas) : lecture d'un fichier d'environnement « NOM=valeur » (l'export de Portainer, Advanced mode).
// Les valeurs ne vivent que dans la mémoire de la page : ni mémoire locale, ni envoi. « Oublier » ou quitter la page les efface.

// Même règle qu'Atlas : un nom qui dit mot de passe, secret, jeton, clé, code, hash ou identifiant de compte est masqué.
const SENSIBLE = /PASSWORD|PASSWD|SECRET|TOKEN|JETON|(?:^|_)KEY(?:_|$)|(?:^|_)CLE(?:_|$)|ENCRYPTION|PRIVATE|HASH|(?:^|_)CODE(?:_|$)|CLIENT_ID|API_ID|ICLOUD_USER|(?:^|_)EMAIL(?:_|$)/

export const sensible = (nom) => SENSIBLE.test(nom)

// « NOM=valeur », une par ligne ; lignes vides et commentaires ignorés ; « export » et guillemets retirés.
export function comprendre(texte) {
  const valeurs = {}
  let ecartees = 0
  for (const brute of String(texte || '').replace(/^﻿/, '').split(/\r?\n/)) {
    const ligne = brute.trim()
    if (!ligne || ligne.startsWith('#')) continue
    const m = ligne.match(/^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$/)
    if (!m) { ecartees++; continue }
    let v = m[2]
    const g = v.match(/^(["'])(.*)\1\s*(?:#.*)?$/)
    if (g) v = g[2]
    else v = v.replace(/\s+#.*$/, '').trim()
    valeurs[m[1]] = v
  }
  return { valeurs, ecartees }
}

// Le texte à recoller dans Portainer (Advanced mode) : une ligne NOM=valeur par variable de la stack.
// Une variable à remplir absente reste « NOM= » ; une facultative absente n'est pas écrite (son défaut est gardé) ;
// une variable que la stack n'utilise plus est laissée de côté. Sans liste de la stack : toutes les valeurs, triées.
export function pourPortainer(valeurs, variables) {
  const lignes = []
  let vides = 0
  if (!variables?.length) {
    for (const nom of Object.keys(valeurs).sort()) lignes.push(`${nom}=${valeurs[nom]}`)
    return { texte: lignes.join('\n') + (lignes.length ? '\n' : ''), n: lignes.length, vides: 0 }
  }
  for (const v of variables) {
    const a = Object.prototype.hasOwnProperty.call(valeurs, v.nom)
    if (a) { lignes.push(`${v.nom}=${valeurs[v.nom]}`); if (valeurs[v.nom] === '' && v.defaut === null) vides++ }
    else if (v.defaut === null) { lignes.push(`${v.nom}=`); vides++ }
  }
  return { texte: lignes.join('\n') + (lignes.length ? '\n' : ''), n: lignes.length, vides }
}

// Le lien qui ouvre la note d'une variable dans Obsidian.
export const lienNote = (coffre, nom) =>
  `obsidian://open?vault=${encodeURIComponent(coffre || 'Maison')}&file=${encodeURIComponent(`3 Infrastructure et stack/Stack/Variables/Variable — ${nom}`)}`
