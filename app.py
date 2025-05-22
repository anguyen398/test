import os, sys

# Move CWD into the folder where this script lives:
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

import os
import subprocess
import pandas as pd
import streamlit as st
import openai
import smtplib
import json
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env')
openai.api_key = os.getenv("OPENAI_API_KEY")

# Email configs
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_SENDER = "antnguyen398@gmail.com"
EMAIL_PASSWORD = "bphl iwbr kwuh fkqk"

# Logo display
logo_path = "logo.png"
col1, col2 = st.columns([6, 10])
with col1:
    if os.path.exists(logo_path): st.image(logo_path, width=250)
    else: st.warning(f"Logo not found at {logo_path}")
with col2:
    st.markdown(
        """
        <h1 style=\"font-size:40px; margin-bottom:0;\">PR News Scraper & GPT Summarizer</h1>
        """, unsafe_allow_html=True
    )
st.title("PR News Scraper & GPT Summarizer")

# User input
target_csv = "news.csv"
user_email = st.text_input("Enter your email to receive the summary:")

# Scraper function
def run_scraper():
    if os.path.exists(target_csv): os.remove(target_csv)
    subprocess.run(["scrapy","crawl","pr_news_gpt","-O",target_csv], capture_output=True, text=True)

# Action buttons row
cols = st.columns(5)
# Left-aligned Run Scraper
with cols[0]:
    if st.button("Run Scraper"):
        with st.spinner("Running Scrapy... Please wait."):
            run_scraper()
        st.success("Scraping completed!")
# Center-aligned Email Top Summaries
with cols[2]:
    if st.button("Email Top Summaries"):
        if not st.session_state.get('top_summaries'):
            st.warning("Please generate summaries first.")
        elif not user_email:
            st.warning("Please enter your email before sending.")
        else:
            with st.spinner("Sending email..."):
                html_sections = []
                for art in st.session_state['top_summaries']:
                    paras = art['text'].split("\n\n")
                    summary = paras[0] if paras else ""
                    implication = paras[1] if len(paras) > 1 else ""
                    section = (
                        f"<h2 style='margin-bottom:5px;'>{art['title']}</h2>"
                        f"<p>{summary}</p>"
                        f"<p><em>{implication}</em></p>"
                        f"<p><a href='{art['link']}'>Read the Article &rsaquo;</a></p>"
                        f"<hr/>"
                    )
                    html_sections.append(section)
                signature = "<p>Best regards,<br/>AMPCO Technologies</p>"
                body_html = f"<html><body>{''.join(html_sections)}{signature}</body></html>"
                date_str = datetime.now().strftime("%B %d, %Y")
                subject = f"Top 10 Supply Chain Updates — {date_str}"
                msg = MIMEMultipart('alternative')
                msg['From'] = EMAIL_SENDER
                msg['To'] = user_email
                msg['Subject'] = subject
                msg.attach(MIMEText(body_html, 'html'))
                try:
                    server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
                    server.starttls()
                    server.login(EMAIL_SENDER, EMAIL_PASSWORD)
                    server.send_message(msg)
                    server.quit()
                    st.success(f"Top summaries sent to {user_email}!")
                except Exception as e:
                    st.error(f"Failed to send email: {e}")
# Right-aligned Download CSV (safe against empty/malformed files)
with cols[4]:
    if os.path.exists(target_csv) and os.path.getsize(target_csv) > 0:
        try:
            df = pd.read_csv(target_csv)
        except pd.errors.EmptyDataError:
            # If the CSV is blank or malformed, remove it so downstream code won’t break
            os.remove(target_csv)
            st.warning("news.csv was empty—run the scraper to generate data.")
        else:
            st.download_button(
                "Download CSV",
                df.to_csv(index=False),
                "scraped_news.csv",
                "text/csv"
            )
# Load and show data
if os.path.exists(target_csv) and os.path.getsize(target_csv) > 0:
    df = pd.read_csv(target_csv)
    st.subheader("Scraped Articles")
    st.dataframe(df)

    if st.button("Select & Summarize Top 10 Articles"):
        with st.spinner("Selecting and summarizing top articles..."):
            metadata = [{"idx": idx, "title": row['title'], "categories": row.get('categories', []), "link": row['link']} for idx, row in df.iterrows()]
            sel_prompt = ("You are a supply chain CEO. From the following articles, select the 10 most important and return only a JSON array of their titles.\n\n" + json.dumps(metadata))
            sel_resp = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": sel_prompt}],
                max_tokens=300
            )
            try:
                selected_titles = json.loads(sel_resp.choices[0].message.content)
            except:
                selected_titles = [m['title'] for m in metadata[:10]]
            sel_meta = [m for m in metadata if m['title'] in selected_titles][:10]
            top_summaries = []
            for m in sel_meta:
                row = df.loc[m['idx']]
                pr = f"Title: {row['title']}\nLink: {row['link']}\nContent: {row['full_text']}"
                det_resp = openai.ChatCompletion.create(
                    model="gpt-4-turbo",
                    messages=[{"role": "user", "content": pr+"\n\nWrite a natural paragraph summarizing the article. Then a second paragraph on global implications or key figures."}],
                    max_tokens=400
                )
                top_summaries.append({
                    'title': row['title'],
                    'link': row['link'],
                    'text': det_resp.choices[0].message.content.strip()
                })
            st.session_state['top_summaries'] = top_summaries
            st.success("Top articles summarized!")

    if st.session_state.get('top_summaries'):
        st.subheader("Top 10 Article Summaries")
        for art in st.session_state['top_summaries']:
            st.markdown(f"**{art['title']}**")
            st.markdown(art['link'])
            paras = art['text'].split("\n\n")
            for p in paras:
                st.markdown(p)
            st.markdown("---")
else:
    st.warning("No data found. Run the scraper first.")
