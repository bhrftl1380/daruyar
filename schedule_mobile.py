# -*- coding: utf-8 -*-
"""schedule_mobile.py  -  موتور زمان‌بندی دارویار (نسخه‌ی موبایل)

یک فایل مستقل: فقط پایتون استاندارد، بدون pytest و بدون zoneinfo.
روی Pydroid 3 اجرا کنید (دکمه‌ی Play): تست‌ها خودکار اجرا می‌شوند.

doses = فهرست (نام دارو، ساعت مصرف به وقت تهران)
مثال: [("متفورمین ۵۰۰ میلی‌گرم", "14:00"), ("لوزارتان ۲۵ میلی‌گرم", "20:00")]
"""
from datetime import datetime, timedelta, timezone

# ایران از ۱۴۰۱ ساعت تابستانی ندارد، پس اختلاف ثابت UTC+3:30 است.
TEHRAN = timezone(timedelta(hours=3, minutes=30))

_FA = "۰۱۲۳۴۵۶۷۸۹"


def to_fa(text):
    """رقم‌های انگلیسی را فارسی می‌کند: '14:00' -> '۱۴:۰۰'"""
    return "".join(_FA[int(c)] if c.isdigit() else c for c in str(text))


def _now(now):
    if now is None:
        return datetime.now(TEHRAN)
    if now.tzinfo is None:  # ساعت بدون منطقه را وقت تهران حساب می‌کنیم
        return now.replace(tzinfo=TEHRAN)
    return now.astimezone(TEHRAN)


def _at(day, hhmm):
    h, m = hhmm.split(":")
    return datetime(day.year, day.month, day.day, int(h), int(m), tzinfo=TEHRAN)


def due_next(doses, now=None):
    """نوبت بعدی مصرف را برمی‌گرداند (نوبتی که ساعتش *بعد از* الان است).

    خروجی: dict با کلیدهای name, time, due_at, remaining  یا  None اگر دارویی نیست.
    - اگر امروز نوبتی نمانده باشد، اولین نوبت فردا.
    - اگر الان دقیقاً ساعت یک نوبت باشد، نوبت بعدی برگردانده می‌شود.
    """
    if not doses:
        return None
    now = _now(now)
    best = None
    for add_day in (0, 1):
        day = now + timedelta(days=add_day)
        for name, hhmm in doses:
            due = _at(day, hhmm)
            if due > now and (best is None or due < best["due_at"]):
                best = {"name": name, "time": hhmm, "due_at": due,
                        "remaining": due - now}
        if best is not None:
            break
    return best


def format_remaining(delta):
    """مدت باقی‌مانده را به متن فارسی تبدیل می‌کند (رو به بالا به دقیقه)."""
    total_min = int(-(-delta.total_seconds() // 60))  # سقف به دقیقه
    if total_min <= 0:
        return "کمتر از ۱ دقیقه"
    h, m = divmod(total_min, 60)
    if h and m:
        return to_fa("%d ساعت و %d دقیقه" % (h, m))
    if h:
        return to_fa("%d ساعت" % h)
    return to_fa("%d دقیقه" % m)


def notification_text(doses, now=None):
    """متن نوار اعلان: «۱ ساعت و ۲۵ دقیقه مانده تا مصرف X در ساعت ۱۴:۰۰»"""
    nxt = due_next(doses, now)
    if nxt is None:
        return "دارویی برای یادآوری ثبت نشده است"
    return "%s مانده تا مصرف %s در ساعت %s" % (
        format_remaining(nxt["remaining"]), nxt["name"], to_fa(nxt["time"]))


# ---------------------------------------------------------------- تست‌ها
def _t(h, m=0, s=0, day=1):
    return datetime(2026, 11, day, h, m, s, tzinfo=TEHRAN)

D = [("متفورمین ۵۰۰ میلی‌گرم", "14:00"), ("لوزارتان ۲۵ میلی‌گرم", "20:00")]


def test_next_same_day():
    r = due_next(D, _t(12, 35))
    assert r["time"] == "14:00" and r["name"].startswith("متفورمین")


def test_notification_text_matches_plan():
    assert notification_text(D, _t(12, 35)) == \
        "۱ ساعت و ۲۵ دقیقه مانده تا مصرف متفورمین ۵۰۰ میلی‌گرم در ساعت ۱۴:۰۰"


def test_rolls_to_tomorrow():
    r = due_next(D, _t(23, 0))
    assert r["time"] == "14:00" and r["due_at"].day == 2


def test_exact_time_gives_following_dose():
    assert due_next(D, _t(14, 0))["time"] == "20:00"


def test_empty_list():
    assert due_next([], _t(10)) is None
    assert "ثبت نشده" in notification_text([], _t(10))


def test_unsorted_input_picks_earliest():
    r = due_next([("B", "20:00"), ("A", "08:00"), ("C", "14:00")], _t(9))
    assert r["name"] == "C"


def test_format_remaining():
    assert format_remaining(timedelta(hours=2)) == "۲ ساعت"
    assert format_remaining(timedelta(minutes=20)) == "۲۰ دقیقه"
    assert format_remaining(timedelta(seconds=20)) == "۱ دقیقه"
    assert format_remaining(timedelta(0)) == "کمتر از ۱ دقیقه"


def test_naive_time_is_tehran():
    naive = datetime(2026, 11, 1, 12, 35)
    assert due_next(D, naive)["time"] == "14:00"


def run_tests():
    tests = [(k, v) for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    ok = 0
    for name, fn in tests:
        try:
            fn()
            print("✓", name)
            ok += 1
        except AssertionError:
            print("✗ FAILED:", name)
    print("\n%d از %d تست موفق" % (ok, len(tests)))


if __name__ == "__main__":
    run_tests()
    print("\nنمونه:", notification_text(D))
