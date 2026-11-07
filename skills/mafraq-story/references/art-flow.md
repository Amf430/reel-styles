# الصور: Google Flow (Nano Banana Pro)

كل لقطات الحلقة تنرسم في **Google Flow** (`labs.google/flow`) بحساب علاء في كروم. نشغّله عن طريق Claude in Chrome. ما نستخدم `image-gen` المحلي للحلقات، لأنه ما يحافظ على شكل الشخصيات.

## الإعدادات
- **الموديل:** Nano Banana Pro. Nano Banana 2 هو الافتراضي، فلازم تغيّره.
- **المقاس:** عمودي 9:16.
- **عدد النسخ:** ×2، يعني كل طلب يطلع نسختين ونختار الأحسن.
- **المشروع:** الشخصيات محفوظة في المشروع كـ«Hero» و«Uncle» (Ingredients)، ونرفق صورها مع كل طلب.

## الستايل (ثابت في كل برومبت)
```
black ink comic style with bold outlines and dense crosshatching, charcoal grey palette with warm amber light
as the only accent color, the red shemagh is the only red, subtle paper grain. No text, no captions, no border,
no panel frame.
```
- **البطل:** perfectly round white mannequin head, two small dot eyes, no hair, no nose, dark charcoal hoodie, black pants, white sneakers.
- **العم:** white egg-shaped mannequin head, two small dot eyes, stern eyebrows, grey stubble, no nose, red and white checkered shemagh with black agal, white thobe, black prayer beads.
- **ماجد:** perfectly round white mannequin head, two dot eyes, small smile, no nose, plain white shemagh draped loosely without agal, white thobe.
- **أي شاشة جوال:** «glowing warm amber but completely blank, no interface». الموديل يخرب الكتابة العربية، فكل واجهة (إشعار، موجة صوت، فقاعات) تنضاف بالكود في المونتاج.
- **ولا كتابة أبداً:** no text, no license plate text, no clock numbers.

مراجع الشكل في الكِت: `refs/hero-ref.png` و`refs/uncle-ref.png` و`refs/style-ref.png`.

## الطريقة اللي نجحت (شبكة ← لوحات)
1. **شبكة 3×3:** نطلب ٩ لوحات قصة وحدة في صورة وحدة، ونرفق معها مراجع الشخصيات والستايل. لأنها تنرسم مع بعض، الشخصيات تطلع نفس الشكل في كل اللوحات. البرومبت في `prompts-ep01.md`، رقم ٤ و٨.
2. **نقص الشبكة:** `uv run scripts/split-grid.py grid.jpg panels/` يطلّع `panel-01..09.png`.
3. **نعيد رسم كل لوحة بمقاس كامل:** نرفق اللوحة المقصوصة ومرجع الشخصية، ونستخدم برومبت «Recreate the attached comic panel as a full-size, highly detailed vertical 9:16 image. Keep the same composition…» (الأرقام ٥–٧ و٩–٢٣).
4. **نختار من النسختين،** ونحفظ اللقطات بأسماء `sNN-وصف.jpg` على ترتيب المشاهد.
5. **نكبّر لـ 2K** من قائمة التنزيل في Flow (تنزيل ← 2K)، والمقاس يطلع 1536×2752.
6. **نتأكد من التطابق:** `uv run scripts/match-2k.py <episode_dir>`. لازم كل الصور تطلع OK.

## تشغيل Flow عن طريق Claude in Chrome
- **رفع الملفات:** شغّل البلوك ١ من `scripts/flow-hooks.js`، واضغط زر الإضافة في Flow. بعدها `find "captured file input"` ثم `file_upload` بمسار الصورة. الصورة لازم تكون داخل مجلد كروم يقدر يقرا منه، مثل `~/Desktop/علاء`.
- **إرفاق صورة من المكتبة:** دوّر عليها في مربع البحث، واستنى ٣ ثواني، وكبّر الصورة (zoom) وتأكد إنها الصح قبل ما تضغط إضافة. مرة أرفقنا صورة غلط لأنها كانت لسه تحمّل.
- **تنزيل 2K بالجملة:** شغّل `python3 scripts/flow-recv.py <out_dir>` في الخلفية، وبعدها البلوك ٢ والبلوك ٣ في الصفحة. أداة JS توقف بعد ٤٥ ثانية تقريباً، فشغّل اللوب في الخلفية: `window.__res=[]; (async()=>{for(const [id,n] of JOBS) window.__res.push(await window.__up2k(id,n))})()`، وبعدها اقرا `window.__res`. لما توقف المستقبل بـ `pkill`، يطلع exit 144، وهذا طبيعي.
- **مواقع الأزرار (لقطة شاشة 1440 عرض تقريباً، ولو تغيرت الواجهة خذ لقطة جديدة):**
  - مربع البحث في المنتقي: (792,135) لما البرومبت فاضي، و(792,77) لما فيه مرفقات.
  - زر الإضافة: (618,614) أو (618,557).
  - مربع البرومبت: (790,682).
  - زر الإرسال: (533,725).
  - زر +: (1045,725).

## ملاحظات من ح١
- بعض اللوحات يطلع على أطرافها خط فاتح رفيع (s03، s08، s18). نعالجها بتكبير ٣٪ في المونتاج.
- لو طلبت حركة معينة والصورة ما سوتها (مثل s17 «العم ينحني»)، عوّضها بحركة كاميرا في المونتاج، زوم دخول بطيء.
- خلّ الأماكن الفاضية في الصورة مقصودة، عشان الواجهات تنركّب فيها (الشاشات والسقف فوق الرؤوس).
