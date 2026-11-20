"""Seed a demo project: python seed.py <your name> <participant> <unblocker>"""
import sys
import storage


def main(argv):
    if len(argv) != 3:
        raise SystemExit("Usage: python seed.py <your name> <participant> <unblocker>")
    storage.init_db()
    owner, participant, unblocker = [storage.add_person(name) for name in argv]
    # One focused task keeps the required demo loop clear and works with either backend.
    title = "Connect API and run integration test"
    existing = next((task for task in storage.tasks() if task["title"] == title), None)
    if existing:
        storage.update_task_management(existing["id"], "Pending", None, participant["id"], unblocker["id"])
    else:
        storage.create_task(
            title,
            "Connect the service and verify the integration with test credentials.",
            participant["id"],
            unblocker["id"],
        )
    print("Seeded demo participants: " + ", ".join(p["name"] for p in (owner, participant, unblocker)))
    print(f"Demo task: Connect API and run integration test (Pending; assigned to {participant['name']}; unblocker: {unblocker['name']}).")
    print("Each participant links WhatsApp by messaging the configured business number with /start <their seeded name>.")


if __name__ == "__main__":
    main(sys.argv[1:])
