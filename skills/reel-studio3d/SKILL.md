---
name: reel-studio3d
description: "ستايل استوديو 3D حقيقي خلف المقدّم بدل Blender: غرفة cyclorama بـ Three.js، إضاءة وظلال حقيقية (ظل المقدّم نفسه يتحرك معه على الأرض والجدار)، عمق ميدان، bloom، ديكور 3D مبني بالكود أو موديلات GLB من Sketchfab/CGTrader. يحتاج تصوير كروما/خلفية سادة. استخدمه للكومبوزيتنج الواقعي. يحتاج reel-engine."
---

# reel-studio3d — استوديو 3D (بديل Blender)

مأخوذ من الجزء الأخير في الفيديو المحلَّل: Blender (Cycles، Area/Spot lights، صورة المقدّم كمرجع للظل، DOF) ← هنا نفسه في Three.js داخل نفس المحرّك، على كرت الشاشة (Metal).

**اقرأ `reel-engine` أول** — خصوصاً «فصل المقدّم».

## كيف يشتغل
- المقدّم المفصول يتحط في المشهد كلوح غير مرئي يرمي ظل فقط — والفريمات تتبدل مع الفيديو ⇒ **الظل يتحرك معه**.
- المحرّك يحسب مكان المقدّم على الشاشة (`subject_rect` في meta.json) ويركّبه بالضبط.
- الخلفية تطلع بالظل جواها (ما فيه `_shadow.mov` منفصل).

## الجوب
```json
{
  "style": "reel-studio3d", "video": "../chroma.mp4", "start": 0, "end": 6, "theme": "teal",
  "subject": { "layer": "keyed/subject.mov" },
  "params": {
    "camera": { "screen_height": 0.62, "height": 1.25, "fov": 38 },
    "props": [
      { "type": "bookcase", "pos": [-0.78, -2.35] },
      { "type": "plant", "pos": [-0.62, -1.2], "scale": 1.3 },
      { "type": "lamp", "pos": [0.8, -1.9] },
      { "type": "shelf", "pos": [0.55, 1.5], "length": 1.0 },
      { "type": "frame", "pos": [0.55, 2.2], "w": 0.55, "h": 0.7 },
      { "type": "glb", "src": "models/armchair.glb", "height": 0.9, "pos": [0.5, -0.8], "rot": -30 }
    ]
  }
}
```
### الإحداثيات (مهم)
- **x دايماً نسبة من عرض الإطار المرئي عند ذاك العمق**: −1 الحافة اليسرى، 0 الوسط، +1 اليمنى ⇒ نفس الجوب يطلع صح طولي وعرضي.
- عناصر الأرض: `pos: [x, z]` — z بالمتر: 0 = خط المقدّم، سالب = ورا باتجاه الجدار (الجدار عند `-room.wall_dist`، افتراضي −2.6).
- عناصر الجدار (`shelf, frame, arch`): `pos: [x, y]` — y الارتفاع بالمتر.
- `rot` درجات، `scale` مضاعف. `meta.json` بعد `--stills` يعطيك `view.half_width_*` (نص العرض المرئي بالمتر).
- الأنواع: `bookcase, shelf, frame, arch (LED), lamp (يضوي), plant, vase, table, pedestal, sphere, glb`.
- GLB: نزّله المستخدم (Sketchfab ← Free Standard، أو CGTrader). `height` يوحّد ارتفاعه بالمتر ويحط قاعدته على الأرض.

### باقي الحقول
`room.{wall_dist, width, height, cove, roughness}` · `camera.{fov, height, screen_height, x, look_y, lens_shift}` · `subject.{height_m, x, z, shadow: "plate"|"layer"}` ("layer" = ظل 2D منفصل بدل ظل المشهد؛ بدون ظل نهائياً: `"subject": {..., "shadow": false}` في الجوب) · `key.{pos, intensity, angle, penumbra, shadow_radius}` · `fill` · `env` (انعكاسات) · `halo.{on, x, y, size, intensity}` (دائرة الضوء خلف المقدّم) · `exposure` · `dof.{on, aperture, maxblur}` · `bloom.{strength, radius, threshold}`.

## الثيمات
`teal` (مثل نتيجة Blender في الفيديو) · `navy` · `blush` · `seen` · `charcoal` · `sand`.

## حدود
- المقدّم يتركّب فوق الخلفية ⇒ أي عنصر قدّامه (z > 0) بيطلع كأنه وراه. خل الديكور ورا خط المقدّم (z سالب).
- الكاميرا ثابتة (المقدّم متصور 2D). حركة كاميرا = لازم تتصور هي بنفسها في التصوير.
- الإضاءة على المقدّم نفسه من التصوير — طابق اتجاه `key.pos` مع إضاءة التصوير (مثلاً المفتاح من يسار الكاميرا ⇒ `pos[0]` سالب).
- الديكور المبني بالكود «نظيف/ستايلايزد»؛ للواقعية العالية استخدم GLB.

## معتمد ✅
- (فاضي)

## مرفوض ❌
- (فاضي)

## سجل التغييرات
- v1 (2026-10-04): أول نسخة — cyc، key/halo/fill، ظل متحرك من المقدّم، DOF + bloom، 10 عناصر + GLB، إحداثيات نسبية للإطار.
