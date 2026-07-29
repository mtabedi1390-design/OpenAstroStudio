# AstroStudio — نمونهٔ اولیهٔ کاری (MVP)

این پیاده‌سازی نسخهٔ **کامل و نهایی** طرح اصلی نیست (آن یک پروژهٔ چند ماههٔ تیمی
است)، بلکه یک **نمونهٔ کاری واقعی** است که معماری هسته را با کد واقعی و
تست‌شده پیاده می‌کند: از inspect گرفتن یک تابع پایتون تا رسم بلوک روی بوم،
تولید کد و اجرای واقعی با astropy.

هر بخشی که در این README به‌عنوان "کار می‌کند" ذکر شده، واقعاً اجرا و تست شده
است (نه فقط نوشته شده) — نتایج تست‌ها در پایین آمده.

## چه‌چیزی پیاده‌سازی و تست شده

| بخش | وضعیت |
|---|---|
| Reflection Engine (`engine/reflection.py`) | ✅ کار می‌کند؛ توابع عادی پایتون را کامل پوشش می‌دهد |
| Library Scanner (`engine/library_scanner.py`) | ✅ یک ماژول کامل را اسکن و NodeSpec تولید می‌کند |
| لایهٔ Override دستی (`engine/overrides.py`) | ✅ برای کلاس‌هایی مثل `SkyCoord` که امضای پویا دارند |
| Graph + Dependency Solver (`engine/graph.py`) | ✅ مرتب‌سازی توپولوژیک واقعی، تشخیص حلقه |
| Code Generator (`engine/codegen.py`) | ✅ کد پایتون واقعی و قابل‌اجرا تولید می‌کند |
| Executor (`engine/executor.py`) | ✅ دو حالت: فراخوانی مستقیم و اجرای کد تولیدشده |
| Node Editor (بوم گرافیکی، `gui/node_editor.py`) | ✅ افزودن Node، کشیدن اتصال با ماوس بین پورت‌ها |
| Property Panel (`gui/property_panel.py`) | ✅ ویرایش پارامترها، نمایش مستندات |
| Library Panel (`gui/library_panel.py`) | ✅ لیست بلوک‌ها به تفکیک دسته، دابل‌کلیک برای افزودن |
| Main Window (`gui/main_window.py`) | ✅ چیدمان کامل + دکمهٔ Run + پیش‌نمایش زندهٔ کد |

## چه‌چیزی پیاده‌سازی **نشده** (نسخه‌های بعدی)

- **AI Assistant** (تبدیل جملهٔ فارسی/انگلیسی به گراف) — نیاز به یک لایهٔ NLU/LLM جدا دارد.
- **Live Renderer برای تصویر/نمودار** — فعلاً خروجی فقط در کنسول متنی نمایش داده می‌شود؛
  برای نمایش تصویر FITS یا نمودار matplotlib نیاز به یک `viewer.py` جدا با canvas گرافیکی است.
- **Plugin System به‌صورت فایل/پوشه مستقل با auto-discovery** — الگوی override فعلاً
  دستی در `engine/overrides.py` است؛ لود خودکار پلاگین از پوشه‌ی `plugins/` باقی مانده.
- **ذخیره/بارگذاری پروژه (.astroproj)** — `Graph.to_dict()` سریالایزیشن را آماده کرده
  اما UI برای Save/Load و `from_dict` بازگشتی هنوز نوشته نشده.
- **پشتیبانی از `*args` / `**kwargs`** در Reflection خودکار — فعلاً نادیده گرفته می‌شوند
  (به همین دلیل `SkyCoord` نیاز به override دستی داشت).

## یک چالش واقعی که در حین ساخت کشف شد

`SkyCoord.__init__` به‌شکل `(*args, copy=True, **kwargs)` است — پارامترهای واقعی
مثل `ra`, `dec`, `unit` در امضای واقعی پایتون دیده نمی‌شوند و فقط در مستندات و
زمان اجرا معنا پیدا می‌کنند. Reflection خودکار برای این کلاس شکست می‌خورد.
راه‌حل: `engine/overrides.py` — یک رجیستری کوچک برای تعریف دستی NodeSpec
کلاس‌های پرکاربردی که امضای پویا دارند. بقیهٔ کتابخانه (توابع عادی) کاملاً خودکار
پوشش داده می‌شود. این الگو، همان چیزی است که در استفادهٔ واقعی از این معماری
پیش‌بینی می‌شود: ۹۰٪ خودکار + ۱۰٪ override دستی برای موارد پیچیده.

## اجرا

```bash
pip install -r requirements.txt

# نسخهٔ GUI کامل:
python3 -m astrostudio.main

# یا فقط تست هستهٔ منطقی (بدون GUI)، برای دیدن Reflection+Graph+Codegen+Executor:
python3 -m astrostudio.examples.example_astropy_coords
```

خروجی واقعی `example_astropy_coords.py` هنگام اجرا:

```
n_node_1 = SkyCoord(ra=10.68, dec=41.27, unit='deg', frame='icrs')  # Coordinate (ICRS)
n_node_2 = to_galactic(coord=n_node_1)  # To Galactic
...
موفق. خروجی Node نهایی (Galactic): <SkyCoord (Galactic): (l, b) in deg
    (121.17057502, -21.57193097)>
```

## چگونه یک کتابخانهٔ جدید اضافه کنیم

برای اکثر توابع، فقط کافی است اسکن کنید:

```python
from astrostudio.engine.library_scanner import scan_module
specs = scan_module("scipy.signal", max_items=50)
```

برای کلاس‌هایی که امضای پویا دارند (مثل SkyCoord)، طبق الگوی
`engine/overrides.py` یک NodeSpec دستی بسازید و آن را به `MANUAL_OVERRIDES`
اضافه کنید.

## ساختار پوشه‌ها

```
astrostudio/
    engine/
        node.py            # دیتاکلاس‌های NodeSpec, NodeInstance, Connection
        reflection.py      # موتور Reflection (inspect + docstring_parser)
        library_scanner.py # اسکن خودکار یک ماژول کامل
        overrides.py        # override دستی برای کلاس‌های امضای پویا
        graph.py            # Graph + Dependency Solver (Kahn's algorithm)
        codegen.py          # تولید کد پایتون از گراف
        executor.py         # اجرای مستقیم یا اجرای کد تولیدشده
    gui/
        node_graphics.py    # اجزای بصری: PortItem, NodeGraphicsItem, ConnectionGraphicsItem
        node_editor.py      # QGraphicsScene/View + منطق کشیدن اتصال با ماوس
        property_panel.py   # پنل ویرایش پارامترها و مستندات
        library_panel.py    # لیست بلوک‌های قابل افزودن
        main_window.py      # چیدمان کامل پنجره
    libraries/
        astropy_adapters.py # توابع adapter برای عملیات‌هایی که property هستند
    examples/
        example_astropy_coords.py  # تست کامل بدون GUI
    main.py                 # نقطهٔ ورود GUI
```

## نکتهٔ مهم دربارهٔ محیط تست

این کد در یک محیط بدون نمایشگر (headless) با `QT_QPA_PLATFORM=offscreen` تست
شده — یعنی پنجره واقعاً ساخته شد، Node واقعاً اضافه شد، اتصال واقعاً کشیده شد،
کد واقعاً تولید و اجرا شد، و حتی یک اسکرین‌شات واقعی (`astrostudio_screenshot.png`)
از آن گرفته شده. روی سیستم خودتان با نمایشگر معمولی، فقط با
`python3 -m astrostudio.main` باجرا در می‌آید.
