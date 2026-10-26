"""Project archetypes: realistic IT-services engagements, their team shape and per-role requirements.

Role spec: R(title, family, headcount, min_experience_years, allocation_pct, mandatory skills, preferred skills,
             preferred certs, mandatory certs, ramp_months)
Skills are ';'-separated; "Skill:4" sets an explicit minimum proficiency (1-5).
"""


def _split(s):
    return [x.strip() for x in s.split(";") if x.strip()]


def R(title, family, n, exp, alloc, must, nice="", certs="", mcerts="", ramp=0):
    return dict(title=title, family=family, n=n if isinstance(n, tuple) else (n, n), exp=exp, alloc=alloc,
                must=_split(must), nice=_split(nice), certs=_split(certs), mcerts=_split(mcerts), ramp=ramp)


def PM(domain="", alloc=50, exp=9):
    return R("Project Manager", "pm", 1, exp, alloc,
             "Agile / Scrum;Stakeholder Management;Risk Management;Project Planning & Estimation",
             "Jira;Budget & Financial Management;" + domain, certs="PMP;CSM")


def SM(alloc=50):
    return R("Scrum Master", "pm", 1, 5, alloc, "Agile / Scrum;Jira;Kanban", "Confluence;SAFe", certs="CSM;PSM1")


def A(key, names, industries, ptype, engagement, months, since, desc, domain, roles, vars=None):
    return dict(key=key, names=names, industries=industries, ptype=ptype, engagement=engagement, months=months,
                since=since, desc=desc, domain_skills=_split(domain), roles=roles, vars=vars or {})


ANY = ["BANK", "INS", "HEALTH", "LIFESCI", "RETAIL", "CPG", "TELECOM", "MEDIA", "MFG", "LOGI", "ENERGY"]

ARCHETYPES = [
    # ======================= BANKING & FINANCIAL SERVICES =======================
    A("upi_switch", ["UPI Payment Switch & Reconciliation Platform", "Real-time Payments Hub (UPI/IMPS/NEFT)"],
      ["BANK"], "New Development", ["Fixed Price", "Time & Material"], (10, 20), 2019,
      ["{client} is replacing its vendor-hosted payment switch with an in-house, cloud-native real-time payments hub. "
       "The platform processes UPI, IMPS and NEFT transactions (peak ~{tps} TPS during festive sales), integrates with "
       "NPCI and the core banking system, and performs automated T+0 reconciliation with exception queues for the "
       "operations team. Scope includes dispute and chargeback handling, fraud-rule hooks and an operations dashboard.",
       "Build an event-driven payments hub for {client} that routes UPI and IMPS traffic, settles against the CBS "
       "ledger and reconciles NPCI settlement files automatically. Target: 99.95% availability, sub-300 ms switch "
       "latency at {tps} TPS, and a 70% reduction in manual reconciliation effort."],
      "Payments (UPI/IMPS/NEFT);ISO 20022;PCI DSS",
      [R("Solution Architect", "java", 1, 10, 50, "Java;Microservices Architecture;Apache Kafka;Kubernetes",
         "Payments (UPI/IMPS/NEFT);Amazon Web Services (AWS);Redis", certs="AWS-SAP;AWS-SAA"),
       R("Technical Lead", "java", 1, 7, 100, "Java;Spring Boot;Microservices Architecture;Apache Kafka",
         "Payments (UPI/IMPS/NEFT);Redis;PostgreSQL"),
       R("Senior Java Developer", "java", (2, 4), 4, 100, "Java;Spring Boot;Apache Kafka;PostgreSQL",
         "Redis;Spring Cloud;JUnit & Mockito;Payments (UPI/IMPS/NEFT)"),
       R("Java Developer", "java", (2, 3), 1.5, 100, "Java;Spring Boot;REST API Design", "JUnit & Mockito;PostgreSQL;Apache Kafka"),
       R("QA Automation Engineer", "qa", (1, 2), 2, 100, "API Testing;REST Assured;Java", "Apache JMeter;Postman", certs="ISTQB-CTFL", ramp=1),
       R("DevOps Engineer", "devops", 1, 3, 100, "Kubernetes;Docker;Jenkins;Terraform", "Helm;Prometheus & Grafana", certs="CKA;AWS-SAA"),
       R("Business Analyst", "ba", 1, 3, 100, "Requirements Elicitation;User Stories & Acceptance Criteria;Payments (UPI/IMPS/NEFT):2",
         "Business Process Modeling (BPMN);SQL"),
       PM("Payments (UPI/IMPS/NEFT)")],
      vars={"tps": ["1,200", "2,500", "4,000", "6,000"]}),

    A("los", ["Digital Loan Origination System", "Retail & MSME Lending Platform"],
      ["BANK"], "New Development", ["Fixed Price", "Time & Material"], (9, 18), 2019,
      ["End-to-end digital lending journey for {client}'s personal, home and MSME loans: online application, "
       "bureau pull (CIBIL/Experian), automated underwriting rules, document collection, sanction and e-sign, and "
       "disbursal to the core banking system. Target: cut turnaround time from 7 days to under 48 hours.",
       "Replace {client}'s branch-driven loan processing with a workflow-based Loan Origination System built on "
       "Spring Boot microservices and a Camunda BPMN engine, with a React portal for applicants and credit officers."],
      "Lending & Loan Origination;Core Banking",
      [R("Technical Lead", "java", 1, 7, 100, "Java;Spring Boot;Microservices Architecture;Camunda BPM",
         "Lending & Loan Origination;PostgreSQL"),
       R("Senior Java Developer", "java", (2, 3), 4, 100, "Java;Spring Boot;Hibernate/JPA;REST API Design", "Camunda BPM;Apache Kafka"),
       R("Java Developer", "java", (1, 3), 1.5, 100, "Java;Spring Boot;SQL", "JUnit & Mockito"),
       R("Frontend Developer", "frontend", (1, 2), 2, 100, "React;TypeScript;HTML5 & CSS3", "Redux;Jest"),
       R("QA Engineer", "qa", (1, 2), 2, 100, "Manual Testing;API Testing;SQL", "Selenium WebDriver;Postman", certs="ISTQB-CTFL", ramp=1),
       R("Business Analyst", "ba", 1, 4, 100, "Requirements Elicitation;Lending & Loan Origination:2;Business Process Modeling (BPMN)",
         "User Acceptance Testing (UAT)"),
       R("DevOps Engineer", "devops", 1, 3, 50, "Docker;Kubernetes;Jenkins", "OpenShift;Terraform"),
       PM("Lending & Loan Origination")]),

    A("cbs_modernization", ["Core Banking Modernization (Strangler Migration)", "Core Banking Microservices Re-platforming"],
      ["BANK"], "Modernization", ["Time & Material", "Dedicated Team (ODC)"], (14, 30), 2019,
      ["Multi-year programme to carve out {client}'s deposits, customer and accounts modules from the legacy core "
       "banking system into domain microservices using the strangler-fig pattern. Includes CDC-based data sync via "
       "Kafka, Oracle-to-PostgreSQL migration of 1.8 TB of account data, and an OpenShift-based runtime.",
       "Modernize {client}'s monolithic core banking platform: decompose into bounded-context services, migrate "
       "batch EOD jobs to event-driven processing, and run legacy and new stacks in parallel with reconciliation."],
      "Core Banking;ISO 20022",
      [R("Solution Architect", "java", 1, 11, 100, "Java;Microservices Architecture;Apache Kafka;Oracle Database",
         "Core Banking;OpenShift;Kubernetes", certs="AWS-SAP;AZ-305"),
       R("Technical Lead", "java", (1, 2), 7, 100, "Java;Spring Boot;Microservices Architecture;Oracle Database", "Core Banking;Apache Kafka"),
       R("Senior Java Developer", "java", (3, 5), 4, 100, "Java;Spring Boot;Apache Kafka;Hibernate/JPA", "PL/SQL;PostgreSQL;Core Banking"),
       R("Java Developer", "java", (2, 4), 1.5, 100, "Java;Spring Boot;SQL", "JUnit & Mockito;Oracle Database"),
       R("Data Migration Engineer", "data_eng", (1, 2), 4, 100, "Oracle Database;PL/SQL;ETL/ELT Development;SQL",
         "Informatica PowerCenter;PostgreSQL;Data Modeling"),
       R("DevOps Engineer", "devops", 1, 4, 100, "Kubernetes;Docker;Jenkins", "OpenShift;Ansible;Helm", certs="CKA"),
       R("QA Lead", "qa", 1, 7, 100, "Test Automation Framework Design;Selenium WebDriver;API Testing", "Core Banking;ETL / Data Testing"),
       R("QA Engineer", "qa", (2, 3), 2, 100, "Manual Testing;API Testing;SQL", "ETL / Data Testing;REST Assured"),
       R("Business Analyst", "ba", 1, 5, 100, "Requirements Elicitation;Core Banking:3;Gap Analysis", "Business Process Modeling (BPMN)"),
       PM("Core Banking", alloc=100, exp=11)]),

    A("fraud_ml", ["Real-time Card & UPI Fraud Detection Engine", "Transaction Fraud Scoring Platform (ML)"],
      ["BANK"], "AI/ML", ["Time & Material", "Fixed Price"], (8, 14), 2019,
      ["Design and deploy a real-time fraud scoring engine for {client} that scores card and UPI transactions in "
       "under 150 ms using gradient-boosted models on streaming features (velocity, device, geo, merchant risk). "
       "Includes feature store on Spark/Kafka, champion-challenger model monitoring and an analyst review console.",
       "Reduce {client}'s card fraud losses by building ML-based anomaly and fraud classification models trained on "
       "{volume} historical transactions, served behind a FastAPI scoring service integrated with the payment switch."],
      "Payments (UPI/IMPS/NEFT);PCI DSS",
      [R("Lead Data Scientist", "data_sci", 1, 7, 100, "Machine Learning;Python;XGBoost / LightGBM;Statistics & Probability",
         "MLOps;Payments (UPI/IMPS/NEFT)"),
       R("Data Scientist", "data_sci", (1, 2), 2, 100, "Machine Learning;Python;scikit-learn;pandas & NumPy;SQL", "XGBoost / LightGBM;MLflow"),
       R("Data Engineer", "data_eng", (1, 2), 3, 100, "Apache Spark (PySpark);Apache Kafka;Python;SQL", "Databricks;Delta Lake"),
       R("ML Engineer (MLOps)", "data_sci", 1, 4, 100, "MLOps;Docker;Python", "MLflow;Kubernetes;FastAPI;Amazon SageMaker"),
       R("Python Backend Developer", "python", 1, 3, 100, "Python;FastAPI;REST API Design", "Redis;Docker"),
       R("Business Analyst", "ba", 1, 4, 50, "Requirements Elicitation;Payments (UPI/IMPS/NEFT):2", "SQL;Power BI"),
       PM("Payments (UPI/IMPS/NEFT)")],
      vars={"volume": ["240 million", "480 million", "1.1 billion"]}),

    A("reg_reporting", ["Regulatory Reporting Data Mart (RBI / Basel III)", "Automated RBI Returns & Basel III Reporting"],
      ["BANK"], "Data & Analytics", ["Fixed Price"], (8, 14), 2019,
      ["Build a regulatory data mart for {client} that sources data from core banking, treasury and loan systems "
       "and automates RBI returns (XBRL), Basel III capital adequacy and LCR/NSFR liquidity reports, with full "
       "lineage, reconciliation controls and a Power BI dashboard for the compliance team.",
       "Automate {client}'s monthly and quarterly regulatory submissions, replacing spreadsheet-based processes "
       "with governed ETL pipelines, a dimensional data model and auditable report generation."],
      "Regulatory Reporting (RBI / Basel)",
      [R("Lead Data Engineer", "data_eng", 1, 7, 100, "Data Modeling;ETL/ELT Development;SQL;Oracle Database",
         "Regulatory Reporting (RBI / Basel);Informatica PowerCenter"),
       R("ETL Developer", "data_eng", (2, 3), 2, 100, "Informatica PowerCenter;SQL;PL/SQL", "Oracle Database;Shell Scripting"),
       R("BI Developer", "data_eng", 1, 3, 100, "Power BI;SQL;Data Modeling", "Microsoft SQL Server", certs="PL-300"),
       R("ETL Test Engineer", "qa", 1, 2, 100, "ETL / Data Testing;SQL;Manual Testing", "Regulatory Reporting (RBI / Basel)"),
       R("Business Analyst", "ba", 1, 5, 100, "Requirements Elicitation;Regulatory Reporting (RBI / Basel):3;SQL", "Gap Analysis"),
       PM("Regulatory Reporting (RBI / Basel)")]),

    A("mobile_banking", ["Mobile Banking App Revamp (Android & iOS)", "Retail Mobile Banking Super-App"],
      ["BANK"], "New Development", ["Fixed Price", "Time & Material"], (9, 16), 2019,
      ["Rebuild {client}'s retail mobile banking app (4.2M users) natively on Android (Kotlin/Jetpack Compose) and "
       "iOS (SwiftUI): UPI payments, account opening, card controls, FD/RD, bill payments and personalised offers, "
       "backed by a Spring Boot BFF layer. Includes OWASP MASVS security testing and accessibility compliance.",
       "Design and deliver a new-generation mobile banking experience for {client}, consolidating three legacy apps "
       "into one super-app with biometric login, UPI, wealth and loans journeys."],
      "Payments (UPI/IMPS/NEFT)",
      [R("Mobile Tech Lead", "mobile", 1, 7, 100, "Android Development;Kotlin;REST API Design", "Jetpack Compose;Firebase"),
       R("Android Developer", "mobile", (2, 3), 2, 100, "Android Development;Kotlin", "Jetpack Compose;Firebase"),
       R("iOS Developer", "mobile", (2, 3), 2, 100, "iOS Development;Swift", "SwiftUI;Firebase"),
       R("Backend Developer (BFF)", "java", (1, 2), 3, 100, "Java;Spring Boot;REST API Design", "Redis;Microservices Architecture"),
       R("UX Designer", "ux", 1, 3, 100, "Figma;UI Design;Wireframing & Prototyping", "Accessibility (WCAG);Design Systems"),
       R("Mobile QA Engineer", "qa", (1, 2), 2, 100, "Mobile App Testing;Appium", "API Testing;Manual Testing", ramp=1),
       R("Security Analyst (Mobile VAPT)", "security", 1, 3, 50, "Penetration Testing;OWASP Top 10;Application Security",
         "Burp Suite", certs="CEH", ramp=3),
       PM("Payments (UPI/IMPS/NEFT)")]),

    A("aml", ["AML Transaction Monitoring & Case Management", "Anti-Money Laundering Analytics Platform"],
      ["BANK"], "Data & Analytics", ["Time & Material"], (9, 16), 2019,
      ["Implement an AML transaction-monitoring platform for {client}: scenario-based rules plus ML risk scoring on "
       "Spark, customer risk rating, alert triage and a case-management workflow for the FIU team with STR "
       "filing support. Aim: cut false-positive alerts by 35%.",
       "Modernize {client}'s AML monitoring with a lakehouse-based pipeline and machine-learning alert prioritisation."],
      "AML & KYC",
      [R("Lead Data Engineer", "data_eng", 1, 7, 100, "Apache Spark (PySpark);SQL;Data Modeling", "Databricks;Apache Kafka"),
       R("Data Engineer", "data_eng", (2, 3), 2, 100, "Apache Spark (PySpark);Python;SQL", "Delta Lake;Apache Airflow"),
       R("Data Scientist", "data_sci", 1, 3, 100, "Machine Learning;Python;scikit-learn", "AML & KYC;XGBoost / LightGBM"),
       R("Java Developer", "java", (1, 2), 2, 100, "Java;Spring Boot;REST API Design", "Camunda BPM"),
       R("QA Engineer", "qa", 1, 2, 100, "Manual Testing;ETL / Data Testing;SQL", "API Testing"),
       R("Business Analyst", "ba", 1, 5, 100, "Requirements Elicitation;AML & KYC:3", "Business Process Modeling (BPMN)"),
       PM("AML & KYC")]),

    A("wealth_portal", ["Wealth Management Advisor & Investor Portal", "Digital Wealth & Mutual Fund Platform"],
      ["BANK"], "New Development", ["Fixed Price", "Time & Material"], (8, 14), 2019,
      ["Build a self-service investor portal and relationship-manager workbench for {client}: portfolio "
       "aggregation, goal-based planning, mutual fund and SIP transactions, risk profiling and regulatory "
       "suitability checks, with real-time NAV and market data feeds.",
       "Digitise {client}'s advisory business with an Angular/React portal, Java microservices and a portfolio "
       "analytics engine."],
      "Capital Markets & Wealth",
      [R("Technical Lead", "java", 1, 7, 100, "Java;Spring Boot;Microservices Architecture", "Capital Markets & Wealth;Redis"),
       R("Java Developer", "java", (2, 3), 2, 100, "Java;Spring Boot;REST API Design", "PostgreSQL"),
       R("Frontend Developer", "frontend", (2, 3), 2, 100, "TypeScript;Angular;HTML5 & CSS3", "React;Jest"),
       R("UX Designer", "ux", 1, 3, 50, "Figma;UI Design;UX Research", "Design Systems"),
       R("QA Automation Engineer", "qa", 1, 2, 100, "Selenium WebDriver;Java;TestNG", "API Testing"),
       R("Business Analyst", "ba", 1, 4, 100, "Requirements Elicitation;Capital Markets & Wealth:2", "User Acceptance Testing (UAT)"),
       PM("Capital Markets & Wealth")]),

    A("kyc_onboarding", ["Digital KYC & Customer Onboarding (OCR + Video KYC)", "Paperless Customer Onboarding Platform"],
      ["BANK", "INS"], "New Development", ["Fixed Price"], (6, 12), 2020,
      ["Paperless onboarding for {client}: OCR-based extraction of Aadhaar/PAN and address proofs, face match and "
       "liveness checks, V-CIP compliant video KYC, CKYC registry integration and a maker-checker back-office.",
       "Reduce {client}'s onboarding time from 3 days to 15 minutes using document AI, video KYC and automated "
       "AML screening."],
      "AML & KYC",
      [R("Python Backend Lead", "python", 1, 6, 100, "Python;FastAPI;REST API Design;PostgreSQL", "Docker;AML & KYC"),
       R("Python Developer", "python", (1, 2), 2, 100, "Python;FastAPI;SQL", "Redis"),
       R("Computer Vision Engineer", "data_sci", 1, 3, 100, "Computer Vision;Python;Deep Learning", "PyTorch;TensorFlow"),
       R("Frontend Developer", "frontend", 1, 2, 100, "React;TypeScript;HTML5 & CSS3", "WebRTC"),
       R("QA Engineer", "qa", 1, 2, 100, "Manual Testing;API Testing;Postman", "Mobile App Testing"),
       R("Business Analyst", "ba", 1, 3, 50, "Requirements Elicitation;AML & KYC:2", "User Stories & Acceptance Criteria"),
       PM("AML & KYC")]),

    A("sf_fsc", ["Salesforce Financial Services Cloud Rollout", "Relationship Manager CRM on Salesforce"],
      ["BANK", "INS"], "Implementation (Package)", ["Fixed Price"], (6, 12), 2019,
      ["Implement Salesforce Financial Services Cloud for {client}'s relationship managers and service teams: "
       "household and client 360 views, lead and opportunity management, service requests, and MuleSoft "
       "integrations with core banking and the data warehouse.",
       "Roll out a unified CRM on Salesforce for {client} replacing three legacy CRMs, with data migration of "
       "2.3M customer records."],
      "",
      [R("Salesforce Technical Lead", "salesforce", 1, 6, 100, "Apex;Lightning Web Components (LWC);Salesforce Administration",
         "MuleSoft", mcerts="SF-PD1"),
       R("Salesforce Developer", "salesforce", (2, 3), 2, 100, "Apex;Lightning Web Components (LWC)", "Salesforce Service Cloud", certs="SF-PD1"),
       R("Salesforce Administrator", "salesforce", 1, 2, 100, "Salesforce Administration", "Salesforce Sales Cloud", mcerts="SF-ADMIN"),
       R("Integration Developer (MuleSoft)", "salesforce", 1, 3, 100, "MuleSoft;REST API Design", "Java"),
       R("QA Engineer", "qa", 1, 2, 100, "Manual Testing;API Testing", "User Acceptance Testing (UAT)"),
       R("Business Analyst", "ba", 1, 4, 100, "Requirements Elicitation;Gap Analysis", "Salesforce Sales Cloud"),
       PM()]),

    # ======================= INSURANCE =======================
    A("claims_automation", ["Claims Processing Automation (FNOL to Settlement)", "Intelligent Motor Claims Platform"],
      ["INS"], "New Development", ["Fixed Price", "Time & Material"], (9, 15), 2019,
      ["Automate {client}'s claims lifecycle from first notice of loss to settlement: digital FNOL, AI-based damage "
       "assessment from vehicle photos, rules-based straight-through processing for low-value claims, surveyor "
       "workflow and payment integration. Target: 40% of motor claims settled within 24 hours.",
       "Build a claims workbench for {client} with document AI, fraud flags and SLA tracking for adjusters."],
      "Insurance (P&C / Life)",
      [R("Technical Lead", "java", 1, 7, 100, "Java;Spring Boot;Microservices Architecture", "Insurance (P&C / Life);Camunda BPM"),
       R("Java Developer", "java", (2, 4), 2, 100, "Java;Spring Boot;REST API Design", "PostgreSQL;Apache Kafka"),
       R("Computer Vision Engineer", "data_sci", 1, 3, 100, "Computer Vision;Python;Deep Learning", "PyTorch"),
       R("Frontend Developer", "frontend", 1, 2, 100, "Angular;TypeScript", "HTML5 & CSS3"),
       R("QA Engineer", "qa", (1, 2), 2, 100, "Manual Testing;API Testing", "Selenium WebDriver"),
       R("Business Analyst", "ba", 1, 4, 100, "Requirements Elicitation;Insurance (P&C / Life):3", "Business Process Modeling (BPMN)"),
       PM("Insurance (P&C / Life)")]),

    A("policy_admin", ["Policy Administration System Modernization", "Life & Pensions Policy Platform on Azure"],
      ["INS"], "Modernization", ["Time & Material", "Dedicated Team (ODC)"], (12, 24), 2019,
      ["Re-platform {client}'s legacy policy administration system to .NET 8 microservices on Azure: product "
       "configuration, new business, endorsements, renewals and billing, with phased migration of in-force policies.",
       "Modernize {client}'s life & pensions policy servicing platform with an Angular agent portal, ASP.NET Core "
       "APIs and Azure SQL, decommissioning a 20-year-old mainframe-fed system."],
      "Insurance (P&C / Life)",
      [R("Solution Architect", "dotnet", 1, 10, 50, "C#;ASP.NET Core;Microservices Architecture;Microsoft Azure", "Insurance (P&C / Life)", certs="AZ-305"),
       R("Technical Lead", "dotnet", 1, 7, 100, "C#;ASP.NET Core;Entity Framework Core;Microsoft SQL Server", "Microsoft Azure;Azure DevOps"),
       R(".NET Developer", "dotnet", (3, 4), 2, 100, "C#;ASP.NET Core;Microsoft SQL Server", "Entity Framework Core;Microsoft Azure", certs="AZ-204"),
       R("Angular Developer", "frontend", (1, 2), 2, 100, "Angular;TypeScript;HTML5 & CSS3", "Jest"),
       R("Azure DevOps Engineer", "devops", 1, 3, 100, "Microsoft Azure;Azure DevOps;Terraform", "Kubernetes", certs="AZ-104;AZ-400"),
       R("QA Engineer", "qa", (2, 3), 2, 100, "Manual Testing;Selenium WebDriver;SQL", "API Testing", ramp=2),
       R("Business Analyst", "ba", 1, 5, 100, "Requirements Elicitation;Insurance (P&C / Life):3", "Gap Analysis"),
       PM("Insurance (P&C / Life)", alloc=100)]),

    # ======================= HEALTHCARE & LIFE SCIENCES =======================
    A("his", ["Hospital Information System (HIS) Modernization", "Integrated Hospital Management Platform"],
      ["HEALTH"], "Modernization", ["Fixed Price", "Time & Material"], (12, 24), 2019,
      ["Modernize {client}'s hospital information system across its network: patient registration, OPD/IPD, "
       "pharmacy, lab orders (LIS), billing and insurance pre-authorisation, with HL7/FHIR interfaces to lab and "
       "radiology systems and an ABDM-compliant health-record exchange.",
       "Replace {client}'s fragmented hospital applications with a unified, cloud-hosted HIS built on ASP.NET Core "
       "and Angular, rolled out hospital-by-hospital."],
      "HL7 / FHIR",
      [R("Technical Lead", "dotnet", 1, 7, 100, "C#;ASP.NET Core;Microservices Architecture;Microsoft SQL Server", "HL7 / FHIR"),
       R(".NET Developer", "dotnet", (3, 4), 2, 100, "C#;ASP.NET Core;Entity Framework Core", "Microsoft SQL Server"),
       R("Angular Developer", "frontend", (2, 3), 2, 100, "Angular;TypeScript;HTML5 & CSS3", "Accessibility (WCAG)"),
       R("Integration Engineer (HL7/FHIR)", "java", 1, 4, 100, "HL7 / FHIR:3;REST API Design;Java", "Spring Boot"),
       R("UX Designer", "ux", 1, 3, 50, "Figma;UI Design;UX Research", "Accessibility (WCAG)"),
       R("QA Engineer", "qa", (2, 3), 2, 100, "Manual Testing;API Testing;SQL", "Selenium WebDriver"),
       R("Business Analyst", "ba", 1, 4, 100, "Requirements Elicitation;HL7 / FHIR:2", "Business Process Modeling (BPMN)"),
       PM("HL7 / FHIR", alloc=100)]),

    A("fhir_gateway", ["FHIR Interoperability Gateway", "Clinical Data Exchange (HL7 FHIR R4) Platform"],
      ["HEALTH", "LIFESCI"], "New Development", ["Fixed Price"], (6, 12), 2020,
      ["Build an HL7 FHIR R4 interoperability gateway for {client} exposing patient, encounter, observation and "
       "medication resources to partner apps, with HL7 v2 to FHIR transformation, SMART-on-FHIR OAuth2 security "
       "and audit logging for HIPAA compliance.",
       "Enable {client} to exchange clinical data with payers and providers via standards-based FHIR APIs."],
      "HL7 / FHIR;Healthcare Claims (US Payer)",
      [R("Technical Lead", "java", 1, 7, 100, "Java;Spring Boot;HL7 / FHIR:3;REST API Design", "Amazon Web Services (AWS)"),
       R("Java Developer", "java", (2, 3), 2, 100, "Java;Spring Boot;REST API Design", "HL7 / FHIR"),
       R("IAM Engineer", "security", 1, 4, 50, "Identity & Access Management (IAM);Application Security", "OWASP Top 10"),
       R("API QA Engineer", "qa", 1, 2, 100, "API Testing;Postman;REST Assured", "HL7 / FHIR"),
       R("DevOps Engineer", "devops", 1, 3, 50, "Amazon Web Services (AWS);Docker;Terraform", "Kubernetes", certs="AWS-SAA"),
       PM("HL7 / FHIR")]),

    A("telemedicine", ["Telemedicine & Patient Engagement App", "Virtual Care Mobile Platform"],
      ["HEALTH"], "New Development", ["Fixed Price"], (6, 12), 2020,
      ["Build {client}'s patient app and doctor console for video consultations, appointment booking, e-prescriptions, "
       "lab report access and payments, using Flutter for mobile, a Node.js backend and WebRTC for HD video.",
       "Launch a virtual-care platform for {client} supporting 5,000 daily tele-consults across 32 hospitals."],
      "HL7 / FHIR",
      [R("Mobile Tech Lead", "mobile", 1, 6, 100, "Flutter;Dart;REST API Design", "Firebase;WebRTC"),
       R("Flutter Developer", "mobile", (2, 3), 2, 100, "Flutter;Dart", "Firebase"),
       R("Node.js Developer", "fullstack", (1, 2), 2, 100, "Node.js;JavaScript;REST API Design", "MongoDB;WebRTC;Express.js"),
       R("UX Designer", "ux", 1, 2, 100, "Figma;UI Design;Wireframing & Prototyping", "UX Research"),
       R("Mobile QA Engineer", "qa", 1, 2, 100, "Mobile App Testing;Manual Testing", "Appium"),
       R("DevOps Engineer", "devops", 1, 3, 50, "Amazon Web Services (AWS);Docker", "Kubernetes;Terraform"),
       PM("HL7 / FHIR")]),

    A("clinical_data", ["Clinical Trial Data Platform (GxP-validated)", "Clinical Data Lakehouse & SDTM Automation"],
      ["LIFESCI"], "Data & Analytics", ["Time & Material"], (10, 18), 2019,
      ["Build a GxP-validated clinical data platform for {client} that ingests EDC, lab and CTMS data, standardises it "
       "to CDISC SDTM, and serves study dashboards to clinical operations. Delivered under 21 CFR Part 11 with full "
       "computer system validation (IQ/OQ/PQ) documentation.",
       "Consolidate {client}'s trial data from 40+ studies into a lakehouse with automated SDTM mapping and audit trails."],
      "Clinical Trials;GxP & 21 CFR Part 11",
      [R("Lead Data Engineer", "data_eng", 1, 7, 100, "Databricks;Apache Spark (PySpark);Data Modeling;SQL", "Clinical Trials;Delta Lake", certs="DBX-DEA"),
       R("Data Engineer", "data_eng", (2, 3), 2, 100, "Apache Spark (PySpark);Python;SQL", "Databricks;Snowflake"),
       R("Validation / CSV QA Engineer", "qa", 1, 3, 100, "Manual Testing;ETL / Data Testing;GxP & 21 CFR Part 11:2", "SQL"),
       R("BI Developer", "data_eng", 1, 2, 100, "Power BI;SQL", "Tableau"),
       R("Business Analyst", "ba", 1, 4, 100, "Requirements Elicitation;Clinical Trials:2", "GxP & 21 CFR Part 11"),
       PM("GxP & 21 CFR Part 11")]),

    A("pv_nlp", ["Pharmacovigilance Case Intake Automation (NLP)", "Adverse Event Intake with GenAI"],
      ["LIFESCI"], "AI/ML", ["Time & Material", "Fixed Price"], (6, 12), 2021,
      ["Automate {client}'s adverse-event case intake: extract patient, drug, reaction and reporter details from "
       "emails, call notes and literature using NLP, auto-code to MedDRA, and pre-populate the safety database, with "
       "human review and GxP validation. Target: 60% reduction in case-processing effort.",
       "Apply NLP and LLM-based extraction to {client}'s pharmacovigilance inbox of 3,000+ reports per month."],
      "GxP & 21 CFR Part 11",
      [R("Lead Data Scientist (NLP)", "data_sci", 1, 6, 100, "Natural Language Processing (NLP);Python;Machine Learning",
         "Generative AI / LLMs;PyTorch"),
       R("Data Scientist", "data_sci", (1, 2), 2, 100, "Natural Language Processing (NLP);Python", "Generative AI / LLMs;Prompt Engineering"),
       R("Python Developer", "python", 1, 2, 100, "Python;FastAPI;REST API Design", "Docker"),
       R("Validation QA Engineer", "qa", 1, 3, 100, "Manual Testing;GxP & 21 CFR Part 11:2", "API Testing"),
       PM("GxP & 21 CFR Part 11")]),

    A("imaging_ai", ["Medical Imaging AI – Chest X-ray Triage", "Radiology AI Triage Platform"],
      ["HEALTH"], "AI/ML", ["Time & Material"], (8, 14), 2020,
      ["Develop and deploy deep-learning models that flag critical findings (pneumothorax, effusion, nodules) on "
       "chest X-rays at {client}, integrated with PACS via DICOM, prioritising radiologist worklists. Includes model "
       "validation on 120,000 labelled studies and drift monitoring in production.",
       "Build a computer-vision triage assistant for {client}'s radiology department with explainable heatmaps."],
      "HL7 / FHIR",
      [R("Lead Data Scientist (CV)", "data_sci", 1, 6, 100, "Computer Vision;Deep Learning;PyTorch;Python", "MLOps"),
       R("Data Scientist (CV)", "data_sci", (1, 2), 2, 100, "Computer Vision;Deep Learning;Python", "PyTorch;TensorFlow"),
       R("ML Engineer (MLOps)", "data_sci", 1, 3, 100, "MLOps;Docker;Python", "Kubernetes;MLflow"),
       R("Python Developer", "python", 1, 2, 100, "Python;FastAPI", "PostgreSQL"),
       R("QA Engineer", "qa", 1, 2, 50, "Manual Testing;API Testing", ""),
       PM("HL7 / FHIR")]),

    A("payer_analytics", ["Healthcare Claims & Payer Analytics on Snowflake", "Member & Claims Analytics Platform"],
      ["HEALTH"], "Data & Analytics", ["Time & Material", "Dedicated Team (ODC)"], (9, 18), 2019,
      ["Migrate {client}'s claims and member data warehouse from on-prem SQL Server to Snowflake with dbt-based "
       "transformations, and deliver analytics on medical cost trends, utilisation, HEDIS quality measures and "
       "provider performance in Tableau.",
       "Build a governed claims analytics layer for {client} processing 85M claim lines per year (EDI 837/835)."],
      "Healthcare Claims (US Payer)",
      [R("Lead Data Engineer", "data_eng", 1, 7, 100, "Snowflake;dbt;SQL;Data Modeling", "Healthcare Claims (US Payer)", certs="SNOW-CORE"),
       R("Data Engineer", "data_eng", (2, 3), 2, 100, "Snowflake;SQL;Python", "dbt;Apache Airflow", certs="SNOW-CORE"),
       R("BI Developer", "data_eng", 1, 3, 100, "Tableau;SQL", "Power BI", certs="TABLEAU-CDA"),
       R("ETL Test Engineer", "qa", 1, 2, 100, "ETL / Data Testing;SQL", "Manual Testing"),
       R("Business Analyst", "ba", 1, 4, 100, "Requirements Elicitation;Healthcare Claims (US Payer):2;SQL", ""),
       PM("Healthcare Claims (US Payer)")]),

    # ======================= RETAIL & CPG =======================
    A("headless_commerce", ["Headless E-commerce Storefront Rebuild", "Omnichannel Commerce Platform (Headless)"],
      ["RETAIL"], "New Development", ["Fixed Price", "Time & Material"], (8, 16), 2019,
      ["Re-architect {client}'s storefront as a headless commerce platform: Next.js PWA frontend, Node.js/NestJS "
       "commerce microservices (catalog, cart, checkout, promotions), Elasticsearch-based search and payment gateway "
       "integration. Must handle {users} concurrent users during sale events with sub-2s page loads.",
       "Rebuild {client}'s web and app commerce experience on a composable, API-first stack hosted on AWS."],
      "E-commerce",
      [R("Technical Lead", "fullstack", 1, 7, 100, "Node.js;TypeScript;Microservices Architecture;React", "E-commerce;Next.js"),
       R("Frontend Developer (Next.js)", "frontend", (2, 3), 2, 100, "React;Next.js;TypeScript", "Tailwind CSS;Jest"),
       R("Node.js Developer", "fullstack", (2, 3), 2, 100, "Node.js;TypeScript;REST API Design", "NestJS;MongoDB;Redis"),
       R("Search Engineer", "java", 1, 4, 100, "Elasticsearch;Java", "E-commerce"),
       R("UX Designer", "ux", 1, 3, 100, "Figma;UI Design;UX Research", "Design Systems;Accessibility (WCAG)"),
       R("QA Automation Engineer", "qa", (1, 2), 2, 100, "Playwright;JavaScript;API Testing", "Cypress"),
       R("DevOps Engineer", "devops", 1, 3, 100, "Amazon Web Services (AWS);Kubernetes;Terraform", "GitHub Actions", certs="AWS-SAA"),
       PM("E-commerce")],
      vars={"users": ["80,000", "150,000", "250,000"]}),

    A("demand_forecast", ["Demand Forecasting & Replenishment (ML)", "SKU-level Demand Sensing Platform"],
      ["RETAIL", "CPG"], "AI/ML", ["Time & Material", "Fixed Price"], (6, 12), 2019,
      ["Build SKU x store x week demand forecasts for {client} across {skus} SKUs using gradient boosting and "
       "hierarchical time-series models, incorporating promotions, festivals and weather, and feed auto-replenishment "
       "orders. Target: improve forecast accuracy (WMAPE) by 8-12 points and reduce stock-outs.",
       "Replace {client}'s spreadsheet-based demand planning with ML forecasting on Databricks and Power BI planner views."],
      "Supply Chain & Logistics",
      [R("Lead Data Scientist", "data_sci", 1, 6, 100, "Time Series Forecasting;Machine Learning;Python", "XGBoost / LightGBM;Databricks"),
       R("Data Scientist", "data_sci", (1, 2), 2, 100, "Time Series Forecasting;Python;pandas & NumPy", "Machine Learning"),
       R("Data Engineer", "data_eng", (1, 2), 2, 100, "Databricks;Apache Spark (PySpark);SQL", "Azure Data Factory;Delta Lake"),
       R("BI Developer", "data_eng", 1, 2, 50, "Power BI;SQL", "", certs="PL-300"),
       R("Business Analyst", "ba", 1, 4, 50, "Requirements Elicitation;Supply Chain & Logistics:2", ""),
       PM("Supply Chain & Logistics")],
      vars={"skus": ["18,000", "42,000", "65,000"]}),

    A("loyalty", ["Customer Loyalty & Rewards Platform", "Unified Loyalty Programme Platform"],
      ["RETAIL", "CPG"], "New Development", ["Fixed Price"], (6, 12), 2019,
      ["Build {client}'s unified loyalty platform: points earn/burn across stores, app and web, tier management, "
       "partner rewards, personalised offers and a fraud-safe redemption engine, handling {members} members.",
       "Launch a real-time loyalty and rewards engine for {client} with POS and e-commerce integration."],
      "E-commerce",
      [R("Technical Lead", "java", 1, 7, 100, "Java;Spring Boot;Microservices Architecture", "Redis;Apache Kafka"),
       R("Java Developer", "java", (2, 3), 2, 100, "Java;Spring Boot;REST API Design", "Redis;PostgreSQL"),
       R("Angular Developer", "frontend", 1, 2, 100, "Angular;TypeScript", "HTML5 & CSS3"),
       R("QA Engineer", "qa", 1, 2, 100, "Manual Testing;API Testing", "Selenium WebDriver"),
       PM("E-commerce")],
      vars={"members": ["6 million", "11 million", "22 million"]}),

    A("oms", ["Order Management System & Warehouse Integration", "Distributed Order Management (DOM)"],
      ["RETAIL", "LOGI", "CPG"], "New Development", ["Time & Material"], (9, 16), 2019,
      ["Build a distributed order management system for {client} that orchestrates orders across warehouses, dark "
       "stores and 3PL partners: inventory reservation, split shipments, returns and real-time status events via Kafka, "
       "integrated with the WMS and carrier APIs.",
       "Implement event-driven order orchestration for {client}, reducing order-to-ship time by 30%."],
      "Supply Chain & Logistics;E-commerce",
      [R("Technical Lead", "java", 1, 7, 100, "Java;Spring Boot;Apache Kafka;Microservices Architecture", "Supply Chain & Logistics"),
       R("Java Developer", "java", (2, 4), 2, 100, "Java;Spring Boot;Apache Kafka", "PostgreSQL;Redis"),
       R("QA Automation Engineer", "qa", 1, 2, 100, "API Testing;REST Assured", "Selenium WebDriver"),
       R("Business Analyst", "ba", 1, 4, 100, "Requirements Elicitation;Supply Chain & Logistics:2", ""),
       R("DevOps Engineer", "devops", 1, 3, 50, "Kubernetes;Docker;Jenkins", "Helm"),
       PM("Supply Chain & Logistics")]),

    A("customer360", ["Customer 360 & Personalisation Platform", "Customer Data Platform (CDP) on Snowflake"],
      ["RETAIL", "BANK", "TELECOM", "CPG"], "Data & Analytics", ["Time & Material"], (8, 14), 2019,
      ["Unify {client}'s customer data from POS, app, web, CRM and call centre into a Snowflake-based Customer 360 "
       "with identity resolution, dbt-modelled golden records, segmentation and next-best-offer recommendations "
       "activated to marketing channels.",
       "Build a customer data platform for {client} enabling personalised campaigns for {members} customers."],
      "",
      [R("Lead Data Engineer", "data_eng", 1, 7, 100, "Snowflake;dbt;Data Modeling;SQL", "Apache Airflow", certs="SNOW-CORE"),
       R("Data Engineer", "data_eng", (2, 3), 2, 100, "Snowflake;SQL;Python", "dbt"),
       R("Data Scientist (Recommendations)", "data_sci", 1, 3, 100, "Recommendation Systems;Machine Learning;Python", "Apache Spark (PySpark)"),
       R("BI Developer", "data_eng", 1, 2, 100, "Tableau;SQL", "Power BI"),
       PM()],
      vars={"members": ["9 million", "14 million", "30 million"]}),

    A("quick_commerce", ["Quick-commerce Customer & Rider Apps", "10-minute Delivery Platform"],
      ["RETAIL"], "New Development", ["Fixed Price", "Time & Material"], (6, 12), 2021,
      ["Build {client}'s quick-commerce stack: customer app, rider app with live tracking and route assignment, dark "
       "store picking app, and Node.js backend services for slotting, inventory sync and order dispatch.",
       "Deliver customer and rider mobile apps for {client}'s 10-minute grocery delivery across 6 cities."],
      "E-commerce;Supply Chain & Logistics",
      [R("Mobile Tech Lead", "mobile", 1, 6, 100, "Flutter;Dart;REST API Design", "Google Maps Platform;Firebase"),
       R("Mobile Developer", "mobile", (2, 4), 2, 100, "Flutter;Dart", "Google Maps Platform;Firebase"),
       R("Backend Developer (Node.js)", "fullstack", (2, 3), 2, 100, "Node.js;TypeScript;REST API Design", "MongoDB;Redis;NestJS"),
       R("UX Designer", "ux", 1, 2, 100, "Figma;UI Design", "UX Research"),
       R("Mobile QA Engineer", "qa", (1, 2), 2, 100, "Mobile App Testing;Appium", "API Testing"),
       PM("E-commerce")]),

    A("price_opt", ["Dynamic Pricing & Markdown Optimization", "Price Elasticity & Promotion Optimization"],
      ["RETAIL", "CPG"], "AI/ML", ["Time & Material"], (5, 10), 2020,
      ["Build price-elasticity models and an optimisation engine that recommends regular, promotional and markdown "
       "prices for {client}'s categories, balancing margin and sell-through, with a planner-facing simulation UI.",
       "Apply ML and mathematical optimisation to {client}'s end-of-season markdowns across 240 stores."],
      "E-commerce",
      [R("Lead Data Scientist", "data_sci", 1, 6, 100, "Machine Learning;Operations Research / Optimization;Python", "Statistics & Probability"),
       R("Data Scientist", "data_sci", (1, 2), 2, 100, "Machine Learning;Python;Statistics & Probability", "Operations Research / Optimization"),
       R("Data Engineer", "data_eng", 1, 2, 100, "Apache Spark (PySpark);SQL", "Databricks"),
       R("Python Developer", "python", 1, 2, 100, "Python;FastAPI", "React"),
       PM()]),

    A("ecom_search", ["Product Search & Recommendations Revamp", "AI-powered Site Search & Discovery"],
      ["RETAIL"], "AI/ML", ["Fixed Price"], (5, 10), 2020,
      ["Revamp {client}'s product discovery: Elasticsearch relevance tuning with synonyms and typo tolerance, "
       "learning-to-rank on click data, and 'similar items' / 'frequently bought together' recommendations.",
       "Improve {client}'s search conversion by 15% with semantic search and personalised recommendations."],
      "E-commerce",
      [R("Search Lead", "java", 1, 6, 100, "Elasticsearch;Java;REST API Design", "E-commerce"),
       R("Data Scientist (Recommendations)", "data_sci", (1, 2), 2, 100, "Recommendation Systems;Python;Machine Learning", "Vector Databases"),
       R("Java Developer", "java", 1, 2, 100, "Java;Spring Boot", "Elasticsearch"),
       R("QA Engineer", "qa", 1, 2, 50, "Manual Testing;API Testing", ""),
       PM("E-commerce")]),

    # ======================= TELECOM & MEDIA =======================
    A("bss_billing", ["BSS Billing & Rating Modernization", "Convergent Charging & Billing Transformation"],
      ["TELECOM"], "Modernization", ["Time & Material", "Dedicated Team (ODC)"], (12, 24), 2019,
      ["Modernize {client}'s prepaid/postpaid billing and rating stack: product catalogue, convergent charging, "
       "invoicing and collections, migrating {subs} subscribers from the legacy BSS with zero revenue leakage.",
       "Build cloud-native rating and billing microservices for {client}, integrating with CRM, mediation and the "
       "payment gateway."],
      "Telecom OSS/BSS",
      [R("Solution Architect", "java", 1, 10, 50, "Java;Microservices Architecture;Telecom OSS/BSS:3", "Apache Kafka"),
       R("Technical Lead", "java", 1, 7, 100, "Java;Spring Boot;Oracle Database", "Telecom OSS/BSS;Apache Kafka"),
       R("Java Developer", "java", (3, 4), 2, 100, "Java;Spring Boot;SQL", "Oracle Database;Apache Kafka"),
       R("Data Migration Engineer", "data_eng", 1, 4, 100, "Oracle Database;PL/SQL;ETL/ELT Development", "Telecom OSS/BSS"),
       R("QA Engineer", "qa", (2, 3), 2, 100, "Manual Testing;API Testing;SQL", "ETL / Data Testing"),
       R("Business Analyst", "ba", 1, 5, 100, "Requirements Elicitation;Telecom OSS/BSS:3", "Gap Analysis"),
       PM("Telecom OSS/BSS", alloc=100)],
      vars={"subs": ["8 million", "14 million", "21 million"]}),

    A("network_analytics", ["5G Network Performance Analytics Platform", "Network Operations Analytics & Anomaly Detection"],
      ["TELECOM"], "Data & Analytics", ["Time & Material"], (8, 14), 2020,
      ["Stream cell-site KPIs and alarms from {client}'s 4G/5G RAN into a Kafka + Spark pipeline, store in "
       "Elasticsearch, and provide Grafana dashboards and ML-based anomaly detection that predicts congestion and "
       "outages for the NOC team.",
       "Build real-time network analytics for {client} processing 3 TB/day of performance counters."],
      "Telecom OSS/BSS",
      [R("Lead Data Engineer", "data_eng", 1, 7, 100, "Apache Kafka;Apache Spark (PySpark);Python", "Elasticsearch"),
       R("Data Engineer", "data_eng", (2, 3), 2, 100, "Apache Spark (PySpark);Python;SQL", "Apache Kafka;Elasticsearch"),
       R("Data Scientist", "data_sci", 1, 3, 100, "Machine Learning;Time Series Forecasting;Python", ""),
       R("SRE / Observability Engineer", "devops", 1, 3, 100, "Prometheus & Grafana;Kubernetes;Linux Administration", "ELK Stack"),
       PM("Telecom OSS/BSS")]),

    A("churn", ["Customer Churn Prediction & Retention", "Churn Propensity Models & Retention Campaigns"],
      ["TELECOM", "BANK", "MEDIA", "INS"], "AI/ML", ["Fixed Price", "Time & Material"], (4, 8), 2019,
      ["Build churn-propensity models for {client} using usage, billing, complaints and network-experience data, "
       "explain key churn drivers to business users, and integrate monthly scores with the retention campaign engine.",
       "Predict and reduce voluntary churn at {client} with explainable ML models and uplift-based targeting."],
      "",
      [R("Data Scientist", "data_sci", (1, 2), 2, 100, "Machine Learning;Python;scikit-learn;SQL", "XGBoost / LightGBM;Statistics & Probability"),
       R("Data Engineer", "data_eng", 1, 2, 100, "SQL;Apache Spark (PySpark);Python", "Databricks"),
       R("BI Developer", "data_eng", 1, 2, 50, "Power BI;SQL", "Tableau"),
       PM(alloc=25)]),

    A("ott_app", ["OTT Streaming Apps (Android TV, iOS, Web)", "Video Streaming Platform & Apps"],
      ["MEDIA"], "New Development", ["Fixed Price", "Time & Material"], (8, 14), 2020,
      ["Build {client}'s OTT apps for Android, Android TV, iOS and web: video playback with adaptive bitrate (HLS/DASH) "
       "and DRM, subscriptions and payments, downloads, continue-watching and recommendations rails, backed by "
       "Node.js APIs on AWS.",
       "Launch a multi-platform streaming experience for {client}'s 12M subscribers."],
      "Media Streaming (OTT)",
      [R("Android Developer", "mobile", (2, 3), 2, 100, "Android Development;Kotlin", "Jetpack Compose;Media Streaming (OTT)"),
       R("iOS Developer", "mobile", (1, 2), 2, 100, "iOS Development;Swift", "SwiftUI"),
       R("Frontend Developer", "frontend", (1, 2), 2, 100, "React;TypeScript", "Next.js"),
       R("Node.js Developer", "fullstack", (1, 2), 3, 100, "Node.js;REST API Design;Amazon Web Services (AWS)", "MongoDB;Redis"),
       R("QA Engineer", "qa", (1, 2), 2, 100, "Mobile App Testing;Manual Testing", "Appium"),
       PM("Media Streaming (OTT)")]),

    A("genai_care", ["GenAI Customer Care Assistant (RAG)", "Agent Assist Copilot with LLMs"],
      ["TELECOM", "BANK", "INS", "RETAIL"], "AI/ML", ["Fixed Price", "Time & Material"], (4, 9), 2023,
      ["Build a GenAI assistant for {client}'s contact centre that answers customer and agent queries using "
       "retrieval-augmented generation over product manuals, policies and past tickets, with guardrails, PII "
       "redaction, citation of sources and human hand-off. Target: 25% reduction in average handling time.",
       "Deliver an LLM-powered agent-assist copilot for {client} integrated with the CRM, summarising calls and "
       "suggesting next-best responses grounded in the knowledge base."],
      "",
      [R("GenAI Lead", "data_sci", 1, 6, 100, "Generative AI / LLMs;Retrieval-Augmented Generation (RAG);Python;LangChain",
         "Vector Databases;Prompt Engineering", certs="AI-102;AWS-AIF"),
       R("GenAI Engineer", "data_sci", (1, 2), 2, 100, "Generative AI / LLMs;Python;Prompt Engineering", "LangChain;Vector Databases"),
       R("Python Backend Developer", "python", 1, 3, 100, "Python;FastAPI;REST API Design", "Docker;Redis"),
       R("Frontend Developer", "frontend", 1, 2, 100, "React;TypeScript", ""),
       R("QA Engineer", "qa", 1, 2, 100, "Manual Testing;API Testing", "Python"),
       PM()]),

    # ======================= MANUFACTURING, LOGISTICS, ENERGY =======================
    A("predictive_maint", ["Predictive Maintenance for Plant Equipment (IoT + ML)", "Industrial IoT Condition Monitoring"],
      ["MFG", "ENERGY"], "AI/ML", ["Time & Material", "Fixed Price"], (8, 14), 2019,
      ["Stream sensor data (vibration, temperature, current) from {machines} machines at {client}'s plants via "
       "MQTT/Azure IoT Hub, build remaining-useful-life and anomaly models, and alert maintenance teams through a "
       "Power BI and mobile dashboard. Target: 20% reduction in unplanned downtime.",
       "Implement IIoT-based predictive maintenance for {client}'s CNC and press lines."],
      "IoT (MQTT / Edge);Manufacturing (MES)",
      [R("Lead Data Scientist", "data_sci", 1, 6, 100, "Machine Learning;Time Series Forecasting;Python", "IoT (MQTT / Edge)"),
       R("Data Scientist", "data_sci", 1, 2, 100, "Machine Learning;Python;pandas & NumPy", "Time Series Forecasting"),
       R("IoT / Data Engineer", "data_eng", (1, 2), 3, 100, "Microsoft Azure;Apache Spark (PySpark);Python", "IoT (MQTT / Edge);Azure Data Factory"),
       R("BI Developer", "data_eng", 1, 2, 50, "Power BI;SQL", ""),
       R("Python Developer", "python", 1, 2, 100, "Python;FastAPI", "Docker"),
       PM("Manufacturing (MES)")],
      vars={"machines": ["350", "800", "1,400"]}),

    A("mes_erp", ["MES–SAP ERP Integration Layer", "Shop-floor to ERP Integration Platform"],
      ["MFG"], "Implementation (Package)", ["Fixed Price"], (6, 12), 2019,
      ["Build an integration layer between {client}'s Manufacturing Execution System and SAP S/4HANA: production "
       "orders, material movements, quality inspections and goods receipts via IDoc/BAPI and REST, with monitoring "
       "and retry dashboards.",
       "Integrate {client}'s plant systems with SAP ERP to eliminate manual production reporting."],
      "Manufacturing (MES)",
      [R("Integration Lead", "java", 1, 7, 100, "Java;SAP Integration (IDoc/BAPI);REST API Design", "MuleSoft;Manufacturing (MES)"),
       R("Integration Developer", "java", (2, 3), 2, 100, "Java;Spring Boot;REST API Design", "SAP Integration (IDoc/BAPI);Apache Kafka"),
       R("QA Engineer", "qa", 1, 2, 100, "API Testing;Manual Testing", ""),
       R("Business Analyst", "ba", 1, 4, 100, "Requirements Elicitation;Manufacturing (MES):2", "Business Process Modeling (BPMN)"),
       PM("Manufacturing (MES)")]),

    A("control_tower", ["Supply Chain Control Tower", "End-to-end Supply Chain Visibility Platform"],
      ["LOGI", "CPG", "MFG", "RETAIL"], "Data & Analytics", ["Time & Material"], (6, 12), 2020,
      ["Build a supply chain control tower for {client} giving real-time visibility of inbound, inventory and "
       "outbound flows across plants, warehouses and carriers, with exception alerts and Power BI dashboards on an "
       "Azure lakehouse.",
       "Integrate ERP, WMS and TMS data for {client} into a single control-tower view with OTIF and fill-rate KPIs."],
      "Supply Chain & Logistics",
      [R("Lead Data Engineer", "data_eng", 1, 7, 100, "Azure Data Factory;Databricks;SQL;Data Modeling", "Supply Chain & Logistics", certs="DP-203"),
       R("Data Engineer", "data_eng", (2, 3), 2, 100, "Azure Data Factory;Apache Spark (PySpark);SQL", "Databricks"),
       R("BI Developer", "data_eng", 1, 2, 100, "Power BI;SQL", "Data Modeling", certs="PL-300"),
       R("Business Analyst", "ba", 1, 4, 100, "Requirements Elicitation;Supply Chain & Logistics:2", ""),
       PM("Supply Chain & Logistics")]),

    A("fleet", ["Fleet Tracking & Route Optimization", "Transport Management & Live Tracking Platform"],
      ["LOGI"], "New Development", ["Fixed Price", "Time & Material"], (8, 14), 2019,
      ["Build {client}'s transport management platform: GPS telematics ingestion from {trucks} trucks, live tracking, "
       "ETA prediction, route and load optimisation, driver app for PoD capture, and customer shipment tracking.",
       "Digitise {client}'s line-haul operations with real-time tracking, optimised routing and e-PoD."],
      "Supply Chain & Logistics;IoT (MQTT / Edge)",
      [R("Technical Lead", "java", 1, 7, 100, "Java;Spring Boot;Apache Kafka;Microservices Architecture", "Google Maps Platform"),
       R("Java Developer", "java", (2, 3), 2, 100, "Java;Spring Boot;REST API Design", "PostgreSQL;Apache Kafka"),
       R("Android Developer", "mobile", 1, 2, 100, "Android Development;Kotlin", "Google Maps Platform"),
       R("Data Scientist (Optimization)", "data_sci", 1, 3, 100, "Operations Research / Optimization;Python", "Machine Learning"),
       R("QA Engineer", "qa", 1, 2, 100, "Manual Testing;Mobile App Testing", "API Testing"),
       PM("Supply Chain & Logistics")],
      vars={"trucks": ["3,500", "7,000", "12,000"]}),

    A("smart_meter", ["Smart Meter Data Management Platform (AMI)", "AMI Head-end & Meter Data Analytics"],
      ["ENERGY"], "New Development", ["Time & Material"], (10, 18), 2020,
      ["Build {client}'s meter data management platform for {meters} smart meters: 15-minute interval ingestion via "
       "Kafka, validation-estimation-editing (VEE), billing determinants, theft and loss analytics, and consumer "
       "self-service portal.",
       "Deliver a scalable AMI data platform for {client} supporting prepaid metering and outage detection."],
      "Energy & Utilities (AMI);IoT (MQTT / Edge)",
      [R("Technical Lead", "java", 1, 7, 100, "Java;Apache Kafka;Microservices Architecture", "Cassandra;Energy & Utilities (AMI)"),
       R("Java Developer", "java", (2, 3), 2, 100, "Java;Spring Boot;Apache Kafka", "Cassandra"),
       R("Data Engineer", "data_eng", (1, 2), 3, 100, "Apache Spark (PySpark);SQL;Python", "Cassandra;Apache Kafka"),
       R("DevOps Engineer", "devops", 1, 3, 100, "Kubernetes;Docker;Terraform", "Prometheus & Grafana"),
       R("QA Engineer", "qa", 1, 2, 100, "API Testing;Manual Testing", "Apache JMeter"),
       PM("Energy & Utilities (AMI)")],
      vars={"meters": ["1.2 million", "2.8 million", "4.5 million"]}),

    A("vision_qc", ["AI Visual Quality Inspection on Assembly Line", "Computer-Vision Defect Detection"],
      ["MFG"], "AI/ML", ["Fixed Price"], (5, 10), 2020,
      ["Deploy computer-vision models on edge devices at {client}'s assembly lines to detect surface defects, "
       "missing components and weld anomalies in real time, integrated with the MES for automatic rejection. "
       "Target: catch 98% of visible defects at line speed.",
       "Replace manual visual inspection at {client} with deep-learning defect detection on GPU edge boxes."],
      "Manufacturing (MES);IoT (MQTT / Edge)",
      [R("Lead Data Scientist (CV)", "data_sci", 1, 6, 100, "Computer Vision;Deep Learning;PyTorch", "IoT (MQTT / Edge)"),
       R("Data Scientist (CV)", "data_sci", (1, 2), 2, 100, "Computer Vision;Python;Deep Learning", "TensorFlow"),
       R("Python Developer", "python", 1, 2, 100, "Python;Docker", "FastAPI"),
       PM("Manufacturing (MES)")]),

    # ======================= CROSS-INDUSTRY =======================
    A("aws_migration", ["AWS Cloud Migration (Rehost & Replatform)", "Data Centre Exit to AWS"],
      ANY, "Cloud & Infrastructure", ["Fixed Price", "Time & Material"], (6, 14), 2019,
      ["Migrate {apps} applications from {client}'s on-prem data centre to AWS: discovery and wave planning, landing "
       "zone with Control Tower, rehost via AWS MGN, replatform databases to RDS, and cut-over with rollback plans. "
       "Target: data centre exit within the contract term with 25% infra cost reduction.",
       "Move {client}'s application estate to AWS with a secure multi-account landing zone and IaC-driven environments."],
      "",
      [R("Cloud Architect", "devops", 1, 9, 100, "Amazon Web Services (AWS);Terraform;Kubernetes", "Cloud Security", certs="AWS-SAP", mcerts="AWS-SAA"),
       R("Cloud Engineer", "devops", (2, 4), 2, 100, "Amazon Web Services (AWS);Terraform;Linux Administration", "Docker;Ansible", mcerts="AWS-SAA"),
       R("Database Migration Engineer", "data_eng", 1, 4, 100, "SQL;Oracle Database;PostgreSQL", "Amazon Web Services (AWS)"),
       R("QA Engineer", "qa", 1, 2, 100, "Manual Testing;API Testing", ""),
       PM(alloc=100)],
      vars={"apps": ["60", "120", "210"]}),

    A("azure_lz", ["Azure Landing Zone & Workload Migration", "Microsoft Azure Cloud Adoption Programme"],
      ANY, "Cloud & Infrastructure", ["Fixed Price"], (6, 12), 2019,
      ["Design and build {client}'s Azure landing zone (hub-spoke networking, Entra ID, policies, Defender for Cloud) "
       "using Terraform, then migrate {apps} Windows and .NET workloads with Azure Migrate.",
       "Establish an enterprise-scale Azure foundation for {client} and migrate the first application waves."],
      "",
      [R("Azure Cloud Architect", "devops", 1, 9, 100, "Microsoft Azure;Terraform;Azure DevOps", "Cloud Security", certs="AZ-305"),
       R("Azure Cloud Engineer", "devops", (2, 3), 2, 100, "Microsoft Azure;Terraform;Azure DevOps", "Kubernetes", mcerts="AZ-104"),
       R("Cloud Security Engineer", "security", 1, 4, 50, "Cloud Security;Identity & Access Management (IAM);Microsoft Azure", "", certs="AZ-500"),
       PM()],
      vars={"apps": ["40", "85", "150"]}),

    A("k8s_platform", ["Kubernetes Platform Engineering & GitOps", "Internal Developer Platform on Kubernetes"],
      ANY, "Cloud & Infrastructure", ["Time & Material"], (6, 12), 2020,
      ["Build {client}'s internal developer platform on managed Kubernetes: multi-tenant clusters, GitOps delivery "
       "with Argo CD, Helm golden templates, policy-as-code, observability with Prometheus/Grafana, and self-service "
       "environments for 60+ engineering squads.",
       "Standardise {client}'s container platform and CI/CD with GitOps and SRE practices."],
      "",
      [R("Platform Lead", "devops", 1, 7, 100, "Kubernetes;Helm;Argo CD;Terraform", "Site Reliability Engineering", mcerts="CKA"),
       R("Platform Engineer", "devops", (2, 3), 2, 100, "Kubernetes;Docker;Helm", "Argo CD;Prometheus & Grafana", certs="CKA;CKAD"),
       R("SRE", "devops", 1, 3, 100, "Site Reliability Engineering;Prometheus & Grafana;Kubernetes", "Python"),
       PM(alloc=25)]),

    A("test_automation", ["Enterprise Test Automation Framework", "Quality Engineering Transformation (Shift-Left)"],
      ANY, "Testing Services", ["Managed Services", "Time & Material"], (6, 14), 2019,
      ["Set up a reusable test automation framework for {client} covering web, API and mobile, integrated into CI "
       "pipelines with parallel execution, reporting and test data management. Target: automate 70% of the "
       "regression suite and cut release regression time from 10 days to 2.",
       "Transform {client}'s largely manual QA into automated, CI-integrated quality engineering."],
      "",
      [R("Test Architect", "qa", 1, 8, 100, "Test Automation Framework Design;Selenium WebDriver;API Testing", "Playwright;Jenkins", certs="ISTQB-TAE"),
       R("QA Automation Engineer", "qa", (3, 5), 2, 100, "Selenium WebDriver;Java;TestNG", "Cucumber (BDD);REST Assured", certs="ISTQB-CTFL"),
       R("Mobile Automation Engineer", "qa", 1, 2, 100, "Appium;Mobile App Testing", "Java"),
       PM(alloc=25)]),

    A("perf_eng", ["Performance Engineering for Peak-Season Readiness", "Load & Scalability Testing Programme"],
      ANY, "Testing Services", ["Fixed Price"], (3, 6), 2019,
      ["Validate {client}'s platforms for {multiple}x peak load ahead of the sale/festive season: workload modelling, "
       "JMeter scripts, distributed load generation, APM-based bottleneck analysis and tuning recommendations.",
       "Run end-to-end performance testing and capacity planning for {client}'s critical customer journeys."],
      "",
      [R("Performance Test Lead", "qa", 1, 6, 100, "Performance Testing;Apache JMeter;API Testing", "Prometheus & Grafana"),
       R("Performance Test Engineer", "qa", (1, 2), 2, 100, "Apache JMeter;Performance Testing", "SQL"),
       R("SRE / Observability Engineer", "devops", 1, 3, 50, "Prometheus & Grafana;Linux Administration", "Kubernetes")],
      vars={"multiple": ["3", "5", "8"]}),

    A("genai_knowledge", ["Enterprise GenAI Knowledge Assistant", "Secure Internal Copilot (RAG on SharePoint & Confluence)"],
      ANY, "AI/ML", ["Fixed Price", "Time & Material"], (4, 8), 2023,
      ["Build a secure GenAI knowledge assistant for {client}'s employees that answers questions over SharePoint, "
       "Confluence and policy documents using RAG, respects document-level permissions via Entra ID, cites sources, "
       "and logs every interaction for audit.",
       "Deploy an internal copilot for {client} that reduces time spent searching for policies and procedures."],
      "",
      [R("GenAI Lead", "data_sci", 1, 6, 100, "Generative AI / LLMs;Retrieval-Augmented Generation (RAG);Python", "LangChain;Vector Databases", certs="AI-102"),
       R("GenAI Engineer", "data_sci", (1, 2), 2, 100, "Generative AI / LLMs;Python;Vector Databases", "Prompt Engineering;LangChain"),
       R("Python Backend Developer", "python", 1, 2, 100, "Python;FastAPI", "Docker"),
       R("Frontend Developer", "frontend", 1, 2, 100, "React;TypeScript", ""),
       R("Security Engineer (IAM)", "security", 1, 4, 25, "Identity & Access Management (IAM);Application Security", ""),
       PM(alloc=25)]),

    A("lakehouse", ["Hadoop to Databricks Lakehouse Migration", "Enterprise Data Lakehouse Modernization"],
      ANY, "Data & Analytics", ["Time & Material", "Fixed Price"], (8, 16), 2020,
      ["Migrate {client}'s on-prem Hadoop/Hive platform ({tb} TB, 1,800+ jobs) to a Databricks lakehouse on Delta Lake "
       "with Unity Catalog governance, rewrite Hive/Sqoop jobs as PySpark pipelines, and validate data parity.",
       "Modernize {client}'s data platform from Cloudera to a cloud lakehouse with cost and performance gains."],
      "",
      [R("Data Architect", "data_eng", 1, 9, 100, "Databricks;Delta Lake;Data Modeling;Apache Spark (PySpark)", "Hadoop & Hive", certs="DBX-DEP"),
       R("Senior Data Engineer", "data_eng", (2, 3), 4, 100, "Apache Spark (PySpark);Databricks;Hadoop & Hive", "Delta Lake", certs="DBX-DEA"),
       R("Data Engineer", "data_eng", (2, 3), 2, 100, "Apache Spark (PySpark);SQL;Python", "Databricks"),
       R("Data Test Engineer", "qa", 1, 2, 100, "ETL / Data Testing;SQL", "Python"),
       R("DevOps Engineer", "devops", 1, 3, 50, "Terraform;Azure DevOps", "Microsoft Azure"),
       PM()],
      vars={"tb": ["450", "900", "1,600"]}),

    A("powerbi_migration", ["Enterprise Reporting Migration to Power BI", "Self-service BI Modernization"],
      ANY, "Data & Analytics", ["Fixed Price"], (4, 9), 2019,
      ["Migrate {client}'s {reports} legacy SSRS/Cognos reports to Power BI with a governed semantic model, row-level "
       "security, deployment pipelines and a centre-of-excellence playbook for self-service analytics.",
       "Rationalise and rebuild {client}'s management reporting in Power BI with certified datasets."],
      "",
      [R("BI Lead", "data_eng", 1, 6, 100, "Power BI;Data Modeling;SQL", "Microsoft SQL Server", certs="PL-300"),
       R("BI Developer", "data_eng", (2, 3), 2, 100, "Power BI;SQL", "Microsoft SQL Server", certs="PL-300"),
       R("Business Analyst", "ba", 1, 3, 50, "Requirements Elicitation;Power BI", ""),
       PM(alloc=25)],
      vars={"reports": ["300", "650", "1,100"]}),

    A("fabric", ["Microsoft Fabric Analytics Platform", "Unified Analytics on Microsoft Fabric"],
      ANY, "Data & Analytics", ["Fixed Price", "Time & Material"], (5, 10), 2024,
      ["Implement Microsoft Fabric for {client}: OneLake-based lakehouse, Data Factory pipelines, Spark notebooks, "
       "Direct Lake Power BI semantic models and capacity governance, consolidating three separate BI stacks.",
       "Move {client}'s Azure Synapse and Power BI estate to Microsoft Fabric."],
      "",
      [R("Fabric Lead", "data_eng", 1, 6, 100, "Microsoft Fabric;Power BI;Data Modeling", "Apache Spark (PySpark)", certs="DP-600"),
       R("Data Engineer (Fabric)", "data_eng", (2, 3), 2, 100, "Microsoft Fabric;SQL;Apache Spark (PySpark)", "Azure Data Factory", certs="DP-700;DP-600"),
       R("BI Developer", "data_eng", 1, 2, 100, "Power BI;SQL", "Microsoft Fabric"),
       PM(alloc=25)]),

    A("ams", ["Application Maintenance & Support (L2/L3)", "Managed Application Services"],
      ANY, "Application Support", ["Managed Services"], (18, 36), 2019,
      ["Provide 24x7 L2/L3 application maintenance for {client}'s portfolio of {apps} business applications under "
       "ITIL-aligned SLAs: incident and problem management, minor enhancements, release support and monthly service "
       "reviews, with a target of 99.5% SLA adherence.",
       "Run {client}'s application support desk with shift-based coverage and continuous-improvement automation."],
      "",
      [R("Support Lead", "java", 1, 6, 100, "Java;SQL;ITIL / Incident Management", "Linux Administration;Spring Boot", certs="ITIL4-F"),
       R("Application Support Engineer (Java)", "java", (2, 4), 1, 100, "Java;SQL", "Linux Administration;ITIL / Incident Management"),
       R("Application Support Engineer (.NET)", "dotnet", (1, 3), 1, 100, "C#;Microsoft SQL Server", "ITIL / Incident Management"),
       R("Service Delivery Manager", "pm", 1, 9, 50, "ITIL / Incident Management;Stakeholder Management", "Budget & Financial Management", certs="ITIL4-F")],
      vars={"apps": ["35", "70", "120"]}),

    A("devsecops", ["Application Security Assessment & DevSecOps Enablement", "Secure SDLC & VAPT Programme"],
      ANY, "Security", ["Fixed Price"], (4, 9), 2019,
      ["Perform VAPT across {client}'s {apps} internet-facing applications and APIs, remediate OWASP Top 10 findings "
       "with development teams, and embed SAST/DAST/SCA scanning into CI pipelines with security gates.",
       "Establish a secure SDLC at {client}: threat modelling, automated security testing and developer training."],
      "PCI DSS",
      [R("Security Lead", "security", 1, 7, 100, "Application Security;Penetration Testing;DevSecOps", "ISO 27001 & Compliance", certs="CISSP"),
       R("Penetration Tester", "security", (1, 2), 2, 100, "Penetration Testing;Burp Suite;OWASP Top 10", "", mcerts="CEH"),
       R("DevSecOps Engineer", "devops", 1, 3, 100, "DevSecOps;Jenkins;Docker", "GitHub Actions"),
       PM(alloc=25)],
      vars={"apps": ["25", "60", "110"]}),

    A("sf_service", ["Salesforce Service Cloud Implementation", "Omnichannel Customer Service on Salesforce"],
      ["RETAIL", "TELECOM", "INS", "CPG", "MEDIA", "ENERGY"], "Implementation (Package)", ["Fixed Price"], (5, 10), 2019,
      ["Implement Salesforce Service Cloud for {client}'s customer service: omni-channel routing across voice, email, "
       "chat and WhatsApp, case management with SLAs, knowledge base, and integrations with order and billing systems.",
       "Consolidate {client}'s support channels onto Salesforce Service Cloud for 600 agents."],
      "",
      [R("Salesforce Technical Lead", "salesforce", 1, 6, 100, "Salesforce Service Cloud;Apex;Lightning Web Components (LWC)", "MuleSoft",
         certs="SF-SVC", mcerts="SF-PD1"),
       R("Salesforce Developer", "salesforce", (2, 3), 2, 100, "Apex;Lightning Web Components (LWC)", "Salesforce Service Cloud"),
       R("Salesforce Administrator", "salesforce", 1, 2, 100, "Salesforce Administration;Salesforce Service Cloud", "", mcerts="SF-ADMIN"),
       R("QA Engineer", "qa", 1, 2, 100, "Manual Testing", "API Testing"),
       PM()]),

    A("iam", ["Identity & Access Management Modernization (SSO/MFA)", "Customer & Workforce IAM Programme"],
      ANY, "Security", ["Fixed Price", "Time & Material"], (5, 10), 2019,
      ["Modernize {client}'s identity platform: migrate {apps} applications to SSO with OIDC/SAML, roll out MFA, "
       "automate joiner-mover-leaver provisioning and implement privileged access reviews.",
       "Consolidate {client}'s identity stores onto a cloud IAM platform with conditional access."],
      "",
      [R("IAM Lead", "security", 1, 7, 100, "Identity & Access Management (IAM);Cloud Security", "Microsoft Azure"),
       R("IAM Engineer", "security", (1, 2), 2, 100, "Identity & Access Management (IAM)", "Java"),
       R("Java Developer", "java", 1, 2, 100, "Java;Spring Boot;REST API Design", "Identity & Access Management (IAM)"),
       PM(alloc=25)],
      vars={"apps": ["45", "90", "160"]}),

    A("dotnet_upgrade", ["Legacy .NET Framework to .NET 8 Modernization", "Line-of-Business App Modernization on Azure"],
      ANY, "Modernization", ["Fixed Price", "Time & Material"], (6, 12), 2019,
      ["Upgrade {client}'s {apps} line-of-business applications from .NET Framework 4.x/WebForms to .NET 8 and Angular, "
       "containerise them and deploy on Azure App Service/AKS with Azure DevOps pipelines.",
       "Modernize {client}'s legacy Windows applications to cloud-ready .NET services."],
      "",
      [R("Technical Lead", "dotnet", 1, 7, 100, "C#;ASP.NET Core;Microsoft Azure", "Azure DevOps"),
       R(".NET Developer", "dotnet", (2, 4), 2, 100, "C#;ASP.NET Core;Microsoft SQL Server", "Entity Framework Core", certs="AZ-204"),
       R("Angular Developer", "frontend", 1, 2, 100, "Angular;TypeScript", ""),
       R("QA Engineer", "qa", 1, 2, 100, "Manual Testing;Selenium WebDriver", ""),
       PM()],
      vars={"apps": ["8", "15", "26"]}),

    A("python_api_platform", ["API Platform & Partner Integration Hub", "Open API Gateway & Developer Portal"],
      ANY, "New Development", ["Time & Material"], (6, 12), 2019,
      ["Build {client}'s partner API platform: Python microservices behind an API gateway, OAuth2 client onboarding, "
       "rate limiting, a developer portal with OpenAPI docs and usage analytics, for {partners} partners.",
       "Expose {client}'s core capabilities as secure, documented APIs for partners and fintechs."],
      "",
      [R("Python Tech Lead", "python", 1, 6, 100, "Python;FastAPI;Microservices Architecture;REST API Design", "Amazon Web Services (AWS)"),
       R("Python Developer", "python", (2, 3), 2, 100, "Python;FastAPI;PostgreSQL", "Redis;Docker"),
       R("Frontend Developer", "frontend", 1, 2, 100, "React;TypeScript", ""),
       R("API QA Engineer", "qa", 1, 2, 100, "API Testing;Postman", "REST Assured"),
       R("DevOps Engineer", "devops", 1, 3, 50, "Amazon Web Services (AWS);Docker;Terraform", "Kubernetes"),
       PM(alloc=25)],
      vars={"partners": ["40", "120", "300"]}),
]
