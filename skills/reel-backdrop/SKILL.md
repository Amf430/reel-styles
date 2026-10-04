---
name: reel-backdrop
description: "ستايل خلفية استوديو 2.5D خلف المقدّم: جدار وأرضية بتدرّج، دائرة ضوء خلفه، ديكور مرسوم بالكود (مكتبة، رفوف، أباجورة، زرع، فازات، أقواس LED، لوحات) أو صور PNG، بعمق وبلور، مع ظل المقدّم على الأرض. يحتاج تصوير كروما/خلفية سادة. أسرع وأخف من reel-studio3d. يحتاج reel-engine."
---

# reel-backdrop — خلفية 2.5D

مأخوذ من ريلز «المقدّم على كروما بيضاء ← خلفية كحلية/وردية مع ديكور» (AE: Gradient Ramp + Fast Box Blur + عناصر PNG + ظل مقلوب). شكله «مرسوم» نظيف. للواقعية (إضاءة وظلال حقيقية) استخدم **reel-studio3d**.

**اقرأ `reel-engine` أول** — خصوصاً «فصل المقدّم».

## الخطوات
1. `key.py` على نفس `--start/--end` → افتح `_qc.jpg`.
2. job.json فيه `"subject"` → `--stills` (تطلع مركّبة) → صحح المكان/الحجم.
3. رندر كامل → خلفية + ظل + مقدّم + برفيو.

## الجوب
```json
{
  "style": "reel-backdrop", "video": "../chroma.mp4", "start": 0, "end": 6, "theme": "navy",
  "subject": { "layer": "keyed/subject.mov", "height": 0.62, "x": 0.5,
               "shadow": { "opacity": 0.5, "length": 0.32, "skew": -0.8, "blur": 14, "contact": 0.55 } },
  "params": {
    "floor": 0.8,
    "props": [
      { "type": "bookcase", "x": 0.14, "h": 0.42, "depth": 0.7 },
      { "type": "shelf", "x": 0.8, "y": 0.34, "h": 0.07, "depth": 0.6 },
      { "type": "lamp", "x": 0.84, "h": 0.36, "depth": 0.45 },
      { "type": "png", "src": "assets/chair.png", "aspect": 0.8, "x": 0.25, "h": 0.25, "depth": 0.3 }
    ]
  }
}
```
- `subject.height` = طول الشخص كنسبة من الإطار، `x` = مكان رجوله، والرجول تنحط على `floor` تلقائياً (أو `"feet": 0.86`، أو `"rect": [x,y,w,h]` يدوي). `"shadow": false` يلغي الظل.
- props: `x` مركز أفقي، `h` الارتفاع كنسبة من الإطار، `depth` 0 (قريب، حاد) → 1 (عند الجدار، مبلّر وأغمق). عناصر الأرض تقف على `y` (افتراضي: خط الأرضية)، وعناصر الجدار `y` = أعلاها.
- الأنواع: `bookcase, shelf, arch, frame, strip, lamp, plant, vase, table, pedestal, sphere, png` (`engine/web/decor.js`). لكل واحد `color` وخيارات خاصة (`led` للقوس، `branches` للفازة، `flip`).
- عام: `floor`, `cove` (نعومة التقاء الجدار بالأرض), `glow.{x,y,r,intensity}`, `beam.{on,x,angle,width,intensity}`, `depth_blur`, `vignette`, `grain`, `camera.{zoom_from, zoom_to, pan}`.
- **الكاميرا ثابتة افتراضياً.** zoom/pan يحرّك الخلفية بس والمقدّم ثابت ⇒ إذا استخدمته خله ≤ 1.5%.

## الثيمات
`navy` (ريلز الاستوديو الكحلي) · `blush` (ستايل المحل الوردي مع الأقواس) · `teal` · `seen` · `charcoal` · `sand`.

## معتمد ✅
- (فاضي)

## مرفوض ❌
- (فاضي)

## سجل التغييرات
- v1 (2026-10-04): أول نسخة — 11 عنصر ديكور، 6 ثيمات، ظل مقلوب + ظل تلامس، تموضع تلقائي للمقدّم.
