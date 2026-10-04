---
name: reel-style-new
description: "يحوّل فيديو مرجعي (رابط يوتيوب/انستا أو ملف) إلى ستايل reel-* جديد قابل لإعادة الاستخدام، أو يضيفه كثيم/خيار لستايل موجود. استخدمه لما يقول المستخدم «حلل هالفيديو وسوه ستايل»، «ابغى ستايل زي كذا»، «أضف هالستايل للمهارات». يحتاج reel-engine."
---

# reel-style-new — من فيديو مرجعي إلى ستايل

الهدف: كل ما يجيب المستخدم ستايل عجبه، يصير مهارة `reel-<name>` يقدر يطلبها بالاسم، وتتحسن مع الوقت.

**اقرأ `reel-engine` أول** (العقد، الأوامر، فروع git).

## 1) حلّل المرجع
- **يوتيوب:** افتحه في Browser pane → `document.querySelector('video')` للمدة → افتح التفريغ (Show transcript) واقرأه كامل → صوّر 6–12 لقطة: كبّر الفيديو (`position:fixed; inset:0`)، seek، screenshot. لو اللاقطة ما تلتقط `<video>`، ارسمه على canvas.
- **ملف محلي:** `ffmpeg -i ref.mp4 -vf "select='gt(scene,0.3)',scale=480:-1,tile=4x3" -frames:v 1 sheet.jpg` + لقطات على اللحظات المهمة.
- اكتب للمستخدم: وش العناصر، الألوان (hex)، الخطوط، الحركة (مدد + easing)، طريقة الدمج، وكيف كانت تتسوى في AE/Blender — وقيّم بصراحة.

## 2) قرّر: ستايل جديد أو امتداد؟
| الحالة | الإجراء |
|---|---|
| نفس الفكرة بألوان/قيم مختلفة | theme جديد في `presets.json` لستايل موجود |
| نفس الفكرة بحركة جديدة | خيار جديد (`anim`, `kind`…) في الستايل الموجود |
| عنصر بصري مختلف فعلاً | ستايل جديد `reel-<name>` |
اسأل المستخدم لو مو واضح. أسماء قصيرة بالإنجليزي: `reel-ticker`, `reel-map-pin`…

## 3) ابنِ من القالب
```bash
REEL="$(cd ~/.claude/skills/reel-engine && pwd -P)/../.."
cd "$REEL" && git switch dev && git pull && git switch -c style/reel-<name>
cp -R skills/_template skills/reel-<name> && mv skills/reel-<name>/SKILL.template.md skills/reel-<name>/SKILL.md
```
- `scene.html`: `renderAt(t)` دالة نقية للزمن (لا CSS animations/transitions/timers). كل المقاسات `× R.u`، المواقع نسب من `R.W/R.H`. استخدم `tw()`/`ease`/`rand()`/`noise1()` من base.js. للزجاج/البلور على الفيديو: `R.drawSource()` + `"needs_frames": true`.
- `presets.json`: `output` (`alpha` لطبقة فوق الفيديو / `opaque` لخلفية)، `defaults`، `themes`، `tune` (السلايدرات).
- أعِد الاستخدام: `engine/web/icons.js`, `engine/web/decor.js`, أو أضف لها (تفيد كل الستايلات).
- `SKILL.md`: frontmatter بوصف واضح (متى يُستخدم، بالعربي + كلمات إنجليزية للبحث)، الحقول، الثيمات، الحدود، «معتمد/مرفوض» فاضية، سجل التغييرات v1.

## 4) اختبر على شغل المستخدم الحقيقي
- `install.sh` (يربط المهارة الجديدة) → job على فيديو حقيقي للمستخدم → `--stills` → شوفها بنفسك → `player.py` للمستخدم.
- طولي وعرضي كلاهما لو ممكن.
- قارن مع المرجع جنب بعض، وصرّح بالفروقات.

## 5) سلّم وسجّل
- commit + push الفرع + `gh pr create --base dev` (بدون أي ذكر لـ AI). لا push على dev/main.
- قل للمستخدم اسم المهارة وكيف يطلبها، وأمثلة أوامر.
