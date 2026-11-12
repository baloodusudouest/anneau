// « il y a 40 s », « depuis 12 min » : la fraîcheur se lit d'un coup d'œil.
export function duree(iso, maintenant = Date.now()) {
  if (!iso) return ''
  const s = Math.max(0, Math.round((maintenant - new Date(iso).getTime()) / 1000))
  if (s < 60) return `${s} s`
  if (s < 3600) return `${Math.round(s / 60)} min`
  if (s < 86400) return `${Math.round(s / 3600)} h`
  return `${Math.round(s / 86400)} j`
}
export const secondes = (n) => (n == null ? '' : n < 60 ? `${n} s` : n < 3600 ? `${Math.round(n / 60)} min` : `${Math.round(n / 3600)} h`)
