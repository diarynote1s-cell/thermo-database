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
        # Parse JSON coefficients
        coeffs = json.loads(coeffs_str.replace('""', '"'))

        # Shomate equation
        if eq_type == "shomate":
            t = T / 1000.0
            A, B, C, D, E = coeffs['A'], coeffs['B'], coeffs['C'], coeffs['D'], coeffs['E']
            return (A + B * t + C * (t ** 2) + D * (t ** 3) + E / (t ** 2))

        # Kelley equation
        elif eq_type == "kelley":
            a, b, c = coeffs['a'], coeffs['b'], coeffs['c']
            return a + b * T + c / (T ** 2)

        # Linear equation
        elif eq_type == "linear":
            c0, c1 = coeffs['c0'], coeffs['c1']
            return c0 + c1 * T

        # Constant Cp
        elif eq_type == "const":
            c0 = coeffs['c0']
            return np.full_like(T, c0, dtype=float)

        # Unknown equation
        else:
            return np.full_like(T, np.nan, dtype=float)

    except Exception:
        return np.full_like(T, np.nan, dtype=float)


def get_equation_text(eq_type, coeffs_str):
    """Create a readable equation from stored coefficients."""
    try:
        coeffs = json.loads(coeffs_str.replace('""', '"'))

        if eq_type == "shomate":
            return (
                "Cp = A + B·t + C·t² + D·t³ + E/t²\n"
                "where t = T/1000\n\n"
                f"A = {coeffs['A']}\n"
                f"B = {coeffs['B']}\n"
                f"C = {coeffs['C']}\n"
                f"D = {coeffs['D']}\n"
                f"E = {coeffs['E']}\n\n"
                "(Shomate Equation)"
            )
        elif eq_type == "kelley":
            return (
                "Cp = a + b·T + c/T²\n\n"
                f"a = {coeffs['a']}\n"
                f"b = {coeffs['b']}\n"
                f"c = {coeffs['c']}\n\n"
                "(Kelley Equation)"
            )
        elif eq_type == "linear":
            return (
                "Cp = c₀ + c₁·T\n\n"
                f"c₀ = {coeffs['c0']}\n"
                f"c₁ = {coeffs['c1']}\n\n"
                "(Linear Equation)"
            )
        elif eq_type == "const":
            return (
                "Cp = c₀\n\n"
                f"c₀ = {coeffs['c0']}\n\n"
                "(Constant Equation)"
            )

        return "Equation information unavailable."
    except Exception:
        return "Unable to display equation."

# ============================================================
# SIDEBAR INTERFACE
# ============================================================
st.sidebar.title("Configuration Panel")
st.sidebar.write("Select parameters to plot the specific heat capacity vs. temperature.")

# --- CATEGORY SELECTION ---
categories = ["All"] + list(df['category'].dropna().unique())
selected_category = st.sidebar.selectbox("Select Material Category", categories)

# --- FILTER MATERIALS BY CATEGORY ---
if selected_category == "All":
    filtered_df = df
else:
    filtered_df = df[df['category'] == selected_category]

# --- MATERIAL SELECTION ---
material_list = filtered_df['name'].tolist()
selected_materials = st.sidebar.multiselect(
    "Select Materials to Plot",
    options=material_list,
    default=(material_list[:2] if len(material_list) >= 2 else material_list)
)

# --- TEMPERATURE RANGE ---
st.sidebar.markdown("---")

t_min_slider, t_max_slider = st.sidebar.slider(
    "Select Temperature Range (K)",
    min_value=100,
    max_value=1500, 
    value=(298, 1500),
    step=10
)

# ============================================================
# MAIN DASHBOARD
# ============================================================
st.title("Interactive Thermodynamic Database")
st.markdown("Analyze the variation of specific heat capacity ($C_p$) with temperature ($T$) across various engineering materials.")

if not selected_materials:
    st.info("Please select at least one material from the sidebar to generate the plot.")
else:
    fig = go.Figure()
    export_data = []
    
    # Generate 100 temperature points across the selected slider range for the export table
    T_export_array = np.linspace(t_min_slider, t_max_slider, 100)
    
    colors = [
        "#3B82F6", "#F59E0B", "#10B981", "#EF4444", "#8B5CF6", 
        "#06B6D4", "#EC4899", "#F97316", "#84CC16", "#14B8A6"
    ]
    
    selected_units = set()

    for idx, mat_name in enumerate(selected_materials):
        mat_data = df[df['name'] == mat_name].iloc[0]
        
        formula = mat_data['formula']
        eq_type = mat_data['equation_type']
        coeffs_str = mat_data['coeffs']
        valid_tmin = float(mat_data['Tmin_K'])
        valid_tmax = float(mat_data['Tmax_K'])
        unit = mat_data['unit']
        category = mat_data['category']
        source = mat_data['source'] # Extracting source for the export table
        
        mat_color = colors[idx % len(colors)]
        unit_str = "J/mol·K" if unit == "molar" else "J/g·K"
        selected_units.add(unit_str)

        # --- 1. LOWER EXTRAPOLATION (Dashed) ---
        if t_min_slider < valid_tmin:
            extrap_min = t_min_slider
            extrap_max = min(t_max_slider, valid_tmin)
            
            if extrap_min < extrap_max:
                T_extrap = np.linspace(extrap_min, extrap_max, 100)
                Cp_extrap = calculate_cp(T_extrap, eq_type, coeffs_str)
                
                fig.add_trace(go.Scatter(
                    x=T_extrap, y=Cp_extrap, mode="lines",
                    name=f"{mat_name} (Extrapolated)", legendgroup=mat_name,
                    showlegend=False, line=dict(color=mat_color, dash="dash"),
                    hovertemplate=(f"<b>{mat_name}</b> (Extrapolated)<br>Temp: %{{x:.1f}} K<br>Cp: %{{y:.2f}} {unit_str}<br>Category: {category}<extra></extra>")
                ))

        # --- 2. VALID RANGE (Solid) ---
        plot_t_min = max(t_min_slider, valid_tmin)
        plot_t_max = min(t_max_slider, valid_tmax)

        if plot_t_min <= plot_t_max:
            T_array = np.linspace(plot_t_min, plot_t_max, 500)
            Cp_array = calculate_cp(T_array, eq_type, coeffs_str)
            
            fig.add_trace(go.Scatter(
                x=T_array, y=Cp_array, mode="lines",
                name=f"{mat_name} ({formula})", legendgroup=mat_name, line=dict(color=mat_color),
                hovertemplate=(f"<b>{mat_name}</b><br>Temp: %{{x:.1f}} K<br>Cp: %{{y:.2f}} {unit_str}<br>Category: {category}<extra></extra>")
            ))

        # --- 3. UPPER EXTRAPOLATION (Dashed) ---
        if t_max_slider > valid_tmax:
            extrap_min = max(t_min_slider, valid_tmax)
            extrap_max = t_max_slider
            
            if extrap_min < extrap_max:
                T_extrap = np.linspace(extrap_min, extrap_max, 100)
                Cp_extrap = calculate_cp(T_extrap, eq_type, coeffs_str)
                
                fig.add_trace(go.Scatter(
                    x=T_extrap, y=Cp_extrap, mode="lines",
                    name=f"{mat_name} (Extrapolated)", legendgroup=mat_name,
                    showlegend=False, line=dict(color=mat_color, dash="dash"),
                    hovertemplate=(f"<b>{mat_name}</b> (Extrapolated)<br>Temp: %{{x:.1f}} K<br>Cp: %{{y:.2f}} {unit_str}<br>Category: {category}<extra></extra>")
                ))

        # --- Export Data Compilation (Hidden from UI, pushed to CSV) ---
        Cp_export_vals = calculate_cp(T_export_array, eq_type, coeffs_str)
        for t_val, cp_val in zip(T_export_array, Cp_export_vals):
            in_valid_range = "yes" if valid_tmin <= t_val <= valid_tmax else "no"
            export_data.append({
                "Material": mat_name,
                "Formula": formula,
                "Category": category,
                "T (K)": round(t_val, 1),
                f"Cp ({unit_str})": round(cp_val, 4),
                "In valid range?": in_valid_range,
                "References": source # Added References column here
            })

    # Dynamically build the Y-axis label
    y_axis_unit_str = " or ".join(sorted(list(selected_units)))
    
    fig.update_layout(
        title="Specific Heat Capacity (Cp) vs Temperature (T)",
        xaxis_title="Temperature (K)",
        yaxis_title=f"Specific Heat Capacity ({y_axis_unit_str})",
        legend_title="Selected Materials",
        hovermode="x unified",
        template="plotly_dark"
    )

    st.plotly_chart(fig, use_container_width=True)

    # ============================================================
    # QUICK CP CALCULATOR
    # ============================================================
    st.markdown("---")
    st.markdown("### Quick Cp Calculator & Table Evaluation Temperature")
    st.write("Set a temperature below to calculate the exact $C_p$ value and dynamically update the summary table.")
    
    calc_col1, calc_col2, calc_col3 = st.columns(3)
    
    with calc_col1:
        calc_mat = st.selectbox("Search Material", options=df['name'].unique())
        
    with calc_col2:
        calc_temp = st.number_input("Temperature (K)", min_value=1.0, value=298.15, step=10.0)
        
    with calc_col3:
        if calc_mat:
            mat_row = df[df['name'] == calc_mat].iloc[0]
            unit_str = "J/mol·K" if mat_row['unit'] == "molar" else "J/g·K"
            temp_array = np.array([calc_temp])
            cp_val = calculate_cp(temp_array, mat_row['equation_type'], mat_row['coeffs'])[0]
            
            valid_tmin = float(mat_row['Tmin_K'])
            valid_tmax = float(mat_row['Tmax_K'])
            
            is_extrapolated = calc_temp < valid_tmin or calc_temp > valid_tmax
            display_val = f"{cp_val:.3f} (Extrapolated)" if is_extrapolated else f"{cp_val:.3f}"
            
            st.text_input(f"Cp ({unit_str})", value=display_val, disabled=True)

    st.markdown("---")
    
    # ============================================================
    # EQUATIONS USED
    # ============================================================
    st.markdown("### Equations Used")
    for mat_name in selected_materials:
        mat_data = df[df['name'] == mat_name].iloc[0]
        equation = get_equation_text(mat_data['equation_type'], mat_data['coeffs'])
        st.markdown(f"**{mat_name} ({mat_data['formula']})**")
        st.code(equation)

    # ============================================================
    # SELECTED MATERIAL DETAILS (CLEAN WEBPAGE TABLE)
    # ============================================================
    st.markdown("### Selected Material Details")
    summary_data = []
    
    for mat_name in selected_materials:
        mat_data = df[df['name'] == mat_name].iloc[0]
        unit = mat_data['unit']
        unit_str = "J/mol·K" if unit == "molar" else "J/g·K"
        valid_tmin = float(mat_data['Tmin_K'])
        valid_tmax = float(mat_data['Tmax_K'])
        
        # Calculate Cp at the user-defined calc_temp
        cp_val = calculate_cp(np.array([calc_temp]), mat_data['equation_type'], mat_data['coeffs'])[0]
        is_extrap = calc_temp < valid_tmin or calc_temp > valid_tmax
        cp_display = f"{cp_val:.3f}*" if is_extrap else f"{cp_val:.3f}"
        
        summary_data.append({
            "Material": mat_name,
            "Formula": mat_data['formula'],
            "Category": mat_data['category'],
            f"Cp @ {calc_temp} K ({unit_str})": cp_display,
            "Valid T Range (K)": f"{valid_tmin} - {valid_tmax}",
            "References": mat_data['source']
        })
        
    summary_df = pd.DataFrame(summary_data)
    st.dataframe(summary_df, use_container_width=True)
    st.caption(f"* Indicates the evaluation temperature ({calc_temp} K) falls outside the valid range (extrapolated).")
    
    # ============================================================
    # EXPORT TEMPERATURE SWEEP (CSV ONLY)
    # ============================================================
    # Generates the robust sweep data natively without cluttering the UI
    export_df = pd.DataFrame(export_data)
    csv = export_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="Export Full Temperature Sweep (CSV)",
        data=csv,
        file_name='cp_t_selected_materials.csv',
        mime='text/csv',
    )
