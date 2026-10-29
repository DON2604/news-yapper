"""Clearly labelled DEMO content for credential-free local runs.

These are hand-written EVERGREEN explainers about well-documented past events and
static GK - not today's news and not AI output. Each demo item links to a reference
page that was checked to resolve on 2026-10-29 (see `link_check`), except where noted.
Re-running the seed is idempotent and refreshes the demo edition/question dates.
"""

from __future__ import annotations

import hashlib
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import (
    Article,
    DailyEdition,
    EditionEvent,
    Event,
    EventSource,
    Question,
    Source,
    SourceItem,
    utcnow,
)
from app.services.clock import app_today

PROMPT_VERSION = "demo-manual-v1"
ALL_EXAMS = ["SSC", "UPSC", "BANKING", "RAILWAYS", "STATE_PSC"]

DEMO_ARTICLES: list[dict[str, Any]] = [
    {
        "slug": "demo-chandrayaan-3-south-pole-landing",
        "category": "science",
        "region": "india",
        "importance": 90,
        "source": {
            "title": "Chandrayaan-3 mission details",
            "publisher": "ISRO",
            "url": "https://www.isro.gov.in/Chandrayaan3_Details.html",
            "link_check": "200 OK",
        },
        "headline": "Chandrayaan-3-er Vikram chand-er south pole-er kache soft landing korlo 🚀",
        "banglish_summary": (
            "Bhai, 23 August 2023-e ISRO-r Vikram lander chand-er south polar region-er kache soft landing "
            "korlo. India hoye gelo chand-e soft landing kora 4th desh, ar south pole-er kache prothom. "
            "Rover Pragyan beriye ese ghure ghure data niyeche - proper history class moment!"
        ),
        "neutral_summary": (
            "ISRO's Chandrayaan-3 mission achieved a soft landing near the Moon's south polar region on "
            "23 August 2023. The Vikram lander deployed the Pragyan rover. The mission was launched on 14 July "
            "2023 aboard LVM3 from the Satish Dhawan Space Centre, Sriharikota. India became the fourth country "
            "to soft-land on the Moon and the first to land near its south polar region."
        ),
        "why_matters": (
            "Exams love 'firsts': first landing near the lunar south pole, fourth country overall. It also links "
            "to National Space Day (23 August) and to ISRO's launch vehicle LVM3."
        ),
        "context": (
            "Chandrayaan-2's lander (2019) did not achieve a soft landing; Chandrayaan-3 focused on demonstrating "
            "safe landing and roving."
        ),
        "key_facts": [
            "Chandrayaan-3 soft-landed near the lunar south polar region on 23 August 2023.",
            "The lander is named Vikram and the rover is named Pragyan.",
            "It was launched on 14 July 2023 by LVM3 from Satish Dhawan Space Centre, Sriharikota.",
            "India became the fourth country to achieve a soft landing on the Moon.",
            "The landing point was named Shiv Shakti point and 23 August is observed as National Space Day.",
        ],
        "exam_tags": ALL_EXAMS,
        "mnemonics": ["V-P-L: Vikram lands, Pragyan prowls, LVM3 lifts."],
        "questions": [
            {
                "prompt": "On which date did Chandrayaan-3 soft-land near the Moon's south polar region?",
                "options": ["14 July 2023", "23 August 2023", "2 September 2023", "22 July 2019"],
                "correct": 1,
                "difficulty": "easy",
                "explanation": (
                    "Chandrayaan-3 launched on 14 July 2023 and landed on 23 August 2023. 2 September 2023 was "
                    "Aditya-L1's launch and 22 July 2019 was Chandrayaan-2's launch."
                ),
            },
            {
                "prompt": "What is the name of the rover carried by Chandrayaan-3?",
                "options": ["Vikram", "Pragyan", "Mangalyaan", "Aditya"],
                "correct": 1,
                "difficulty": "easy",
                "explanation": "Vikram is the lander; Pragyan is the rover it deployed.",
            },
        ],
    },
    {
        "slug": "demo-rbi-repo-rate-mpc-explainer",
        "category": "economy",
        "region": "india",
        "importance": 85,
        "source": {
            "title": "Reserve Bank of India",
            "publisher": "Reserve Bank of India",
            "url": "https://www.rbi.org.in/",
            "link_check": "200 OK",
        },
        "headline": "Repo rate ki jinish? RBI-r MPC-r cheat-sheet ☕",
        "banglish_summary": (
            "Repo rate holo sei rate jate RBI commercial bank-ke short-term loan dey, government securities-er "
            "against-e. Eta thik kore 6-jon member-er Monetary Policy Committee, chair koren RBI Governor. "
            "Target? CPI inflation 4%, +/-2% band - mane 2% theke 6%."
        ),
        "neutral_summary": (
            "The repo rate is the rate at which the Reserve Bank of India lends short-term funds to commercial "
            "banks against government securities. Under the RBI Act, 1934, as amended in 2016, a six-member "
            "Monetary Policy Committee (MPC) chaired by the RBI Governor decides the policy repo rate. The "
            "inflation target is 4% CPI inflation with a tolerance band of +/-2%."
        ),
        "why_matters": (
            "Banking and SSC papers repeatedly ask who chairs the MPC, how many members it has, and the inflation "
            "target and band. The repo rate number itself changes - learn the framework, check the current value."
        ),
        "context": "The flexible inflation targeting framework gave the MPC a statutory basis in 2016.",
        "key_facts": [
            "The repo rate is the rate at which RBI lends short-term funds to banks against government securities.",
            "The Monetary Policy Committee has six members and is chaired by the RBI Governor.",
            "The MPC framework comes from the RBI Act, 1934, as amended in 2016.",
            "The inflation target is 4% CPI inflation with a tolerance band of +/-2%.",
        ],
        "exam_tags": ["BANKING", "SSC", "UPSC", "RAILWAYS"],
        "mnemonics": ["MPC = 6 members, Governor chairs, 4 ± 2 = the inflation comfort zone."],
        "questions": [
            {
                "prompt": "How many members does RBI's Monetary Policy Committee have?",
                "options": ["4", "5", "6", "7"],
                "correct": 2,
                "difficulty": "easy",
                "explanation": "The MPC has six members - three from RBI (chaired by the Governor) and three external.",
            },
            {
                "prompt": "Under India's flexible inflation targeting framework, the CPI inflation target is:",
                "options": ["2% (+/-1%)", "4% (+/-2%)", "5% (+/-1%)", "6% (+/-2%)"],
                "correct": 1,
                "difficulty": "medium",
                "explanation": "The target is 4% CPI inflation with a tolerance band of +/-2% (i.e. 2%-6%).",
            },
        ],
    },
    {
        "slug": "demo-article-32-constitutional-remedies",
        "category": "polity",
        "region": "india",
        "importance": 80,
        "source": {
            "title": "Article 32: Remedies for enforcement of rights conferred by this Part",
            "publisher": "Constitution of India (constitutionofindia.net)",
            "url": (
                "https://www.constitutionofindia.net/articles/"
                "article-32-remedies-for-enforcement-of-rights-conferred-by-this-part/"
            ),
            "link_check": "200 OK",
        },
        "headline": "Article 32 = 'heart and soul' - Ambedkar-er favourite remedy, exam-er favourite trap!",
        "banglish_summary": (
            "Btw janish, Article 32 niye exam-e onek confusion hoy... Eta nije-i ekta Fundamental Right - Right "
            "to Constitutional Remedies. Right violate hole sorasori Supreme Court-e jaoa jay, ar SC writ dite "
            "pare. Dr. B.R. Ambedkar eta ke bolechilen Constitution-er 'heart and soul'."
        ),
        "neutral_summary": (
            "Article 32 of the Constitution of India guarantees the right to move the Supreme Court for the "
            "enforcement of Fundamental Rights. The Supreme Court can issue directions, orders or writs, including "
            "habeas corpus, mandamus, prohibition, certiorari and quo warranto. Dr. B.R. Ambedkar described "
            "Article 32 as the 'heart and soul' of the Constitution. Article 226 separately empowers High Courts "
            "to issue writs."
        ),
        "why_matters": (
            "Classic trap: Article 32 (Supreme Court, only Fundamental Rights, itself a Fundamental Right) versus "
            "Article 226 (High Courts, Fundamental Rights and 'for any other purpose')."
        ),
        "context": "Both articles sit at the core of judicial review questions in polity papers.",
        "key_facts": [
            "Article 32 guarantees the right to move the Supreme Court to enforce Fundamental Rights.",
            "The Supreme Court can issue writs of habeas corpus, mandamus, prohibition, certiorari and quo warranto.",
            "Dr. B.R. Ambedkar called Article 32 the 'heart and soul' of the Constitution.",
            "Article 226 empowers High Courts to issue writs.",
        ],
        "exam_tags": ALL_EXAMS,
        "mnemonics": ["Writs = H-M-P-C-Q: 'Har Mahine Pocket Cash Quick'."],
        "questions": [
            {
                "prompt": "Who described Article 32 as the 'heart and soul' of the Indian Constitution?",
                "options": [
                    "Jawaharlal Nehru",
                    "Dr. B.R. Ambedkar",
                    "Sardar Vallabhbhai Patel",
                    "Dr. Rajendra Prasad",
                ],
                "correct": 1,
                "difficulty": "easy",
                "explanation": "Dr. B.R. Ambedkar called Article 32 the 'heart and soul' of the Constitution.",
            },
            {
                "prompt": "Which writ is issued against unlawful detention of a person?",
                "options": ["Mandamus", "Habeas corpus", "Certiorari", "Quo warranto"],
                "correct": 1,
                "difficulty": "medium",
                "explanation": (
                    "Habeas corpus ('that you have the body') orders a detained person to be produced before the "
                    "court. Mandamus commands a duty, certiorari quashes orders, quo warranto questions a claim to "
                    "public office."
                ),
            },
        ],
    },
    {
        "slug": "demo-g20-new-delhi-african-union",
        "category": "international",
        "region": "world",
        "importance": 86,
        "source": {
            "title": "G20 New Delhi Leaders' Declaration",
            "publisher": "Ministry of External Affairs, Government of India",
            "url": "https://www.mea.gov.in/bilateral-documents?dtl/37084/G20_New_Delhi_Leaders_Declaration",
            "link_check": "200 OK",
        },
        "headline": "G20 New Delhi: African Union permanent member holo - 'One Earth, One Family, One Future' 🌍",
        "banglish_summary": (
            "India-r G20 presidency-r summit hoyechilo New Delhi-te, 9-10 September 2023. Boro news: African "
            "Union G20-er permanent member hoye gelo! Theme chhilo 'Vasudhaiva Kutumbakam - One Earth, One "
            "Family, One Future', ar New Delhi Leaders' Declaration adopt holo."
        ),
        "neutral_summary": (
            "The 18th G20 Leaders' Summit was held in New Delhi on 9-10 September 2023 under India's G20 "
            "Presidency. The African Union was admitted as a permanent member of the G20. The theme of India's "
            "Presidency was 'Vasudhaiva Kutumbakam - One Earth, One Family, One Future'. Leaders adopted the G20 "
            "New Delhi Leaders' Declaration."
        ),
        "why_matters": (
            "Expect questions on the African Union's membership, the presidency theme and the summit number. "
            "The European Union was already a member before 2023."
        ),
        "context": "India held the G20 Presidency from 1 December 2022 to 30 November 2023.",
        "key_facts": [
            "The 18th G20 Leaders' Summit was held in New Delhi on 9-10 September 2023.",
            "The African Union became a permanent member of the G20 at this summit.",
            "India's G20 Presidency theme was 'Vasudhaiva Kutumbakam - One Earth, One Family, One Future'.",
            "Leaders adopted the G20 New Delhi Leaders' Declaration.",
        ],
        "exam_tags": ALL_EXAMS,
        "mnemonics": ["AU joined at 18: the 18th summit added the African Union."],
        "questions": [
            {
                "prompt": "Which organisation became a permanent member of the G20 at the New Delhi Summit in 2023?",
                "options": ["ASEAN", "African Union", "European Union", "SAARC"],
                "correct": 1,
                "difficulty": "easy",
                "explanation": "The African Union joined in 2023; the European Union was already a G20 member.",
            },
            {
                "prompt": "What was the theme of India's G20 Presidency?",
                "options": [
                    "Sabka Saath, Sabka Vikas",
                    "Vasudhaiva Kutumbakam - One Earth, One Family, One Future",
                    "Recover Together, Recover Stronger",
                    "Building Bridges for Global Growth",
                ],
                "correct": 1,
                "difficulty": "medium",
                "explanation": (
                    "India's theme was 'Vasudhaiva Kutumbakam - One Earth, One Family, One Future'. "
                    "'Recover Together, Recover Stronger' was Indonesia's 2022 theme."
                ),
            },
        ],
    },
    {
        "slug": "demo-kunming-montreal-30x30",
        "category": "environment",
        "region": "world",
        "importance": 78,
        "source": {
            "title": "Kunming-Montreal Global Biodiversity Framework",
            "publisher": "Convention on Biological Diversity",
            "url": "https://www.cbd.int/gbf",
            "link_check": "200 OK",
        },
        "headline": "30x30: 2030-er moddhe 30% land ar 30% ocean protect korar promise 🌿",
        "banglish_summary": (
            "December 2022-e Montreal-e CBD COP15 theke ashlo Kunming-Montreal Global Biodiversity Framework. "
            "Headline target '30x30': 2030-er moddhe 30% land ar 30% ocean/coastal area conserve kora. Total 23-ta "
            "target ar 4-te long-term goal."
        ),
        "neutral_summary": (
            "The Kunming-Montreal Global Biodiversity Framework was adopted at the 15th Conference of the Parties "
            "(COP15) to the Convention on Biological Diversity in Montreal in December 2022. Its '30x30' target "
            "aims to effectively conserve at least 30% of land and inland waters and 30% of marine and coastal "
            "areas by 2030. The framework sets 23 global targets for 2030 and four goals for 2050."
        ),
        "why_matters": (
            "Environment papers mix up COPs: this is the biodiversity (CBD) COP15, not the climate (UNFCCC) COP. "
            "Remember 30x30 and the 23 targets."
        ),
        "context": "China held the COP15 presidency; the meeting was hosted in Montreal.",
        "key_facts": [
            "The framework was adopted at CBD COP15 in Montreal in December 2022.",
            "Its 30x30 target aims to conserve at least 30% of land and 30% of marine and coastal areas by 2030.",
            "It contains 23 global targets for 2030 and four goals for 2050.",
        ],
        "exam_tags": ["UPSC", "SSC", "STATE_PSC"],
        "mnemonics": ["30-30-23-4: thirty land, thirty sea, twenty-three targets, four goals."],
        "questions": [
            {
                "prompt": "The '30x30' target of the Kunming-Montreal Global Biodiversity Framework refers to:",
                "options": [
                    "Cutting emissions by 30% by 2030",
                    "Conserving 30% of land and 30% of oceans by 2030",
                    "Planting 30 billion trees by 2030",
                    "Reducing plastic use by 30% by 2030",
                ],
                "correct": 1,
                "difficulty": "easy",
                "explanation": "30x30 = conserve at least 30% of land and 30% of marine and coastal areas by 2030.",
            },
            {
                "prompt": "The Kunming-Montreal framework was adopted under which convention?",
                "options": ["UNFCCC", "Convention on Biological Diversity", "Ramsar Convention", "CITES"],
                "correct": 1,
                "difficulty": "medium",
                "explanation": "It was adopted at COP15 of the Convention on Biological Diversity (CBD).",
            },
        ],
    },
    {
        "slug": "demo-nobel-peace-2023-narges-mohammadi",
        "category": "awards",
        "region": "world",
        "importance": 72,
        "source": {
            "title": "The Nobel Peace Prize 2023 - Summary",
            "publisher": "NobelPrize.org",
            "url": "https://www.nobelprize.org/prizes/peace/2023/summary/",
            "link_check": "200 OK",
        },
        "headline": "Nobel Peace Prize 2023: Narges Mohammadi - Iran-e women's rights-er jonno lorai",
        "banglish_summary": (
            "2023-er Nobel Peace Prize pelen Iran-er Narges Mohammadi - Iran-e mohilader opor oppression-er "
            "biruddhe ar shobar human rights o freedom-er jonno tar lorai-er jonno. Serious topic, tai shudhu "
            "facts: prize ghoshona-r shomoy tini Iran-e bondi chhilen."
        ),
        "neutral_summary": (
            "The Norwegian Nobel Committee awarded the 2023 Nobel Peace Prize to Narges Mohammadi for her fight "
            "against the oppression of women in Iran and her fight to promote human rights and freedom for all. "
            "She was imprisoned in Iran at the time of the announcement."
        ),
        "why_matters": (
            "Award questions pair laureate, country and cause. Do not confuse with 2022 (Ales Bialiatski, Memorial "
            "and the Center for Civil Liberties) or 2021 (Maria Ressa and Dmitry Muratov)."
        ),
        "context": None,
        "tone": "serious",
        "key_facts": [
            "The 2023 Nobel Peace Prize was awarded to Narges Mohammadi of Iran.",
            "The prize recognised her fight against the oppression of women in Iran and for human rights for all.",
            "She was imprisoned in Iran when the prize was announced.",
        ],
        "exam_tags": ALL_EXAMS,
        "mnemonics": [],
        "questions": [
            {
                "prompt": "Who was awarded the Nobel Peace Prize in 2023?",
                "options": ["Narges Mohammadi", "Ales Bialiatski", "Maria Ressa", "Malala Yousafzai"],
                "correct": 0,
                "difficulty": "easy",
                "explanation": (
                    "Narges Mohammadi won in 2023. Ales Bialiatski shared the 2022 prize, Maria Ressa shared 2021 "
                    "and Malala Yousafzai shared 2014."
                ),
            }
        ],
    },
    {
        "slug": "demo-neeraj-chopra-tokyo-gold",
        "category": "sports",
        "region": "india",
        "importance": 70,
        "source": {
            "title": "Tokyo 2020 Olympic Games",
            "publisher": "Olympics.com",
            "url": "https://olympics.com/en/olympic-games/tokyo-2020",
            "link_check": "unverified: olympics.com was unreachable from the development network",
        },
        "headline": "Neeraj Chopra-r 87.58 m - Olympic athletics-e India-r prothom gold 🥇",
        "banglish_summary": (
            "Tokyo 2020 Olympics (2021-e hoyechilo) - men's javelin final-e Neeraj Chopra 87.58 m chhure gold "
            "jitlo. Eta Olympic athletics-e India-r prothom gold. Exam-e '87.58' number-ta mone rakhis!"
        ),
        "neutral_summary": (
            "Neeraj Chopra won the gold medal in the men's javelin throw at the Tokyo 2020 Olympic Games, held in "
            "2021, with a best throw of 87.58 m. It was India's first Olympic gold medal in athletics and India's "
            "second individual Olympic gold after Abhinav Bindra in 2008."
        ),
        "why_matters": "Sports GK repeats records: event, distance, edition and 'first' achievements.",
        "context": "The Tokyo 2020 Games were postponed to 2021 because of the COVID-19 pandemic.",
        "key_facts": [
            "Neeraj Chopra won gold in men's javelin throw at the Tokyo 2020 Olympics, held in 2021.",
            "His winning throw measured 87.58 m.",
            "It was India's first Olympic gold medal in athletics.",
            "It was India's second individual Olympic gold, after Abhinav Bindra in 2008.",
        ],
        "exam_tags": ["SSC", "RAILWAYS", "BANKING", "STATE_PSC"],
        "mnemonics": ["87.58 - 'eight-seven, five-eight, gold on the plate'."],
        "questions": [
            {
                "prompt": "Neeraj Chopra's gold-winning throw at the Tokyo 2020 Olympics measured:",
                "options": ["86.65 m", "87.58 m", "88.07 m", "89.94 m"],
                "correct": 1,
                "difficulty": "medium",
                "explanation": "His winning throw in the Tokyo 2020 final was 87.58 m.",
            }
        ],
    },
    {
        "slug": "demo-upi-npci-explainer",
        "category": "economy",
        "region": "india",
        "importance": 74,
        "source": {
            "title": "UPI product overview",
            "publisher": "National Payments Corporation of India",
            "url": "https://www.npci.org.in/what-we-do/upi/product-overview",
            "link_check": "200 OK",
        },
        "headline": "UPI: 2016-e launch, NPCI-r baby - QR scan kore cha-er dam dewa-r science 📱",
        "banglish_summary": (
            "UPI = Unified Payments Interface. NPCI (National Payments Corporation of India) baniyeche, 2016-e "
            "launch. NPCI nije RBI ar Indian Banks' Association-er initiative. Ekhon cha-wala theke shopping mall - "
            "shob jaygay QR!"
        ),
        "neutral_summary": (
            "The Unified Payments Interface (UPI) is a real-time payment system developed by the National Payments "
            "Corporation of India (NPCI) and launched in 2016. NPCI is an initiative of the Reserve Bank of India "
            "and the Indian Banks' Association."
        ),
        "why_matters": "Banking awareness staples: who runs UPI (NPCI, not RBI directly) and when it launched.",
        "context": None,
        "key_facts": [
            "UPI was developed by the National Payments Corporation of India (NPCI).",
            "UPI was launched in 2016.",
            "NPCI is an initiative of the RBI and the Indian Banks' Association.",
        ],
        "exam_tags": ["BANKING", "SSC", "RAILWAYS"],
        "mnemonics": ["UPI's parent is NPCI; NPCI's parents are RBI + IBA."],
        "questions": [
            {
                "prompt": "Which organisation developed the Unified Payments Interface (UPI)?",
                "options": ["RBI", "NPCI", "SEBI", "NABARD"],
                "correct": 1,
                "difficulty": "easy",
                "explanation": "UPI was developed by NPCI, an initiative of the RBI and the Indian Banks' Association.",
            }
        ],
    },
    {
        "slug": "demo-gst-council-279a",
        "category": "economy",
        "region": "india",
        "importance": 76,
        "source": {
            "title": "GST Council",
            "publisher": "GST Council Secretariat",
            "url": "https://gstcouncil.gov.in/",
            "link_check": "200 OK",
        },
        "headline": "GST: 1 July 2017 theke 'One Nation, One Tax' - Council chalay FM 🧾",
        "banglish_summary": (
            "GST roll out hoyechilo 1 July 2017. Constitutional backing: 101st Amendment Act, 2016. GST Council "
            "(Article 279A) - chair koren Union Finance Minister. Exam-e '279A' ar '101st' - duto-i favourite!"
        ),
        "neutral_summary": (
            "The Goods and Services Tax (GST) came into effect in India on 1 July 2017. It was enabled by the "
            "Constitution (One Hundred and First Amendment) Act, 2016. The GST Council, constituted under Article "
            "279A, is chaired by the Union Finance Minister and includes state finance ministers."
        ),
        "why_matters": "Polity + economy overlap: amendment number, article number and Council chair are all asked.",
        "context": None,
        "key_facts": [
            "GST came into effect in India on 1 July 2017.",
            "GST was enabled by the Constitution (101st Amendment) Act, 2016.",
            "The GST Council is constituted under Article 279A.",
            "The GST Council is chaired by the Union Finance Minister.",
        ],
        "exam_tags": ALL_EXAMS,
        "mnemonics": ["GST = 1-7-17 start, 101st amendment, Council in 279A."],
        "questions": [
            {
                "prompt": "GST came into effect in India on:",
                "options": ["1 April 2017", "1 July 2017", "8 November 2016", "1 January 2018"],
                "correct": 1,
                "difficulty": "easy",
                "explanation": "GST was rolled out on 1 July 2017.",
            },
            {
                "prompt": "The GST Council is constituted under which Article of the Constitution?",
                "options": ["Article 246A", "Article 269A", "Article 279A", "Article 280"],
                "correct": 2,
                "difficulty": "medium",
                "explanation": (
                    "Article 279A creates the GST Council. 246A gives GST law-making power, 269A covers inter-state "
                    "GST and 280 is the Finance Commission."
                ),
            },
        ],
    },
    {
        "slug": "demo-aditya-l1-solar-observatory",
        "category": "science",
        "region": "india",
        "importance": 82,
        "source": {
            "title": "Aditya-L1",
            "publisher": "ISRO",
            "url": "https://www.isro.gov.in/Aditya_L1.html",
            "link_check": "200 OK",
        },
        "headline": "Aditya-L1: Surya-ke dekhte L1 point-e ISRO-r observatory ☀️",
        "banglish_summary": (
            "2 September 2023-e PSLV-C57-e launch holo Aditya-L1 - India-r prothom space-based solar observatory. "
            "6 January 2024-e eta Sun-Earth Lagrange point L1-er halo orbit-e pouchhe gelo, Earth theke prai "
            "1.5 million km dure."
        ),
        "neutral_summary": (
            "Aditya-L1, India's first space-based solar observatory, was launched by ISRO on 2 September 2023 aboard "
            "PSLV-C57. On 6 January 2024 it was inserted into a halo orbit around the Sun-Earth Lagrange point L1, "
            "about 1.5 million km from Earth."
        ),
        "why_matters": "Space questions ask launch vehicle, date and orbit - L1 versus L2 is a common trap.",
        "context": None,
        "key_facts": [
            "Aditya-L1 is India's first space-based solar observatory.",
            "It was launched on 2 September 2023 aboard PSLV-C57.",
            "It was placed in a halo orbit around Sun-Earth Lagrange point L1 on 6 January 2024.",
            "L1 is about 1.5 million km from Earth.",
        ],
        "exam_tags": ALL_EXAMS,
        "mnemonics": ["Aditya at L1: 'Sun-er dike 1 number seat'."],
        "questions": [
            {
                "prompt": "Aditya-L1 observes the Sun from a halo orbit around which point?",
                "options": ["Sun-Earth L1", "Sun-Earth L2", "Earth-Moon L1", "Geostationary orbit"],
                "correct": 0,
                "difficulty": "easy",
                "explanation": "Aditya-L1 orbits the Sun-Earth Lagrange point L1, about 1.5 million km from Earth.",
            }
        ],
    },
    {
        "slug": "demo-womens-reservation-act-2023",
        "category": "polity",
        "region": "india",
        "importance": 84,
        "source": {
            "title": "Women's Reservation Bill 2023 [The Constitution (128th Amendment) Bill, 2023]",
            "publisher": "PRS Legislative Research",
            "url": "https://prsindia.org/billtrack/the-constitution-one-hundred-twenty-eighth-amendment-bill-2023",
            "link_check": "200 OK",
        },
        "headline": "Nari Shakti Vandan Adhiniyam: Lok Sabha ar Assembly-te 1/3 seat mohilader jonno 🗳️",
        "banglish_summary": (
            "2023-e Parliament pass korlo Women's Reservation Bill - Constitution (128th Amendment) Bill, 2023, "
            "jeta Act hishebe 106th Amendment. Lok Sabha, state assemblies ar Delhi assembly-te one-third seat "
            "mohilader jonno reserve - kintu chalu hobe next census-er pore delimitation hole."
        ),
        "neutral_summary": (
            "The Constitution (128th Amendment) Bill, 2023, known as the Nari Shakti Vandan Adhiniyam, was passed by "
            "Parliament in September 2023 and enacted as the Constitution (106th Amendment) Act, 2023. It reserves "
            "one-third of seats for women in the Lok Sabha, state legislative assemblies and the Legislative "
            "Assembly of Delhi. The reservation takes effect after delimitation based on the first census "
            "conducted after the Act commences."
        ),
        "why_matters": "Bill number (128th) versus Act number (106th) is the favourite trap; so is the census trigger.",
        "context": None,
        "key_facts": [
            "The Women's Reservation Bill was introduced as the Constitution (128th Amendment) Bill, 2023.",
            "It was enacted as the Constitution (106th Amendment) Act, 2023.",
            "It reserves one-third of seats for women in the Lok Sabha, state assemblies and the Delhi assembly.",
            "Reservation takes effect after delimitation based on the census conducted after the Act commences.",
        ],
        "exam_tags": ALL_EXAMS,
        "mnemonics": ["Bill 128 -> Act 106: 'bill boro, act chhoto'."],
        "questions": [
            {
                "prompt": "The Nari Shakti Vandan Adhiniyam reserves what share of Lok Sabha seats for women?",
                "options": ["One-fourth", "One-third", "One-half", "Two-fifths"],
                "correct": 1,
                "difficulty": "easy",
                "explanation": "It reserves one-third of seats in the Lok Sabha, state assemblies and the Delhi assembly.",
            },
            {
                "prompt": "The Women's Reservation Act of 2023 is which Constitutional Amendment Act?",
                "options": ["103rd", "104th", "105th", "106th"],
                "correct": 3,
                "difficulty": "hard",
                "explanation": (
                    "It is the 106th Amendment Act (introduced as the 128th Amendment Bill). The 103rd introduced "
                    "EWS reservation, the 104th extended SC/ST legislative reservation and the 105th restored states' "
                    "power to identify backward classes."
                ),
            },
        ],
    },
    {
        "slug": "demo-project-tiger-1973",
        "category": "environment",
        "region": "india",
        "importance": 68,
        "source": {
            "title": "National Tiger Conservation Authority",
            "publisher": "NTCA, Government of India",
            "url": "https://ntca.gov.in/",
            "link_check": "200 OK",
        },
        "headline": "Project Tiger: 1973 theke bagh bachano mission 🐯",
        "banglish_summary": (
            "India 1973-e launch korechilo Project Tiger - bagh-der habitat bachanor jonno. Ekhon eta dekhashona "
            "kore National Tiger Conservation Authority (NTCA). Ar haan, Jim Corbett National Park 1936-e Hailey "
            "National Park nam-e shuru hoyechilo."
        ),
        "neutral_summary": (
            "Project Tiger was launched by the Government of India in 1973 to conserve tigers and their habitats. It "
            "is now administered by the National Tiger Conservation Authority (NTCA), a statutory body under the "
            "Wildlife (Protection) Act, 1972, as amended in 2006. Jim Corbett National Park was established in 1936 "
            "as Hailey National Park."
        ),
        "why_matters": "Environment GK pairs schemes with years: Project Tiger 1973, Project Elephant 1992.",
        "context": None,
        "key_facts": [
            "Project Tiger was launched in 1973.",
            "Project Tiger is administered by the National Tiger Conservation Authority (NTCA).",
            "NTCA is a statutory body under the Wildlife (Protection) Act, 1972, as amended in 2006.",
            "Jim Corbett National Park was established in 1936 as Hailey National Park.",
        ],
        "exam_tags": ["SSC", "UPSC", "STATE_PSC", "RAILWAYS"],
        "mnemonics": ["Tiger '73, Elephant '92 - bagh aage, hati pore."],
        "questions": [
            {
                "prompt": "Project Tiger was launched in which year?",
                "options": ["1972", "1973", "1980", "1992"],
                "correct": 1,
                "difficulty": "easy",
                "explanation": (
                    "Project Tiger began in 1973. 1972 is the Wildlife (Protection) Act, 1980 the Forest "
                    "(Conservation) Act and 1992 Project Elephant."
                ),
            }
        ],
    },
    {
        "slug": "demo-tagore-nobel-1913",
        "category": "awards",
        "region": "india",
        "importance": 66,
        "source": {
            "title": "The Nobel Prize in Literature 1913 - Summary",
            "publisher": "NobelPrize.org",
            "url": "https://www.nobelprize.org/prizes/literature/1913/summary/",
            "link_check": "200 OK",
        },
        "headline": "Rabindranath Tagore: 1913 Nobel - prothom non-European Literature laureate 📜",
        "banglish_summary": (
            "Bangali-r gorbo! 1913-e Rabindranath Tagore Literature-e Nobel pelen, ar tini chhilen prothom "
            "non-European jini Literature-e Nobel pelen. English 'Gitanjali (Song Offerings)' 1912-e beriyechilo - "
            "1913 ar Gitanjali ek shathe mone rakh."
        ),
        "neutral_summary": (
            "Rabindranath Tagore was awarded the Nobel Prize in Literature in 1913. He was the first non-European to "
            "receive the Nobel Prize in Literature. His collection Gitanjali (Song Offerings), published in English "
            "in 1912, brought his poetry to Western readers."
        ),
        "why_matters": "Evergreen static GK - Bengal state PSC and SSC both ask it.",
        "context": None,
        "key_facts": [
            "Rabindranath Tagore received the Nobel Prize in Literature in 1913.",
            "He was the first non-European to win the Nobel Prize in Literature.",
            "Gitanjali (Song Offerings) was published in English in 1912.",
        ],
        "exam_tags": ["SSC", "STATE_PSC", "RAILWAYS", "BANKING"],
        "mnemonics": ["Gitanjali 1912 -> Nobel 1913: 'gaan-er porer bochhor puroshkar'."],
        "questions": [
            {
                "prompt": "In which year was Rabindranath Tagore awarded the Nobel Prize in Literature?",
                "options": ["1905", "1913", "1921", "1930"],
                "correct": 1,
                "difficulty": "easy",
                "explanation": "Tagore received the Nobel Prize in Literature in 1913.",
            }
        ],
    },
]

STATIC_GK: list[tuple[str, str, list[str], int, str]] = [
    (
        "polity",
        "Which Article of the Indian Constitution provides the Right to Constitutional Remedies?",
        ["Article 14", "Article 21", "Article 32", "Article 356"],
        2,
        "Article 32 lets a person move the Supreme Court to enforce Fundamental Rights.",
    ),
    (
        "economy",
        "Who chairs the GST Council?",
        ["Prime Minister", "Union Finance Minister", "RBI Governor", "Chief Justice of India"],
        1,
        "The Union Finance Minister chairs the GST Council (Article 279A).",
    ),
    (
        "science",
        "Which planet is known as the Red Planet?",
        ["Venus", "Mars", "Jupiter", "Mercury"],
        1,
        "Mars looks red because of iron oxide on its surface.",
    ),
    (
        "science",
        "Where is the headquarters of ISRO?",
        ["Hyderabad", "Bengaluru", "Thiruvananthapuram", "Chennai"],
        1,
        "ISRO is headquartered in Bengaluru.",
    ),
    (
        "science",
        "The Satish Dhawan Space Centre is located at:",
        ["Sriharikota", "Thumba", "Balasore", "Chandipur"],
        0,
        "India's primary launch site is at Sriharikota, Andhra Pradesh.",
    ),
    (
        "other",
        "Which river is known as the 'Sorrow of Bengal'?",
        ["Damodar", "Hooghly", "Teesta", "Mahanadi"],
        0,
        "The Damodar earned the name because of its historic floods.",
    ),
    (
        "other",
        "The Tropic of Cancer does NOT pass through which state?",
        ["Gujarat", "Rajasthan", "Odisha", "Mizoram"],
        2,
        "It crosses eight states including Gujarat, Rajasthan and Mizoram - but not Odisha.",
    ),
    (
        "other",
        "Who was the first Governor-General of independent India?",
        ["C. Rajagopalachari", "Lord Mountbatten", "Lord Linlithgow", "Lord Wavell"],
        1,
        "Lord Mountbatten; C. Rajagopalachari was the first (and last) Indian Governor-General.",
    ),
    (
        "other",
        "'Vande Mataram' was written by:",
        ["Rabindranath Tagore", "Bankim Chandra Chattopadhyay", "Sarojini Naidu", "Subramania Bharati"],
        1,
        "Bankim Chandra Chattopadhyay wrote it; it appears in his novel Anandamath.",
    ),
    (
        "polity",
        "The words 'Socialist' and 'Secular' were added to the Preamble by which amendment?",
        ["42nd", "44th", "52nd", "73rd"],
        0,
        "The 42nd Amendment (1976) added them.",
    ),
    (
        "polity",
        "Which amendment gave constitutional status to Panchayati Raj institutions?",
        ["42nd", "61st", "73rd", "86th"],
        2,
        "The 73rd Amendment (1992) added Part IX on Panchayats.",
    ),
    (
        "other",
        "Which is the largest state of India by area?",
        ["Madhya Pradesh", "Maharashtra", "Rajasthan", "Uttar Pradesh"],
        2,
        "Rajasthan is the largest by area.",
    ),
    (
        "international",
        "What is the currency of Japan?",
        ["Yuan", "Won", "Yen", "Ringgit"],
        2,
        "Japan uses the Yen; Yuan is China's, Won is Korea's, Ringgit is Malaysia's.",
    ),
    (
        "international",
        "Where is the headquarters of the United Nations?",
        ["Geneva", "New York", "Paris", "Vienna"],
        1,
        "UN headquarters is in New York.",
    ),
    (
        "other",
        "The Battle of Plassey was fought in:",
        ["1757", "1764", "1857", "1761"],
        0,
        "Plassey was 1757; Buxar was 1764 and the Third Battle of Panipat 1761.",
    ),
    (
        "science",
        "Which gas is the most abundant in Earth's atmosphere?",
        ["Oxygen", "Carbon dioxide", "Nitrogen", "Argon"],
        2,
        "Nitrogen makes up about 78% of the atmosphere.",
    ),
    (
        "science",
        "The chemical symbol 'Fe' stands for:",
        ["Fluorine", "Iron", "Lead", "Francium"],
        1,
        "Fe comes from the Latin 'ferrum' (iron).",
    ),
    (
        "other",
        "Which Indian state has the longest coastline?",
        ["Andhra Pradesh", "Tamil Nadu", "Gujarat", "Maharashtra"],
        2,
        "Gujarat has the longest coastline.",
    ),
    (
        "other",
        "Who is known as the 'Iron Man of India'?",
        ["Jawaharlal Nehru", "Sardar Vallabhbhai Patel", "Lal Bahadur Shastri", "Subhas Chandra Bose"],
        1,
        "Sardar Vallabhbhai Patel, for integrating the princely states.",
    ),
    (
        "polity",
        "Article 21 of the Constitution guarantees:",
        [
            "Right to Equality",
            "Protection of life and personal liberty",
            "Freedom of religion",
            "Right against exploitation",
        ],
        1,
        "Article 21 protects life and personal liberty.",
    ),
    (
        "economy",
        "NITI Aayog replaced which body in 2015?",
        ["Finance Commission", "Planning Commission", "National Development Council", "Election Commission"],
        1,
        "NITI Aayog replaced the Planning Commission on 1 January 2015.",
    ),
    (
        "economy",
        "In which year was the Reserve Bank of India established?",
        ["1935", "1947", "1949", "1969"],
        0,
        "RBI was established on 1 April 1935 (nationalised in 1949).",
    ),
    (
        "environment",
        "The Chipko movement is associated with:",
        ["Forest conservation", "River cleaning", "Ban on wildlife hunting", "Anti-dam protests in Kerala"],
        0,
        "Villagers hugged trees to stop felling - a forest conservation movement.",
    ),
    (
        "environment",
        "What is the national aquatic animal of India?",
        ["Gangetic river dolphin", "Olive ridley turtle", "Dugong", "Saltwater crocodile"],
        0,
        "The Gangetic river dolphin was declared the national aquatic animal in 2009.",
    ),
    (
        "environment",
        "Kaziranga National Park is famous for the:",
        ["Asiatic lion", "One-horned rhinoceros", "Snow leopard", "Nilgiri tahr"],
        1,
        "Kaziranga (Assam) protects the greater one-horned rhinoceros.",
    ),
    (
        "environment",
        "The Sundarbans lie in the delta of the:",
        ["Ganga-Brahmaputra", "Godavari", "Krishna", "Mahanadi"],
        0,
        "The Sundarbans mangroves are in the Ganga-Brahmaputra delta.",
    ),
    (
        "polity",
        "Who was the first President of India?",
        ["Dr. Rajendra Prasad", "Dr. S. Radhakrishnan", "Zakir Husain", "V.V. Giri"],
        0,
        "Dr. Rajendra Prasad served from 1950 to 1962.",
    ),
    (
        "polity",
        "The Constitution of India came into force on:",
        ["15 August 1947", "26 November 1949", "26 January 1950", "30 January 1948"],
        2,
        "It was adopted on 26 November 1949 and came into force on 26 January 1950.",
    ),
    (
        "polity",
        "Which Schedule of the Constitution lists the recognised languages?",
        ["Seventh", "Eighth", "Ninth", "Tenth"],
        1,
        "The Eighth Schedule lists 22 languages.",
    ),
    (
        "science",
        "Which is the largest planet in our Solar System?",
        ["Saturn", "Jupiter", "Neptune", "Earth"],
        1,
        "Jupiter is the largest planet.",
    ),
    (
        "other",
        "The Howrah Bridge spans which river?",
        ["Hooghly", "Damodar", "Teesta", "Rupnarayan"],
        0,
        "Howrah Bridge (Rabindra Setu) spans the Hooghly.",
    ),
]


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def seed_demo(db: Session) -> dict[str, int]:
    settings = get_settings()
    today = app_today()
    now = utcnow()
    source = db.scalar(select(Source).where(Source.slug == "demo-reference"))
    if source is None:
        raise RuntimeError("Run seed_sources first")

    created = {"events": 0, "questions": 0}
    demo_event_ids = []
    for rank, spec in enumerate(DEMO_ARTICLES):
        event = db.scalar(select(Event).where(Event.slug == spec["slug"]))
        if event is None:
            item = SourceItem(
                source_id=source.id,
                canonical_url=f"demo://{spec['slug']}",
                original_url=spec["source"]["url"],
                original_title=spec["source"]["title"],
                short_excerpt=None,
                publisher=spec["source"]["publisher"],
                published_at=None,
                language="en",
                country="IN" if spec["region"] == "india" else None,
                item_metadata={"link_check": spec["source"]["link_check"], "demo": True},
                content_hash=_hash("demo", spec["slug"]),
                fetch_status="clustered",
                rights_notes="Reference link for a hand-written DEMO explainer.",
                is_demo=True,
            )
            db.add(item)
            db.flush()
            event = Event(
                topic=spec["category"],
                title=spec["headline"],
                slug=spec["slug"],
                status="published",
                date=today,
                region=spec["region"],
                relevance_score=float(spec["importance"]),
                relevance_reasons=[
                    "DEMO: hand-curated evergreen explainer (heuristic score, not exam probability)"
                ],
                cluster_hash=_hash("demo-cluster", spec["slug"]),
                is_demo=True,
                sensitive=False,
            )
            db.add(event)
            db.flush()
            db.add(EventSource(event_id=event.id, source_item_id=item.id, source_role="primary"))
            article = Article(
                event_id=event.id,
                headline=spec["headline"],
                banglish_summary=spec["banglish_summary"],
                neutral_summary=spec["neutral_summary"],
                why_matters=spec["why_matters"],
                context=spec.get("context"),
                key_facts=[{"claim": f, "source_item_ids": [str(item.id)]} for f in spec["key_facts"]],
                exam_tags=spec["exam_tags"],
                mnemonics=spec["mnemonics"],
                confidence_flags={"uncertainties": [], "demo": True, "tone": spec.get("tone", "playful")},
                category=spec["category"],
                importance_score=spec["importance"],
                sensitive_story=False,
                ai_provider=None,
                ai_model=None,
                prompt_version=PROMPT_VERSION,
                verified_at=now,
                verification_method="demo_manual",
                published_at=now,
                content_hash=_hash("demo-article", spec["slug"], PROMPT_VERSION),
                is_demo=True,
            )
            db.add(article)
            db.flush()
            for q in spec["questions"]:
                db.add(
                    Question(
                        event_id=event.id,
                        article_id=article.id,
                        exam_topic=spec["category"],
                        kind="current_affairs",
                        difficulty=q["difficulty"],
                        prompt=q["prompt"],
                        options=q["options"],
                        correct_index=q["correct"],
                        explanation=q["explanation"],
                        evidence_urls=[spec["source"]["url"]],
                        evidence_source_item_ids=[str(item.id)],
                        validation_status="validated",
                        generation_version=PROMPT_VERSION,
                        content_hash=_hash("demo-q", q["prompt"]),
                        active_from=today,
                        is_demo=True,
                    )
                )
                created["questions"] += 1
            created["events"] += 1
        else:
            event.date = today
        demo_event_ids.append((rank, event.id))

    # Keep demo current-affairs questions inside the rolling quiz window.
    for q in db.scalars(
        select(Question).where(Question.is_demo.is_(True), Question.kind == "current_affairs")
    ).all():
        q.active_from = today

    for topic, prompt, options, correct, explanation in STATIC_GK:
        digest = _hash("static-gk", prompt)
        if db.scalar(select(Question.id).where(Question.content_hash == digest)) is None:
            db.add(
                Question(
                    exam_topic=topic,
                    kind="static_gk",
                    difficulty="easy",
                    prompt=prompt,
                    options=options,
                    correct_index=correct,
                    explanation=explanation,
                    evidence_urls=[],
                    validation_status="validated",
                    generation_version=PROMPT_VERSION,
                    content_hash=digest,
                    is_demo=True,
                )
            )
            created["questions"] += 1

    edition = db.scalar(
        select(DailyEdition).where(
            DailyEdition.edition_date == today, DailyEdition.timezone == settings.app_timezone
        )
    )
    if edition is None:
        edition = DailyEdition(
            edition_date=today,
            timezone=settings.app_timezone,
            status="published",
            title="DEMO edition - evergreen explainers (not today's news)",
            published_at=now,
            is_demo=True,
        )
        db.add(edition)
        db.flush()
    if edition.is_demo:
        db.execute(delete(EditionEvent).where(EditionEvent.edition_id == edition.id))
        ranked = sorted(demo_event_ids, key=lambda r: -DEMO_ARTICLES[r[0]]["importance"])
        for position, (_, event_id) in enumerate(ranked):
            db.add(EditionEvent(edition_id=edition.id, event_id=event_id, ranking=position + 1))

    db.flush()
    return {**created, "demo_articles": len(DEMO_ARTICLES), "static_gk": len(STATIC_GK)}
