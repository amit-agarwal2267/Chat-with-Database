import streamlit as st
from app.config import config
from app.logger import get_logger
from app.db.connector_factory import get_connector
from app.health import readiness_check
from app.errors.exceptions import (
    AppError, LLMRateLimitError, LLMServiceUnavailableError, LLMTimeoutError
)
from app.core.agent.graph import build_graph
from app.core.conversation import Conversation, new_id

logger = get_logger(__name__)

STATUS_ICON = {"ok": "🟢", "error": "🔴", "not_configured": "🟡", "partial": "🟡", "not_ready": "🔴"}

CUSTOM_CSS = """
<style>
    .block-container { padding-top: 2rem; padding-bottom: 4rem; }
    div[data-testid="stChatMessage"] { border-radius: 12px; }

    .health-footer {
        position: fixed;
        bottom: 14px;
        right: 18px;
        z-index: 9999;
        background: rgba(20, 20, 20, 0.92);
        border: 1px solid rgba(255,255,255,0.08);
        padding: 6px 14px;
        border-radius: 999px;
        font-size: 0.78rem;
        color: #e5e5e5;
        box-shadow: 0 2px 10px rgba(0,0,0,0.3);
    }

    .conv-item {
        padding: 6px 10px;
        border-radius: 8px;
        cursor: pointer;
        font-size: 0.85rem;
    }
</style>
"""


def render_health_footer():
    health = readiness_check()
    icon = STATUS_ICON.get(health["status"], "⚪")
    label = health["status"].replace("_", " ").title()
    st.markdown(
        f'<div class="health-footer">{icon} System: {label}</div>',
        unsafe_allow_html=True,
    )


def render_connection_form():
    st.title("🧠 Text to SQL")
    st.caption("Connect to a database to start chatting with your data.")
    st.caption("🔒 Credentials stay in memory for this session only. Nothing is written to disk.")

    left, right = st.columns([1, 1.3], gap="large")

    with left:
        st.markdown("### 1. Choose your database")
        db_type = st.selectbox("Database Type", ["sqlite", "mysql", "oracle"], label_visibility="collapsed")
        icons = {"sqlite": "📁", "mysql": "🐬", "oracle": "🏛️"}
        st.info(f"{icons[db_type]} You selected **{db_type.upper()}**")

    with right:
        st.markdown("### 2. Enter connection details")
        with st.form("db_connection_form"):
            if db_type == "sqlite":
                db_name = st.text_input("Database file path", value="app.db")
                host = port = user = password = None
            else:
                col1, col2 = st.columns([2, 1])
                host = col1.text_input("Host", value="localhost")
                default_port = "3306" if db_type == "mysql" else "1521"
                port = col2.text_input("Port", value=default_port)
                db_name = st.text_input("Database / service name")
                user = st.text_input("Username")
                password = st.text_input("Password", type="password")

            submitted = st.form_submit_button("Connect", use_container_width=True, type="primary")

        if submitted:
            config.set("DB_TYPE", db_type)
            config.set("DB_NAME", db_name or "")
            if db_type != "sqlite":
                config.set("DB_HOST", host or "")
                config.set("DB_PORT", port or "")
                config.set("DB_USER", user or "")
                config.set("DB_PASSWORD", password or "")

            if not config.is_db_configured:
                logger.warning("Connection attempt with incomplete fields (db_type=%s)", db_type)
                st.error("Please fill in all required fields before connecting.")
                return

            try:
                with st.spinner("Connecting..."):
                    connector = get_connector(db_type)
                    connector.connect()
                    tables = connector.list_tables()
                    schema = {"tables": {t: connector.get_schema(t) for t in tables}}

                st.session_state.connector = connector
                st.session_state.connected = True
                st.session_state.schema = schema
                st.session_state.agent_graph = build_graph(connector)

                first_conv = Conversation(id=new_id())
                st.session_state.conversations = {first_conv.id: first_conv}
                st.session_state.active_conversation_id = first_conv.id

                logger.info("Connected to %s DB with %d tables, schema built for %d tables",
                            db_type, len(tables), len(schema["tables"]))
                st.rerun()

            except AppError as e:
                logger.error("DB connection failed: %s", e.message)
                st.error(e.message)
            except Exception:
                logger.exception("Unexpected DB connection error")
                st.error("Could not connect to the database. Check your details and try again.")


def render_sidebar():
    with st.sidebar:
        st.markdown("### 💬 Conversations")

        if st.button("➕ New chat", use_container_width=True):
            conv = Conversation(id=new_id())
            st.session_state.conversations[conv.id] = conv
            st.session_state.active_conversation_id = conv.id
            logger.info("Created new conversation %s", conv.id)
            st.rerun()

        st.divider()

        confirm_delete_id = st.session_state.get("confirm_delete_id")

        # Most recent first
        for conv_id, conv in reversed(list(st.session_state.conversations.items())):
            is_active = conv_id == st.session_state.active_conversation_id

            if confirm_delete_id == conv_id:
                st.warning(f"Delete \"{conv.title}\"?")
                col1, col2 = st.columns(2)
                if col1.button("✅ Yes", key=f"confirm_del_{conv_id}", use_container_width=True):
                    _delete_conversation(conv_id)
                    st.rerun()
                if col2.button("✖️ No", key=f"cancel_del_{conv_id}", use_container_width=True):
                    st.session_state.confirm_delete_id = None
                    st.rerun()
                continue

            label_col, delete_col = st.columns([5, 1])
            label = ("🟢 " if is_active else "") + conv.title
            if label_col.button(label, key=f"conv_{conv_id}", use_container_width=True):
                st.session_state.active_conversation_id = conv_id
                logger.debug("Switched to conversation %s", conv_id)
                st.rerun()

            if delete_col.button("🗑️", key=f"del_{conv_id}"):
                st.session_state.confirm_delete_id = conv_id
                st.rerun()

        st.divider()
        if st.button("🔌 Disconnect", use_container_width=True):
            logger.info("Disconnecting DB and clearing session")
            st.session_state.connector.disconnect()
            config.clear()
            st.session_state.clear()
            st.rerun()


def _delete_conversation(conv_id: str):
    conv = st.session_state.conversations.pop(conv_id, None)
    if conv is None:
        logger.warning("Attempted to delete non-existent conversation %s", conv_id)
        return

    logger.info("Deleted conversation %s ('%s') with %d messages", conv_id, conv.title, len(conv.messages))
    st.session_state.confirm_delete_id = None

    if st.session_state.active_conversation_id == conv_id:
        if st.session_state.conversations:
            # fall back to the most recently created remaining conversation
            st.session_state.active_conversation_id = next(reversed(st.session_state.conversations))
            logger.debug("Active conversation switched to %s after deletion", st.session_state.active_conversation_id)
        else:
            # no conversations left — create a fresh one so the UI never has zero conversations
            new_conv = Conversation(id=new_id())
            st.session_state.conversations[new_conv.id] = new_conv
            st.session_state.active_conversation_id = new_conv.id
            logger.info("Created replacement conversation %s after deleting the last one", new_conv.id)


def render_message(conv: Conversation, msg, position: int):
    editing = st.session_state.get("editing_message_id") == msg.id

    with st.chat_message(msg.role):
        if editing:
            new_content = st.text_area("Edit message", value=msg.content, key=f"edit_area_{msg.id}", label_visibility="collapsed")
            col1, col2 = st.columns([1, 1])
            if col1.button("Save & regenerate", key=f"save_{msg.id}", use_container_width=True):
                logger.info("User edited message %s in conversation %s", msg.id, conv.id)
                conv.branch_from(msg.id)
                st.session_state.editing_message_id = None
                st.session_state.pending_prompt = new_content
                st.rerun()
            if col2.button("Cancel", key=f"cancel_{msg.id}", use_container_width=True):
                st.session_state.editing_message_id = None
                st.rerun()
        else:
            st.markdown(msg.content)
            if msg.data:
                st.dataframe(msg.data, use_container_width=True)
            if msg.role == "user":
                if st.button("✏️ Edit", key=f"editbtn_{msg.id}"):
                    st.session_state.editing_message_id = msg.id
                    st.rerun()


def run_agent_turn(conv: Conversation, user_prompt: str):
    conv.add("user", user_prompt)

    with st.chat_message("assistant"):
        try:
            with st.spinner("Thinking..."):
                logger.debug("Invoking agent graph | conversation=%s query=%r", conv.id, user_prompt)
                result = st.session_state.agent_graph.invoke({
                    "user_query": user_prompt,
                    "messages": conv.to_lc_messages()[:-1],  # exclude the message just added
                    "schema": st.session_state.schema,
                    "db_type": config.DB_TYPE,
                })

            response_text = result["final_response"]
            query_result = result.get("query_result")
            st.markdown(response_text)
            if query_result:
                st.dataframe(query_result, use_container_width=True)

            conv.add("assistant", response_text, data=query_result)
            logger.info("Turn completed | conversation=%s plan=%s rows=%s",
                        conv.id, result.get("plan_decision"), len(query_result) if query_result else 0)

        except (LLMRateLimitError, LLMServiceUnavailableError, LLMTimeoutError) as e:
            logger.warning("Retryable LLM error surfaced to user | conversation=%s error=%s", conv.id, type(e).__name__)
            st.error(f"⚠️ {e.message}")
            if st.button("🔄 Retry", key=f"retry_{new_id()}"):
                st.session_state.pending_prompt = user_prompt
                conv.branch_from(conv.messages[-1].id) if conv.messages and conv.messages[-1].role == "user" else None
                st.rerun()

        except AppError as e:
            logger.error("Agent turn failed | conversation=%s error=%s", conv.id, e.message)
            st.error(e.message)

        except Exception:
            logger.exception("Unhandled agent execution failure | conversation=%s", conv.id)
            st.error("Something went wrong processing that question.")


def render_chat_interface():
    render_sidebar()
    conv = st.session_state.conversations[st.session_state.active_conversation_id]

    st.title("💬 " + conv.title)

    if not conv.messages:
        st.markdown("##### Try asking:")
        cols = st.columns(3)
        suggestions = ["Show me the first 10 rows", "What tables are available?", "Summarize this dataset"]
        for col, suggestion in zip(cols, suggestions):
            if col.button(suggestion, use_container_width=True):
                st.session_state.pending_prompt = suggestion
                st.rerun()

    for i, msg in enumerate(conv.messages):
        render_message(conv, msg, i)

    prompt = st.chat_input("Ask a question about your data...")
    if "pending_prompt" in st.session_state:
        prompt = st.session_state.pop("pending_prompt")

    if prompt:
        run_agent_turn(conv, prompt)

    render_health_footer()


def run():
    st.set_page_config(page_title="Text to SQL", page_icon="🧠", layout="wide")
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

    if "connected" not in st.session_state:
        st.session_state.connected = False

    if not st.session_state.connected:
        render_connection_form()
        render_health_footer()
    else:
        render_chat_interface()


if __name__ == "__main__":
    run()