import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.colors as pc
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
            A = coeffs['A']
            B = coeffs['B']
            C = coeffs['C']
            D = coeffs['D']
            E = coeffs['E']
            return (A + B * t + C * (t ** 2) + D * (t ** 3) + E / (t ** 2))

        # Kelley equation
        elif eq_type == "kelley":
            a = coeffs['a']
            b = coeffs['b']
            c = coeffs['c']
            return a + b * T + c / (T ** 2)

        # Linear equation
        elif eq_type == "linear":
            c0 = coeffs['c0']
            c1 = coeffs['c1']
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


def get_equation_markdown(eq_type, coeffs_str):
    """Create a LaTeX-rendered equation from stored coefficients."""
    try:
        coeffs = json.loads(coeffs_str.replace('""', '"'))

        if eq_type == "shomate":
            return (
                "$$C_p = A + B t + C t^2 + D t^3 + \\frac{E}{t^2}$$\n"
                "*(where $t = T/1000$)*\n\n"
                f"* **A** = {coeffs['A']}\n"
                f"* **B** = {coeffs['B']}\n"
                f"* **C** = {coeffs['C']}\n"
                f"* **D** = {coeffs['D']}\n"
                f"* **E** = {coeffs['E']}"
            )
        elif eq_type == "kelley":
            return (
                "$$C_p = a + b T + \\frac{c}{T^2}$$\n\n"
                f"* **a** = {coeffs['a']}\n"
                f"* **b** = {coeffs['b']}\n"
                f"* **c** = {coeffs['c']}"
            )
        elif eq_type == "linear":
            return (
                "$$C_p = c_0 + c_1 T$$\n\n"
                f"* **c₀** = {coeffs['c0']}\n"
                f"* **c₁** = {coeffs['c1']}"
            )
        elif eq_type == "const":
            return (
                "$$C_p = c_0$$\n\n"
                f"* **c₀** = {coeffs['c0']}"
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
    summary_data = []
    
    # Vibrant, eye-catching colors inspired by the reference image
    colors = [
        "#3B82F6",  # Vibrant Blue
        "#F59E0B",  # Vibrant Amber/Gold
        "#10B981",  # Vibrant Mint Green
        "#EF4444",  # Vibrant Red
        "#8B5CF6",  # Vibrant Purple
        "#06B6D4",  # Vibrant Cyan
        "#EC4899",  # Vibrant Pink
        "#F97316",  # Vibrant Orange
        "#84CC16",  # Vibrant Lime
        "#14B8A6"   # Vibrant Teal
    ]
    
    # Keep track of units to dynamically set the y-axis label
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
        source = mat_data['source']
        
        # Assign a specific color to this material
        mat_color = colors[idx % len(colors)]

        y_label = "Cp (J/mol·K)" if unit == "molar" else "Cp (J/g·K)"
        selected_units.add("J/mol·K" if unit == "molar" else "J/g·K")

        # --- 1. LOWER EXTRAPOLATION (Dashed) ---
        if t_min_slider < valid_tmin:
            extrap_min = t_min_slider
            extrap_max = min(t_max_slider, valid_tmin)
            
            if extrap_min < extrap_max:
                T_extrap = np.linspace(extrap_min, extrap_max, 100)
                Cp_extrap = calculate_cp(T_extrap, eq_type, coeffs_str)
                
                fig.add_trace(
                    go.Scatter(
                        x=T_extrap,
                        y=Cp_extrap,
                        mode="lines",
                        name=f"{mat_name} (Extrapolated)",
                        legendgroup=mat_name,
                        showlegend=False, # Hide from legend to avoid duplicates
                        line=dict(color=mat_color, dash="dash"),
                        hovertemplate=(
                            f"<b>{mat_name}</b> (Extrapolated)<br>"
                            "Temp: %{x:.1f} K<br>"
                            f"Cp: %{{y:.2f}} {y_label}<br>"
                            f"Category: {category}"
                            "<extra></extra>"
                        )
                    )
                )

        # --- 2. VALID RANGE (Solid) ---
        plot_t_min = max(t_min_slider, valid_tmin)
        plot_t_max = min(t_max_slider, valid_tmax)

        if plot_t_min <= plot_t_max:
            T_array = np.linspace(plot_t_min, plot_t_max, 500)
            Cp_array = calculate_cp(T_array, eq_type, coeffs_str)
            
            fig.add_trace(
                go.Scatter(
                    x=T_array,
                    y=Cp_array,
                    mode="lines",
                    name=f"{mat_name} ({formula})",
                    legendgroup=mat_name,
                    line=dict(color=mat_color),
                    hovertemplate=(
                        f"<b>{mat_name}</b><br>"
                        "Temp: %{x:.1f} K<br>"
                        f"Cp: %{{y:.2f}} {y_label}<br>"
                        f"Category: {category}"
                        "<extra></extra>"
                    )
                )
            )

        # --- 3. UPPER EXTRAPOLATION (Dashed) ---
        if t_max_slider > valid_tmax:
            extrap_min = max(t_min_slider, valid_tmax)
            extrap_max = t_max_slider
            
            if extrap_min < extrap_max:
                T_extrap = np.linspace(extrap_min, extrap_max, 100)
                Cp_extrap = calculate_cp(T_extrap, eq_type, coeffs_str)
                
                fig.add_trace(
                    go.Scatter(
                        x=T_extrap,
                        y=Cp_extrap,
                        mode="lines",
                        name=f"{mat_name} (Extrapolated)",
                        legendgroup=mat_name,
                        showlegend=False, # Hide from legend to avoid duplicates
                        line=dict(color=mat_color, dash="dash"),
                        hovertemplate=(
                            f"<b>{mat_name}</b> (Extrapolated)<br>"
                            "Temp: %{x:.1f} K<br>"
                            f"Cp: %{{y:.2f}} {y_label}<br>"
                            f"Category: {category}"
                            "<extra></extra>"
                        )
                    )
                )

        # Summary data
        summary_data.append({
            "Material": mat_name,
            "Formula": formula,
            "Category": category,
            "Valid T Range (K)": f"{valid_tmin} - {valid_tmax}",
            "Unit": unit,
            "Data Source": source
        })

    # Dynamically build the Y-axis label based on selected materials
    y_axis_unit_str = " or ".join(sorted(list(selected_units)))
    y_axis_title = f"Specific Heat Capacity ({y_axis_unit_str})"

    # Graph layout
    fig.update_layout(
        title="Specific Heat Capacity (Cp) vs Temperature (T)",
        xaxis_title="Temperature (K)",
        yaxis_title=y_axis_title,
        legend_title="Selected Materials",
        hovermode="x unified",
        template="plotly_dark"
    )

    st.plotly_chart(fig, use_container_width=True)

    # Equations
    st.markdown("### Equations Used")
    
    # Map raw equation types to readable names
    equation_names = {
        "shomate": "Shomate",
        "kelley": "Kelley",
        "linear": "Linear",
        "const": "Constant"
    }
    
    for mat_name in selected_materials:
        mat_data = df[df['name'] == mat_name].iloc[0]
        equation_md = get_equation_markdown(mat_data['equation_type'], mat_data['coeffs'])
        
        # Get readable equation name, fallback to capitalized raw type if not found
        eq_display_name = equation_names.get(mat_data['equation_type'], str(mat_data['equation_type']).capitalize())
        
        st.markdown(f"**{mat_name} ({mat_data['formula']}) [{eq_display_name} Equation]**")
        st.markdown(equation_md)
        st.write("---") # Adds a subtle visual separator between multiple materials

    # Summary Table & Export
    st.markdown("### Selected Material Details")
    summary_df = pd.DataFrame(summary_data)
    st.dataframe(summary_df, use_container_width=True)
    
    # Add Export Button
    csv = summary_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="Export data (as csv)",
        data=csv,
        file_name='material_summary.csv',
        mime='text/csv',
    )
