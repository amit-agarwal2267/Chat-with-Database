import streamlit as st
from langchain_core.messages import HumanMessage, AIMessage

from app.config import config
from app.logger import get_logger
from app.db.connector_factory import get_connector
from app.health import readiness_check
from app.errors.exceptions import (
    AppError, LLMRateLimitError, LLMServiceUnavailableError, LLMTimeoutError
)
from app.core.schema_extraction import extract_schema
from app.core.agent.graph import build_graph

logger = get_logger(__name__)

STATUS_ICON = {"ok": "🟢", "error": "🔴", "not_configured": "🟡", "partial": "🟡", "not_ready": "🔴"}

CUSTOM_CSS = """
<style>
    .block-container { padding-top: 2rem; }
    div[data-testid="stChatMessage"] { border-radius: 12px; }
    .status-pill {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 999px;
        font-size: 0.8rem;
        font-weight: 600;
        margin-bottom: 4px;
    }
    .pill-ok { background: #103b1f; color: #4ade80; }
    .pill-error { background: #3b1010; color: #f87171; }
    .pill-warn { background: #3b3110; color: #facc15; }
</style>
"""


def status_pill(status: str, label: str) -> str:
    css_class = {"ok": "pill-ok", "error": "pill-error"}.get(status, "pill-warn")
    icon = STATUS_ICON.get(status, "⚪")
    return f'<span class="status-pill {css_class}">{icon} {label}</span>'


def render_health_sidebar():
    health = readiness_check()
    st.markdown("#### System Status")
    for name, detail in health["details"].items():
        label = name.replace("_", " ").title()
        st.markdown(status_pill(detail["status"], f"{label}: {detail['status']}"), unsafe_allow_html=True)
        if detail.get("detail"):
            st.caption(detail["detail"])
    return health


def render_connection_form():
    st.title("🧠 Text to SQL")
    st.caption("Connect to a database to start chatting with your data.")

    with st.sidebar:
        render_health_sidebar()
        st.divider()
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
                st.error("Please fill in all required fields before connecting.")
                return

            try:
                with st.spinner("Connecting..."):
                    connector = get_connector(db_type)
                    connector.connect()
                    tables = connector.list_tables()

                    # Build a combined schema dict across all tables for the agent's planner/SQL prompts
                    schema = {"tables": {}}
                    for table in tables:
                        schema["tables"][table] = connector.get_schema(table)

                st.session_state.connector = connector
                st.session_state.connected = True
                st.session_state.tables = tables
                st.session_state.schema = schema
                st.session_state.messages = []
                st.session_state.lc_messages = []
                st.session_state.agent_graph = build_graph(connector)

                logger.info("Connected to %s DB with %d tables", db_type, len(tables))
                st.rerun()

            except AppError as e:
                logger.error("DB connection failed: %s", e.message)
                st.error(e.message)
            except Exception:
                logger.exception("Unexpected DB connection error")
                st.error("Could not connect to the database. Check your details and try again.")


def render_chat_interface():
    connector = st.session_state.connector

    with st.sidebar:
        health = render_health_sidebar()
        st.divider()
        st.markdown("#### Connection")
        st.markdown(status_pill("ok", f"{config.DB_TYPE.upper()} connected"), unsafe_allow_html=True)
        st.caption(f"📋 {len(st.session_state.tables)} tables available")
        with st.expander("View tables"):
            for t in st.session_state.tables:
                st.text(f"• {t}")
        st.divider()
        if st.button("🔌 Disconnect", use_container_width=True):
            connector.disconnect()
            config.clear()
            st.session_state.clear()
            st.rerun()

    st.title("💬 Chat with your database")

    if health["details"].get("database", {}).get("status") == "error":
        st.warning("⚠️ Database connection appears unstable. Some queries may fail.")

    if not st.session_state.messages:
        st.markdown("##### Try asking:")
        cols = st.columns(3)
        suggestions = ["Show me the first 10 rows", "What tables are available?", "Summarize this dataset"]
        for col, suggestion in zip(cols, suggestions):
            if col.button(suggestion, use_container_width=True):
                st.session_state.pending_prompt = suggestion
                st.rerun()

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if "data" in msg:
                st.dataframe(msg["data"], use_container_width=True)

    prompt = st.chat_input("Ask a question about your data...")
    if "pending_prompt" in st.session_state:
        prompt = st.session_state.pop("pending_prompt")

    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        st.session_state.pending_retry_prompt = prompt
        st.session_state.retry_count = 0

        def run_agent_turn(user_prompt: str):
            with st.chat_message("assistant"):
                try:
                    with st.spinner("Thinking..."):
                        result = st.session_state.agent_graph.invoke({
                            "user_query": user_prompt,
                            "messages": st.session_state.lc_messages,
                            "schema": st.session_state.schema,
                            "db_type": config.DB_TYPE,
                        })

                    response_text = result["final_response"]
                    st.markdown(response_text)

                    query_result = result.get("query_result")
                    if query_result:
                        st.dataframe(query_result, use_container_width=True)

                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": response_text,
                        **({"data": query_result} if query_result else {}),
                    })
                    st.session_state.lc_messages.append(HumanMessage(content=user_prompt))
                    st.session_state.lc_messages.append(AIMessage(content=response_text))
                    st.session_state.pop("pending_retry_prompt", None)
                except (LLMRateLimitError, LLMServiceUnavailableError, LLMTimeoutError) as e:
                    st.error(f"⚠️ {e.message}")
                    if st.button("🔄 Retry", key=f"retry_{len(st.session_state.messages)}"):
                        st.rerun()

                except AppError as e:
                    st.error(e.message)
                    st.session_state.pop("pending_retry_prompt", None)

                except Exception:
                    logger.exception("Agent execution failed")
                    st.error("Something went wrong processing that question.")
                    st.session_state.pop("pending_retry_prompt", None)


        if "pending_retry_prompt" in st.session_state:
            run_agent_turn(st.session_state.pending_retry_prompt)


def run():
    st.set_page_config(page_title="Text to SQL", page_icon="🧠", layout="wide")
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

    if "connected" not in st.session_state:
        st.session_state.connected = False

    if not st.session_state.connected:
        render_connection_form()
    else:
        render_chat_interface()


if __name__ == "__main__":
    run()