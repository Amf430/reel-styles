---
name: reel-sfx
description: "مكتبة مؤثرات صوتية خاصة متولّدة بالكود (بدون عينات): هواء وسحبات، كلك وبوب وكيبورد، إشعارات ونغمات، ضربات وبوم وبراام، عدّاد وتكات، لمعة وقلتش ونيون، ماركر وورق وكاميرا وزوم، رايزر ودرون وستنگر. 48kHz/24-bit WAV. استخدمه لما يطلب صوت/مؤثر/SFX/whoosh/pop/ding/riser/صوت مع الحركة، أو لما ستايل reel-* يحتاج صوت يمشي ويا الطبقة."
---

# reel-sfx — مؤثرات صوتية خاصة

كل صوت يتولّد من وصفة كود في `synth.py` (موجات + نويز + فلاتر + ريفيرب صناعي)، فما فيها أي تسجيل لأحد ثاني: الأصوات ملك المستخدم بالكامل. نفس الوصفة تطلع نفس الملف على أي جهاز.

## التوليد
```bash
SFX="$(cd ~/.claude/skills/reel-sfx && pwd -P)"
python3 "$SFX/synth.py"                 # كل الأصوات → ~/.reel-styles/sfx  (+ index.json + audition.html)
python3 "$SFX/synth.py" --only pop,ding # أصوات معيّنة بس (بعد تعديل وصفة)
python3 "$SFX/synth.py" --list          # الكتالوج
```
- أول تشغيل ينزّل numpy في `~/.reel-styles/venv` (برا الريبو).
- الملفات ما تنحفظ في الريبو؛ تتولّد عند الحاجة. لو `~/.reel-styles/sfx/index.json` مو موجود، ولّدها أول.
- للاستماع: افتح `~/.reel-styles/sfx/audition.html` عبر سيرفر محلي (المتصفح يمنع الصوت من `file://`).

## الكتالوج (`index.json`)
`{ id, category, name {ar,en}, use, tags, files: ["pop.wav","pop_2.wav",…], duration }` — الأصوات اللي تتكرر كثير (pop, click, key, tap, whoosh…) لها 2–3 نسخ: بدّل بينها حتى ما يحس المشاهد بالتكرار.

| الفئة | الأصوات |
|---|---|
| whoosh | whoosh_soft ×3, whoosh_fast ×3, whoosh_deep, whip ×2, whoosh_in, swipe_ui |
| ui | click ×3, click_soft, tap ×3, pop ×3, pop_low, bubble ×2, toggle_on/off, key ×3, typing, scroll_tick |
| notify | ding, chime_up/down, notify, message_in/out, success, error, alert |
| impact | hit_deep, hit_punch ×2, slam, thud, boom, braam |
| element | tick, count_up, count_end, sparkle, shine, glitch ×2, neon_on, neon_hum, draw_line ×3, draw_circle, scribble, paper ×2, stamp, shutter, zoom_in/out, coin, cash, pin_drop |
| drama | riser, riser_long, downlifter, drone_dark, stinger, reverse_swell, tension_tick |
| reaction | correct, wrong, boing, scratch |

## أي صوت لأي حركة
| الحركة | الصوت | متى بالضبط |
|---|---|---|
| reel-hook (slam/punch) | slam أو hit_punch | على فريم الضربة |
| reel-hook (rise/stretch) | whoosh_soft | يبدأ مع الحركة |
| reel-neon | neon_on (+ neon_hum تحت لو العنوان يطول) | مع أول وميض |
| reel-glass كرت يدخل | swipe_ui أو whoosh_soft | مع الدخول |
| reel-glass رقم يعدّ | count_up ثم count_end | العد ثم لحظة الوصول |
| reel-marker | draw_line / draw_circle / scribble | يبدأ مع الرسم، نفس المدة تقريباً |
| reel-ui إشعار | notify | لما يوصل مكانه |
| reel-ui محادثة | message_in / message_out | مع كل فقاعة |
| reel-ui بحث يكتب | typing | من أول حرف |
| reel-ui زر/مؤشر | click | لحظة الضغط |
| reel-collage | paper / stamp | كل قصاصة |
| reel-map | whoosh_deep (تقريب) ثم pin_drop | الدبوس لما يلمس |
| reel-captions كلمة مميزة | pop (بدّل النسخ) | بداية الكلمة، بخفّة |
| انتقال/قطع | whip أو reverse_swell (ينتهي على القطع) | — |
| كشف كبير | riser → hit_deep أو boom | الرايزر ينتهي على الضربة |

## تلقائياً مع الرندر
أي ستايل يقدر يرجّع من `meta()` قائمة `sfx`: `[{ "t": 12.4, "id": "pop", "v": 1, "gain": -3, "len": 1.2 }]` (t على تايملاين الفيديو). `render.py` يخلطها (`engine/sfx.py`) في `<layer>_sfx.wav` يبدأ مع الطبقة، ويحطها في البرفيو فوق صوت الفيديو. في الجوب: `"sfx": false` يطفيها، و`"sfx_gain": -6` يخفضها كلها.

## مع الطبقات
- مستوى الأصوات مضبوط على peak: الضربات −1dB، الهواء −3، الواجهة والعناصر −5. في البريمير نزّلها 6–12dB تحت الصوت المتكلم.
- لا تحط صوت على كل عنصر؛ صوت لكل لحظة مهمة يكفي، وكابشن الكلمات بأصوات خفيفة جداً أو بدون.
- حط الصوت على تراك تحت الطبقة بنفس وقتها (الوقت مكتوب في اسم ملف الطبقة).

## مكتبة المستخدم الشخصية
المستخدم عنده أصوات Epidemic Sound (اشتراك، استخدام شخصي) على الهارد الخارجي. **لا تنسخها للريبو ولا ترفعها لأي مكان**؛ لو احتجتها أشّر على مسارها المحلي بس.

## معتمد ✅
- (فاضي)

## مرفوض ❌
- (فاضي)

## سجل التغييرات
- v1 (2026-10-08): أول نسخة — 62 وصفة / 81 ملف في 7 فئات، صفحة استماع، جدول الحركة ← الصوت.
