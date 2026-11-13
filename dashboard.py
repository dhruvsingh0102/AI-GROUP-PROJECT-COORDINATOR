"""Functional Streamlit frontend for the project coordinator."""
import streamlit as st
from dotenv import load_dotenv
import os

load_dotenv()
import storage


st.set_page_config(page_title="Coordinator", page_icon="🧭", layout="wide")
storage.init_db()

STATUSES = ["Pending", "In Progress", "Blocked", "Needs Clarification", "Complete"]
STATUS_COLORS = {
    "Pending": ("#eef2f7", "#465468"),
    "In Progress": ("#e8f1ff", "#2456a6"),
    "Blocked": ("#fff0ed", "#b63d2b"),
    "Needs Clarification": ("#fff7df", "#8a6410"),
    "Complete": ("#e7f6ed", "#247347"),
}

st.markdown(
    """
    <style>
      .stApp { background: #f7f8fb; }
      [data-testid="stAppViewContainer"] .main .block-container {
        max-width: 1320px; padding-top: 2rem; padding-bottom: 3rem;
      }
      [data-testid="stSidebar"] { background: #f0f3f8; border-right: 1px solid #e2e7ef; }
      [data-testid="stMetric"] {
        background: #fff; border: 1px solid #e5e9f0; border-radius: 12px;
        padding: 14px 16px; box-shadow: 0 1px 3px rgba(22, 35, 58, .04);
      }
      [data-testid="stMetricLabel"] { color: #596579; }
      [data-testid="stMetricValue"] { color: #19263a; }
      [data-testid="stVerticalBlockBorderWrapper"] {
        background: #fff; border-color: #e5e9f0; border-radius: 14px;
      }
      .stTabs [data-baseweb="tab-list"] { gap: 10px; border-bottom-color: #e5e9f0; }
      .stTabs [data-baseweb="tab"] { color: #556277; padding: 10px 14px; }
      .stTabs [aria-selected="true"] { color: #244f93; }
      div[data-testid="stForm"] { border-color: #e5e9f0; border-radius: 12px; }
      .coordinator-eyebrow {
        color: #557098; font-size: .78rem; font-weight: 700;
        letter-spacing: .08em; text-transform: uppercase; margin-bottom: .25rem;
      }
      .coordinator-subtitle { color: #627086; margin-top: -.6rem; margin-bottom: 1.4rem; }
      .stButton > button[kind="primary"] {
        background: #315fa6; border-color: #315fa6; border-radius: 9px; font-weight: 650;
      }
      .stButton > button[kind="primary"]:hover { background: #244d8c; border-color: #244d8c; }
      [data-testid="stTextInput"] input, [data-testid="stTextArea"] textarea {
        border-radius: 9px; border-color: #d9e0ea;
      }
      [data-testid="stSelectbox"] div[data-baseweb="select"] > div { border-radius: 9px; }
      [data-testid="stAlert"] { border-radius: 11px; }
      #MainMenu, footer { visibility: hidden; }
      @media (max-width: 700px) {
        [data-testid="stAppViewContainer"] .main .block-container { padding: 1rem .8rem 2rem; }
      }
    </style>
    """,
    unsafe_allow_html=True,
)


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


def render_task(task, people):
    with st.container(border=True):
        title_col, status_col = st.columns([4, 1])
        title_col.subheader(f"#{task['id']} · {task['title']}")
        bg, fg = STATUS_COLORS.get(task["status"], ("#eef2f7", "#465468"))
        status_col.markdown(
            f'<span style="display:inline-block;background:{bg};color:{fg};'
            f'padding:.35rem .7rem;border-radius:999px;font-size:.82rem;font-weight:700">'
            f'{task["status"]}</span>',
            unsafe_allow_html=True,
        )
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
            names = [person["name"] for person in people]
            left, right = st.columns(2)
            new_status = left.selectbox(
                "Change status",
                STATUSES,
                index=STATUSES.index(task["status"]),
                key=f"status_{task['id']}",
            )
            owner_options = ["Unassigned"] + names
            unblocker_options = ["None"] + names
            owner = right.selectbox(
                "Owner",
                owner_options,
                index=owner_options.index(task["assignee"] or "Unassigned"),
                key=f"owner_{task['id']}",
            )
            left, right = st.columns(2)
            unblocker = left.selectbox(
                "Can unblock",
                unblocker_options,
                index=unblocker_options.index(task["unblocker"] or "None"),
                key=f"unblocker_{task['id']}",
            )
            blocker = right.text_input(
                "Blocker (required when Blocked)",
                value=task["blocker"] or "",
                key=f"blocker_{task['id']}",
            )
            submitted = st.form_submit_button("Save task changes", type="primary")
            if submitted:
                if new_status == "Blocked" and not blocker.strip():
                    st.error("Add the dependency that is blocking this task.")
                else:
                    owner_id = next((person["id"] for person in people if person["name"] == owner), None)
                    unblocker_id = next((person["id"] for person in people if person["name"] == unblocker), None)
                    storage.update_task_management(
                        task["id"], new_status, blocker.strip() if new_status == "Blocked" else None,
                        owner_id, unblocker_id,
                    )
                    st.rerun()


st.markdown('<div class="coordinator-eyebrow">W-PS-1 · AI Group Project Coordinator</div>', unsafe_allow_html=True)
st.title("Project Coordinator")
st.markdown('<div class="coordinator-subtitle">Keep the group project moving. Track progress, replies, and blockers in one place.</div>', unsafe_allow_html=True)
if not os.getenv("TELEGRAM_BOT_TOKEN", "").strip():
    st.warning("Telegram isn’t configured yet. Add TELEGRAM_BOT_TOKEN to .env, then start the bot with python bot.py.")

people = storage.people()
all_tasks = storage.tasks()
counts = {status: sum(task["status"] == status for task in all_tasks) for status in STATUSES}
metric_cols = st.columns(len(STATUSES))
for col, (status, count) in zip(metric_cols, counts.items()):
    col.metric(status, count)

tasks_tab, activity_tab, people_tab = st.tabs(["Tasks", "Activity", "Participants"])

with tasks_tab:
    with st.expander("Send a Telegram follow-up"):
        open_tasks = [task for task in all_tasks if task["status"] != "Complete" and task["assignee"]]
        if open_tasks:
            tasks_by_id = {task["id"]: task for task in open_tasks}
            followup_task_id = st.selectbox(
                "Choose an assigned task",
                list(tasks_by_id),
                format_func=lambda task_id: f"#{task_id} · {tasks_by_id[task_id]['title']} — {tasks_by_id[task_id]['assignee']}",
            )
            st.write("In Telegram, send this command to the coordinator bot:")
            st.code(f"/ask {followup_task_id}", language=None)
        else:
            st.info("Assign an open task before sending a follow-up.")
    with st.expander("Add a task", expanded=not all_tasks):
        create_task_form(people)
    filter_col, search_col = st.columns([1, 2])
    status_filter = filter_col.selectbox("Show status", ["All"] + STATUSES)
    search = search_col.text_input("Find a task", placeholder="Search task or blocker")
    visible_tasks = all_tasks if status_filter == "All" else [task for task in all_tasks if task["status"] == status_filter]
    if search.strip():
        query = search.strip().casefold()
        visible_tasks = [
            task for task in visible_tasks
            if query in task["title"].casefold()
            or query in (task["description"] or "").casefold()
            or query in (task["blocker"] or "").casefold()
        ]
    priority = {"Blocked": 0, "Needs Clarification": 1, "Pending": 2, "In Progress": 3, "Complete": 4}
    visible_tasks.sort(key=lambda task: (priority.get(task["status"], 5), task["id"]))
    if not visible_tasks:
        st.info("No tasks match this filter yet.")
    else:
        for task in visible_tasks:
            render_task(task, people)

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
                width="stretch",
                hide_index=True,
            )
        else:
            st.info("Add participants here or run seed.py to load the demo group.")
