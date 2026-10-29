

import argparse
import random
import re
import sys
from datetime import date, timedelta

import config
import db

SCHEMA_FILE = config.BASE_DIR / "schema.sql"


def create_database(reset):

    name = config.DB_NAME

    if not re.fullmatch(r"[A-Za-z0-9_]+", name):
        raise db.DBError(
            "DB_NAME in .env may only contain letters, digits and "
            "underscores (got '%s')." % name
        )

    server = db.connect(with_database=False)
    try:
        cursor = server.cursor()
        if reset:
            cursor.execute("DROP DATABASE IF EXISTS `" + name + "`")
        cursor.execute(
            "CREATE DATABASE IF NOT EXISTS `" + name + "` "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
        cursor.close()
    except Exception as exc:  
        raise db.translate_error(exc) from exc
    finally:
        server.close()


def split_sql(text):

    lines = [ln for ln in text.splitlines() if not ln.strip().startswith("--")]
    statements = "\n".join(lines).split(";")
    return [s.strip() for s in statements if s.strip()]


def run_schema():

    text = SCHEMA_FILE.read_text(encoding="utf-8")
    statements = split_sql(text)
    for statement in statements:
        db.execute(statement)
    return len(statements)


CHECK_NAME = "chk_attachment_one_owner"


def add_attachment_check():

    exists = db.query_one(
        "SELECT COUNT(*) AS n FROM information_schema.TABLE_CONSTRAINTS "
        "WHERE CONSTRAINT_SCHEMA = %s AND TABLE_NAME = 'attachments' "
        "AND CONSTRAINT_NAME = %s",
        (config.DB_NAME, CHECK_NAME),
    )
    if exists and exists["n"]:
        return "already present"
    try:
        db.execute(
            "ALTER TABLE attachments ADD CONSTRAINT " + CHECK_NAME + " CHECK ("
            "(note_id IS NOT NULL AND journal_id IS NULL) OR "
            "(note_id IS NULL AND journal_id IS NOT NULL))"
        )
        return "added"
    except db.DBError as exc:
        return "NOT added (the app will enforce the rule instead): " + exc.technical


def initialize_database(reset=False):

    create_database(reset)
    count = run_schema()
    attachment_check = add_attachment_check()
    config.UPLOAD_DIR.mkdir(exist_ok=True)
    return count, attachment_check


def has_data():

    for table in ("plots", "crops", "workers"):
        row = db.query_one("SELECT COUNT(*) AS n FROM " + table)  
        if row["n"]:
            return True
    return False


def add_minutes(hhmm, minutes):

    hours, mins = (int(x) for x in hhmm.split(":"))
    total = hours * 60 + mins + minutes
    return "%02d:%02d:00" % (total // 60, total % 60)


def seed(today=None):

    today = today or date.today()

    def day(offset):

        return today + timedelta(days=offset)

    crops = [
        ("Palay", "#D4A017", 120, "Rice. Transplant seedlings at 20 to 25 days old."),
        ("Kamatis", "#D9402B", 75, "Tomato for the market. Stake early."),
        ("Talong", "#7B3FA0", 80, "Eggplant. Watch for fruit and shoot borer."),
        ("Sitaw", "#3E8E41", 60, "Yardlong beans. Needs a trellis."),
        ("Basil", "#2E8B57", 45, "Pinch the flowers to keep leaves coming."),
        ("Mint", "#26A69A", 50, "Spreads fast, keep it in a pot."),
        ("Cherry Tomato", "#EF6C57", 70, "Prune suckers weekly."),
        ("Lettuce", "#8BC34A", 40, "Likes cool mornings and light shade."),
        ("Marigold", "#F5A623", 55, "Flowers help keep pests away."),
    ]
    crop_id, crop_days = {}, {}
    for name, color, days, notes in crops:
        crop_id[name] = db.execute(
            "INSERT INTO crops (name, color, days_to_harvest, notes) "
            "VALUES (%s, %s, %s, %s)",
            (name, color, days, notes),
        )
        crop_days[name] = days

    plots = [
        ("Palayan A", "1.5 ha", "Irrigated rice paddy near the creek."),
        ("Gulayan B", "0.5 ha", "Vegetable plot with loam soil."),
        ("Gulayan C", "0.25 ha", "Trellis rows for beans."),
        ("Raised Bed 1", "2 sq m", "Sunny backyard bed."),
        ("Raised Bed 2", "2 sq m", "Gets light shade in the afternoon."),
        ("Herb Corner", "1 sq m", "Pots beside the kitchen door."),
        ("Front Border", "3 sq m", "Flower strip along the fence."),
    ]
    plot_id = {}
    for name, area, notes in plots:
        plot_id[name] = db.execute(
            "INSERT INTO plots (name, area, notes) VALUES (%s, %s, %s)",
            (name, area, notes),
        )

    workers = [
        ("Jose Reyes", "Farm foreman", "0900-000-0001", 650, 1),
        ("Maria Santos", "Planter", "0900-000-0002", 550, 1),
        ("Ben Dela Cruz", "Irrigation tender", "0900-000-0003", 550, 1),
        ("Lito Ramos", "Harvest helper", "0900-000-0004", 500, 1),
        ("Ana Villanueva", "Seasonal worker", "0900-000-0005", 500, 1),
        ("Lola Nena", "Garden helper (watering)", "0900-000-0006", 0, 1),
        ("Kuya Migs", "Weekend garden helper", "0900-000-0007", 0, 1),
    ]
    worker_id = {}
    for name, role, phone, rate, active in workers:
        worker_id[name] = db.execute(
            "INSERT INTO workers (name, role, phone, daily_rate, active) "
            "VALUES (%s, %s, %s, %s, %s)",
            (name, role, phone, rate, active),
        )

    plantings = [
        ("Palayan A", "Palay", -60, "growing", "Wet season rice."),
        ("Gulayan B", "Kamatis", -30, "growing", "First flowers showing."),
        ("Gulayan B", "Talong", -20, "growing", "Transplanted last month."),
        ("Gulayan C", "Sitaw", -14, "growing", "Vines reaching the trellis."),
        ("Gulayan C", "Kamatis", -100, "harvested", "Good yield, sold at the market."),
        ("Raised Bed 1", "Cherry Tomato", -35, "growing", "Two plants, caged."),
        ("Raised Bed 2", "Lettuce", -15, "growing", "Seeds sown in rows."),
        ("Herb Corner", "Basil", -10, "growing", "Three pots."),
        ("Herb Corner", "Mint", -25, "growing", "One big pot."),
        ("Front Border", "Marigold", -30, "growing", "Border plants."),
    ]
    planting_id = {}
    for plot, crop, offset, status, notes in plantings:
        planted = day(offset)
        expected = planted + timedelta(days=crop_days[crop])
        planting_id[(plot, crop)] = db.execute(
            "INSERT INTO plantings (plot_id, crop_id, plant_date, "
            "expected_harvest, status, notes) VALUES (%s, %s, %s, %s, %s, %s)",
            (plot_id[plot], crop_id[crop], planted, expected, status, notes),
        )

    tasks = [
        ("Check water level in the rice paddy", 0, "high", 0, "Palayan A", "Palay", "Ben Dela Cruz"),
        ("Apply fertilizer to the kamatis", 1, "medium", 0, "Gulayan B", "Kamatis", "Maria Santos"),
        ("Stake the talong plants", 2, "medium", 0, "Gulayan B", "Talong", "Lito Ramos"),
        ("Weed the sitaw rows", -2, "high", 0, "Gulayan C", "Sitaw", "Ana Villanueva"),
        ("Pest inspection on the kamatis", -1, "medium", 1, "Gulayan B", "Kamatis", "Jose Reyes"),
        ("Buy seedlings for the next planting", 5, "low", 0, None, None, None),
        ("Prepare sacks for the palay harvest", 30, "low", 0, "Palayan A", "Palay", None),
        ("Pay weekly wages", 3, "medium", 0, None, None, "Jose Reyes"),
        ("Water the herbs", 0, "high", 0, "Herb Corner", "Basil", "Lola Nena"),
        ("Pinch the basil flowers", 1, "low", 0, "Herb Corner", "Basil", None),
        ("Prune the cherry tomato suckers", 2, "medium", 0, "Raised Bed 1", "Cherry Tomato", None),
        ("Thin out the lettuce", -1, "medium", 0, "Raised Bed 2", "Lettuce", "Kuya Migs"),
        ("Deadhead the marigolds", 4, "low", 0, "Front Border", "Marigold", None),
        ("Add compost to the beds", 7, "medium", 0, "Raised Bed 1", None, "Kuya Migs"),
        ("Order new seed packets", -3, "low", 1, None, None, None),
    ]
    for title, offset, priority, done, plot, crop, worker in tasks:
        db.execute(
            "INSERT INTO tasks (title, due_date, priority, done, plot_id, "
            "planting_id, worker_id) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (
                title,
                day(offset),
                priority,
                done,
                plot_id[plot] if plot else None,
                planting_id.get((plot, crop)),
                worker_id[worker] if worker else None,
            ),
        )

    shifts = [
        ("Jose Reyes", "Field supervision", [0, 1, 2, 3, 4, 5], "06:00", "15:00", None),
        ("Maria Santos", "Planting and weeding", [0, 1, 2, 3, 4], "06:00", "14:00", "Gulayan B"),
        ("Ben Dela Cruz", "Irrigation rounds", [0, 2, 4], "05:30", "11:30", "Palayan A"),
        ("Lito Ramos", "Harvest help", [1, 3, 5], "13:00", "17:00", "Gulayan C"),
        ("Ana Villanueva", "General field work", [0, 1, 2], "07:00", "12:00", None),
        (None, "Water the tomatoes", [0, 1, 2, 3, 4, 5, 6], "06:00", "06:30", "Raised Bed 1"),
        (None, "Water the herbs", [0, 1, 2, 3, 4, 5, 6], "17:00", "17:30", "Herb Corner"),
        (None, "Check the lettuce for pests", [0, 3], "07:00", "07:15", "Raised Bed 2"),
        ("Kuya Migs", "Weed and tidy the beds", [5], "08:00", "09:30", "Front Border"),
    ]
    for worker, title, weekdays, start, end, plot in shifts:
        for weekday in weekdays:
            db.execute(
                "INSERT INTO shifts (worker_id, title, weekday, start_time, "
                "end_time, plot_id) VALUES (%s, %s, %s, %s, %s, %s)",
                (
                    worker_id[worker] if worker else None,
                    title,
                    weekday,
                    start + ":00",
                    end + ":00",
                    plot_id[plot] if plot else None,
                ),
            )

    standard_hours = {
        "Jose Reyes": ("06:00", "15:00"),
        "Maria Santos": ("06:00", "14:00"),
        "Ben Dela Cruz": ("05:30", "11:30"),
        "Lito Ramos": ("13:00", "17:00"),
        "Ana Villanueva": ("07:00", "12:00"),
    }
    remarks_for = {"late": "Arrived late", "half_day": "Left early",
                   "absent": "No message", "leave": "Approved leave"}
    rng = random.Random(42)  
    attendance_rows = []
    for back in range(1, 15):
        att_day = day(-back)
        if att_day.weekday() == 6:  
            continue
        for name, (start, end) in standard_hours.items():
            status = rng.choices(
                ["present", "late", "half_day", "absent", "leave"],
                weights=[70, 10, 8, 7, 5],
            )[0]
            time_in = time_out = None
            if status == "present":
                time_in, time_out = start + ":00", end + ":00"
            elif status == "late":
                time_in, time_out = add_minutes(start, 25), end + ":00"
            elif status == "half_day":
                time_in, time_out = start + ":00", add_minutes(start, 240)
            attendance_rows.append(
                (worker_id[name], att_day, status, time_in, time_out,
                 remarks_for.get(status))
            )
    db.execute_many(
        "INSERT INTO attendance (worker_id, att_date, status, time_in, "
        "time_out, remarks) VALUES (%s, %s, %s, %s, %s, %s)",
        attendance_rows,
    )

    journal = [
        (0, "Rice paddy checked", "Water level is good after last night's rain. "
            "Ben cleaned the canal.", "Cloudy", "Palayan A", "Palay"),
        (-1, "Kamatis flowering", "First flowers on the kamatis. Sprayed neem "
            "oil as a precaution.", "Sunny", "Gulayan B", "Kamatis"),
        (-2, "Weeding day", "Spent the morning weeding the sitaw rows. "
            "Some leaves have small holes.", "Hot", "Gulayan C", "Sitaw"),
        (-3, "Herbs doing well", "The basil is bushy. Harvested a handful "
            "for dinner.", "Sunny", "Herb Corner", "Basil"),
        (-5, "Heavy rain", "Strong rain all afternoon. Checked the drains "
            "and the raised beds.", "Rainy", None, None),
        (-6, "Lettuce sprouting", "Lettuce seedlings are up. Will thin them "
            "next week.", "Cool", "Raised Bed 2", "Lettuce"),
        (-9, "Marigold border", "Planted marigolds along the fence to "
            "attract bees.", "Windy", "Front Border", "Marigold"),
        (-12, "Planning the month", "Listed the seedlings and fertilizer "
            "to buy this month.", "Sunny", None, None),
    ]
    for offset, title, body, mood, plot, crop in journal:
        db.execute(
            "INSERT INTO journal_entries (entry_date, title, body, "
            "mood_weather, plot_id, crop_id) VALUES (%s, %s, %s, %s, %s, %s)",
            (day(offset), title, body, mood,
             plot_id[plot] if plot else None,
             crop_id[crop] if crop else None),
        )

    notes = [
        ("Rice field water schedule",
         "Keep 3 to 5 cm of water after transplanting. Drain the field "
         "about two weeks before harvest.", "Palayan A", "Palay"),
        ("Fertilizer mix for kamatis",
         "Complete fertilizer at planting, then side-dress every 3 weeks. "
         "Water the soil, not the leaves.", "Gulayan B", "Kamatis"),
        ("Basil care tips",
         "Pinch the top leaves often. Water in the morning. "
         "Keep it out of strong afternoon sun.", "Herb Corner", "Basil"),
        ("Simple compost recipe",
         "Mix dry leaves, kitchen scraps and a little soil. "
         "Turn the pile once a week.", None, None),
    ]
    for title, body, plot, crop in notes:
        db.execute(
            "INSERT INTO notes (title, body, plot_id, crop_id) "
            "VALUES (%s, %s, %s, %s)",
            (title, body,
             plot_id[plot] if plot else None,
             crop_id[crop] if crop else None),
        )

    counts = {}
    for table in ("crops", "plots", "workers", "plantings", "tasks", "shifts",
                  "attendance", "journal_entries", "notes"):
        counts[table] = db.query_one("SELECT COUNT(*) AS n FROM " + table)["n"]
    return counts


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Create the planner database, and optionally add sample data."
    )
    parser.add_argument("--seed", action="store_true",
                        help="add sample Farm and Garden data")
    parser.add_argument("--reset", action="store_true",
                        help="DELETE the whole database first, then rebuild it")
    parser.add_argument("--yes", action="store_true",
                        help="do not ask for confirmation with --reset")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    if args.reset and not args.yes:
        answer = input(
            "This will DELETE the database '%s' and everything in it.\n"
            "Type YES to continue: " % config.DB_NAME
        )
        if answer.strip() != "YES":
            print("Cancelled. Nothing was changed.")
            return 0

    try:
        print("Connecting to MySQL at %s:%s as '%s' ..."
              % (config.DB_HOST, config.DB_PORT, config.DB_USER))
        count, attachment_check = initialize_database(args.reset)
        print("Database '%s' is ready." % config.DB_NAME)
        print("Tables created or already present (%d statements run)." % count)
        print("Attachment CHECK rule: " + attachment_check)

        if args.seed:
            if has_data():
                print("\nSample data NOT added: the database already has rows.")
                print("To start fresh, run:  python setup_db.py --reset --seed")
            else:
                counts = seed()
                print("\nSample data added:")
                for table, number in counts.items():
                    print("  %-16s %3d rows" % (table, number))
    except db.DBError as exc:
        print("\nSETUP FAILED\n" + str(exc))
        return 1
    finally:
        db.close()

    print("\nDone. Open http://localhost/phpmyadmin to look at the tables.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
