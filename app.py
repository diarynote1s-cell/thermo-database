import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import json

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Material Specific Heat Database",
    layout="wide"
)

# --- DATA LOADING ---
@st.cache_data
def load_data():
    # CSV file must be in the same folder as app.py
    df = pd.read_csv("materials_seed_dataset (1).csv")
    return df

df = load_data()

# --- HELPER FUNCTIONS FOR THERMODYNAMICS ---
def calculate_cp(T, eq_type, coeffs_str):
    """Calculate Cp based on the equation type and coefficients."""
    try:
        coeffs = json.loads(coeffs_str.replace('""', '"'))

        if eq_type == "shomate":
            t = T / 1000.0
            A, B, C, D, E = coeffs['A'], coeffs['B'], coeffs['C'], coeffs['D'], coeffs['E']
            return (A + B * t + C * (t ** 2) + D * (t ** 3) + E / (t ** 2))

        elif eq_type == "kelley":
            a, b, c = coeffs['a'], coeffs['b'], coeffs['c']
            return a + b * T + c / (T ** 2)

        elif eq_type == "linear":
            c0, c1 = coeffs['c0'], coeffs['c1']
            return c0 + c1 * T

        elif eq_type == "const":
            c0 = coeffs['c0']
            return np.full_like(T, c0, dtype=float)

        else:
            return np.full_like(T, np.nan, dtype=float)

    except Exception:
        return np.full_like(T, np.nan, dtype=float)

def get_brief_equation(eq_type, coeffs_str):
    """Create a single-line equation string for the summary table."""
    try:
        coeffs = json.loads(coeffs_str.replace('""', '"'))
        if eq_type == "shomate":
            return f"Cp = {coeffs['A']} + {coeffs['B']}·t + {coeffs['C']}·t² + {coeffs['D']}·t³ + {coeffs['E']}/t² (Shomate)"
        elif eq_type == "kelley":
            return f"Cp = {coeffs['a']} + {coeffs['b']}·T + {coeffs['c']}/T² (Kelley)"
        elif eq_type == "linear":
            return f"Cp = {coeffs['c0']} + {coeffs['c1']}·T (Linear)"
        elif eq_type == "const":
            return f"Cp = {coeffs['c0']} (Constant)"
        return "Unknown"
    except:
        return "N/A"

# ============================================================
# SIDEBAR INTERFACE
# ============================================================
st.sidebar.title("Configuration Panel")
st.sidebar.write("Select parameters to plot the specific heat capacity vs. temperature.")

categories = ["All"] + list(df['category'].dropna().unique())
selected_category = st.sidebar.selectbox("Select Material Category", categories)

if selected_category == "All":
    filtered_df = df
else:
    filtered_df = df[df['category'] == selected_category]

material_list = filtered_df['name'].tolist()
selected_materials = st.sidebar.multiselect(
    "Select Materials to Plot",
    options=material_list,
    default=(material_list[:2] if len(material_list) >= 2 else material_list)
)

st.sidebar.markdown("---")

t_min_slider, t_max_slider = st.sidebar.slider(
    "Select Temperature Range (K)",
    min_value=100, max_value=1500, 
    value=(298, 1500), step=10
)

# ============================================================
# MAIN DASHBOARD
# ============================================================
st.title("Cp-T Materials Explorer")
st.markdown("Interactive specific heat capacity database.")

if not selected_materials:
    st.info("Please select at least one material from the sidebar to generate the plot.")
else:
    fig = go.Figure()
    
    # Data containers
    summary_table_data = []
    export_data = []
    
    # Generate 100 temperature points across the selected slider range for the CSV export
    T_export_array = np.linspace(t_min_slider, t_max_slider, 100)
    
    colors = ["#3B82F6", "#F59E0B", "#10B981", "#EF4444", "#8B5CF6", "#06B6D4", "#EC4899", "#F97316", "#84CC16", "#14B8A6"]
    selected_units = set()

    # Pre-fetch cursor temperature for the summary table
    st.markdown("---")
    col1, col2 = st.columns([1, 3])
    with col1:
        cursor_t = st.number_input("Set Evaluation Temperature (K)", min_value=1.0, value=298.15, step=10.0, help="Acts as the 'Cursor T' for the table below.")

    for idx, mat_name in enumerate(selected_materials):
        mat_data = df[df['name'] == mat_name].iloc[0]
        
        formula = mat_data['formula']
        eq_type = mat_data['equation_type']
        coeffs_str = mat_data['coeffs']
        valid_tmin = float(mat_data['Tmin_K'])
        valid_tmax = float(mat_data['Tmax_K'])
        unit = mat_data['unit']
        category = mat_data['category']
        source = mat_data['source']
        
        mat_color = colors[idx % len(colors)]
        y_label = "Cp (J/mol·K)" if unit == "molar" else "Cp (J/g·K)"
        selected_units.add(y_label)

        # --- GRAPH PLOTTING ---
        # 1. Lower Extrapolation
        if t_min_slider < valid_tmin:
            ex_min, ex_max = t_min_slider, min(t_max_slider, valid_tmin)
            if ex_min < ex_max:
                T_ex = np.linspace(ex_min, ex_max, 50)
                Cp_ex = calculate_cp(T_ex, eq_type, coeffs_str)
                fig.add_trace(go.Scatter(x=T_ex, y=Cp_ex, mode="lines", name=f"{mat_name} (Extrapolated)", legendgroup=mat_name, showlegend=False, line=dict(color=mat_color, dash="dash"), hovertemplate=(f"<b>{mat_name}</b> (Extrap)<br>T: %{{x:.1f}} K<br>Cp: %{{y:.2f}}<extra></extra>")))

        # 2. Valid Range
        p_min, p_max = max(t_min_slider, valid_tmin), min(t_max_slider, valid_tmax)
        if p_min <= p_max:
            T_val = np.linspace(p_min, p_max, 200)
            Cp_val = calculate_cp(T_val, eq_type, coeffs_str)
            fig.add_trace(go.Scatter(x=T_val, y=Cp_val, mode="lines", name=f"{mat_name} ({formula})", legendgroup=mat_name, line=dict(color=mat_color), hovertemplate=(f"<b>{mat_name}</b><br>T: %{{x:.1f}} K<br>Cp: %{{y:.2f}}<extra></extra>")))

        # 3. Upper Extrapolation
        if t_max_slider > valid_tmax:
            ex_min, ex_max = max(t_min_slider, valid_tmax), t_max_slider
            if ex_min < ex_max:
                T_ex = np.linspace(ex_min, ex_max, 50)
                Cp_ex = calculate_cp(T_ex, eq_type, coeffs_str)
                fig.add_trace(go.Scatter(x=T_ex, y=Cp_ex, mode="lines", name=f"{mat_name} (Extrapolated)", legendgroup=mat_name, showlegend=False, line=dict(color=mat_color, dash="dash"), hovertemplate=(f"<b>{mat_name}</b> (Extrap)<br>T: %{{x:.1f}} K<br>Cp: %{{y:.2f}}<extra></extra>")))

        # --- EXPORT DATA (Full Temperature Sweep) ---
        Cp_export_vals = calculate_cp(T_export_array, eq_type, coeffs_str)
        for t_val, cp_val in zip(T_export_array, Cp_export_vals):
            in_range = "yes" if valid_tmin <= t_val <= valid_tmax else "no"
            export_data.append({
                "Material": mat_name,
                "Formula": formula,
                "Category": category,
                "T (K)": round(t_val, 1),
                f"Cp ({y_label.split(' ')[1]})": round(cp_val, 4),
                "In valid range?": in_range
            })

        # --- UI SUMMARY TABLE DATA (Single Cursor T) ---
        cp_at_cursor = calculate_cp(np.array([cursor_t]), eq_type, coeffs_str)[0]
        is_extrapolated = cursor_t < valid_tmin or cursor_t > valid_tmax
        cp_display = f"{cp_at_cursor:.3f}*" if is_extrapolated else f"{cp_at_cursor:.3f}"

        summary_table_data.append({
            "MATERIAL": mat_name,
            "FORMULA": formula,
            "CATEGORY": category,
            f"CP @ CURSOR T": cp_display,
            "VALID RANGE (K)": f"{valid_tmin} - {valid_tmax}",
            "EQUATION & COEFFICIENTS": get_brief_equation(eq_type, coeffs_str),
            "SOURCE": source
        })

    # Render Graph
    y_axis_title = " or ".join(sorted(list(selected_units)))
    fig.update_layout(
        xaxis_title="Temperature, T (K)",
        yaxis_title=f"Heat capacity, Cp ({y_axis_title})",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode="x unified",
        template="plotly_white",
        margin=dict(l=40, r=40, t=40, b=40)
    )
    st.plotly_chart(fig, use_container_width=True)

    # Render Summary Table
    st.dataframe(pd.DataFrame(summary_table_data), hide_index=True, use_container_width=True)
    st.caption("* Indicates the evaluation temperature falls outside the literature-verified valid range (extrapolated).")

    # Render Export Button
    export_df = pd.DataFrame(export_data)
    csv = export_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Export selected curves (CSV)",
        data=csv,
        file_name='cp_t_selected_materials.csv',
        mime='text/csv',
    )
