import traceback
import flet as ft


def main(page: ft.Page):
    page.scroll = ft.ScrollMode.AUTO
    out = []
    for name in ["db", "notify", "schedule_mobile", "jdatetime"]:
        try:
            __import__(name)
            out.append("OK   " + name)
        except Exception:
            out.append("FAIL " + name + "\n" + traceback.format_exc())
    try:
        import schedule_mobile
        out.append("TEXT: " + str(schedule_mobile.notification_text([("test", "23:59")])))
    except Exception:
        out.append("FAIL notification_text\n" + traceback.format_exc())
    try:
        import db
        db.init_db()
        out.append("DB OK: " + str(db.get_medicines()))
    except Exception:
        out.append("FAIL db\n" + traceback.format_exc())
    page.add(ft.Text("\n\n".join(out), selectable=True, size=12))


(getattr(ft, "run", None) or ft.app)(main)
