import streamlit as st
from vc_scraper import extract_companies
import csv
from io import StringIO
import pandas as pd

# Page configuration
st.set_page_config(
    page_title="VC Portfolio Scraper",
    page_icon="🕸️",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Custom CSS
st.markdown("""
    <style>
    /* Modern styling */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    /* Base styles */
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif !important;
    }
    
    /* Container styling */
    .main > div {
        padding: 2rem 3rem 3rem 3rem;
        max-width: 46rem;
    }
    
    /* Header styling */
    h1 {
        font-weight: 700 !important;
        font-size: 2.5rem !important;
        margin-bottom: 0.5rem !important;
    }
    
    /* Input field styling */
    .stTextInput > div > div > input {
        background-color: #f8f9fa;
        padding: 1rem;
        font-size: 1rem;
        border: 2px solid #e9ecef;
        border-radius: 8px;
    }
    
    .stTextInput > div > div > input:focus {
        border-color: #6c757d;
        box-shadow: none;
    }
    
    /* Button styling */
    .stButton > button {
        width: 100%;
        padding: 0.75rem 1.5rem;
        font-size: 1rem;
        font-weight: 600;
        border-radius: 8px;
        margin-top: 1rem;
        background-color: #000;
        color: white;
        border: none;
        transition: all 0.2s;
    }
    
    .stButton > button:hover {
        background-color: #1a1a1a;
        transform: translateY(-1px);
    }
    
    /* Success message styling */
    .success-box {
        padding: 1.5rem;
        border-radius: 8px;
        background-color: #f8f9fa;
        border: 2px solid #e9ecef;
        margin: 1rem 0;
    }
    
    /* Download button styling */
    .stDownloadButton > button {
        width: 100%;
        padding: 0.75rem 1.5rem;
        font-size: 1rem;
        font-weight: 600;
        border-radius: 8px;
        background-color: #28a745;
        color: white;
        border: none;
        margin-top: 0.5rem;
        transition: all 0.2s;
    }
    
    .stDownloadButton > button:hover {
        background-color: #218838;
        transform: translateY(-1px);
    }
    </style>
    """, unsafe_allow_html=True)

# Header
st.title("VC Portfolio Scraper")
st.markdown("""
    <p style='font-size: 1.1rem; color: #6c757d; margin-bottom: 2rem;'>
        Extract portfolio companies from any VC website with one click.
    </p>
""", unsafe_allow_html=True)

# URL Input
url = st.text_input(
    "Enter portfolio URL",
    placeholder="https://example.vc/portfolio",
    help="Paste the URL of any VC portfolio page"
)

# Process Button
if st.button("Extract Companies 🚀"):
    if not url:
        st.error("Please enter a portfolio URL")
    else:
        with st.spinner("🔍 Analyzing portfolio page..."):
            try:
                # Extract companies
                companies = extract_companies(url)
                
                if not companies:
                    st.error("No companies found. Please check the URL and try again.")
                else:
                    # Create CSV in memory
                    output = StringIO()
                    writer = csv.writer(output)
                    writer.writerow(["Company", "URL"])
                    writer.writerows(companies)
                    
                    # Success message
                    st.markdown(f"""
                        <div class='success-box'>
                            <h3 style='margin: 0; color: #28a745; font-size: 1.2rem;'>✨ Success!</h3>
                            <p style='margin: 0.5rem 0 0 0; color: #6c757d;'>
                                Found {len(companies)} companies. Download the CSV below.
                            </p>
                        </div>
                    """, unsafe_allow_html=True)
                    
                    # Download button
                    st.download_button(
                        "📥 Download CSV",
                        output.getvalue(),
                        file_name="portfolio_companies.csv",
                        mime="text/csv"
                    )
                    
                    # Preview table
                    st.markdown("### Preview")
                    preview_df = pd.DataFrame(companies[:5], columns=["Company", "URL"])
                    st.dataframe(preview_df, use_container_width=True)
                    
                    if len(companies) > 5:
                        st.caption(f"Showing 5 of {len(companies)} companies. Download the CSV to see all.")
                    
            except Exception as e:
                st.error(f"An error occurred: {str(e)}")

# Footer
st.markdown("""
    <div style='position: fixed; bottom: 0; left: 0; right: 0; background-color: white; padding: 1rem; text-align: center; border-top: 1px solid #e9ecef;'>
        <p style='color: #6c757d; margin: 0; font-size: 0.9rem;'>
            Built with ❤️ using Streamlit
        </p>
    </div>
""", unsafe_allow_html=True)
