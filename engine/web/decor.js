// Vector studio decor drawn in code (no downloaded assets). Each entry returns
// { svg, aspect, mount } where aspect = width/height and mount = "floor" | "wall".
// Shading assumes a key light from the upper left; colours come from the theme.

let uid = 0;
const id = (p) => `${p}${++uid}`;

const shade = (hex, k) => {
  // k>0 lighten, k<0 darken
  const n = parseInt(hex.replace("#", ""), 16);
  let r = (n >> 16) & 255, g = (n >> 8) & 255, b = n & 255;
  const f = (c) => Math.round(k >= 0 ? c + (255 - c) * k : c * (1 + k));
  return `rgb(${f(r)},${f(g)},${f(b)})`;
};

function lathe(gid, base) {
  return `<linearGradient id="${gid}" x1="0" x2="1">
    <stop offset="0" stop-color="${shade(base, 0.25)}"/><stop offset=".35" stop-color="${shade(base, 0.08)}"/>
    <stop offset=".75" stop-color="${shade(base, -0.28)}"/><stop offset="1" stop-color="${shade(base, -0.45)}"/></linearGradient>`;
}

export const DECOR = {
  vase(T, o = {}) {
    const g = id("v"), c = o.color || T.ceramic;
    const branches = o.branches !== false
      ? Array.from({ length: 7 }, (_, i) => {
          const a = -0.9 + i * 0.3, x2 = 20 + Math.sin(a) * 26, y2 = 4 + Math.abs(Math.cos(a)) * 4;
          return `<path d="M20 44 Q${20 + Math.sin(a) * 10} 24 ${x2} ${y2}" stroke="${o.branch || shade(T.wood, 0.35)}" stroke-width="0.7" fill="none"/>
                  <ellipse cx="${x2}" cy="${y2 + 3}" rx="2.2" ry="5" fill="${o.plume || shade(T.ceramic, -0.12)}" opacity=".85" transform="rotate(${a * 40} ${x2} ${y2 + 3})"/>`;
        }).join("")
      : "";
    return {
      aspect: 0.42, mount: "floor",
      svg: `<svg viewBox="0 0 40 96"><defs>${lathe(g, c)}</defs>${branches}
        <path d="M15 44 Q13 50 10 58 Q4 72 8 86 Q11 94 20 95 Q29 94 32 86 Q36 72 30 58 Q27 50 25 44 Z" fill="url(#${g})"/>
        <ellipse cx="20" cy="44" rx="5" ry="1.2" fill="${shade(c, -0.5)}"/></svg>`,
    };
  },
  pedestal(T, o = {}) {
    const g = id("p"), c = o.color || T.ceramic;
    return {
      aspect: 0.5, mount: "floor",
      svg: `<svg viewBox="0 0 50 100"><defs>${lathe(g, c)}</defs>
        <rect x="5" y="8" width="40" height="90" fill="url(#${g})"/>
        <ellipse cx="25" cy="8" rx="20" ry="4" fill="${shade(c, 0.18)}"/><ellipse cx="25" cy="98" rx="20" ry="2.5" fill="${shade(c, -0.4)}"/></svg>`,
    };
  },
  table(T, o = {}) {
    const g = id("t"), c = o.color || T.wood;
    return {
      aspect: 0.9, mount: "floor",
      svg: `<svg viewBox="0 0 90 100"><defs>${lathe(g, c)}</defs>
        <rect x="41" y="14" width="8" height="84" fill="url(#${g})"/>
        <ellipse cx="45" cy="98" rx="20" ry="3" fill="${shade(c, -0.35)}"/>
        <ellipse cx="45" cy="12" rx="43" ry="8" fill="${shade(c, -0.25)}"/><ellipse cx="45" cy="10" rx="43" ry="8" fill="${shade(c, 0.1)}"/></svg>`,
    };
  },
  lamp(T, o = {}) {
    // Floor lamp: warm shade that glows.
    const g = id("l"), gl = id("lg"), c = o.color || T.accent;
    return {
      aspect: 0.42, mount: "floor", glow: { x: 0.5, y: 0.13, color: c },
      svg: `<svg viewBox="0 0 42 100" overflow="visible"><defs>
        <radialGradient id="${gl}"><stop offset="0" stop-color="${c}" stop-opacity=".55"/><stop offset="1" stop-color="${c}" stop-opacity="0"/></radialGradient>
        <linearGradient id="${g}" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="${shade(c, 0.6)}"/><stop offset="1" stop-color="${c}"/></linearGradient></defs>
        <circle cx="21" cy="14" r="34" fill="url(#${gl})"/>
        <rect x="20" y="22" width="2" height="74" fill="${shade(T.wood, -0.4)}"/>
        <path d="M9 22 L33 22 L28 4 L14 4 Z" fill="url(#${g})"/>
        <ellipse cx="21" cy="97" rx="9" ry="2" fill="${shade(T.wood, -0.5)}"/></svg>`,
    };
  },
  plant(T, o = {}) {
    const g = id("pt"), c = o.color || T.leaf, pot = o.pot || T.ceramic;
    const leaves = Array.from({ length: 11 }, (_, i) => {
      const a = -75 + i * 15, len = 26 + (i % 3) * 7;
      return `<ellipse cx="30" cy="${58 - len / 2}" rx="${4.5 + (i % 2)}" ry="${len / 2}" fill="${shade(c, ((i % 4) - 1.5) * 0.12)}" transform="rotate(${a} 30 58)"/>`;
    }).join("");
    return {
      aspect: 0.62, mount: "floor",
      svg: `<svg viewBox="0 0 60 100" overflow="visible"><defs>${lathe(g, pot)}</defs>${leaves}
        <path d="M16 62 L44 62 L40 97 L20 97 Z" fill="url(#${g})"/><rect x="14" y="58" width="32" height="6" rx="1.5" fill="${shade(pot, 0.1)}"/></svg>`,
    };
  },
  shelf(T, o = {}) {
    // Wall shelf with books and a small vase.
    const c = o.color || T.wood, books = T.books || ["#ddd"];
    let x = 6, items = "";
    for (let i = 0; i < 9; i++) {
      const w = 3 + ((i * 7) % 4), h = 16 + ((i * 5) % 7);
      items += `<rect x="${x}" y="${30 - h}" width="${w}" height="${h}" fill="${books[i % books.length]}"/>`;
      x += w + 0.4;
    }
    const vg = id("sv");
    items += `<defs>${lathe(vg, T.ceramic)}</defs><path d="M70 30 Q64 24 67 16 Q70 12 73 16 Q76 24 70 30Z" fill="url(#${vg})"/>`;
    items += `<circle cx="86" cy="25" r="5" fill="${shade(T.ceramic, -0.1)}"/>`;
    return {
      aspect: 3.2, mount: "wall",
      svg: `<svg viewBox="0 0 100 31">${items}<rect x="0" y="30" width="100" height="1.6" fill="${shade(c, 0.1)}"/><rect x="0" y="31.4" width="100" height=".6" fill="${shade(c, -0.4)}"/></svg>`,
    };
  },
  bookcase(T, o = {}) {
    const c = o.color || T.wood, books = T.books || ["#ddd"];
    let body = `<rect x="0" y="0" width="60" height="100" fill="${shade(c, -0.55)}"/>`;
    for (let s = 0; s < 4; s++) {
      const y = 4 + s * 24;
      let x = 4;
      for (let i = 0; i < 11 && x < 54; i++) {
        const w = 2.5 + ((i * 3 + s) % 3), h = 14 + ((i * 5 + s * 3) % 6);
        if ((i + s) % 5 === 4) { x += 4; continue; }
        body += `<rect x="${x}" y="${y + 20 - h}" width="${w}" height="${h}" fill="${books[(i + s) % books.length]}"/>`;
        x += w + 0.3;
      }
      body += `<rect x="0" y="${y + 20}" width="60" height="2.2" fill="${shade(c, 0.05)}"/>`;
    }
    body += `<rect x="0" y="0" width="2.5" height="100" fill="${shade(c, 0.12)}"/><rect x="57.5" y="0" width="2.5" height="100" fill="${shade(c, -0.25)}"/>`;
    return { aspect: 0.6, mount: "floor", svg: `<svg viewBox="0 0 60 100">${body}</svg>` };
  },
  arch(T, o = {}) {
    // Arched wall niche with a glowing edge (the "boutique" look).
    const g = id("a"), c = o.color || T.wall_bottom, led = o.led ?? T.accent;
    return {
      aspect: 0.55, mount: "wall",
      svg: `<svg viewBox="0 0 55 100" overflow="visible"><defs>
        <linearGradient id="${g}" x1="0" x2="1"><stop offset="0" stop-color="${shade(c, -0.35)}"/><stop offset=".5" stop-color="${shade(c, -0.15)}"/><stop offset="1" stop-color="${shade(c, -0.3)}"/></linearGradient></defs>
        <path d="M2 100 L2 27.5 A25.5 25.5 0 0 1 53 27.5 L53 100 Z" fill="${shade(c, 0.12)}"/>
        <path d="M6 100 L6 27.5 A21.5 21.5 0 0 1 49 27.5 L49 100 Z" fill="url(#${g})"/>
        ${led ? `<path d="M6 100 L6 27.5 A21.5 21.5 0 0 1 49 27.5 L49 100" fill="none" stroke="${led}" stroke-width="1" opacity=".9" style="filter:drop-shadow(0 0 2px ${led})"/>` : ""}
        <rect x="6" y="56" width="43" height="1.6" fill="${shade(c, 0.2)}"/><rect x="6" y="78" width="43" height="1.6" fill="${shade(c, 0.2)}"/></svg>`,
    };
  },
  frame(T, o = {}) {
    const g = id("f"), c = o.color || T.wood, art = o.art || T.glow;
    return {
      aspect: o.aspect || 0.78, mount: "wall",
      svg: `<svg viewBox="0 0 78 100" preserveAspectRatio="none"><defs>
        <linearGradient id="${g}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="${shade(art, 0.5)}"/><stop offset="1" stop-color="${shade(art, -0.3)}"/></linearGradient></defs>
        <rect x="0" y="0" width="78" height="100" fill="${shade(c, -0.1)}"/><rect x="5" y="5" width="68" height="90" fill="${shade(T.ceramic, -0.03)}"/>
        <rect x="12" y="12" width="54" height="76" fill="url(#${g})"/><circle cx="46" cy="38" r="12" fill="${shade(T.accent, 0.1)}" opacity=".8"/>
        <path d="M12 88 Q30 60 44 70 T66 58 L66 88Z" fill="${shade(art, -0.45)}" opacity=".7"/></svg>`,
    };
  },
  strip(T, o = {}) {
    const c = o.color || T.accent;
    return {
      aspect: 0.04, mount: "wall",
      svg: `<svg viewBox="0 0 4 100" overflow="visible"><rect x="1" y="0" width="2" height="100" rx="1" fill="${shade(c, 0.5)}" style="filter:drop-shadow(0 0 3px ${c}) drop-shadow(0 0 8px ${c})"/></svg>`,
    };
  },
  sphere(T, o = {}) {
    const g = id("s"), c = o.color || T.accent;
    return {
      aspect: 1, mount: "floor",
      svg: `<svg viewBox="0 0 100 100"><defs><radialGradient id="${g}" cx=".35" cy=".3" r=".75">
        <stop offset="0" stop-color="${shade(c, 0.5)}"/><stop offset=".6" stop-color="${c}"/><stop offset="1" stop-color="${shade(c, -0.55)}"/></radialGradient></defs>
        <circle cx="50" cy="50" r="49" fill="url(#${g})"/></svg>`,
    };
  },
};
export const DECOR_TYPES = Object.keys(DECOR);
