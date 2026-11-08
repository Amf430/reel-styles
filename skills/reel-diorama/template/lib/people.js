// Faceless paper people drawn in code, so the template ships without licensed character art.
// Adult proportions (~7 heads), no features — the look Alaa asked for. Each returns an SVG string
// to pass to sticker(); swap in your own cut-out PNGs for a real film.
const SKIN = ["#e8b98f", "#c98f62", "#a8714b"];
function personSVG({ h = 100, robe = "#fbfdfc", head = "#fbfdfc", band = null, skin = SKIN[0], kid = false } = {}) {
  const W = kid ? 52 : 46, hr = kid ? 9.5 : 7.2;                 // viewBox 0 0 W 100
  const cx = W / 2, top = 100 - (kid ? 62 : 96);
  const sh = top + hr * 2 + 3;                                    // shoulders
  const edge = "stroke:#fff;stroke-width:1.6;stroke-linejoin:round";
  return `<svg viewBox="0 0 ${W} 100" style="width:100%;height:100%;display:block;overflow:visible">
    <ellipse cx="${cx}" cy="99" rx="${W * 0.42}" ry="1.8" fill="rgba(16,40,40,.18)"/>
    <path d="M${cx - W * 0.2} ${sh} Q${cx} ${sh - 3} ${cx + W * 0.2} ${sh} L${cx + W * 0.3} 98 L${cx - W * 0.3} 98 Z" fill="${robe}" style="${edge}"/>
    ${band ? `<path d="M${cx - W * 0.21} ${sh + 2} L${cx + W * 0.21} ${sh + 2}" stroke="${band}" stroke-width="2.4"/>` : ""}
    ${head !== null ? `<path d="M${cx - hr - 1.2} ${top + hr + 2} Q${cx - hr - 1} ${top - 1.5} ${cx} ${top - 1.2} Q${cx + hr + 1} ${top - 1.5} ${cx + hr + 1.2} ${top + hr + 2}
       L${cx + hr * 1.5} ${sh + 6} L${cx - hr * 1.5} ${sh + 6} Z" fill="${head}" style="${edge}"/>` : ""}
    <ellipse cx="${cx}" cy="${top + hr + (head !== null ? 0.8 : 0)}" rx="${head !== null ? hr * 0.72 : hr}" ry="${head !== null ? hr * 0.82 : hr}" fill="${skin}"${head !== null ? "" : ` style="${edge}"`}/>
  </svg>`;
}
// presets: a man in a thobe and ghutra, a woman in an abaya and hijab, a child
const MAN = (skin = SKIN[1]) => personSVG({ robe: "#fbfdfc", head: "#fbfdfc", band: PAL.edge, skin });
const WOMAN = (skin = SKIN[0], col = PAL.ink) => personSVG({ robe: col, head: col, skin });
const CHILD = (skin = SKIN[0], col = PAL.accent) => personSVG({ robe: col, head: null, skin, kid: true });
