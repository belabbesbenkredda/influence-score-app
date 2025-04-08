import streamlit as st
import pandas as pd
import numpy as np
import re
from sklearn.feature_extraction.text import TfidfVectorizer

st.set_page_config(page_title="Influence Score: US Pilot", layout="wide")

st.title("🇺🇸 US Public Sphere Pilot: Influence Scoring Dashboard")
st.write("This tool allows you to input, score, and compare media samples for the US pilot phase of the Public Sphere Health project.")

st.header("🔍 Score a Single Media Sample")
sample_title = st.text_input("Sample Title", "September 11 Harris–Trump Debate")
reach = st.slider("Reach Score (0–1)", 0.0, 1.0, 0.5, 0.01)

# Upload transcript to calculate salience
transcript_file = st.file_uploader("Upload Transcript (.txt)", type=["txt"])
salience = 0.5  # default placeholder
if transcript_file:
    text = transcript_file.read().decode("utf-8")
    # Basic keyword list for Gallup-style issues (can be expanded)
    keywords = [
        "economy", "jobs", "inflation", "immigration", "crime", "healthcare", "education",
        "taxes", "climate", "environment", "leadership", "government", "abortion"
    ]
    keyword_counts = {kw: len(re.findall(rf"\\b{kw}\\b", text.lower())) for kw in keywords}
    total_mentions = sum(keyword_counts.values())
    if total_mentions > 0:
        weighted_sum = 0.3 * total_mentions  # simulate frequency score
        tfidf = TfidfVectorizer(vocabulary=keywords)
        tfidf_matrix = tfidf.fit_transform([text])
        tfidf_score = tfidf_matrix.sum()
        salience = min(1.0, (0.3 * total_mentions + 0.7 * tfidf_score) / 100)
    st.write("Keyword Mentions:", keyword_counts)
    st.write("Salience Score (auto-calculated):", round(salience, 3))
else:
    salience = st.slider("Manual Salience Score (0–1)", 0.0, 1.0, 0.5, 0.01)

discursiveness = st.slider("Machine Discursiveness Score (0–1)", 0.0, 1.0, 0.5, 0.01)

influence_score = 0.4 * reach + 0.4 * salience + 0.2 * discursiveness
st.metric("📊 Machine Influence Score", f"{influence_score:.3f}")

st.markdown("---")
st.subheader("✍️ Human Evaluation (Optional)")
human_salience = st.slider("Human Salience Score (0–1)", 0.0, 1.0, 0.5, 0.01)
human_discursiveness = st.slider("Human Discursiveness Score (0–1)", 0.0, 1.0, 0.5, 0.01)
human_justification = st.text_input("Why did you assign this salience score?")
human_comments = st.text_area("Additional Comments")

if st.button("Save Sample Entry"):
    st.success("Sample saved (simulation only). In future: entries will persist to a database or spreadsheet.")

st.markdown("---")
st.subheader("📥 Upload Batch of Samples")
uploaded_file = st.file_uploader("Upload CSV with columns: Title, Reach, Salience, Discursiveness", type=["csv"])

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    if all(col in df.columns for col in ["Title", "Reach", "Salience", "Discursiveness"]):
        df["Influence"] = 0.4 * df["Reach"] + 0.4 * df["Salience"] + 0.2 * df["Discursiveness"]
        st.dataframe(df.style.format({"Reach": "{:.2f}", "Salience": "{:.2f}", "Discursiveness": "{:.2f}", "Influence": "{:.3f}"}))
    else:
        st.error("Missing required columns. Please include: Title, Reach, Salience, Discursiveness")
