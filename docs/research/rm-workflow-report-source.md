# Research source: Relationship Manager workflow, commercial outcomes, and integration strategy

## Research question

How should Client Future Room fit into a private-banking Relationship Manager's workflow if the business objective is to acquire and serve clients faster, increase commercially valuable client activity, and reduce administrative work without weakening suitability or human control?

## Scope

- Relationship Manager workflows across prospecting, onboarding, advice, servicing, deepening, and retention.
- Existing systems commonly used across CRM, client lifecycle management, portfolio and advisory, research and market data, productivity, records, and service workflows.
- Public Julius Baer evidence where available.
- Product implications for the Lau Chi Ming demo and the longer-term platform.

## Scope limits

- Public sources do not establish Julius Baer's complete current internal application inventory.
- Vendor capabilities describe product offerings, not proof that every capability is deployed by a specific bank.
- Some productivity evidence is drawn from North American banking and advisory studies and is treated as directional for private banking in Asia.
- The supplied challenge dataset does not contain prospect pipeline, onboarding, held-away assets, product economics, or complete revenue attribution.

## Findings

### 1. Administrative load and fragmented workflows constrain commercial capacity

Relationship Managers and frontline bankers report administrative burden, weak lead quality, and difficult meeting preparation as major constraints.
McKinsey describes potential uses of agentic AI across lead prioritization, prospect qualification, meeting preparation, documentation, and approvals.
Its survey covered 406 frontline bankers, Relationship Managers, and sales leaders in the United States and Canada, so the findings are directional rather than a direct measurement of Julius Baer RMs.

Source: [McKinsey, Agentic AI is here. Is your bank's frontline team ready?](https://www.mckinsey.com/industries/financial-services/our-insights/agentic-ai-is-here-is-your-banks-frontline-team-ready)

McKinsey's wealth-management research also identifies meeting preparation, post-meeting notes and actions, planning simulations, compliance reporting, and workflow automation as capacity opportunities.
It estimates that these tools can return meaningful advisor time, but its estimates are market-level projections and should not be used as MVP performance claims.

Source: [McKinsey, The looming advisor shortage in US wealth management](https://www.mckinsey.com/industries/financial-services/our-insights/the-looming-advisor-shortage-in-us-wealth-management)

### 2. Commercial value spans the full relationship lifecycle

The most useful analytics and automation opportunities occur across acquisition and onboarding, engagement and deepening, and service and retention.
Examples include lead generation, share-of-wallet analysis, onboarding, personalized research, next-best conversations, and event-triggered recommendations.

Source: [McKinsey, Analytics transformation in wealth management](https://www.mckinsey.com/industries/financial-services/our-insights/analytics-transformation-in-wealth-management)

Current client behavior makes retention and share of wallet as important as acquisition.
EY reports that wealthy clients commonly use multiple wealth managers and that many plan to move a meaningful share of their assets.
The product implication is that timely, personalized service and goal progress should be treated as commercial outcomes, not merely operational support.

Source: [EY, Client expectations rise as wealth managers face increasing competition for assets](https://www.ey.com/en_gl/newsroom/2026/06/client-expectations-rise-as-wealth-managers-face-increasing-competition-for-assets-ey-report)

### 3. Julius Baer already frames technology as support for human advice and operational leverage

Julius Baer's current description of its global AI direction emphasizes scalable foundations rather than isolated tools.
It identifies advisory preparation, decision support, client-interaction clarity, operational efficiency, and risk and compliance as connected priorities.
It also describes an AI-powered source of investment insights for RMs, AI-assisted screening, and a secure internal generative AI assistant.

Source: [Julius Baer, How Julius Baer's 20 years in Asia are shaping its global AI transformation](https://www.juliusbaer.com/en/insights/company-insights/behind-the-scenes/how-julius-baers-20-years-in-asia-are-shaping-its-global-ai-transformation/)

Julius Baer states that its guided digital onboarding was designed to keep the Relationship Manager involved while making account opening faster and more convenient.
The bank explicitly described the aim of allowing RMs to focus on value creation instead of administration.

Source: [Julius Baer, Julius Baer enables its private clients to be onboarded digitally](https://www.juliusbaer.com/en/media/news-portal/julius-baer-enables-its-private-clients-to-be-onboarded-digitally/)

Julius Baer's Digital Advisory Suite in Asia was described as an integrated end-to-end advisory experience that gives RMs a holistic client view, identifies engagement opportunities, navigates regulatory requirements, and automates administrative work.

Source: [Julius Baer, Julius Baer launches award-winning digital advisory platform in Asia](https://www.juliusbaer.com/sg/en/news/julius-baer-launches-award-winning-digital-advisory-platform-in-asia/)

Julius Baer's 2024 half-year report describes a CRM application built around a client lifecycle management solution, with work to integrate KYC profiling and apply AI and machine learning to simplify data capture.
This supports an integration-first proposal, but the public statement should not be treated as a complete description of the bank's current architecture.

Source: [Julius Baer, Half-year Report 2024](https://www.juliusbaer.com/index.php?eID=dumpFile&f=98245&t=f&token=01bbcfa56b911b16ae4eabd2e3c2caacd827658c)

Temenos reports that Julius Baer's Asian operations deployed Temenos Wealth across core banking, portfolio management, digital channels, and analytics.
This is a vendor case study and should be labeled as such.

Source: [Temenos, Julius Baer success story](https://www.temenos.com/success-story/julius-baer/)

### 4. The RM stack is a set of systems of record, not one application

CRM platforms manage households, relationships, referrals, opportunities, tasks, interactions, and client events.
Salesforce Financial Services Cloud publicly documents wealth-management features such as relationship maps, action plans, actionable segmentation, life events, interaction summaries, onboarding, document workflows, and financial deals.

Sources:

- [Salesforce Financial Services Cloud](https://www.salesforce.com/financial-services/cloud/)
- [Salesforce Wealth Management help](https://help.salesforce.com/s/articleView?id=ind.fsc_admin_landing_wealth.htm&language=en_US&type=5)

Client lifecycle management platforms coordinate onboarding, KYC, screening, review, documents, approvals, and status.
Fenergo positions its private-banking product as an end-to-end lifecycle platform and emphasizes CRM integration and faster time to revenue.

Source: [Fenergo for private banking and wealth](https://www.fenergo.com/segments/private-banking)

Portfolio and advisory platforms support client profiling, portfolio construction, risk, suitability, rebalancing, product selection, and trade workflows.
Temenos Wealth Front Office describes prioritized actions, personalized advisory, risk, compliance, and portfolio capabilities.

Source: [Temenos Wealth Front Office](https://www.temenos.com/products/wealth-management/wealth-front-office/)

Market-data and research platforms provide news, research, risk analytics, events, product data, and portfolio context.
FactSet documents CRM integrations for Salesforce, Microsoft Dynamics, and DealCloud.
Bloomberg and LSEG describe connected research, portfolio, analytics, and workflow capabilities.

Sources:

- [FactSet for CRM](https://www.factset.com/marketplace/catalog/product/factset-for-crm)
- [Bloomberg buy-side solutions](https://professional.bloomberg.com/solutions/buy-side/)
- [LSEG Workspace](https://www.lseg.com/en/data-analytics/products/workspace)

Portfolio-data aggregation platforms can unify liquid and illiquid assets while connecting CRM, order-management, and accounting systems.
Addepar's integration model illustrates why Client Future Room should consume governed data from systems of record rather than create a new shadow record.

Source: [Addepar integrations](https://addepar.com/integrations)

### 5. Product implication: orchestrate the final mile from insight to approved action

Client Future Room should read governed context from existing systems, calculate and explain the connected client consequence, help the RM rehearse the conversation, and write approved outcomes back to the correct record.
It should not attempt to rebuild CRM, KYC, portfolio accounting, order management, research distribution, or records management.

The differentiated workflow is:

`Detect -> understand -> simulate -> decide -> rehearse -> approve -> write back -> learn`

This final-mile orchestration is the gap between descriptive systems and a completed client outcome.

### 6. Commercial objective: trusted growth throughput

Raw revenue maximization is an unsafe north star because it can reward product pushing, ignore service obligations, and create suitability conflicts.
The recommended north star is trusted growth throughput: the number and value of client outcomes advanced per RM hour, subject to suitability, evidence, and control gates.

The measurement framework should balance:

- Growth: qualified pipeline, net new money, recurring revenue, share-of-wallet progress, and opportunity conversion.
- Speed: time to first contact, onboarding cycle time, time to funded account, and insight-to-action time.
- Service: service-level adherence, proactive coverage, client goal progress, retention, and outflow-risk resolution.
- Capacity: client-facing time, preparation time, administrative time, manual re-entry, and system switching.
- Control: KYC completeness, suitability exceptions, rework, unsupported claims, complaints, and actions executed without approval.

Revenue should be displayed only when approved pricing, probability, attribution, and product-economics data are available.

### 7. Dataset implications

The challenge data is sufficient to demonstrate a deepening and service case for Lau.
It is not sufficient to calculate reliable bank revenue or acquisition performance.

Production extensions require at least:

- Prospects, referrals, and lead-source records.
- Opportunity stage, probability, expected assets, and expected close date.
- Onboarding cases, KYC state, documents, blockers, and approval timestamps.
- Held-away assets and consented share-of-wallet estimates.
- Product pricing, fee schedules, spreads, costs, attribution, and realized revenue.
- Interactions, meeting outcomes, response history, and channel preferences.
- Service cases, service-level targets, complaints, and resolution state.
- Specialist availability and ownership.

## Claim-source ledger

| Claim | Source | Use in PRD | Limitation |
|---|---|---|---|
| Julius Baer's AI direction favors scalable, responsible foundations and already includes advisory, risk, and internal productivity use cases | Julius Baer Asia and AI transformation article | Strategic fit and non-duplication | Public description does not disclose implementation architecture |
| Administrative work, lead quality, and preparation constrain frontline capacity | McKinsey agentic AI article | Business problem and commercial operating loop | US and Canada survey across several banking segments |
| Wealth analytics creates value across acquisition, deepening, and retention | McKinsey analytics transformation | Lifecycle model | Includes industry examples and estimates, not an MVP benchmark |
| Digital onboarding can preserve guided RM interaction and reduce administration | Julius Baer digital onboarding | Integration strategy and roadmap | Public 2021 description, not proof of current implementation details |
| DiAS integrates advice, regulatory navigation, engagement opportunities, and administration | Julius Baer DiAS announcement | Existing workflow context | Public 2021 description |
| Julius Baer described CRM, CLM, KYC integration, and AI-assisted data capture | Julius Baer 2024 half-year report | Bank-specific feasibility context | Intermediaries rollout details do not establish universal deployment |
| Temenos Wealth was deployed in Julius Baer's Asian operations | Temenos success story | Bank-specific integration example | Vendor-authored case study |
| CRM, CLM, portfolio, research, and productivity systems have distinct responsibilities | Salesforce, Fenergo, Temenos, FactSet, Bloomberg, LSEG, and Addepar product pages | Tool landscape and system boundaries | Vendor capability pages are not deployment evidence |
| Client retention and share of wallet are commercially material | EY 2026 wealth report | Balanced KPI framework | Global survey and report summary, not dataset evidence |

## Recommended PRD decisions

1. Position Client Future Room as the decision-to-execution layer across existing RM systems.
2. Keep Lau as the only judged case and frame it as a service and relationship-deepening workflow.
3. Use trusted growth throughput as the strategic north star.
4. Do not show invented revenue for Lau.
5. Add a compact outcome strip that shows risk protected, client goal advanced, and approved follow-up created.
6. Extend Action Bridge to CRM, CLM, service-case, research, and portfolio systems in the production architecture.
7. Add a Prospect Future Room only as a later roadmap module for acquisition and onboarding.
8. Treat every connector write as approval-gated, auditable, and reversible where the destination permits it.
