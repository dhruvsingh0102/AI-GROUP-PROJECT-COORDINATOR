"""Seed a demo project: python seed.py <your name> <participant> <unblocker>"""
import sys
import storage


def main(argv):
    if len(argv) != 3:
        raise SystemExit("Usage: python seed.py <your name> <participant> <unblocker>")
    storage.init_db()
    owner, participant, unblocker = [storage.add_person(name) for name in argv]
    # One focused task keeps the required demo loop clear.
    with storage.connect() as db:
        existing = db.execute("SELECT id FROM tasks WHERE title=? ORDER BY id LIMIT 1", ("Connect API and run integration test",)).fetchone()
        if existing:
            db.execute("UPDATE tasks SET assignee_id=?, unblocker_id=?, status='Pending', blocker=NULL WHERE id=?", (participant["id"], unblocker["id"], existing["id"]))
        else:
            db.execute("INSERT INTO tasks(title,description,assignee_id,unblocker_id,status) VALUES(?,?,?,?, 'Pending')", ("Connect API and run integration test", "Connect the service and verify the integration with test credentials.", participant["id"], unblocker["id"]))
        # Remove only the old untouched demo task; preserve it if it has update history.
        stale = db.execute("SELECT id FROM tasks WHERE title=?", ("Prepare demo walkthrough",)).fetchall()
        for (task_id,) in stale:
            has_updates = db.execute("SELECT 1 FROM updates WHERE task_id=? LIMIT 1", (task_id,)).fetchone()
            if not has_updates:
                db.execute("DELETE FROM tasks WHERE id=?", (task_id,))
    print("Seeded demo participants: " + ", ".join(p["name"] for p in (owner, participant, unblocker)))
    print(f"Demo task: Connect API and run integration test (Pending; assigned to {participant['name']}; unblocker: {unblocker['name']}).")
    print("Each participant must link Telegram with /start <their seeded name> before follow-ups or escalations can be delivered.")


if __name__ == "__main__":
    main(sys.argv[1:])
