import os
import json
import uuid
import time
import gradio as gr
from dotenv import load_dotenv
from google import genai
from datetime import datetime

load_dotenv()

try:
    import spaces
    HAS_SPACES = True
except ImportError:
    HAS_SPACES = False

# ==========================================
# BACKEND LOGIC (AI & HISTORY)
# ==========================================

def get_client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set in the environment.")
    return genai.Client(api_key=api_key)

MODEL_ID = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

# In-memory history DB
history_db = []

DEFAULT_CASE = """The famous Aurora Diamond has vanished from its highly secure display case during a gala at the City Museum. 
The power went out for exactly 30 seconds at 9:00 PM. When the lights came back on, the glass was cut, and the diamond was gone.

Suspects:
1. Arthur Pendelton (Museum Director) - Has massive gambling debts. Had keys to the security override.
2. Beatrice Vance (Security Chief) - Seen near the breaker box right before the outage.
3. Julian Thorne (Billionaire Collector) - Openly offered to buy the diamond for double its value, was denied.
4. Elara Quinn (Expert Thief) - Released from prison recently; a glass cutter matching her signature style was found nearby.

Evidence:
- The security cameras were manually disabled 2 minutes before the outage.
- A glass cutter (Elara's style) found on the floor.
- Muddy footprints leading from the breaker box to a side exit.
- An anonymous tip claims the diamond is already out of the country."""

def investigate(case_text, evidence_removal):
    if evidence_removal:
        case_text += f"\n\nNOTE: The following evidence has been debunked and should be IGNORED: {evidence_removal}"

    try:
        client = get_client()
    except Exception as e:
        yield f"Error: {e}", "", "", "", "", "Failed to start investigation."
        return

    yield "Detective Agent is investigating...", "", "", "", "", "Investigation in progress..."
    
    detective_prompt = f"You are the Detective Agent.\nCase:\n{case_text}\n\nTask: Build timeline, identify confirmed facts, open questions. Plain text bullet points only."
    try:
        detective_response = client.models.generate_content(model=MODEL_ID, contents=detective_prompt).text
    except Exception as e:
        yield f"Error: {e}", "", "", "", "", "Failed at Detective Agent."
        return
        
    yield detective_response, "Evidence Agent is analyzing...", "", "", "", "Investigation in progress..."

    evidence_prompt = f"You are Evidence Agent.\nCase:\n{case_text}\nDetective:\n{detective_response}\n\nTask: Analyze clues, separate fact from inference, find contradictions. Plain text bullet points."
    try:
        evidence_response = client.models.generate_content(model=MODEL_ID, contents=evidence_prompt).text
    except Exception as e:
        yield detective_response, f"Error: {e}", "", "", "", "Failed at Evidence Agent."
        return

    yield detective_response, evidence_response, "Suspect Agent is evaluating...", "", "", "Investigation in progress..."

    suspect_prompt = f"You are Suspect Agent.\nCase:\n{case_text}\nDetective:\n{detective_response}\nEvidence:\n{evidence_response}\n\nTask: Compare suspects (motive, means, opportunity, alibi). Plain text bullet points."
    try:
        suspect_response = client.models.generate_content(model=MODEL_ID, contents=suspect_prompt).text
    except Exception as e:
        yield detective_response, evidence_response, f"Error: {e}", "", "", "Failed at Suspect Agent."
        return
        
    yield detective_response, evidence_response, suspect_response, "Skeptic Agent is challenging...", "", "Investigation in progress..."

    skeptic_prompt = f"You are Skeptic Agent.\nCase:\n{case_text}\nReports:\n{detective_response}\n{evidence_response}\n{suspect_response}\n\nTask: Challenge theory, identify assumptions, suggest alternatives. Plain text bullet points."
    try:
        skeptic_response = client.models.generate_content(model=MODEL_ID, contents=skeptic_prompt).text
    except Exception as e:
        yield detective_response, evidence_response, suspect_response, f"Error: {e}", "", "Failed at Skeptic Agent."
        return

    yield detective_response, evidence_response, suspect_response, skeptic_response, "Chief Agent is concluding...", "Investigation in progress..."

    chief_prompt = f"You are Chief Agent.\nCase:\n{case_text}\nReports:\n{detective_response}\n{evidence_response}\n{suspect_response}\n{skeptic_response}\n\nTask: Synthesize and give FINAL VERDICT. First line MUST be 'FINAL VERDICT: [Name] is the thief. Confidence: [Score]%'. Plain text bullet points."
    try:
        chief_response = client.models.generate_content(model=MODEL_ID, contents=chief_prompt).text
    except Exception as e:
        yield detective_response, evidence_response, suspect_response, skeptic_response, f"Error: {e}", "Failed at Chief Agent."
        return

    verdict_name = "Unknown"
    confidence = "N/A"
    try:
        first_line = chief_response.split('\n')[0]
        if "Confidence:" in first_line:
            verdict_name = first_line.split('FINAL VERDICT:')[1].split('is the')[0].strip()
            confidence = first_line.split('Confidence:')[1].strip()
    except:
        pass

    record_id = str(uuid.uuid4())[:8]
    history_db.append({
        "id": record_id,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "case_preview": case_text[:50] + "...",
        "verdict": verdict_name,
        "confidence": confidence,
        "report": chief_response
    })

    yield detective_response, evidence_response, suspect_response, skeptic_response, chief_response, "Investigation Complete. Report saved to History."

if HAS_SPACES:
    investigate = spaces.GPU(investigate)

# ==========================================
# HISTORY & AUTH HANDLERS
# ==========================================

def get_history_html(search_query=""):
    if not history_db:
        return "<div style='color: white; padding: 20px; text-align:center;'>No history found. Run an investigation first!</div>"
    html = "<div style='display:flex; flex-direction:column; gap:10px;'>"
    for item in reversed(history_db):
        if search_query.lower() in item['case_preview'].lower() or search_query.lower() in item['verdict'].lower():
            html += f"""
            <div class='glass-panel' style='display:flex; justify-content:space-between; align-items:center;'>
                <div>
                    <h4 style='margin:0; color:var(--primary);'>{item['date']} | ID: {item['id']}</h4>
                    <p style='margin:5px 0 0 0; font-size:0.9em;'><strong>Case:</strong> {item['case_preview']}</p>
                    <p style='margin:5px 0 0 0; font-size:0.9em;'><strong>Verdict:</strong> {item['verdict']} ({item['confidence']})</p>
                </div>
            </div>
            """
    html += "</div>"
    return html

def clear_all_history():
    global history_db
    history_db = []
    return get_history_html()

def delete_single_history(rec_id):
    global history_db
    history_db = [h for h in history_db if h['id'] != rec_id.strip()]
    return get_history_html()

def handle_search(query):
    return get_history_html(query)

def generate_pdf():
    time.sleep(1.5)
    return "✅ PDF Export Generated! (Mock download complete)"

# ==========================================
# CSS & HTML
# ==========================================

custom_css = """
:root {
    --primary: #4F46E5;
    --accent: #0ea5e9;
    --glass-bg: rgba(20, 20, 20, 0.7);
    --glass-border: rgba(255, 255, 255, 0.1);
    --body-bg: #050505;
    --body-text: white;
}

body.light, .light .gradio-container {
    --glass-bg: rgba(255, 255, 255, 0.8) !important;
    --glass-border: rgba(0, 0, 0, 0.1) !important;
    --body-bg: #f8fafc !important;
    --body-text: #0f172a !important;
}

body, .gradio-container { background: var(--body-bg) !important; color: var(--body-text) !important; font-family: 'Inter', sans-serif; transition: all 0.3s ease; }
footer { display: none !important; }

/* Dynamic text colors for light mode */
body.light h1, body.light h2, body.light h3, body.light h4, body.light p, body.light span, body.light div { color: var(--body-text) !important; }

/* Hide Gradio Tab Buttons (We use custom buttons for navigation) */
div[role="tablist"] { display: none !important; }

.glass-panel {
    background: var(--glass-bg) !important;
    backdrop-filter: blur(16px) !important;
    -webkit-backdrop-filter: blur(16px) !important;
    border: 1px solid var(--glass-border) !important;
    border-radius: 12px !important;
    padding: 20px;
    box-shadow: 0 4px 30px rgba(0,0,0,0.3) !important;
}

.custom-btn {
    background: linear-gradient(135deg, #4F46E5, #0ea5e9) !important;
    border: none !important;
    color: white !important;
    font-weight: bold !important;
    border-radius: 8px !important;
    transition: transform 0.2s !important;
}
.custom-btn:hover { transform: translateY(-2px) !important; box-shadow: 0 0 15px rgba(79, 70, 229, 0.5) !important; }

.danger-btn { background: #ef4444 !important; color: white !important; border: none !important; }

/* Custom Navbar (using Gradio Row) */
#custom-navbar {
    background: rgba(10,10,10,0.9);
    border-bottom: 1px solid var(--glass-border);
    padding: 10px 20px;
    position: sticky;
    top: 0;
    z-index: 1000;
    display: flex;
    align-items: center;
    justify-content: space-between;
}

#sidebar-col { border-right: 1px solid var(--glass-border); padding-right: 15px; }
.sidebar-btn { background: transparent !important; border: 1px solid transparent !important; color: white !important; text-align: left !important; justify-content: flex-start !important; padding-left: 15px !important; }
.sidebar-btn:hover { background: rgba(255,255,255,0.05) !important; border: 1px solid var(--glass-border) !important; }

.hero-title { font-size: 4.5rem; font-weight: 900; text-align: center; background: linear-gradient(135deg, #4F46E5, #0ea5e9); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 10px; line-height: 1.1;}
.hero-subtitle { text-align: center; color: #a0a0a0; font-size: 1.4rem; margin-bottom: 40px; }

.suspect-card { background: rgba(255,255,255,0.05); border: 1px solid var(--glass-border); padding: 15px; border-radius: 10px; margin-bottom: 10px; }
.suspect-card h4 { margin: 0 0 10px 0; color: var(--accent); }
"""

# ==========================================
# GRADIO APP BUILDER
# ==========================================

with gr.Blocks(theme=gr.themes.Monochrome(), css=custom_css, title="Aurora AI") as demo:
    
    # ---------------- NAVBAR ----------------
    with gr.Row(elem_id="custom-navbar"):
        nav_logo_btn = gr.Button("🔮 Aurora AI", min_width=150, elem_classes="custom-btn")
        
        # Wrapped in a Group so we can hide/show them based on Auth
        with gr.Row(visible=False) as nav_utilities:
            nav_search = gr.Textbox(placeholder="Search history...", show_label=False, container=False, min_width=300)
            nav_bell = gr.Button("🔔", min_width=50)
            nav_gear = gr.Button("⚙️", min_width=50)
            nav_user = gr.Button("👤", min_width=50)

    # Toast notifications for navbar icons
    def notify_bell():
        count = len(history_db)
        if count == 0:
            gr.Info("🔔 You have 0 saved investigations.")
        else:
            gr.Info(f"🔔 You have {count} investigations saved in your history!")
    
    def notify_gear():
        return gr.Tabs(selected="settings")
        
    def notify_user():
        gr.Info("👤 Logged out successfully.")
        # Hide the dashboard/settings, hide the navbar utilities, route to landing
        return gr.Tabs(selected="landing"), gr.update(visible=False), gr.update(visible=False), gr.update(visible=False)

    
    # We use tabs to switch between everything
    with gr.Tabs(elem_id="main-tabs") as main_tabs:
        
        # =========================================================
        # TAB 1: LANDING PAGE (HERO ONLY)
        # =========================================================
        with gr.TabItem("landing_page", id="landing"):
            gr.HTML("<div class='hero-title'>The Future of<br>Criminal Investigation</div>")
            gr.HTML("<div class='hero-subtitle'>Five specialized AI agents. One unified platform.</div>")
            
            with gr.Row():
                gr.HTML("<div style='flex:1'></div>") # Spacer
                go_login_btn = gr.Button("🔒 Login", elem_classes="custom-btn", size="lg")
                go_reg_btn = gr.Button("📝 Register", elem_classes="custom-btn", size="lg")
                gr.HTML("<div style='flex:1'></div>") # Spacer
            
            with gr.Accordion("📜 Privacy Policy & Terms of Service", open=False):
                gr.Markdown("""
                **Privacy Policy:** We collect standard usage data. Case data submitted to Aurora AI is processed securely. 
                **Terms of Service:** Aurora AI is an investigative tool. Final verdicts require human review. By using this platform, you agree to not misuse the AI agents.
                """)

        # =========================================================
        # TAB 2: LOGIN FORM
        # =========================================================
        with gr.TabItem("login_page", id="login"):
            with gr.Column(elem_classes="glass-panel"):
                gr.Markdown("### 🔒 Login")
                gr.Markdown("Welcome back. Please sign in to access the investigation dashboard.")
                log_email = gr.Textbox(label="Email")
                log_pwd = gr.Textbox(label="Password", type="password")
                log_btn = gr.Button("Login", elem_classes="custom-btn")
                log_res = gr.Textbox(label="Status", interactive=False)
                
                # Mock Login logic
                def do_login(email, pwd):
                    time.sleep(1)
                    if not email: 
                        return "⚠️ Please enter email", gr.Tabs(selected="login"), gr.update(), gr.update(), gr.update()
                    gr.Info(f"✅ Logged in as {email}")
                    # Unlocks Dashboard & Settings, Unlocks Navbar Utilities, routes to dashboard
                    return f"✅ Success", gr.Tabs(selected="dashboard"), gr.update(visible=True), gr.update(visible=True), gr.update(visible=True)
                
                # Binding moved to bottom

        # =========================================================
        # TAB 3: REGISTER FORM
        # =========================================================
        with gr.TabItem("register_page", id="register"):
            with gr.Column(elem_classes="glass-panel"):
                gr.Markdown("### 📝 Sign Up")
                gr.Markdown("Join the Aurora AI investigation team.")
                reg_name = gr.Textbox(label="Full Name")
                reg_email = gr.Textbox(label="Email")
                reg_pwd = gr.Textbox(label="Password", type="password")
                reg_btn = gr.Button("Create Account", elem_classes="custom-btn")
                reg_res = gr.Textbox(label="Status", interactive=False)
                
                def do_register(name, email, pwd):
                    time.sleep(1)
                    if not name: 
                        return "⚠️ Please enter name", gr.Tabs(selected="register")
                    gr.Info(f"✅ Account created for {name}. Please login.")
                    # Routes to login tab
                    return f"✅ Account created", gr.Tabs(selected="login")
                    
                # Binding moved to bottom

        # =========================================================
        # TAB 4: MAIN DASHBOARD (SIDE FEATURES) - HIDDEN BY DEFAULT
        # =========================================================
        with gr.TabItem("app_dashboard", id="dashboard", visible=False) as dash_tab:
            with gr.Row():
                # ---- SIDEBAR ----
                with gr.Column(scale=1, elem_id="sidebar-col"):
                    gr.Markdown("### 📑 Menu")
                    btn_dash = gr.Button("📊 Dashboard (Upload Case)", elem_classes="sidebar-btn")
                    btn_evid = gr.Button("🧪 Challenge Evidence", elem_classes="sidebar-btn")
                    btn_susp = gr.Button("🕵️ Suspect Cards", elem_classes="sidebar-btn")
                    btn_work = gr.Button("🤖 Agent Workflow", elem_classes="sidebar-btn")
                    btn_hist = gr.Button("📜 Investigation History", elem_classes="sidebar-btn")
                    btn_rept = gr.Button("📄 Report / Export", elem_classes="sidebar-btn")

                # ---- CONTENT AREA ----
                with gr.Column(scale=4):
                    with gr.Tabs(elem_id="content-tabs") as content_tabs:
                        
                        # Dashboard (Case Input)
                        with gr.TabItem("Dashboard", id="sub_dash"):
                            gr.Markdown("### 📝 Custom Case Input")
                            gr.Markdown("Write or paste the mystery/crime scene details below. The AI agents will investigate whatever you provide.")
                            case_input = gr.Textbox(lines=10, value=DEFAULT_CASE, label="Case Description", elem_classes="glass-panel")
                            start_inv_btn = gr.Button("🔍 START INVESTIGATION", elem_classes="custom-btn", size="lg")
                            inv_status = gr.Textbox(label="System Status")
                        
                        # Challenge Mode
                        with gr.TabItem("Challenge Mode", id="sub_evid"):
                            gr.Markdown("### 🧪 Challenge Mode / Remove Evidence")
                            gr.Markdown("Type the evidence you want the agents to IGNORE (e.g. 'Security cameras' or 'Muddy footprints').")
                            evidence_remove = gr.Textbox(label="Evidence to Debunk", elem_classes="glass-panel")
                            gr.Markdown("*Note: Set this before clicking Start Investigation in the Dashboard.*")
                        
                        # Suspect Cards
                        with gr.TabItem("Suspect Cards", id="sub_susp"):
                            gr.Markdown("### 🕵️ Known Suspects Visualization")
                            gr.HTML("""
                            <div class='suspect-card'><h4>Arthur Pendelton</h4><p>Museum Director. Massive gambling debts. Keys to security.</p></div>
                            <div class='suspect-card'><h4>Beatrice Vance</h4><p>Security Chief. Seen near breaker box.</p></div>
                            <div class='suspect-card'><h4>Julian Thorne</h4><p>Billionaire. Obsessed with diamond.</p></div>
                            <div class='suspect-card'><h4>Elara Quinn</h4><p>Expert Thief. Signature tool found.</p></div>
                            """)
                            gr.Markdown("*If using a custom case, suspects will be derived dynamically by the AI.*")
                        
                        # Agent Workflow Visualization
                        with gr.TabItem("Agent Workflow", id="sub_work"):
                            gr.Markdown("### 🤖 Agent Workflow Visualization")
                            with gr.Row():
                                out_det = gr.Textbox(label="1. Detective", lines=8, interactive=False, elem_classes="glass-panel")
                                out_evi = gr.Textbox(label="2. Evidence", lines=8, interactive=False, elem_classes="glass-panel")
                            with gr.Row():
                                out_sus = gr.Textbox(label="3. Suspect", lines=8, interactive=False, elem_classes="glass-panel")
                                out_ske = gr.Textbox(label="4. Skeptic", lines=8, interactive=False, elem_classes="glass-panel")
                        
                        # Investigation Report
                        with gr.TabItem("Investigation Report", id="sub_rept"):
                            gr.Markdown("### ⚖️ Final Chief Verdict")
                            out_chi = gr.Textbox(label="5. Chief Agent (Final Verdict)", lines=12, interactive=False, elem_classes="glass-panel")
                            pdf_btn = gr.Button("📄 Export PDF", elem_classes="custom-btn")
                            pdf_status = gr.Textbox(show_label=False)
                            pdf_btn.click(generate_pdf, outputs=pdf_status)
                        
                        # History
                        with gr.TabItem("Investigation History", id="sub_hist"):
                            gr.Markdown("### 📜 Investigation History")
                            with gr.Row():
                                refresh_hist_btn = gr.Button("🔄 Refresh History", elem_classes="custom-btn")
                                clear_all_btn = gr.Button("🗑️ Clear All History", elem_classes="danger-btn")
                            
                            hist_html = gr.HTML(get_history_html())
                            
                            gr.Markdown("#### Delete Specific Record")
                            with gr.Row():
                                del_id_input = gr.Textbox(placeholder="Enter ID to delete...", show_label=False)
                                del_btn = gr.Button("Delete Record", elem_classes="danger-btn")
                            
                            refresh_hist_btn.click(lambda: get_history_html(), outputs=hist_html)
                            clear_all_btn.click(clear_all_history, outputs=hist_html)
                            del_btn.click(delete_single_history, inputs=[del_id_input], outputs=hist_html)
                            
                            # Wire Navbar Search to History
                            nav_search.submit(handle_search, inputs=[nav_search], outputs=[hist_html]).then(
                                lambda: (gr.Tabs(selected="dashboard"), gr.Tabs(selected="sub_hist")), outputs=[main_tabs, content_tabs]
                            )

        # =========================================================
        # TAB 5: SETTINGS - HIDDEN BY DEFAULT
        # =========================================================
        with gr.TabItem("settings_page", id="settings", visible=False) as set_tab:
            with gr.Column(elem_classes="glass-panel", scale=1):
                gr.Markdown("## ⚙️ Platform Settings")
                theme_radio = gr.Radio(["Dark Mode", "Light Mode", "System Default"], label="Theme", value="Dark Mode")
                model_drop = gr.Dropdown(["gemini-3.5-flash-lite", "gemini-pro"], label="AI Model", value="gemini-3.5-flash-lite")
                save_btn = gr.Button("Save Settings", elem_classes="custom-btn")
                
                def save_mock(theme, model):
                    gr.Info(f"✅ Settings saved! (Theme: {theme}, Model: {model})")
                
                theme_js = """
                (theme, model) => {
                    if (theme === 'Light Mode') {
                        document.body.classList.remove('dark');
                        document.body.classList.add('light');
                    } else {
                        document.body.classList.add('dark');
                        document.body.classList.remove('light');
                    }
                    return [theme, model];
                }
                """
                save_btn.click(save_mock, inputs=[theme_radio, model_drop], outputs=[], js=theme_js)
            
            back_btn = gr.Button("⬅️ Back to Dashboard", elem_classes="custom-btn")
            back_btn.click(lambda: gr.Tabs(selected="dashboard"), outputs=main_tabs)

    # ---------------- FOOTER ----------------
    gr.HTML("""
    <div style='text-align:center; padding: 20px; color:#666; margin-top:40px; border-top:1px solid rgba(255,255,255,0.1);'>
        Aurora AI Investigative Platform &copy; 2026. <a style='color:#888' href='#'>Privacy Policy</a> | <a style='color:#888' href='#'>Terms of Service</a>
    </div>
    """)

    # ---------------- BINDINGS ----------------
    
    # Navbar Icon bindings
    nav_bell.click(notify_bell, outputs=[])
    nav_gear.click(notify_gear, outputs=main_tabs)
    nav_user.click(notify_user, outputs=[main_tabs, dash_tab, set_tab, nav_utilities])

    # Landing page routing
    nav_logo_btn.click(lambda: gr.Tabs(selected="landing"), outputs=main_tabs)
    go_login_btn.click(lambda: gr.Tabs(selected="login"), outputs=main_tabs)
    go_reg_btn.click(lambda: gr.Tabs(selected="register"), outputs=main_tabs)
    
    # Auth logic bindings
    log_btn.click(do_login, inputs=[log_email, log_pwd], outputs=[log_res, main_tabs, dash_tab, set_tab, nav_utilities])
    reg_btn.click(do_register, inputs=[reg_name, reg_email, reg_pwd], outputs=[reg_res, main_tabs])
    
    # Sidebar routing
    btn_dash.click(lambda: gr.Tabs(selected="sub_dash"), outputs=content_tabs)
    btn_evid.click(lambda: gr.Tabs(selected="sub_evid"), outputs=content_tabs)
    btn_susp.click(lambda: gr.Tabs(selected="sub_susp"), outputs=content_tabs)
    btn_work.click(lambda: gr.Tabs(selected="sub_work"), outputs=content_tabs)
    btn_rept.click(lambda: gr.Tabs(selected="sub_rept"), outputs=content_tabs)
    btn_hist.click(lambda: get_history_html(), outputs=hist_html).then(
        lambda: gr.Tabs(selected="sub_hist"), outputs=content_tabs
    )

    # Starts investigation
    start_inv_btn.click(
        lambda: gr.Tabs(selected="sub_work"), outputs=content_tabs
    ).then(
        investigate,
        inputs=[case_input, evidence_remove],
        outputs=[out_det, out_evi, out_sus, out_ske, out_chi, inv_status]
    ).then(
        lambda: gr.Tabs(selected="sub_rept"), outputs=content_tabs
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    demo.launch(server_name="0.0.0.0", server_port=port)
