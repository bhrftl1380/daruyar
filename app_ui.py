"""
app_ui.py - رابط کاربری دارویار (Flet)
اتصال db.py و schedule_mobile.py به UI + به‌روزرسانی نوار اعلان دائمی.
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
    save_button = ft.FilledButton("ذخیره تغییرات", icon=ft.Icons.CHECK, visible=False)
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
