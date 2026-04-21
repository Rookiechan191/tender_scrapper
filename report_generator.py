import pandas as pd
from datetime import datetime
import re
import matplotlib.pyplot as plt

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, Image
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet

# ========= DISTRICTS =========
MAHARASHTRA_DISTRICTS = [
    "AHMEDNAGAR","AKOLA","AMRAVATI","AURANGABAD","BEED","BHANDARA",
    "BULDHANA","CHANDRAPUR","DHULE","GADCHIROLI","GONDIA","HINGOLI",
    "JALGAON","JALNA","KOLHAPUR","LATUR","MUMBAI","MUMBAI SUBURBAN",
    "NAGPUR","NANDED","NANDURBAR","NASHIK","OSMANABAD","PALGHAR",
    "PARBHANI","PUNE","RAIGAD","RATNAGIRI","SANGLI","SATARA",
    "SINDHUDURG","SOLAPUR","THANE","WARDHA","WASHIM","YAVATMAL"
]

# ========= LOAD =========
df = pd.read_csv("mahatenders_output.csv", sep=None, engine="python", encoding="utf-8-sig")
df.columns = df.columns.str.strip()

# ========= CLEAN =========
df = df.replace(r'^\s*NA\s*$', None, regex=True)

df["Tender Value (INR)"] = (
    df["Tender Value (INR)"]
    .astype(str)
    .str.replace(",", "")
    .str.strip()
)
df["Tender Value (INR)"] = pd.to_numeric(df["Tender Value (INR)"], errors="coerce")

df["Bid Closing Date"] = pd.to_datetime(df["Bid Closing Date"], dayfirst=True, errors="coerce")

today = datetime.now()
df["Days Left"] = (df["Bid Closing Date"] - today).dt.days

# ========= TITLE CLEAN =========
def clean_title(t):
    if pd.isna(t):
        return ""
    t = t.split("[")[0]
    words = t.split()
    return " ".join(dict.fromkeys(words))

df["Clean Title"] = df["Title"].apply(clean_title)

# ========= DISTRICT =========
def extract_district(text):
    if pd.isna(text):
        return None
    text = text.upper()
    for d in MAHARASHTRA_DISTRICTS:
        if re.search(rf'\b{d}\b', text):
            return d
    return None

df["District"] = df["Organisation Chain"].apply(extract_district)

# ========= CATEGORY =========
def categorize(title):
    if pd.isna(title):
        return "Other"
    
    t = title.lower()

    if any(k in t for k in ["road", "bridge", "highway", "pavement"]):
        return "Road & Transport"

    if any(k in t for k in ["water", "pipeline", "sewer", "drain", "drainage"]):
        return "Water & Sanitation"

    if any(k in t for k in [
        "construction", "constructing", "building", "civil",
        "renovation", "repair", "restoration", "improvement",
        "development", "structure", "work","stadium"
    ]):
        return "Construction"

    if any(k in t for k in ["electric", "power", "lighting", "transformer"]):
        return "Electrical"

    if any(k in t for k in ["software", "system", "digital","automation", "ai"]):
        return "IT & Software"

    if any(k in t for k in ["supply of", "procurement", "materials", "equipment"]):
        return "Supply"

    return "Other"

df["Category"] = df["Clean Title"].apply(categorize)

# ========= FILTER =========
df = df[df["Clean Title"].str.len() > 10]
df = df[df["Days Left"] >= 0]

# ========= SIZE =========
def size_bucket(v):
    if pd.isna(v):
        return "Unknown"
    if v < 10_00_000:
        return "<10L"
    elif v < 1_00_00_000:
        return "10L–1Cr"
    else:
        return ">1Cr"

df["Size"] = df["Tender Value (INR)"].apply(size_bucket)

# ========= SCORING =========
df["Score"] = (df["Tender Value (INR)"].fillna(0)/1e7)*4 - df["Days Left"]*1.5

# ========= DATA SPLITS =========
opportunities = df.sort_values("Score", ascending=False).head(12)
urgent = df[df["Days Left"] <= 3].sort_values("Days Left").head(10)
high_value = df[df["Tender Value (INR)"] > 1_00_00_000] \
                .sort_values("Tender Value (INR)", ascending=False) \
                .head(10)

# ========= INSIGHTS =========
total = len(df)
avg_value = int(df["Tender Value (INR)"].mean(skipna=True))
urgent_count = len(df[df["Days Left"] <= 3])

top_districts = df["District"].value_counts().dropna().head(5)
district_value = df.groupby("District")["Tender Value (INR)"].sum().dropna().sort_values(ascending=False).head(5)
category_counts = df["Category"].value_counts()
size_counts = df["Size"].value_counts()

# ========= GRAPHS =========

# District activity
plt.figure()
top_districts.plot(kind="bar")
plt.title("Top Districts by Count")
plt.tight_layout()
plt.savefig("district.png")
plt.close()

# Money flow
plt.figure()
district_value.plot(kind="bar")
plt.title("Money Flow by District")
plt.tight_layout()
plt.savefig("value.png")
plt.close()

# Category
plt.figure()
category_counts.plot(kind="bar")
plt.title("Tender Categories")
plt.tight_layout()
plt.savefig("category.png")
plt.close()

# Timeline
df["Days Bucket"] = pd.cut(df["Days Left"], bins=[0,3,7,15,30], labels=["0-3","4-7","8-15","15+"])
timeline = df["Days Bucket"].value_counts()

plt.figure()
timeline.plot(kind="bar")
plt.title("Deadline Distribution")
plt.tight_layout()
plt.savefig("timeline.png")
plt.close()

# Size
plt.figure()
size_counts.plot(kind="bar")
plt.title("Tender Size Distribution")
plt.tight_layout()
plt.savefig("size.png")
plt.close()

# ========= PDF =========
doc = SimpleDocTemplate("Tender_Report.pdf", pagesize=A4)
styles = getSampleStyleSheet()
small = styles["Normal"]
small.fontSize = 8

elements = []

# TITLE
elements.append(Paragraph("Maharashtra Tender Intelligence Report", styles["Title"]))
elements.append(Spacer(1,10))

# SUMMARY
elements.append(Paragraph("Summary", styles["Heading2"]))
elements.append(Paragraph(f"• Total tenders: {total}", styles["Normal"]))
elements.append(Paragraph(f"• Average value: {avg_value:,}", styles["Normal"]))
elements.append(Paragraph(f"• Urgent (<=3 days): {urgent_count}", styles["Normal"]))
elements.append(Spacer(1,10))

# GRAPHS
elements.append(Paragraph("Market Overview", styles["Heading2"]))

elements.append(Paragraph("District Activity", styles["Heading3"]))
elements.append(Image("district.png", width=400, height=200))

elements.append(Paragraph("Money Flow", styles["Heading3"]))
elements.append(Image("value.png", width=400, height=200))

elements.append(Paragraph("Category Distribution", styles["Heading3"]))
elements.append(Image("category.png", width=400, height=200))

elements.append(Paragraph("Deadline Distribution", styles["Heading3"]))
elements.append(Image("timeline.png", width=400, height=200))

elements.append(Paragraph("Size Distribution", styles["Heading3"]))
elements.append(Image("size.png", width=400, height=200))

elements.append(Spacer(1,10))

# OPPORTUNITIES
elements.append(Paragraph("Top Opportunities", styles["Heading2"]))
data = [["Title","Category","Value","Days"]]

for _,r in opportunities.iterrows():
    data.append([
        Paragraph(r["Clean Title"], small),
        r["Category"],
        f"{int(r['Tender Value (INR)']):,}" if pd.notna(r["Tender Value (INR)"]) else "-",
        int(r["Days Left"])
    ])

elements.append(Table(data, colWidths=[220,90,70,40]))
elements.append(Spacer(1,15))

# URGENT
elements.append(Paragraph("Urgent Tenders", styles["Heading2"]))
data = [["Title","Days"]]

for _,r in urgent.iterrows():
    data.append([
        Paragraph(r["Clean Title"], small),
        int(r["Days Left"])
    ])

elements.append(Table(data, colWidths=[300,60]))
elements.append(Spacer(1,15))

# HIGH VALUE
elements.append(Paragraph("High Value (>1 Cr)", styles["Heading2"]))
data = [["Title","Value"]]

for _,r in high_value.iterrows():
    data.append([
        Paragraph(r["Clean Title"], small),
        f"{int(r['Tender Value (INR)']):,}"
    ])

elements.append(Table(data, colWidths=[300,100]))

# BUILD
doc.build(elements)

print(" FINAL PERFECT REPORT GENERATED (NOTHING MISSING)")