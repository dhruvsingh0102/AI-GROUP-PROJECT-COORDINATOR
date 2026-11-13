"""Functional Streamlit frontend for the project coordinator."""
import streamlit as st
from dotenv import load_dotenv

load_dotenv()
import storage


st.set_page_config(page_title="Coordinator", page_icon="🧭", layout="wide")
storage.init_db()

STATUSES = ["Pending", "In Progress", "Blocked", "Needs Clarification", "Complete"]


def add_person_form(people):
    with st.form("add_person", clear_on_submit=True):
        name = st.text_input("Participant name", placeholder="e.g. Aanya")
        submitted = st.form_submit_button("Add participant")
        if submitted:
            name = name.strip()
            if not name:
                st.error("Enter a name.")
            elif any(person["name"].casefold() == name.casefold() for person in people):
                st.warning("That participant is already in the project.")
            else:
                storage.add_person(name)
                st.success(f"Added {name}.")
                st.rerun()


def create_task_form(people):
    people_names = [person["name"] for person in people]
    with st.form("create_task", clear_on_submit=True):
        title = st.text_input("Task", placeholder="Connect the payment API")
        description = st.text_area("Details", placeholder="What needs to be done?")
        left, right = st.columns(2)
        assignee_name = left.selectbox("Owner", ["Unassigned"] + people_names)
        unblocker_name = right.selectbox("Can unblock", ["None"] + people_names)
        submitted = st.form_submit_button("Add task")
        if submitted:
            if not title.strip():
                st.error("Enter a task title.")
                return
            assignee = next((person["id"] for person in people if person["name"] == assignee_name), None)
            unblocker = next((person["id"] for person in people if person["name"] == unblocker_name), None)
            storage.create_task(title.strip(), description.strip(), assignee, unblocker)
            st.success("Task added with Pending status.")
            st.rerun()


def render_task(task):
    with st.container(border=True):
        title_col, status_col = st.columns([4, 1])
        title_col.subheader(f"#{task['id']} · {task['title']}")
        status_col.markdown(f"**{task['status']}**")
        if task["description"]:
            st.write(task["description"])
        st.caption(
            f"Owner: {task['assignee'] or 'Unassigned'} · "
            f"Can unblock: {task['unblocker'] or 'Unassigned'} · "
            f"Last updated: {task['updated_at']}"
        )
        if task["status"] == "Blocked":
            st.error(f"Blocker: {task['blocker'] or 'Not recorded'}")

        with st.form(f"task_update_{task['id']}"):
            left, right = st.columns([1, 2])
            new_status = left.selectbox(
                "Change status",
                STATUSES,
                index=STATUSES.index(task["status"]),
                key=f"status_{task['id']}",
            )
            blocker = right.text_input(
                "Blocker (required when Blocked)",
                value=task["blocker"] or "",
                key=f"blocker_{task['id']}",
            )
            submitted = st.form_submit_button("Save status")
            if submitted:
                if new_status == "Blocked" and not blocker.strip():
                    st.error("Add the dependency that is blocking this task.")
                else:
                    storage.set_task_status(task["id"], new_status, blocker.strip() if new_status == "Blocked" else None)
                    st.rerun()


st.title("Project Coordinator")
st.caption("Follow up on project work, track progress, and surface blockers.")

people = storage.people()
all_tasks = storage.tasks()
counts = {status: sum(task["status"] == status for task in all_tasks) for status in STATUSES}
metric_cols = st.columns(len(STATUSES))
for col, (status, count) in zip(metric_cols, counts.items()):
    col.metric(status, count)

tasks_tab, activity_tab, people_tab = st.tabs(["Tasks", "Activity", "Participants"])

with tasks_tab:
    with st.expander("Add a task", expanded=not all_tasks):
        create_task_form(people)
    status_filter = st.selectbox("Show status", ["All"] + STATUSES)
    visible_tasks = all_tasks if status_filter == "All" else [task for task in all_tasks if task["status"] == status_filter]
    if not visible_tasks:
        st.info("No tasks match this filter yet.")
    else:
        for task in visible_tasks:
            render_task(task)

with activity_tab:
    updates, followups = st.tabs(["Participant replies", "Follow-ups sent"])
    with updates:
        history = storage.update_history()
        if not history:
            st.info("Participant replies will appear here after the bot records them.")
        for entry in history:
            with st.container(border=True):
                st.markdown(f"**{entry['title']}** · {entry['status']} · {entry['person'] or 'Unknown participant'}")
                st.write(entry["message"])
                if entry["blocker"]:
                    st.error(f"Blocker: {entry['blocker']}")
                st.caption(entry["created_at"])
    with followups:
        history = storage.followup_history()
        if not history:
            st.info("Follow-ups sent from Telegram will appear here.")
        for entry in history:
            with st.container(border=True):
                st.markdown(f"**{entry['title']}** · To {entry['recipient']}")
                st.write(entry["message"])
                st.caption(entry["sent_at"])

with people_tab:
    left, right = st.columns([2, 3])
    with left:
        st.subheader("Add participant")
        add_person_form(people)
    with right:
        st.subheader("Project participants")
        if people:
            st.dataframe(
                [
                    {"Name": person["name"], "Telegram": "Linked" if person["telegram_id"] else "Not linked"}
                    for person in people
                ],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("Add participants here or run seed.py to load the demo group.")
