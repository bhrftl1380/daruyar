"""
app_ui.py - رابط کاربری داروپیار (Flet)
اتصال db.py و schedule.py به UI + به‌روزرسانی نوار اعلان دائمی.

فرض‌های من درباره‌ی API هم‌تیمی‌ها (فقط در بخش ADAPTER تنظیم شود):
  db.init_db()
  db.get_medicines()                -> list[dict]  کلیدها: id, name, dose, times (list["HH:MM"])
  db.add_medicine(name, dose, times)
  db.delete_medicine(med_id)
  schedule_mobile.notification_text(doses) -> str   (doses = [(نام, "HH:MM")])
"""
import asyncio
from datetime import datetime

import flet as ft

import db
import schedule_mobile as schedule
from notify import update_persistent_notification

try:  # تاریخ شمسی؛ اگر نصب نبود تاریخ میلادی نمایش داده می‌شود
    import jdatetime
except ImportError:
    jdatetime = None


# ───────────────────────── ADAPTER ─────────────────────────
# اگر اسم توابع هم‌تیمی‌ها فرق داشت، فقط همین‌جا را عوض کنید.
def load_medicines() -> list[dict]:
    return db.get_medicines()


def save_medicine(name: str, dose: str, times: list[str]) -> None:
    db.add_medicine(name, dose, times)


def edit_medicine(med_id, name: str, dose: str, times: list[str]) -> None:
    db.update_medicine(med_id, name, dose, times)


def remove_medicine(med_id) -> None:
    db.delete_medicine(med_id)


def to_doses(medicines: list[dict]) -> list[tuple[str, str]]:
    """تبدیل داروها به فرمت schedule_mobile: [(نام و دوز, "HH:MM"), ...]"""
    doses = []
    for med in medicines:
        label = f"{med['name']} {med.get('dose', '')}".strip()
        for t in med.get("times", []):
            doses.append((label, t))
    return doses


def notification_body(medicines: list[dict]) -> str:
    return schedule.notification_text(to_doses(medicines))


# ───────────────────────── کمکی‌ها ─────────────────────────
def today_text(now: datetime) -> str:
    if jdatetime:
        j = jdatetime.datetime.fromgregorian(datetime=now)
        return j.strftime("%A %d %B %Y")
    return now.strftime("%Y/%m/%d")


def remaining_text(delta_seconds: float) -> str:
    total_min = max(int(delta_seconds // 60), 0)
    h, m = divmod(total_min, 60)
    if h and m:
        return f"{h} ساعت و {m} دقیقه"
    if h:
        return f"{h} ساعت"
    return f"{m} دقیقه"


def build_status(medicines: list[dict]) -> tuple[str, str]:
    """(عنوان، متن) برای کارت اصلی و نوار اعلان."""
    title = today_text(datetime.now())
    return title, notification_body(medicines)


# ───────────────────────── UI ─────────────────────────
def _main(page: ft.Page):
    page.title = "دارویار"
    page.padding = 16
    page.theme_mode = ft.ThemeMode.LIGHT
    try:
        page.rtl = True
    except Exception:
        pass

    db.init_db()

    date_text = ft.Text(size=14, color=ft.Colors.GREY_700)
    next_text = ft.Text(size=18, weight=ft.FontWeight.BOLD)
    status_card = ft.Card(
        content=ft.Container(
            padding=16,
            content=ft.Column([date_text, next_text], spacing=6),
        )
    )
    med_list = ft.ListView(expand=True, spacing=8)

    name_field = ft.TextField(label="نام دارو", expand=True)
    dose_field = ft.TextField(label="مقدار مصرف", width=120)
    times_field = ft.TextField(
        label="ساعت‌ها (مثلاً 08:00, 20:00)", hint_text="08:00, 20:00"
    )
    error_text = ft.Text(color=ft.Colors.RED_700, size=12)
    editing = {"id": None}  # شناسه‌ی داروی در حال ویرایش (None = افزودن جدید)
    add_button = ft.FilledButton("افزودن دارو", icon=ft.Icons.ADD)
    cancel_button = ft.TextButton("انصراف", visible=False)

    def refresh_status():
        title, body = build_status(load_medicines())
        date_text.value = title
        next_text.value = body
        update_persistent_notification(title, body)
        page.update()

    def refresh_list():
        med_list.controls.clear()
        for med in load_medicines():
            med_list.controls.append(
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.MEDICATION),
                    title=ft.Text(med["name"]),
                    subtitle=ft.Text(
                        f"{med.get('dose', '')} — " + "، ".join(med.get("times", []))
                    ),
                    trailing=ft.Row(
                        [
                            ft.IconButton(
                                icon=ft.Icons.EDIT_OUTLINED,
                                on_click=lambda e, m=med: on_edit(m),
                            ),
                            ft.IconButton(
                                icon=ft.Icons.DELETE_OUTLINE,
                                on_click=lambda e, mid=med["id"]: on_delete(mid),
                            ),
                        ],
                        tight=True,
                    ),
                )
            )
        page.update()

    def on_add(e):
        name = (name_field.value or "").strip()
        dose = (dose_field.value or "").strip()
        raw = (times_field.value or "").replace("،", ",")
        times = [t.strip() for t in raw.split(",") if t.strip()]
        try:
            for t in times:
                datetime.strptime(t, "%H:%M")
        except ValueError:
            error_text.value = "فرمت ساعت باید HH:MM باشد"
            page.update()
            return
        if not name or not times:
            error_text.value = "نام دارو و حداقل یک ساعت لازم است"
            page.update()
            return
        error_text.value = ""
        if editing["id"] is None:
            save_medicine(name, dose, times)
        else:
            edit_medicine(editing["id"], name, dose, times)
        reset_form()
        refresh_list()
        refresh_status()

    def reset_form():
        editing["id"] = None
        name_field.value = dose_field.value = times_field.value = ""
        add_button.text = "افزودن دارو"
        add_button.icon = ft.Icons.ADD
        cancel_button.visible = False

    def on_edit(med):
        """مقادیر دارو را داخل فرم می‌گذارد؛ با زدن «ذخیره تغییرات» ثبت می‌شود."""
        editing["id"] = med["id"]
        name_field.value = med["name"]
        dose_field.value = med.get("dose", "")
        times_field.value = ", ".join(med.get("times", []))
        error_text.value = ""
        add_button.text = "ذخیره تغییرات"
        add_button.icon = ft.Icons.CHECK
        cancel_button.visible = True
        page.update()

    def on_cancel(e):
        reset_form()
        error_text.value = ""
        page.update()

    def on_delete(med_id):
        if editing["id"] == med_id:
            reset_form()
        remove_medicine(med_id)
        refresh_list()
        refresh_status()

    async def ticker():
        """هر ۳۰ ثانیه متن زمان باقی‌مانده و اعلان را تازه می‌کند."""
        while True:
            refresh_status()
            await asyncio.sleep(30)

    page.add(
        status_card,
        ft.Row([name_field, dose_field]),
        times_field,
        error_text,
        ft.Row([add_button, cancel_button]),
        ft.Divider(),
        med_list,
    )
    add_button.on_click = on_add
    cancel_button.on_click = on_cancel
    refresh_list()
    page.run_task(ticker)


def main(page: ft.Page):
    """اگر خطایی رخ دهد، به‌جای بسته شدن برنامه، متن خطا روی صفحه نمایش داده می‌شود."""
    try:
        _main(page)
    except Exception:
        import traceback

        page.controls.clear()
        page.add(ft.Text(traceback.format_exc(), selectable=True, size=11))
        page.update()


if __name__ == "__main__":
    # Flet 1.x: ft.run ، نسخه‌های قدیمی‌تر: ft.app
    (getattr(ft, "run", None) or ft.app)(main)
