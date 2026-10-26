"""Client accounts of Nexora Technologies (fictional company names, realistic profiles).

(client_code, name, industry_key, sub_industry, hq_city, country, relationship_since, account_weight)
"""

INDUSTRY_NAMES = {
    "BANK": "Banking & Financial Services",
    "INS": "Insurance",
    "HEALTH": "Healthcare",
    "LIFESCI": "Life Sciences & Pharma",
    "RETAIL": "Retail & E-commerce",
    "CPG": "Consumer Goods (CPG)",
    "TELECOM": "Telecommunications",
    "MEDIA": "Media & Entertainment",
    "MFG": "Manufacturing",
    "LOGI": "Transportation & Logistics",
    "ENERGY": "Energy & Utilities",
}

CLIENTS = [
    ("KCB", "Kaveri Commercial Bank", "BANK", "Retail & Commercial Banking", "Bengaluru", "India", 2016, 3.0),
    ("BRF", "Bayridge Financial Group", "BANK", "Retail Banking & Cards", "Charlotte", "United States", 2018, 2.0),
    ("ASF", "Ashoka Small Finance Bank", "BANK", "Small Finance Bank / Microfinance", "Pune", "India", 2019, 1.5),
    ("UPX", "UnityPay Fintech", "BANK", "Payments & Wallets", "Gurugram", "India", 2020, 1.8),
    ("PWP", "Pinnacle Wealth Partners", "BANK", "Wealth & Asset Management", "Singapore", "Singapore", 2019, 1.0),
    ("HLB", "Harbourline Bank plc", "BANK", "Retail & SME Banking", "Manchester", "United Kingdom", 2021, 1.5),
    ("SMI", "Sterling Mutual Insurance", "INS", "Life & Pensions", "London", "United Kingdom", 2017, 1.5),
    ("TLI", "Trident Life Insurance", "INS", "Life Insurance", "Mumbai", "India", 2018, 1.5),
    ("ECG", "Evergreen Casualty & General", "INS", "Property & Casualty", "Hartford", "United States", 2020, 1.2),
    ("ARG", "Arogya Hospitals Group", "HEALTH", "Hospital Network (32 hospitals)", "Chennai", "India", 2018, 1.6),
    ("MAX", "MedAxis Health Plans", "HEALTH", "US Health Insurance Payer", "Dallas", "United States", 2019, 1.4),
    ("LSD", "Lifespring Diagnostics", "HEALTH", "Diagnostics & Pathology Labs", "Hyderabad", "India", 2021, 0.9),
    ("CNP", "CuraNova Pharmaceuticals", "LIFESCI", "Generic & Specialty Pharma", "Ahmedabad", "India", 2019, 1.2),
    ("HCR", "Helix Clinical Research", "LIFESCI", "Contract Research Organization (CRO)", "Boston", "United States", 2020, 1.0),
    ("UKT", "UrbanKart", "RETAIL", "Online Marketplace", "Bengaluru", "India", 2018, 2.0),
    ("FBK", "FreshBasket", "RETAIL", "Online Grocery & Quick Commerce", "Hyderabad", "India", 2021, 1.4),
    ("SWA", "Stylewise Apparel", "RETAIL", "Fashion Retail (Omnichannel, 240 stores)", "Mumbai", "India", 2019, 1.2),
    ("HNF", "HomeNest Furnishings", "RETAIL", "Home Furnishing Retail", "Atlanta", "United States", 2020, 1.0),
    ("SDF", "Sundara Foods", "CPG", "Packaged Foods & Beverages", "Chennai", "India", 2019, 1.2),
    ("SKT", "Skyline Telecom", "TELECOM", "Mobile Network Operator", "Dubai", "United Arab Emirates", 2018, 1.6),
    ("AWB", "AirWave Broadband", "TELECOM", "Fibre Broadband ISP", "Pune", "India", 2020, 1.0),
    ("SBX", "StreamBox Media", "MEDIA", "OTT Video Streaming", "Mumbai", "India", 2020, 1.2),
    ("TAC", "Tarang Auto Components", "MFG", "Automotive Components", "Pune", "India", 2019, 1.2),
    ("VSA", "Vajra Steel & Alloys", "MFG", "Steel Manufacturing", "Jamshedpur", "India", 2021, 0.9),
    ("OPE", "Orion Precision Engineering GmbH", "MFG", "Industrial Machinery", "Stuttgart", "Germany", 2020, 1.0),
    ("SHL", "SwiftHaul Logistics", "LOGI", "Road Freight & 3PL", "Gurugram", "India", 2019, 1.2),
    ("BOF", "BlueOcean Freight B.V.", "LOGI", "Ocean & Air Freight Forwarding", "Rotterdam", "Netherlands", 2021, 0.9),
    ("GGP", "GreenGrid Power Distribution", "ENERGY", "Electricity Distribution (DISCOM)", "Hyderabad", "India", 2020, 1.0),
    ("SLR", "Solaris Renewables", "ENERGY", "Solar & Wind Generation", "Austin", "United States", 2021, 0.9),
]
