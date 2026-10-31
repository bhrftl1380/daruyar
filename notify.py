"""
notify.py - نوار اعلان دائمی (ongoing) برای اندروید.

روی ویندوز (هنگام تست با `flet run`) هیچ کاری نمی‌کند.
روی اندروید از pyjnius برای ساخت Notification با setOngoing(True) استفاده می‌کند.

محدودیت: این اعلان فقط تا وقتی پروسه‌ی اپ زنده است به‌روز می‌شود.
برای به‌روزرسانی در پس‌زمینه‌ی کامل باید Foreground Service یا WorkManager
در سمت Flutter/Kotlin اضافه شود (از Python به‌تنهایی ممکن نیست).
"""

CHANNEL_ID = "darupiar_ongoing"
NOTIFICATION_ID = 1001

try:
    from jnius import autoclass
except Exception:  # ویندوز/لینوکس یا pyjnius در دسترس نیست
    autoclass = None

_channel_ready = False


def _context():
    # Application context بدون نیاز به PythonActivity
    ActivityThread = autoclass("android.app.ActivityThread")
    return ActivityThread.currentApplication()


def update_persistent_notification(title: str, text: str) -> bool:
    """اعلان دائمی را می‌سازد یا به‌روز می‌کند. True یعنی ارسال شد."""
    global _channel_ready
    if autoclass is None:
        return False
    try:
        ctx = _context()
        Build_VERSION = autoclass("android.os.Build$VERSION")
        NotificationManager = autoclass("android.app.NotificationManager")
        Builder = autoclass("android.app.Notification$Builder")
        nm = ctx.getSystemService("notification")

        if Build_VERSION.SDK_INT >= 26:
            if not _channel_ready:
                Channel = autoclass("android.app.NotificationChannel")
                ch = Channel(
                    CHANNEL_ID,
                    "یادآور دارو",
                    NotificationManager.IMPORTANCE_LOW,  # بدون صدا
                )
                nm.createNotificationChannel(ch)
                _channel_ready = True
            builder = Builder(ctx, CHANNEL_ID)
        else:
            builder = Builder(ctx)

        builder.setContentTitle(title)
        builder.setContentText(text)
        builder.setSmallIcon(ctx.getApplicationInfo().icon)
        builder.setOngoing(True)       # کاربر نمی‌تواند آن را کنار بزند
        builder.setOnlyAlertOnce(True)  # با هر به‌روزرسانی صدا/لرزش ندارد
        nm.notify(NOTIFICATION_ID, builder.build())
        return True
    except Exception as exc:
        print("persistent notification failed:", exc)
        return False


def clear_persistent_notification() -> None:
    if autoclass is None:
        return
    try:
        _context().getSystemService("notification").cancel(NOTIFICATION_ID)
    except Exception:
        pass
