---
name: mafraq-story
description: "طريقة شغل حساب «مفرق» (@mafraq.story)، قصة سعودية تفاعلية بالكوميكس، من النص لين الفيديو الجاهز: كتابة الحلقة وخيارين في آخرها، ورسم اللقطات في Google Flow (Nano Banana Pro، شبكة ← لوحات ← 2K)، وتسجيل علاء بصوته وتنظيفه وتقطيعه وتوقيت الكلمات، والمونتاج بـ HyperFrames (شاشات جوال بمنظور، وكابشن كلمة كلمة، وبطاقات الخيارات)، والصوت، والرندر، والكابشن. استخدمه لما يقول: الحلقة الجاية، حلقة جديدة، مفرق، الفويس الغلط، نص الحلقة، صور الحلقة، سجلت الصوت، ركّب الحلقة، كابشن الحلقة."
---

# مفرق: من النص لين الحلقة الجاهزة

قصة تفاعلية بالعامية، بستايل كوميكس حبر. كل حلقة تخلص بخيارين، والتعليقات تقرر الحلقة اللي بعدها. هالمهارة فيها كل اللي اشتغلنا عليه في ح١ (اعتمدها علاء ٢٠٢٦-١١-٠٦)، عشان أي حلقة جاية، ومن أي جهاز، تطلع بنفس الأسلوب.

## المراحل (بالترتيب، وكل مرحلة لها ملف)
| # | المرحلة | الملف | يطلع منها |
|---|---|---|---|
| ١ | **النص:** نتيجة التصويت ← `epNN.md` ← نص التسجيل | `references/story-format.md` | `epNN.md` و`epNN-script.txt`، وعلاء يعتمدها |
| ٢ | **الصور:** برومبتات ← Flow ← شبكة ← لوحات ← 2K | `references/art-flow.md`، و`references/prompts-ep01.md` (أمثلة) | `epNN/shots-2k/sNN-*.jpg` |
| ٣ | **الصوت:** علاء يسجّل ← تقطيع ← تنظيف ← توقيت الكلمات | `references/voice.md` | `vo/mine/lines/*.wav` و`words.json` |
| ٤ | **المونتاج:** مولّد HTML ← فحص ← لقطات ← مراجعة | `references/edit.md`، و`templates/build-ep01.py` | `epNN/edit/` |
| ٥ | **الرندر والتسليم:** رندر ← ‎-14 LUFS ← نسخة خفيفة ← كابشن | `references/edit.md` و`references/instagram.md` | `epNN-v1.mp4` والكابشن |

**قبل الرندر، علاء لازم يعتمد النص (١).** والصور والصوت يمشون مع بعض: الصور ما تحتاج الصوت، بس المونتاج يحتاج الثنين.

## الأدوات (`scripts/`)
سكربتات الصور (`split-grid` و`contact-sheet` و`match-2k` و`screen-quad`) تشتغل بـ `uv run <script>`، و`uv` ينزّل مكتباتها لحاله. سكربتات الصوت تشتغل بالأمر اللي في `voice.md`.
| السكربت | وش يسوي |
|---|---|
| `split-grid.py grid.jpg out/` | يقص شبكة 3×3 من Flow لتسع لوحات |
| `contact-sheet.py dir out.jpg` | يطلع ورقة فيها كل اللقطات عشان تراجعها |
| `match-2k.py epdir` | يتأكد إن كل لقطة 2K تطابق اللقطة الأصلية |
| `screen-quad.py shots s03 …` | يطلع زوايا شاشة الجوال في الصورة، عشان الـ `matrix3d` |
| `flow-hooks.js` + `flow-recv.py out/` | رفع الصور وتنزيل 2K بالجملة من Flow عن طريق Claude in Chrome |
| `vo-split.py` / `vo-cut.py` / `vo-words.py` | الصوت: يقسم ويفرّغ، وبعدها ينظف ويقص، وبعدها يوقّت الكلمات |
| `make-sfx.sh assets/sfx` | المؤثرات، والخلفية (bed)، وصوت الاهتزاز (buzz)، ونبض القلب |

## قواعد ما تنكسر
- **الصوت صوت علاء.** لا تقترح أصوات AI مرة ثانية. ليش؟ مكتوبة في `voice.md`.
- **ولا كتابة داخل الصور.** كل نص وكل واجهة ينضافون بالكود.
- **لا تحرق الحلقة.** لا في الكابشن، ولا في البداية.
- **ولا شي تحت الوجوه،** ولا شي في أعلى ١٦٨ بكسل من الشاشة.
- **أسرار القصة ما تدخل هالريبو** لأنه عام. مكانها الكِت الخاص.
- **ما ننشر شي.** علاء ينشر بنفسه.

## جهاز جديد
1. `git clone https://github.com/Amf430/reel-styles.git && cd reel-styles && ./install.sh`. هذا يربط المهارات في `~/.claude/skills`.
2. **الأدوات:**
   - `brew install ffmpeg node uv`
   - `pip3 install pillow numpy scipy`
   - `npx hyperframes --version`
   - أول مرة: `uvx --python 3.11 --from mlx-whisper mlx_whisper --help`. يحتاج Apple Silicon.
3. **المهارات اللي تعتمد عليها:** `hyperframes`، و`media-use`، و`ig-caption`، و`reel-sfx` (من هالريبو). بعد التركيب شغّل `python3 ~/.claude/skills/reel-sfx/synth.py` مرة وحدة.
4. **الخط:** ركّب DIN Next LT Arabic (ملفات ArbFONTS: Medium وBold وBlack) في `~/Library/Fonts`. الخط تجاري، ونسخته في الكِت.
5. **الكِت الخاص (`mafraq-kit.zip`):** فكّه في `~/Desktop/علاء/`، وانقل `docs/` إلى `~/Coding/temp/the-wrong-voice/`. وتأكد إن ح١ تبني: `python3 templates/build-ep01.py <kit>/mafraq/ep01/edit templates/ep01-words.json && cd … && npx hyperframes check`.
6. **Google Flow:** سجّل دخول بحساب علاء في كروم، وركّب إضافة Claude in Chrome. المشروع والشخصيات محفوظة في الحساب نفسه.
