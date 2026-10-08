# reel-styles

ستايلات موشن للريلز والفيديوهات كمهارات لـ Claude Code. كل ستايل مهارة تطلبها بالاسم، وكلها على محرّك واحد: HTML حتمي ← طبقات ProRes 4444 شفافة للبريمير + برفيو مباشر في المتصفح.

| المهارة | وش تسوي | التصوير |
|---|---|---|
| `reel-glass` | كروت زجاجية تبلّر الفيديو اللي وراها: نص، أيقونة، رقم يعدّ | أي تصوير |
| `reel-neon` | عنوان نيون عربي متوهج | أي تصوير (أحلى على غامق) |
| `reel-backdrop` | خلفية استوديو 2.5D بديكور مرسوم بالكود + ظل المقدّم | كروما / خلفية سادة |
| `reel-studio3d` | استوديو 3D حقيقي (Three.js): إضاءة، ظلال تتحرك مع المقدّم، DOF، موديلات GLB — بديل Blender | كروما / خلفية سادة |
| `reel-textfx` | 33 حركة نص عربي قصيرة (كشيدة، قلتش، هايلايتر، شريط خبر، رقم يعدّ…) مع صوت لكل حركة | أي تصوير |
| `reel-info` | عناصر معلومات: تعريف أسفل الشاشة، بطاقات، إحصائيات، رقم يعدّ، تقويم، قوائم، زر متابعة، شاشة ختامية، callouts | أي تصوير |
| `reel-docu` | وثائقي أحمر: كرة لامعة برقم يعدّ، كرة كلمات بكشيدة، مربع نص، عنوان بضوء، وميض عابر | أي تصوير |
| `reel-sfx` | مؤثرات صوتية خاصة متولّدة بالكود (هواء، بوب، ضربات، رايزر، نيون، ماركر…) تمشي ويا الطبقات | — |
| `reel-style-new` | يحلل فيديو مرجعي ويطلع منه ستايل جديد | — |
| `reel-engine` | المحرّك المشترك: الرندر، البرفيو، فصل المقدّم، الظل، التركيب | — |

## التثبيت (كل جهاز)
```bash
git clone https://github.com/Amf430/reel-styles.git ~/Coding/reel-styles
bash ~/Coding/reel-styles/install.sh
```
يربط المهارات في `~/.claude/skills/` ويفحص: Python 3 + `playwright`، Chromium، ffmpeg فيه `prores_ks`.
بعد أي `git pull` شغّل `install.sh` مرة ثانية عشان تنربط الستايلات الجديدة.

## الاستخدام
اطلب من Claude بالاسم، مثلاً: «سو كروت reel-glass على الشقة من ثانية 24 لـ 31: ٣ غرف، 180م²، جاهزة للسكن».

يدوياً (فيديو واحد = مشروع: `reel_work/project.json` = `{"video": "../clip.mp4", "jobs": ["cards.json"]}`):
```bash
python3 engine/player.py reel_work/project.json               # المحرّر: الفيديو كامل + تايملاين + transform
python3 engine/render.py reel_work/project.json --stills 25,27 # صور للفحص
python3 engine/render.py reel_work/project.json               # الطبقات + برفيو للفيديو كامل
```
المحرّر: تسحب القطع على التايملاين (تقديم/تأخير/دخول/خروج)، وتسحب/تدوّر/تكبّر كل قطعة على الفيديو، opacity من اللوحة، `⌘Z` تراجع، `⌘S` يحفظ في ملفات الجوب.

## البنية
```
engine/        render.py · player.py · key.py · shadow.py · composite.py · common.py
  web/         base.js (الزمن، القطع، transform) · player.html/js (المحرّر) · base.css · icons.js · decor.js
  fonts/       Tajawal (OFL)
  vendor/three Three.js r186 (MIT)
skills/<name>/ SKILL.md · scene.html · presets.json · examples/
skills/_template/  قالب الستايل الجديد
```

## التحديث
فرع من `dev` ← PR إلى `dev` ← الترقية لـ `main` يدوياً. التفاصيل في `skills/reel-engine/SKILL.md`.

## الرخص
- Tajawal: SIL Open Font License (`engine/fonts/OFL.txt`).
- Three.js: MIT (`engine/vendor/three/LICENSE`).
