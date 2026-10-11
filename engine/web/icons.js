// Small stroke icon set (24×24, currentColor). Original drawings, free to use.
const P = {
  bed: '<path d="M3 18v-7a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v7M3 14h18M3 18v2M21 18v2"/><path d="M6 9V7a1 1 0 0 1 1-1h3a1 1 0 0 1 1 1v2M13 9V7a1 1 0 0 1 1-1h3a1 1 0 0 1 1 1v2"/>',
  bath: '<path d="M4 12h16v3a4 4 0 0 1-4 4H8a4 4 0 0 1-4-4v-3zM6 12V6a2 2 0 0 1 3.5-1.3M7 19l-1 2M17 19l1 2"/>',
  area: '<rect x="4" y="4" width="16" height="16" rx="1.5"/><path d="M8 8h3M8 8v3M16 16h-3M16 16v-3"/>',
  pin: '<path d="M12 21s7-6.2 7-11.5A7 7 0 0 0 5 9.5C5 14.8 12 21 12 21z"/><circle cx="12" cy="9.5" r="2.5"/>',
  tag: '<path d="M3 12V4h8l10 10-8 8L3 12z"/><circle cx="7.5" cy="8" r="1.5"/>',
  check: '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
  star: '<path d="M12 3.5l2.6 5.3 5.9.9-4.3 4.1 1 5.8-5.2-2.8-5.2 2.8 1-5.8-4.3-4.1 5.9-.9z"/>',
  phone: '<path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a1 1 0 0 1-1 1A16 16 0 0 1 4 5a1 1 0 0 1 1-1z"/>',
  building: '<path d="M4 21V5l8-2v18M12 21V9l8 2v10M2 21h20M7 8h2M7 12h2M7 16h2M15 13h2M15 17h2"/>',
  key: '<circle cx="8" cy="15" r="4"/><path d="M11 12l9-9M17 6l2 2M15 8l2 2"/>',
  car: '<path d="M5 16l1.5-5A2 2 0 0 1 8.4 9.5h7.2a2 2 0 0 1 1.9 1.5L19 16M4 16h16v3H4zM6.5 19v1.5M17.5 19v1.5"/><circle cx="7.5" cy="16.5" r=".6"/><circle cx="16.5" cy="16.5" r=".6"/>',
  clock: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
  arrow: '<path d="M19 12H5M11 6l-6 6 6 6"/>',
  sparkle: '<path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5L18 18M6 18l2.5-2.5M15.5 8.5L18 6"/>',
  home: '<path d="M4 11l8-7 8 7v9a1 1 0 0 1-1 1h-4v-6H9v6H5a1 1 0 0 1-1-1z"/>',
  bulb: '<path d="M9 18h6M10 21h4M12 3a6 6 0 0 0-3.5 10.9c.6.5 1 1.2 1 2V17h5v-1.1c0-.8.4-1.5 1-2A6 6 0 0 0 12 3z"/>',
  book: '<path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v15H6.5A2.5 2.5 0 0 0 4 20.5zM4 20.5A2.5 2.5 0 0 0 6.5 23H20v-5"/><path d="M8 7h8M8 10.5h6"/>',
  target: '<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1.5"/>',
  warning: '<path d="M12 3.5L2.5 20h19z"/><path d="M12 10v4.5M12 17.5v.01"/>',
  x: '<path d="M6 6l12 12M18 6L6 18"/>',
  question: '<circle cx="12" cy="12" r="8.5"/><path d="M9.5 9.5a2.6 2.6 0 0 1 5 1c0 1.8-2.5 2.2-2.5 3.8M12 17v.01"/>',
  lock: '<rect x="5" y="10.5" width="14" height="10" rx="2"/><path d="M8 10.5V8a4 4 0 0 1 8 0v2.5M12 14.5v2.5"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
  userplus: '<circle cx="10" cy="8" r="4"/><path d="M2.5 21a7.5 7.5 0 0 1 15 0M19 8v6M16 11h6"/>',
  heart: '<path d="M12 20s-7.5-4.6-7.5-10.2A4.3 4.3 0 0 1 12 7.2a4.3 4.3 0 0 1 7.5 2.6C19.5 15.4 12 20 12 20z"/>',
  bell: '<path d="M6 16V11a6 6 0 0 1 12 0v5l1.5 2h-15zM10 20.5a2 2 0 0 0 4 0"/>',
  bookmark: '<path d="M6 3.5h12v17l-6-4-6 4z"/>',
  share: '<circle cx="18" cy="5.5" r="2.5"/><circle cx="6" cy="12" r="2.5"/><circle cx="18" cy="18.5" r="2.5"/><path d="M8.2 10.8l7.6-4M8.2 13.2l7.6 4"/>',
  play: '<path d="M7 4.5v15l12-7.5z"/>',
  calendar: '<rect x="3.5" y="5" width="17" height="15.5" rx="2"/><path d="M3.5 10h17M8 3v4M16 3v4"/>',
  money: '<rect x="2.5" y="6" width="19" height="12" rx="2"/><circle cx="12" cy="12" r="2.8"/><path d="M6 9.5v5M18 9.5v5"/>',
  trend: '<path d="M3 17l6-6 4 4 8-8M15 7h6v6"/>',
  cursor: '<path d="M5 3l14 7.5-6.2 1.8L10 19z"/>',
  chart: '<path d="M4 20h16M7 16v-5M12 16V7M17 16v-8"/>',
};
export function icon(name, sw = 1.8) {
  const body = P[name];
  if (!body) return "";
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="${sw}" stroke-linecap="round" stroke-linejoin="round">${body}</svg>`;
}
export const ICONS = Object.keys(P);
