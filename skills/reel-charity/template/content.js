// Everything the intro and the end card say. Edit this file per project; the compositions read it.
// Texts are Arabic RTL; values that must read left-to-right (phone, IBAN, URL, @handle) stay as typed.
const CONTENT = {
  // the association's own colours: primary = headings/numbers, accent = rings/icons, the light pair = colour layers
  palette: { primary: "#32657e", accent: "#a7c258", light: "#8fbccd", lightAccent: "#d6e6a6", ink: "#3a4a52", mist: "#f1f6f7" },

  stats: {
    title: "إحصائيات الجمعية",
    // 2 to 4 cards, first card sits on the right. icon: a name from lib/icons.js
    items: [
      { value: 21, label: "برنامج منفّذ<br>هذا العام", icon: "screen" },
      { value: 1762, label: "مستفيد<br>من البرامج", icon: "people" },
      { value: 973, label: "يتيم", icon: "care" },
      { value: 405, label: "أرملة", icon: "woman" },
    ],
  },

  tagline: "اسم الجمعية .. جملة الختام",

  // 2 or 3 columns, read right to left
  columns: [
    { type: "qr", title: "المتجر الإلكتروني", src: "assets/qr.svg", caption: "example.org" },
    { type: "phone", title: "الرقم المباشر", value: "050 000 0000" },
    { type: "bank", title: "حساب الجمعية", accounts: [{ logo: "", iban: "SA00 0000 0000 0000 0000 0000" }] },
  ],

  // the strip at the bottom. icon: pin · web · mail · phone; social lists networks from lib/icons.js
  bar: [
    { icon: "pin", text: "المدينة - الحي - الشارع" },
    { icon: "web", text: "example.org", ltr: true },
    { icon: "mail", text: "info@example.org", ltr: true },
    { social: ["x", "tiktok", "instagram", "youtube"], text: "@handle", ltr: true },
  ],
};
