import streamlit as st
import pandas as pd
import json
from io import BytesIO
from agno.agent import Agent
from agno.tools.exa import ExaTools
from agno.models.openai import OpenAIChat
from openpyxl import load_workbook

# ----- Load secrets from .streamlit/secrets.toml -----
import os
os.environ['OPENAI_API_KEY'] = st.secrets.get("OPENAI_API_KEY", "")
os.environ['EXA_API_KEY'] = st.secrets.get("EXA_API_KEY", "")

# ----- Utility Functions -----

@st.cache_data
def read_excel(file):
    return pd.read_excel(file)

def clean_json_string(raw):
    if isinstance(raw, dict):
        return raw
    raw = raw.strip()
    start = raw.find('{')
    end = raw.rfind('}')
    if start != -1 and end != -1 and end > start:
        return raw[start:end+1]
    return raw

def clean_json_array(raw):
    raw = raw.strip()
    start = raw.find('[')
    end = raw.rfind(']')
    if start != -1 and end != -1 and end > start:
        return raw[start:end+1]
    return raw

# ----- Pipeline Logic -----

def search_in_excel_df(df, search_name, name_column='Full Name'):
    result = df[df[name_column].str.lower() == search_name.lower()]
    selected_cols = ['Full Name', 'URL', 'Company', 'Position']
    if not result.empty:
        filtered = result[selected_cols].iloc[0].to_dict()
        return filtered
    else:
        return None

def linkedin_profile_searcher(search_name):
    agent = Agent(
        name="LinkedIn Finder Agent",
        role="Find top 5 LinkedIn profiles for a given person's name",
        model=OpenAIChat(id="gpt-4o-mini"),
        tools=[ExaTools()],
    )
    query = f"""
    Use ExaSearch to find LinkedIn profiles for the person named "{search_name}".
        Requirements:
        - Only include **individual people profiles** on LinkedIn (URLs should match the pattern "https://www.linkedin.com/in/...").
        - Exclude company pages, posts, job listings, or articles.
        - Return up to **5 most relevant** profile URLs.
        - The output must be **only** a valid JSON array of strings, e.g.:
        ["https://www.linkedin.com/in/john-doe/", "https://www.linkedin.com/in/johndoe123/"]
        - If no profiles are found, return an empty array: []
    """
    result = agent.run(query)
    output = getattr(result, "content", result)
    return output

def scrape_linkedin_profile(linkedin_url):
    try:
        agent = Agent(
            name="LinkedIn Profile Scraper",
            role="Scrape and summarize LinkedIn data",
            model=OpenAIChat(id="gpt-4o-mini"),
            tools=[ExaTools()],
            markdown=True,
        )
        result = agent.run(f"""
        You are given a LinkedIn URL, which is of a person. Use the Exa search tool to extract information from this page.
        Focus on:
          - Organization Name
          - Link to Organization's LinkedIn Page
          - Sector Of Organization
          - Location of the person
        URL: {linkedin_url}
        Return your answer strictly as a JSON object with these keys:
            - Org_Name
            - Org_LinkedIn_URL
            - Org_Sector
            - Location
        """)
        return result.content if hasattr(result, 'content') else str(result)
    except Exception as e:
        st.warning(f"Error scraping LinkedIn profile: {e}")
        return None

def get_org_details(organization_name, org_linkedin_url):
    agent = Agent(
        name="Organization Research Agent",
        role="Find and summarize company information using Exa",
        model=OpenAIChat(id="gpt-4o-mini"),
        tools=[ExaTools()],
    )
    org_types = [
        "enterprise", "corporation", "business", "mid-sized", "company",
        "education", "university", "higher_ed", "agency", "startup",
        "non-profit", "business_influencer", "journalist", "individual", "political"
    ]
    
    details = {"revenue": "unknown", "employee_count": "unknown", "type_of_organization": "unknown"}
    if org_linkedin_url and org_linkedin_url.strip().startswith("https://"):
        prompt = f"""
            You are given a LinkedIn organization/company page at this URL: {org_linkedin_url}
            Extract, using ExaSearch, the following as a JSON object:
            - revenue (approximate, in USD, ONLY an integer value with NO text, NO currency symbol, NO commas, NO decimals, NO words like 'million' or 'billion'; e.g., 102300000000 for $102.3 Billion; or "unknown" if unsure)
            - employee_count (approximate, ONLY an integer, or "unknown")
            - type_of_organization (choose from: {', '.join(org_types)}, or "unknown")
            IMPORTANT:
            - For revenue, return only the integer value in USD (no $ sign, no commas, no words), e.g., 102300000000.
            - If exact value not available, convert any stated amount (e.g., "$2.4B", "$960 million", "3,200,000,000") to the integer form (e.g., 2400000000, 960000000, 3200000000).
            - If revenue can't be determined, set as "unknown".
            Only return the JSON object, nothing else.
            """
        result = agent.run(prompt)
        output = getattr(result, "content", result)
        output = clean_json_string(output)
        try:
            org_page_details = json.loads(output)
            for k in details:
                if org_page_details.get(k) and org_page_details[k] not in ["unknown", "", None]:
                    details[k] = org_page_details[k]
        except Exception as e:
            st.warning(f"Org LinkedIn page parse failed. Will fallback for all fields. Err: {e}\nRaw: {output}")

    missing = [k for k in details if details[k] == "unknown"]
    if missing:
        prompt = f"""
        Search for verified company information about "{organization_name}".
        Return ONLY a JSON object with these keys:
        {', '.join(missing)}
        Use company websites, LinkedIn, or Crunchbase only. If unavailable, "unknown".
        """
        result = agent.run(prompt)
        output = getattr(result, "content", result)
        output = clean_json_string(output)
        try:
            fallback_details = json.loads(output)
            for k in missing:
                if fallback_details.get(k) and fallback_details[k] not in ["unknown", "", None]:
                    details[k] = fallback_details[k]
        except Exception as e:
            st.warning(f"Fallback company search failed for missing fields {missing}. Err: {e}\nRaw: {output}")
    return details

def classify_entity(org_type, revenue, employee_count):
    try:
        revenue = float(revenue) if revenue != "unknown" else 0
    except:
        revenue = 0
    try:
        employee_count = int(employee_count) if employee_count != "unknown" else 0
    except:
        employee_count = 0
    if org_type in ['enterprise', 'corporation'] and revenue > 1e9 and employee_count >= 5000:
        return "Enterprise"
    elif org_type in ['business', 'mid-sized', 'company'] and 5e7 <= revenue <= 1e9 and 100 <= employee_count < 5000:
        return "Mid-Sized Business"
    elif org_type in ['education', 'university', 'higher_ed']:
        if revenue >= 1e7:
            return "Education - University"
        else:
            return "Education - K-12/Ed-tech"
    elif org_type == 'agency':
        if revenue > 5e8:
            return "Agency - Holding Company"
        elif 2.5e7 <= revenue <= 1e8:
            return "Agency - Mid-Tier"
        elif 5e6 <= revenue <= 5e8:
            return "Agency"
        else:
            return "Agency"
    elif org_type == 'startup':
        if revenue <= 5e7:
            return "Startup"
        else:
            return "Growth Stage Startup"
    elif org_type == 'non-profit':
        if revenue < 1e6:
            return "Non-Profit - Local"
        elif revenue >= 5e8:
            return "Non-Profit - National/Global"
        else:
            return "Non-Profit"
    elif org_type == 'business_influencer':
        return "Business Influencer"
    elif org_type == 'journalist':
        return "Journalist"
    elif org_type == 'individual':
        return "Individual"
    elif org_type == 'political':
        if revenue >= 1e6:
            return "Political - PAC/Committee"
        elif 1e7 <= revenue <= 5e8 and employee_count >= 50:
            return "Political Consulting Firm"
        elif 5e6 <= revenue <= 3e8 and employee_count >= 30:
            return "Political Think Tank"
        else:
            return "Political"
    else:
        return "Unclassified"

# ----- Main Streamlit App -----

st.set_page_config(page_title="LinkedIn Org Intelligence", layout="wide")
st.title("LinkedIn & Organization Intelligence Pipeline")

excel_file = st.file_uploader("Upload your Excel file (.xlsx)", type=["xlsx"])
if excel_file:
    with st.spinner("Loading your Excel file..."):
        try:
            df = read_excel(excel_file)
            st.subheader("Excel Preview")
            st.dataframe(df)
        except Exception as e:
            st.error(f"Could not read Excel file: {e}")
            st.stop()
else:
    st.info("Please upload an Excel file to proceed.")
    st.stop()

search_name = st.text_input("Enter name to search (case-insensitive):")
run_button = st.button("Run Agents")

results = []

if run_button and search_name:
    with st.spinner("Running agents and fetching data..."):
        # Step 1: Excel search
        excel_result = search_in_excel_df(df, search_name)
        linkedin_urls = []
        # Prefer Excel match
        if excel_result and excel_result.get("URL"):
            linkedin_urls.append(excel_result.get("URL"))
        else:
            agent_result = linkedin_profile_searcher(search_name)
            cleaned_agent_result = clean_json_array(agent_result)
            try:
                linkedin_urls = json.loads(cleaned_agent_result)
            except Exception as e:
                st.error(f"Could not parse LinkedIn URLs: {e}")
                st.stop()
        if not linkedin_urls:
            st.warning("No LinkedIn URLs available.")
            st.stop()

        for idx, linkedin_url in enumerate(linkedin_urls, start=1):
            st.markdown(f"""<hr style="border-top:2px solid #bbb">""", unsafe_allow_html=True)
            st.markdown(f"### Candidate #{idx}: [{linkedin_url}]({linkedin_url})")
            linkedin_details = scrape_linkedin_profile(linkedin_url)
            try:
                cleaned_linkedin_details = json.loads(clean_json_string(linkedin_details))
            except Exception as e:
                st.error(f"Could not parse LinkedIn profile JSON for {linkedin_url}: {e}\nRaw: {linkedin_details}")
                continue
            st.json(cleaned_linkedin_details)
            org_name = cleaned_linkedin_details.get("Org_Name")
            org_linkedin_url = cleaned_linkedin_details.get("Org_LinkedIn_URL", "")

            if org_name:
                org_details = get_org_details(org_name, org_linkedin_url)
                if isinstance(org_details, dict):
                    org_details_cleaned = org_details
                else:
                    cleaned = clean_json_string(org_details)
                    try:
                        org_details_cleaned = json.loads(cleaned)
                    except Exception as e:
                        st.error(f"Could not parse Organization JSON for {org_name}: {e}\nRaw: {org_details}")
                        continue
                st.json(org_details_cleaned)
                org_type = org_details_cleaned.get("type_of_organization", "unknown")
                revenue = org_details_cleaned.get("revenue", "unknown")
                employee_count = org_details_cleaned.get("employee_count", "unknown")
                entity_type = classify_entity(org_type, revenue, employee_count)
                st.write(f"**Entity Classification:** {entity_type}")

                results.append({
                    "LinkedIn URL": linkedin_url,
                    "Org Name": org_name,
                    "Org LinkedIn": org_linkedin_url,
                    "Org Sector": cleaned_linkedin_details.get("Org_Sector", ""),
                    "Location": cleaned_linkedin_details.get("Location", ""),
                    "Org Type": org_type,
                    "Revenue": revenue,
                    "Employee Count": employee_count,
                    "Entity Classification": entity_type
                })
            else:
                st.warning(f"No organization name found for {linkedin_url}")

    # Display table
    if results:
        st.subheader("Processed Results")
        results_df = pd.DataFrame(results)
        st.dataframe(results_df)
        # Download button
        out_csv = results_df.to_csv(index=False).encode("utf-8")
        st.download_button("Download CSV", out_csv, "results.csv", mime="text/csv")
        out_excel = BytesIO()
        results_df.to_excel(out_excel, index=False, engine="openpyxl")
        st.download_button("Download Excel", out_excel.getvalue(), "results.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.info("No results to display yet.")

else:
    st.info("Enter a name and click 'Run Agents' to begin.")

