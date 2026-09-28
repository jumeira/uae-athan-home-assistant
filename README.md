# UAE Athan for Home Assistant

تكامل مخصص يضيف مواقيت الصلاة لثلاث عشرة مدينة ومنطقة في دولة الإمارات إلى
Home Assistant. يستقبل التكامل المواقيت من خدمة جميرابس، ثم يرسل حدثاً عند
دخول وقت كل صلاة مع رابط تسجيل الأذان الذي اختاره المستخدم.

## المزايا

- إعداد كامل من واجهة Home Assistant باللغتين العربية والإنجليزية.
- 13 مدينة ومنطقة: أبوظبي، دبي، الشارقة، عجمان، أم القيوين، رأس الخيمة،
  الفجيرة، العين، ليوا، أرياف دبي، حتا، خورفكان، وكلباء.
- حساسات لأوقات الصلوات الخمس، والصلاة القادمة، ووقت الصلاة القادمة.
- اختيار تسجيل مستقل للفجر وتسجيل لبقية الصلوات من مكتبة جميرابس.
- حدث `uae_athan_event` للأتمتة، وإجراء اختباري لإطلاق الحدث فوراً.
- تحقق صارم من مصدر كل منطقة قبل قبول أي مواقيت.

## التثبيت اليدوي

1. فك ملف `uae-athan-home-assistant.zip` داخل مجلد إعداد Home Assistant.
2. تأكد من وجود المسار `custom_components/uae_athan/manifest.json`.
3. أعد تشغيل Home Assistant.
4. افتح **الإعدادات ← الأجهزة والخدمات ← إضافة تكامل** وابحث عن
   **UAE Athan**.
5. اختر المدينة أو المنطقة وتسجيلات الأذان.

يمكن أيضاً إضافة مستودع المشروع كمستودع مخصص من HACS بعد نشره على GitHub.

## الكيانات

- `sensor.*_next_prayer`: اسم الصلاة القادمة.
- `sensor.*_next_prayer_time`: وقت الصلاة القادمة كتاريخ ووقت.
- خمسة حساسات زمنية للفجر والظهر والعصر والمغرب والعشاء.

تعرض خصائص الكيانات المنطقة، وطريقة الحساب، ورابط التسجيل الصوتي المختار.

## الحدث

يرسل التكامل الحدث التالي عند دخول وقت الصلاة:

```text
uae_athan_event
```

ومن أهم بياناته:

- `prayer_id`
- `prayer` و`prayer_ar`
- `date` و`time` و`due_at`
- `area_id` واسم المنطقة
- `audio_url` و`audio_content_type`
- `source` و`method`

## مثال تشغيل الأذان على جهاز صوتي

```yaml
alias: UAE Athan - Play on speaker
triggers:
  - trigger: event
    event_type: uae_athan_event
conditions:
  - condition: template
    value_template: "{{ trigger.event.data.test | default(false) or trigger.event.data.type == 'prayer_time_due' }}"
actions:
  - action: media_player.play_media
    target:
      entity_id: media_player.living_room
    data:
      media_content_id: "{{ trigger.event.data.audio_url }}"
      media_content_type: "{{ trigger.event.data.audio_content_type | default('audio/mpeg') }}"
mode: restart
```

## الاختبار والتحديث

من **أدوات المطور ← الإجراءات**:

- `uae_athan.test_prayer`: يطلق حدثاً تجريبياً فوراً مع رابط التسجيل المختار.
- `uae_athan.refresh`: يجلب المواقيت ومكتبة الصوتيات الآن.

## مصدر المواقيت

يتصل Home Assistant بخدمة جميرابس فقط. تطبق الخدمة سياسة مصدرين واضحة:

- دبي وأرياف دبي وحتا: جدول IACAD الميلادي الدائم المعاد نشره عبر جميرابس.
- المناطق العشر الأخرى: محرك جميرابس `uae_praytimes_evidence_v2`.

يتحقق التكامل من المنطقة والمزود والوضع ومعلومات توليد كل يوم. ويرفض أي استجابة
تستخدم مزوداً غير معروف، أو جدول IACAD خارج مناطق دبي الثلاث، أو نموذجاً غير
محرك v2 في بقية المناطق.

## التطوير

```bash
python3 scripts/validate_release.py
python3 scripts/build_release.py
```

ينتج أمر البناء الملف `build/uae-athan-home-assistant.zip`.
