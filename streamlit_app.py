import streamlit as st
import pandas as pd

st.set_page_config(page_title="Public Sphere Influence Calculator", layout="centered")

st.title("🧠 Public Sphere Influence Score Calculator")
st.write("Enter the Reach, Salience, and Discursiveness scores below (each between 0 and 1). The Influence Score will be calculated automatically.")

# Input fields
reach = st.slider("Reach Score", 0.0, 1.0, 0.5, 0.01)
salience = st.slider("Salience Score", 0.0, 1.0, 0.5, 0.01)
discursiveness = st.slider("Discursiveness Score", 0.0, 1.0, 0.5, 0.01)

# Calculation
influence_score = 0.4 * reach + 0.4 * salience + 0.2 * discursiveness

# Display result
st.metric("📊 Influence Score", f"{influence_score:.3f}")

# Optional data entry
st.subheader("📝 Enter Multiple Samples")
data_input = st.text_area("Paste data (one line per sample, comma-separated Reach, Salience, Discursiveness)",
                          "0.8, 0.6, 0.7\n0.5, 0.5, 0.5")

if data_input:
    try:
        rows = [list(map(float, line.split(","))) for line in data_input.strip().split("\n")]
        df = pd.DataFrame(rows, columns=["Reach", "Salience", "Discursiveness"])
        df["Influence"] = 0.4 * df["Reach"] + 0.4 * df["Salience"] + 0.2 * df["Discursiveness"]
        st.dataframe(df.style.format("{:.3f}"))
    except:
        st.error("Please ensure all lines contain exactly 3 comma-separated numeric values between 0 and 1.")
