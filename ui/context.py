"""Shared runtime context for the Streamlit UI modules.

Streamlit runs the script top-to-bottom in a single thread per session, so a
mutable module-level context is safe. streamlit_app.py fills this in after
loading the authenticated user's settings and building the NVIDIA client;
ui/ modules read from it while rendering.
"""

import streamlit as st


class AppContext:
    def __init__(self):
        # NVIDIA client + model settings (populated by the orchestrator).
        self.client = None
        self.model = None
        self.system_prompt = None
        self.temperature = 1.0
        self.max_tokens = 2048
        self.thinking = True
        self.show_reasoning = False
        self.verify_answers = False

        # Persisted UI preferences (defaults before the settings popover runs).
        self.notes_width = 38
        self.notes_visible = True
        self.panel_h = 620

        # File system locations.
        self.upload_dir = None

        # UI constants.
        self.subjects = [
            "-",
            "Deep Learning",
            "Machine Learning",
            "DBMS",
            "Computer Networks",
            "Operating Systems",
            "Data Structures",
            "Mathematics",
            "Python",
            "Web Development",
            "Other",
        ]
        self.suggestions = {
            ":blue[:material/science:] Explain supervised learning": (
                "Define supervised learning, explain its working with an example, "
                "its advantages, limitations and applications."
            ),
            ":green[:material/functions:] Bayes theorem basics": (
                "Explain Bayes' theorem with its formula, an example, and key "
                "applications in machine learning."
            ),
            ":purple[:material/network_intake:] OSI model layers": (
                "Explain the seven layers of the OSI model with the function and "
                "example protocol of each layer."
            ),
        }


ctx = AppContext()


def mark_active(node_id):
    """Flag a note section as the active one (drives the rail highlight)."""
    st.session_state["notes_active"] = node_id