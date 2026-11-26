<script>
  // 0.19 : pictogramme de chaque thème des réglages (trait fin, comme les icônes des familles).
  let { id, taille = 20 } = $props()
  const TRACES = {
    services: '<rect x="4" y="4" width="7" height="7" rx="1.5"/><rect x="13" y="4" width="7" height="7" rx="1.5"/><rect x="4" y="13" width="7" height="7" rx="1.5"/><rect x="13" y="13" width="7" height="7" rx="1.5"/>',
    stack: '<path d="M12 4 3.5 8.5 12 13l8.5-4.5L12 4Z"/><path d="m3.5 12.5 8.5 4.5 8.5-4.5"/><path d="m3.5 16.5 8.5 4.5 8.5-4.5"/>',
    sauvegardes: '<rect x="3.5" y="4.5" width="17" height="4.5" rx="1"/><path d="M5 9v9.5a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V9"/><path d="M10 13h4"/>',
    connexions: '<path d="M9 7V3.5M15 7V3.5"/><path d="M6.5 7h11v3.5a5.5 5.5 0 0 1-11 0V7Z"/><path d="M12 16v4.5"/>',
    maison: '<path d="M4 11.5 12 5l8 6.5"/><path d="M6.5 10v9h11v-9"/><path d="M10.5 19v-5h3v5"/>',
  }
</script>

<svg viewBox="0 0 24 24" width={taille} height={taille} fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{@html TRACES[id] || ''}</svg>
