"""
db.py - پایگاه داده SQLite برنامه‌ی دارویار (فقط کتابخانه‌ی داخلی sqlite3)

جدول‌ها:
  medicines        داروهای بیمار (نام، دوز، نوع دارو، ساعت‌های مصرف)
  medication_logs  تاریخچه‌ی مصرف برای پزشک معالج (MAR)

توابع اصلی:
  init_db()
  add_medicine(name, dose, times, drug_type="")  -> id
  get_medicines()                                -> list[dict]
  update_medicine(med_id, name, dose, times)     (ویرایش)
  delete_medicine(med_id)
  log_dose(medicine_id, scheduled_time, status="taken") -> id
  get_doctor_report(days=None)                   -> list[dict]

تست در Pydroid 3: همین فایل را Run کنید (خروجی تست چاپ می‌شود).
"""
import os
import sqlite3
from datetime import datetime

try:  # اگر jdatetime نصب باشد از آن استفاده می‌شود
    import jdatetime
except ImportError:
    jdatetime = None


# ───────────────────────── مسیر فایل دیتابیس ─────────────────────────
def _db_path() -> str:
    custom = os.environ.get("DARUYAR_DB")
    if custom:
        return custom
    # در اپ Flet روی اندروید، این پوشه قابل نوشتن است
    folder = os.environ.get("FLET_APP_STORAGE_DATA") or os.path.dirname(
        os.path.abspath(__file__)
    )
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "daruyar.db")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    return conn


# ───────────────────────── تاریخ شمسی و روز هفته ─────────────────────────
WEEKDAYS_FA = {
    5: "شنبه",
    6: "یکشنبه",
    0: "دوشنبه",
    1: "سه‌شنبه",
    2: "چهارشنبه",
    3: "پنجشنبه",
    4: "جمعه",
}

STATUS_FA = {
    "taken": "مصرف شد",
    "snoozed": "تعویق (۱۰ دقیقه بعد)",
    "skipped": "مصرف نشد (نخوردم)",
}


def _gregorian_to_jalali(gy: int, gm: int, gd: int) -> tuple[int, int, int]:
    """تبدیل میلادی به شمسی (بدون نیاز به کتابخانه)."""
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy + 1 if gm > 2 else gy
    days = (
        355666
        + 365 * gy
        + (gy2 + 3) // 4
        - (gy2 + 99) // 100
        + (gy2 + 399) // 400
        + gd
        + g_d_m[gm - 1]
    )
    jy = -1595 + 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm = 1 + days // 31
        jd = 1 + days % 31
    else:
        jm = 7 + (days - 186) // 30
        jd = 1 + (days - 186) % 30
    return jy, jm, jd


def jalali_date_str(dt: datetime) -> str:
    """مثلاً 1405/08/10"""
    if jdatetime:
        j = jdatetime.datetime.fromgregorian(datetime=dt)
        return f"{j.year:04d}/{j.month:02d}/{j.day:02d}"
    jy, jm, jd = _gregorian_to_jalali(dt.year, dt.month, dt.day)
    return f"{jy:04d}/{jm:02d}/{jd:02d}"


def weekday_fa(dt: datetime) -> str:
    return WEEKDAYS_FA[dt.weekday()]


# ───────────────────────── ساخت جدول‌ها ─────────────────────────
def init_db() -> None:
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS medicines (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT NOT NULL,
                dose       TEXT NOT NULL DEFAULT '',
                drug_type  TEXT NOT NULL DEFAULT '',
                times      TEXT NOT NULL,            -- مثل "08:00,20:00"
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS medication_logs (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                medicine_id    INTEGER,
                drug_name      TEXT NOT NULL,
                drug_type      TEXT NOT NULL DEFAULT '',
                dose           TEXT NOT NULL DEFAULT '',
                scheduled_time TEXT NOT NULL,        -- ساعت مقرر HH:MM
                taken_time     TEXT,                 -- ساعت ثبت HH:MM
                weekday        TEXT NOT NULL,        -- روز هفته (فارسی)
                jalali_date    TEXT NOT NULL,        -- 1405/08/10
                status         TEXT NOT NULL,        -- taken / snoozed / skipped
                logged_at      TEXT NOT NULL         -- زمان دقیق میلادی ISO
            );
            """
        )
    conn.close()


# ───────────────────────── داروها ─────────────────────────
def _row_to_med(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "dose": row["dose"],
        "drug_type": row["drug_type"],
        "times": [t for t in row["times"].split(",") if t],
    }


def add_medicine(name: str, dose: str = "", times=None, drug_type: str = "") -> int:
    """times: لیست مثل ["08:00", "20:00"]. شناسه‌ی داروی جدید را برمی‌گرداند."""
    times = times or []
    for t in times:
        datetime.strptime(t, "%H:%M")  # اگر فرمت غلط باشد ValueError می‌دهد
    if not name.strip():
        raise ValueError("نام دارو خالی است")
    conn = _connect()
    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO medicines (name, dose, drug_type, times, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (
                    name.strip(),
                    dose.strip(),
                    drug_type.strip(),
                    ",".join(sorted(times)),
                    datetime.now().isoformat(timespec="seconds"),
                ),
            )
            return cur.lastrowid
    finally:
        conn.close()


def get_medicines() -> list[dict]:
    conn = _connect()
    try:
        rows = conn.execute("SELECT * FROM medicines ORDER BY id").fetchall()
        return [_row_to_med(r) for r in rows]
    finally:
        conn.close()


def update_medicine(med_id: int, name: str, dose: str = "", times=None, drug_type=None) -> None:
    """ویرایش دارو. drug_type=None یعنی نوع قبلی دست‌نخورده بماند."""
    times = times or []
    for t in times:
        datetime.strptime(t, "%H:%M")
    if not name.strip():
        raise ValueError("نام دارو خالی است")
    conn = _connect()
    try:
        with conn:
            if drug_type is None:
                conn.execute(
                    "UPDATE medicines SET name=?, dose=?, times=? WHERE id=?",
                    (name.strip(), dose.strip(), ",".join(sorted(times)), med_id),
                )
            else:
                conn.execute(
                    "UPDATE medicines SET name=?, dose=?, drug_type=?, times=?"
                    " WHERE id=?",
                    (name.strip(), dose.strip(), drug_type.strip(),
                     ",".join(sorted(times)), med_id),
                )
    finally:
        conn.close()


def delete_medicine(med_id: int) -> None:
    """دارو حذف می‌شود ولی تاریخچه‌ی مصرفش برای پزشک می‌ماند."""
    conn = _connect()
    try:
        with conn:
            conn.execute("DELETE FROM medicines WHERE id = ?", (med_id,))
    finally:
        conn.close()


# ───────────────────────── ثبت مصرف (برای دکمه‌های اعلان) ─────────────────────────
def log_dose(
    medicine_id: int,
    scheduled_time: str,
    status: str = "taken",
    when: datetime | None = None,
) -> int:
    """
    وقتی بیمار یکی از دکمه‌ها را می‌زند صدا بزنید:
      status="taken"   -> «مصرف کردم»
      status="snoozed" -> «۱۰ دقیقه بعد»
      status="skipped" -> «نخوردم»
    """
    if status not in STATUS_FA:
        raise ValueError("status باید taken, snoozed یا skipped باشد")
    when = when or datetime.now()
    conn = _connect()
    try:
        med = conn.execute(
            "SELECT * FROM medicines WHERE id = ?", (medicine_id,)
        ).fetchone()
        if med is None:
            raise ValueError("چنین دارویی وجود ندارد")
        with conn:
            cur = conn.execute(
                "INSERT INTO medication_logs (medicine_id, drug_name, drug_type,"
                " dose, scheduled_time, taken_time, weekday, jalali_date, status,"
                " logged_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    medicine_id,
                    med["name"],
                    med["drug_type"],
                    med["dose"],
                    scheduled_time,
                    None if status == "skipped" else when.strftime("%H:%M"),
                    weekday_fa(when),
                    jalali_date_str(when),
                    status,
                    when.isoformat(timespec="seconds"),
                ),
            )
            return cur.lastrowid
    finally:
        conn.close()


# ───────────────────────── گزارش پزشک معالج ─────────────────────────
def get_doctor_report(days: int | None = None) -> list[dict]:
    """
    تاریخچه‌ی مصرف، جدیدترین اول. days=7 یعنی فقط هفته‌ی اخیر.
    هر ردیف: drug_name, dose, drug_type, weekday, jalali_date,
             scheduled_time, taken_time, status (فارسی), status_key
    """
    query = "SELECT * FROM medication_logs"
    params: tuple = ()
    if days:
        from datetime import timedelta

        since = (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")
        query += " WHERE logged_at >= ?"
        params = (since,)
    query += " ORDER BY logged_at DESC"
    conn = _connect()
    try:
        rows = conn.execute(query, params).fetchall()
    finally:
        conn.close()
    return [
        {
            "drug_name": r["drug_name"],
            "dose": r["dose"],
            "drug_type": r["drug_type"],
            "weekday": r["weekday"],
            "jalali_date": r["jalali_date"],
            "scheduled_time": r["scheduled_time"],
            "taken_time": r["taken_time"] or "—",
            "status": STATUS_FA[r["status"]],
            "status_key": r["status"],
        }
        for r in rows
    ]


# ───────────────────────── تست ساده ─────────────────────────
if __name__ == "__main__":
    import tempfile

    os.environ["DARUYAR_DB"] = os.path.join(tempfile.gettempdir(), "daruyar_test.db")
    if os.path.exists(os.environ["DARUYAR_DB"]):
        os.remove(os.environ["DARUYAR_DB"])

    init_db()
    mid = add_medicine(
        "متفورمین", "۵۰۰ میلی‌گرم", ["08:00", "14:00"], "کاهنده قند خون خوراکی"
    )
    add_medicine("لوزارتان", "۲۵ میلی‌گرم", ["20:00"], "کاهنده فشار خون")
    assert len(get_medicines()) == 2

    log_dose(mid, "14:00", "taken")
    log_dose(mid, "08:00", "skipped")
    report = get_doctor_report()
    assert len(report) == 2
    for row in report:
        print(row)

    assert jalali_date_str(datetime(2026, 11, 1)) == "1405/08/10"
    update_medicine(mid, "متفورمین ۱۰۰۰", "۱۰۰۰ میلی‌گرم", ["09:00"])
    m = [x for x in get_medicines() if x["id"] == mid][0]
    assert m["times"] == ["09:00"] and m["drug_type"] == "کاهنده قند خون خوراکی"
    delete_medicine(mid)
    assert len(get_medicines()) == 1
    assert len(get_doctor_report()) == 2  # تاریخچه می‌ماند
    print("همه‌ی تست‌ها موفق بود ✓")
